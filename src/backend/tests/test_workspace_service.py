"""Unit and Integration Tests for WorkspaceService (Phase 5).

Verifies:
- Finding status transitions (OPEN -> IN_REVIEW -> RESOLVED / DISMISSED)
- Rejection of invalid status transitions
- Investigator notes persistence
- Full provenance bundle reaching SourceRecord (Finding -> Pattern -> Entity -> Evidence -> SourceRecord)
- Workspace dashboard summary metrics
- Bounded entity neighborhood (depth in {1, 2})
- Strict rejection of traversal depth > 2 or depth < 1
"""

from datetime import datetime, timezone
import pytest
from neo4j import Driver

from app.schemas.finding import FindingStatus, InvestigativeFinding
from app.schemas.analytics import MultiSignalPattern, PatternType, TimeWindow
from app.schemas.record import SourceRecord
from app.schemas.entity import PersonEntity, EntityType
from app.schemas.evidence import EvidenceProvenance
from app.schemas.relationship import Relationship, RelationshipType, RelationshipOrigin
from app.pipeline import PipelineResult
from app.graph.config import get_driver, verify_connection
from app.graph.loader import load_pipeline_result
from app.graph.query import Neo4jGraphQuery
from app.services.finding_service import FindingSynthesizer
from app.services.workspace_service import WorkspaceService


@pytest.fixture(scope="module")
def neo4j_driver():
    """Provides a live Neo4j driver or marks tests BLOCKED if unavailable."""
    if not verify_connection():
        pytest.fail("BLOCKED — LIVE NEO4J TEST ENVIRONMENT UNAVAILABLE")
    driver = get_driver()
    yield driver
    driver.close()


@pytest.fixture(autouse=True)
def clean_graph(neo4j_driver: Driver):
    """Cleans up the database before and after each test."""
    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield
    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")


def _setup_provenance_graph(driver: Driver) -> PipelineResult:
    """Populates graph with a traceable chain from SourceRecord down to Entity/Relationship."""
    t0 = datetime(2026, 3, 10, 10, 0, 0, tzinfo=timezone.utc)

    source = SourceRecord(
        source_id="urn:source:cdr:001",
        source_type="CALL_DATA_RECORD",
        document_name="CDR_March_2026.csv",
        raw_content="Call from +919876543210 to +919876543211 on 2026-03-10T10:00:00Z duration 120s",
        ingested_at=t0,
    )

    ev1 = EvidenceProvenance(
        evidence_id="urn:ev:call:001",
        source_record_id=source.source_id,
        source_type=source.source_type,
        document_name=source.document_name,
        raw_snippet="Call from +919876543210 to +919876543211",
        offset_start=0,
        offset_end=42,
        extractor_name="CallLogExtractor",
        extracted_at=t0,
    )

    p1 = PersonEntity(
        entity_id="urn:ent:person:001",
        entity_type=EntityType.PERSON,
        canonical_name="Alpha Operative",
        full_name="Alpha Operative",
    )
    p2 = PersonEntity(
        entity_id="urn:ent:person:002",
        entity_type=EntityType.PERSON,
        canonical_name="Bravo Contact",
        full_name="Bravo Contact",
    )

    rel1 = Relationship(
        relationship_id="urn:rel:comm:001",
        source_entity_id=p1.entity_id,
        target_entity_id=p2.entity_id,
        relationship_type=RelationshipType.COMMUNICATED_WITH,
        confidence=1.0,
        origin=RelationshipOrigin.EXTRACTED,
        timestamp_context=t0,
        evidence_ids=[ev1.evidence_id],
    )

    pipeline_result = PipelineResult(
        source_records=[source],
        normalized_records=[],
        extracted_entities=[p1, p2],
        evidence_items=[ev1],
        resolution_candidates=[],
        resolution_decisions=[],
        relationships=[rel1],
    )

    load_pipeline_result(pipeline_result, driver=driver)
    return pipeline_result


def test_finding_status_transitions(neo4j_driver: Driver):
    """Verifies valid lifecycle status transitions: OPEN -> IN_REVIEW -> RESOLVED / DISMISSED."""
    query = Neo4jGraphQuery(driver=neo4j_driver)
    service = WorkspaceService(query=query)

    finding = InvestigativeFinding(
        finding_id="urn:finding:test:001",
        title="Test Status Transition Finding",
        summary="Summary of analytical signals",
        entity_ids=["urn:ent:person:001"],
        confidence=1.0,
    )
    service.register_finding(finding)

    # 1. Initial status is OPEN
    assert service.get_finding("urn:finding:test:001").status == FindingStatus.OPEN

    # 2. OPEN -> IN_REVIEW
    f_review = service.update_finding_status("urn:finding:test:001", FindingStatus.IN_REVIEW)
    assert f_review.status == FindingStatus.IN_REVIEW

    # 3. IN_REVIEW -> RESOLVED
    f_resolved = service.update_finding_status("urn:finding:test:001", FindingStatus.RESOLVED)
    assert f_resolved.status == FindingStatus.RESOLVED

    # 4. RESOLVED -> IN_REVIEW -> DISMISSED
    service.update_finding_status("urn:finding:test:001", FindingStatus.IN_REVIEW)
    f_dismissed = service.update_finding_status("urn:finding:test:001", FindingStatus.DISMISSED)
    assert f_dismissed.status == FindingStatus.DISMISSED


def test_rejection_of_invalid_status_transitions(neo4j_driver: Driver):
    """Verifies that invalid transitions (e.g. OPEN -> RESOLVED directly) raise ValueError."""
    query = Neo4jGraphQuery(driver=neo4j_driver)
    service = WorkspaceService(query=query)

    finding = InvestigativeFinding(
        finding_id="urn:finding:test:002",
        title="Direct Transition Test",
        summary="Direct resolution test",
        confidence=1.0,
    )
    service.register_finding(finding)

    # Direct OPEN -> RESOLVED should be rejected
    with pytest.raises(ValueError, match="Invalid status transition from OPEN to RESOLVED"):
        service.update_finding_status("urn:finding:test:002", FindingStatus.RESOLVED)


def test_investigator_notes_persistence(neo4j_driver: Driver):
    """Verifies that investigator notes can be attached and persisted upon status update."""
    query = Neo4jGraphQuery(driver=neo4j_driver)
    service = WorkspaceService(query=query)

    finding = InvestigativeFinding(
        finding_id="urn:finding:test:003",
        title="Notes Test Finding",
        summary="Summary test",
        confidence=1.0,
    )
    service.register_finding(finding)

    updated = service.update_finding_status(
        finding_id="urn:finding:test:003",
        status=FindingStatus.IN_REVIEW,
        notes="Investigator confirmed high betweenness centrality on bridge node.",
    )

    assert updated.status == FindingStatus.IN_REVIEW
    assert updated.investigator_notes == "Investigator confirmed high betweenness centrality on bridge node."

    # Subsequent status change without specifying notes should retain existing notes
    updated_again = service.update_finding_status(
        finding_id="urn:finding:test:003",
        status=FindingStatus.RESOLVED,
    )
    assert updated_again.status == FindingStatus.RESOLVED
    assert updated_again.investigator_notes == "Investigator confirmed high betweenness centrality on bridge node."


def test_provenance_bundle_reaches_source_record(neo4j_driver: Driver):
    """Verifies full click-through provenance traversal:

    Finding -> Pattern/Signals -> Entities/Relationships -> Evidence -> SourceRecord
    """
    pipe_res = _setup_provenance_graph(neo4j_driver)
    query = Neo4jGraphQuery(driver=neo4j_driver)
    service = WorkspaceService(query=query)

    pattern = MultiSignalPattern(
        pattern_id="urn:pattern:hub:prov001",
        pattern_type=PatternType.INTERMEDIARY_HUB_BURST,
        title="Pattern Flagged for Investigation: Hub Activity",
        entity_ids=["urn:ent:person:001", "urn:ent:person:002"],
        contributing_signal_ids=["urn:sig:001", "urn:sig:002"],
        relationship_ids=["urn:rel:comm:001"],
        evidence_ids=["urn:ev:call:001"],
        detection_method="heuristic_multi_signal",
        explanation="Test explanation",
        limitations=["Test limitation"],
    )

    finding = FindingSynthesizer().synthesize_finding(pattern)
    service.register_finding(finding, pattern=pattern)

    bundle = service.get_finding_provenance_bundle(finding.finding_id)

    # 1. Finding is present
    assert bundle.finding.finding_id == finding.finding_id

    # 2. Pattern is present
    assert bundle.pattern is not None
    assert bundle.pattern.pattern_id == pattern.pattern_id

    # 3. Entities are populated
    assert len(bundle.entities) >= 2
    eids = {e["entity_id"] for e in bundle.entities}
    assert "urn:ent:person:001" in eids
    assert "urn:ent:person:002" in eids

    # 4. Relationships are populated
    assert len(bundle.relationships) >= 1
    rel_ids = {r["relationship_id"] for r in bundle.relationships}
    assert "urn:rel:comm:001" in rel_ids

    # 5. Evidence is populated
    assert len(bundle.evidence) >= 1
    ev_ids = {ev["evidence_id"] for ev in bundle.evidence}
    assert "urn:ev:call:001" in ev_ids

    # 6. SourceRecord is populated with raw content
    assert len(bundle.source_records) >= 1
    source_record = bundle.source_records[0]
    assert source_record["source_id"] == "urn:source:cdr:001"
    assert "Call from +919876543210" in source_record["raw_content"]


def test_workspace_summary_metrics(neo4j_driver: Driver):
    """Verifies calculation of workspace overview dashboard metrics."""
    query = Neo4jGraphQuery(driver=neo4j_driver)
    service = WorkspaceService(query=query)

    f1 = InvestigativeFinding(
        finding_id="urn:finding:sum:001",
        title="Finding 1",
        summary="Summary 1",
        entity_ids=["urn:ent:001", "urn:ent:002"],
        signal_ids=["urn:sig:001"],
        status=FindingStatus.OPEN,
        pattern_type="INTERMEDIARY_HUB_BURST",
        confidence=1.0,
    )
    f2 = InvestigativeFinding(
        finding_id="urn:finding:sum:002",
        title="Finding 2",
        summary="Summary 2",
        entity_ids=["urn:ent:002", "urn:ent:003"],
        signal_ids=["urn:sig:002", "urn:sig:003"],
        status=FindingStatus.IN_REVIEW,
        pattern_type="DENSE_COMMUNITY_BURST",
        confidence=1.0,
    )

    service.register_finding(f1)
    service.register_finding(f2)

    summary = service.get_workspace_summary()

    assert summary.total_findings == 2
    assert summary.findings_by_status[FindingStatus.OPEN.value] == 1
    assert summary.findings_by_status[FindingStatus.IN_REVIEW.value] == 1
    assert summary.findings_by_pattern_type["INTERMEDIARY_HUB_BURST"] == 1
    assert summary.findings_by_pattern_type["DENSE_COMMUNITY_BURST"] == 1
    assert summary.total_entities_monitored == 3  # ent:001, ent:002, ent:003
    assert summary.total_signals_detected == 3  # sig:001, sig:002, sig:003


def test_bounded_entity_neighborhood_and_depth_limits(neo4j_driver: Driver):
    """Verifies that entity neighborhood exploration is strictly bounded to depth 1 or 2.

    Depth > 2 and depth < 1 must be rejected.
    """
    _setup_provenance_graph(neo4j_driver)
    query = Neo4jGraphQuery(driver=neo4j_driver)
    service = WorkspaceService(query=query)

    # 1. Depth = 1 is allowed
    nb1 = service.get_entity_neighborhood("urn:ent:person:001", depth=1, limit=50)
    assert nb1.depth == 1
    assert nb1.center_entity_id == "urn:ent:person:001"
    assert nb1.total_nodes >= 1

    # 2. Depth = 2 is allowed
    nb2 = service.get_entity_neighborhood("urn:ent:person:001", depth=2, limit=50)
    assert nb2.depth == 2
    assert nb2.center_entity_id == "urn:ent:person:001"

    # 3. Depth > 2 is strictly rejected
    with pytest.raises(ValueError, match="Traversal depth must be 1 or 2, got 3"):
        service.get_entity_neighborhood("urn:ent:person:001", depth=3)

    # 4. Depth <= 0 is strictly rejected
    with pytest.raises(ValueError, match="Traversal depth must be 1 or 2, got 0"):
        service.get_entity_neighborhood("urn:ent:person:001", depth=0)
