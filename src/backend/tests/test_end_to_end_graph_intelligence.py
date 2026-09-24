"""Phase 4E End-to-End Acceptance and Integration Proof.

Proves the complete unified Graph Intelligence pipeline against live Neo4j:
Phase 2 Controlled Data
  → Phase 3 Neo4j Graph Persistence
  → Phase 4B Structural Analysis (Centrality & Degree)
  → Phase 4C Temporal Analysis (Burst Concentration)
  → Phase 4D Multi-Signal Pattern Detection
  → Strict Provenance Verification (Pattern → Relationship → Evidence → SourceRecord)

Verifies:
- Pattern requires multiple independent signals
- Deterministic, repeatable execution
- Real canonical entity and relationship IDs are preserved
- Evidence references resolve through live Neo4j graph back to SourceRecord
- Time windows reflect strictly observed timestamp boundaries without fabrication
- Zero guilt, criminality, mastermind, or universal risk score inferences
- Full backward and Phase 4A–4C compatibility
"""

from datetime import datetime, timezone
import pytest
from neo4j import Driver

from app.schemas.entity import EntityType, PersonEntity, PhoneEntity, VehicleEntity
from app.schemas.relationship import RelationshipType, RelationshipOrigin, Relationship
from app.schemas.evidence import EvidenceProvenance
from app.schemas.record import SourceRecord
from app.schemas.analytics import PatternType
from app.pipeline import PipelineResult
from app.graph.config import get_driver, verify_connection
from app.graph.loader import load_pipeline_result
from app.graph.query import Neo4jGraphQuery
from app.analytics.patterns import PatternDetector, PatternDetectionConfig


@pytest.fixture(scope="module")
def neo4j_driver():
    """Provides a live Neo4j driver or fails if unavailable."""
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


def _setup_pipeline_scenario() -> PipelineResult:
    """Creates a controlled investigative scenario demonstrating multi-signal convergence."""
    t0 = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 10, 2, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 10, 2, 12, 0, tzinfo=timezone.utc)

    # 1. Source Records
    src_cdr = SourceRecord(
        source_id="urn:source:cdr:hub_01",
        source_type="CALL_DETAIL_RECORD",
        document_name="telecom_cdr_aug2026.csv",
        raw_content="CALL,2026-08-10T02:00:00Z,+91-9900000101,+91-9900000102,480s",
        ingested_at=t0,
    )
    src_toll = SourceRecord(
        source_id="urn:source:toll:hub_01",
        source_type="VEHICLE_TOLL_LOG",
        document_name="toll_records_nh48.json",
        raw_content='{"timestamp":"2026-08-10T01:00:00Z","reg":"DL-01-AB-1234"}',
        ingested_at=t0,
    )

    # 2. Evidence
    ev_cdr = EvidenceProvenance(
        evidence_id="urn:ev:cdr:hub_01",
        source_record_id=src_cdr.source_id,
        source_type=src_cdr.source_type,
        document_name=src_cdr.document_name,
        raw_snippet="+91-9900000101",
        extractor_name="CdrExtractor",
        extracted_at=t0,
    )
    ev_toll = EvidenceProvenance(
        evidence_id="urn:ev:toll:hub_01",
        source_record_id=src_toll.source_id,
        source_type=src_toll.source_type,
        document_name=src_toll.document_name,
        raw_snippet="DL-01-AB-1234",
        extractor_name="TollExtractor",
        extracted_at=t0,
    )

    # 3. Canonical Entities:
    # Central coordinator: person_vikram
    # Connects to phone_primary, phone_associate, and vehicle
    person_coordinator = PersonEntity(
        entity_id="urn:entity:person:coord_01",
        entity_type=EntityType.PERSON,
        canonical_name="Vikram Singh",
        full_name="Vikram Singh",
        aliases=["Vicky"],
        created_at=t0,
        updated_at=t0,
    )
    phone_target = PhoneEntity(
        entity_id="urn:entity:phone:target_01",
        entity_type=EntityType.PHONE,
        canonical_name="+91-9900000101",
        phone_number="+91-9900000101",
        created_at=t0,
        updated_at=t0,
    )
    phone_associate = PhoneEntity(
        entity_id="urn:entity:phone:assoc_01",
        entity_type=EntityType.PHONE,
        canonical_name="+91-9900000102",
        phone_number="+91-9900000102",
        created_at=t0,
        updated_at=t0,
    )
    vehicle_target = VehicleEntity(
        entity_id="urn:entity:vehicle:target_01",
        entity_type=EntityType.VEHICLE,
        canonical_name="DL-01-AB-1234",
        registration_number="DL-01-AB-1234",
        created_at=t0,
        updated_at=t0,
    )

    # 4. Relationships:
    # r1: coordinator -> target phone (ASSOCIATED_WITH)
    r1 = Relationship(
        relationship_id="urn:rel:assoc:coord_target",
        source_entity_id=person_coordinator.entity_id,
        target_entity_id=phone_target.entity_id,
        relationship_type=RelationshipType.ASSOCIATED_WITH,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=0.9,
        timestamp_context=t0,
        evidence_ids=[ev_cdr.evidence_id],
    )
    # r2: coordinator -> vehicle (OWNED_BY)
    r2 = Relationship(
        relationship_id="urn:rel:owned:coord_vehicle",
        source_entity_id=person_coordinator.entity_id,
        target_entity_id=vehicle_target.entity_id,
        relationship_type=RelationshipType.OWNED_BY,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=0.85,
        timestamp_context=t0,
        evidence_ids=[ev_toll.evidence_id],
    )
    # r3 & r4: target phone <-> associate phone: 2 observations within 12 minutes (t1 and t2)
    # Pre-aggregates into single edge with 2 interactions in 12 minutes -> Burst signal!
    r3 = Relationship(
        relationship_id="urn:rel:comm:burst_phones",
        source_entity_id=phone_target.entity_id,
        target_entity_id=phone_associate.entity_id,
        relationship_type=RelationshipType.COMMUNICATED_WITH,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=0.95,
        timestamp_context=t1,
        evidence_ids=[ev_cdr.evidence_id],
    )
    r4 = Relationship(
        relationship_id="urn:rel:comm:burst_phones",
        source_entity_id=phone_target.entity_id,
        target_entity_id=phone_associate.entity_id,
        relationship_type=RelationshipType.COMMUNICATED_WITH,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=0.95,
        timestamp_context=t2,
        evidence_ids=[ev_cdr.evidence_id],
    )

    return PipelineResult(
        source_records=[src_cdr, src_toll],
        normalized_records=[],
        extracted_entities=[person_coordinator, phone_target, phone_associate, vehicle_target],
        evidence_items=[ev_cdr, ev_toll],
        relationships=[r1, r2, r3, r4],
        resolution_candidates=[],
        resolution_decisions=[],
    )


def test_end_to_end_graph_intelligence_pipeline(neo4j_driver: Driver):
    """Proves Phase 2 -> Phase 3 -> Phase 4B -> Phase 4C -> Phase 4D -> Provenance Traceability."""
    pipeline_res = _setup_pipeline_scenario()

    # Step 1: Idempotent Persistence into live Neo4j (Phase 3A)
    load_pipeline_result(pipeline_res, driver=neo4j_driver)

    # Step 2: Query Layer verification (Phase 3B)
    query = Neo4jGraphQuery(driver=neo4j_driver)
    entities = query.search_entities(limit=10)
    assert len(entities) == 4

    # Step 3: Run Pattern Detection over live Neo4j (Phase 4B + 4C + 4D)
    detector_config = PatternDetectionConfig(
        bridge_threshold=0.0,
        high_degree_threshold=2,
        min_burst_interactions=2,
        max_burst_span_seconds=1800.0,  # 30 mins
    )

    with PatternDetector(query=query, detection_config=detector_config) as detector:
        patterns = detector.detect_patterns(limit=100)

        # Step 4: Verify Multi-Signal Pattern Characteristics
        assert len(patterns) >= 1
        hub_pattern = next((p for p in patterns if p.pattern_type == PatternType.INTERMEDIARY_HUB_BURST), None)
        assert hub_pattern is not None

        # Verify pattern requires multiple signals
        assert len(hub_pattern.contributing_signal_ids) >= 2
        assert len(hub_pattern.contributing_signal_types) >= 2
        assert "BURST_COMMUNICATION_WINDOW" in hub_pattern.contributing_signal_types

        # Verify real canonical entity & relationship IDs
        assert "urn:entity:phone:target_01" in hub_pattern.entity_ids
        assert "urn:rel:comm:burst_phones" in hub_pattern.relationship_ids

        # Verify time window integrity (never fabricated, derived from real timestamps)
        assert hub_pattern.time_window is not None
        assert hub_pattern.time_window.start_time == datetime(2026, 8, 10, 2, 0, 0, tzinfo=timezone.utc)
        assert hub_pattern.time_window.end_time == datetime(2026, 8, 10, 2, 12, 0, tzinfo=timezone.utc)

        # Verify neutral language (no criminality / guilt / mastermind / risk scores)
        assert "Pattern Flagged for Investigation" in hub_pattern.title
        explanation_lower = hub_pattern.explanation.lower()
        for forbidden in ["criminal", "guilt", "intent", "mastermind", "perpetrator", "risk score"]:
            assert forbidden not in explanation_lower

        # Step 5: Provenance Chain Verification
        # Every evidence ID in the pattern must resolve directly in live Neo4j back to SourceRecord
        assert len(hub_pattern.evidence_ids) > 0
        for ev_id in hub_pattern.evidence_ids:
            ev_record = query.get_evidence_by_id(ev_id)
            assert ev_record is not None
            assert ev_record["evidence"]["evidence_id"] == ev_id
            assert ev_record["source_record"] is not None
            assert ev_record["source_record"]["source_id"].startswith("urn:source:")

        # Step 6: Determinism Verification
        patterns_run_2 = detector.detect_patterns(limit=100)
        assert len(patterns) == len(patterns_run_2)
        for p1, p2 in zip(patterns, patterns_run_2):
            assert p1.pattern_id == p2.pattern_id
            assert p1.title == p2.title
            assert p1.contributing_signal_ids == p2.contributing_signal_ids
            assert p1.relationship_ids == p2.relationship_ids
            assert p1.evidence_ids == p2.evidence_ids
            assert p1.time_window == p2.time_window
