"""Integration Tests for Neo4j Graph Loader Foundation against LIVE Neo4j.

Validates:
1. Live Neo4j connection and schema constraint initialization.
2. SourceRecord and Evidence node persistence.
3. Strict provenance chain: Native relationship -> evidence_ids -> Evidence -> [:FROM_SOURCE] -> SourceRecord.
4. Native relationship aggregate properties: interaction_count, timestamps, evidence_ids, attributes_json.
5. Absolute idempotency: repeated loading of identical PipelineResult yields identical graph state.
6. POSSIBLE_MATCH candidate pairs remain unmerged and represented as [:EVALUATED_PAIR].
7. Missing timestamps remain null in Neo4j; partial timestamps record actual values only.
8. Rejection of unsupported relationship types.
9. No separate (:Relationship) nodes or [:HAS_EVIDENCE] edges exist.
"""

from datetime import datetime, timezone
import pytest
from neo4j import Driver

from app.schemas.record import SourceRecord, NormalizedRecord
from app.schemas.entity import PersonEntity, PhoneEntity, EntityType
from app.schemas.evidence import EvidenceProvenance
from app.schemas.relationship import (
    Relationship,
    RelationshipType,
    RelationshipOrigin,
    ResolutionCandidate,
    ResolutionStatus,
)
from app.pipeline import PipelineResult
from app.graph.config import get_driver, verify_connection, Neo4jConfig
from app.graph.loader import Neo4jGraphLoader, load_pipeline_result


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
    """Cleans up the database before and after each integration test."""
    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield
    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")


def _build_test_pipeline_result(
    ts1: datetime | None = None,
    ts2: datetime | None = None,
    include_possible_match: bool = True,
) -> PipelineResult:
    """Builds a deterministic, valid PipelineResult for graph loading tests."""
    t_fixed = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)

    src = SourceRecord(
        source_id="urn:source:cdr:001",
        source_type="CALL_DETAIL_RECORD",
        document_name="cdr_aug2026.csv",
        raw_content="CALL,2026-08-10T01:15:00Z,+91-9900000101,+91-9900000102,480s,TOWER_DELHI_NORTH",
        metadata={"feed": "telecom_gateway"},
        ingested_at=t_fixed,
    )

    ev1 = EvidenceProvenance(
        evidence_id="urn:ev:001",
        source_record_id=src.source_id,
        source_type=src.source_type,
        document_name=src.document_name,
        raw_snippet="+91-9900000101",
        offset_start=26,
        offset_end=40,
        extractor_name="RegexPhoneExtractor",
        extracted_at=t_fixed,
    )
    ev2 = EvidenceProvenance(
        evidence_id="urn:ev:002",
        source_record_id=src.source_id,
        source_type=src.source_type,
        document_name=src.document_name,
        raw_snippet="+91-9900000102",
        offset_start=41,
        offset_end=55,
        extractor_name="RegexPhoneExtractor",
        extracted_at=t_fixed,
    )

    p1 = PhoneEntity(
        entity_id="urn:entity:phone:001",
        entity_type=EntityType.PHONE,
        canonical_name="+91-9900000101",
        phone_number="+91-9900000101",
        source_record_ids=[src.source_id],
        created_at=t_fixed,
        updated_at=t_fixed,
    )
    p2 = PhoneEntity(
        entity_id="urn:entity:phone:002",
        entity_type=EntityType.PHONE,
        canonical_name="+91-9900000102",
        phone_number="+91-9900000102",
        source_record_ids=[src.source_id],
        created_at=t_fixed,
        updated_at=t_fixed,
    )

    # Two observations sharing relationship_id
    rel1 = Relationship(
        relationship_id="urn:rel:comm:001",
        source_entity_id=p1.entity_id,
        target_entity_id=p2.entity_id,
        relationship_type=RelationshipType.COMMUNICATED_WITH,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=0.9,
        timestamp_context=ts1,
        attributes={"call_duration_sec": 120},
        evidence_ids=[ev1.evidence_id],
    )
    rel2 = Relationship(
        relationship_id="urn:rel:comm:001",
        source_entity_id=p1.entity_id,
        target_entity_id=p2.entity_id,
        relationship_type=RelationshipType.COMMUNICATED_WITH,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=1.0,
        timestamp_context=ts2,
        attributes={"call_duration_sec": 360},
        evidence_ids=[ev2.evidence_id],
    )

    entities = [p1, p2]
    candidates = []

    if include_possible_match:
        person_a = PersonEntity(
            entity_id="urn:entity:person:001",
            entity_type=EntityType.PERSON,
            canonical_name="Vikram Singh",
            full_name="Vikram Singh",
            source_record_ids=[src.source_id],
            created_at=t_fixed,
            updated_at=t_fixed,
        )
        person_b = PersonEntity(
            entity_id="urn:entity:person:002",
            entity_type=EntityType.PERSON,
            canonical_name="V. Singh",
            full_name="V. Singh",
            source_record_ids=[src.source_id],
            created_at=t_fixed,
            updated_at=t_fixed,
        )
        entities.extend([person_a, person_b])
        cand = ResolutionCandidate(
            candidate_id="urn:res:cand:001",
            entity_id_a=person_a.entity_id,
            entity_id_b=person_b.entity_id,
            similarity_score=0.85,
            heuristic_name="Name_Similarity_Heuristic",
            status=ResolutionStatus.POSSIBLE_MATCH,
            confidence=0.85,
            justification="High name similarity; requires analyst review.",
        )
        candidates.append(cand)

    return PipelineResult(
        source_records=[src],
        normalized_records=[],
        extracted_entities=entities,
        evidence_items=[ev1, ev2],
        resolution_candidates=candidates,
        resolution_decisions=[],
        relationships=[rel1, rel2],
    )


def test_live_neo4j_connectivity_and_schema_constraints(neo4j_driver: Driver):
    """Verify live Neo4j driver connection and schema constraint creation."""
    with Neo4jGraphLoader(driver=neo4j_driver) as loader:
        loader.init_schema()

    with neo4j_driver.session() as session:
        constraints = session.run("SHOW CONSTRAINTS").data()
        c_names = {c["name"] for c in constraints}
        assert "entity_id_unique" in c_names
        assert "source_record_id_unique" in c_names
        assert "evidence_id_unique" in c_names


def test_loader_persistence_and_provenance_traversal(neo4j_driver: Driver):
    """Verify complete persistence, aggregate properties, and provenance traversal."""
    dt1 = datetime(2026, 8, 10, 1, 15, 0, tzinfo=timezone.utc)
    dt2 = datetime(2026, 8, 10, 3, 30, 0, tzinfo=timezone.utc)
    pipeline_res = _build_test_pipeline_result(ts1=dt1, ts2=dt2)

    stats = load_pipeline_result(pipeline_res, driver=neo4j_driver)
    assert stats["source_records"] == 1
    assert stats["evidence_items"] == 2
    assert stats["entities"] == 4
    assert stats["relationships"] == 1
    assert stats["evaluated_pairs"] == 1

    with neo4j_driver.session() as session:
        # 1. SourceRecord verified
        src_row = session.run(
            "MATCH (s:SourceRecord {source_id: 'urn:source:cdr:001'}) RETURN s"
        ).single()
        assert src_row is not None
        assert src_row["s"]["document_name"] == "cdr_aug2026.csv"

        # 2. Evidence nodes linked to SourceRecord via [:FROM_SOURCE]
        ev_rows = session.run(
            """
            MATCH (ev:Evidence)-[:FROM_SOURCE]->(s:SourceRecord)
            RETURN ev.evidence_id AS ev_id, s.source_id AS s_id
            ORDER BY ev_id
            """
        ).data()
        assert len(ev_rows) == 2
        assert ev_rows[0]["ev_id"] == "urn:ev:001"
        assert ev_rows[0]["s_id"] == "urn:source:cdr:001"
        assert ev_rows[1]["ev_id"] == "urn:ev:002"

        # 3. Native aggregated relationship verified
        rel_row = session.run(
            """
            MATCH (a:Entity {entity_id: 'urn:entity:phone:001'})-[r:COMMUNICATED_WITH]->(b:Entity {entity_id: 'urn:entity:phone:002'})
            RETURN r
            """
        ).single()
        assert rel_row is not None
        rel = rel_row["r"]
        assert rel["relationship_id"] == "urn:rel:comm:001"
        assert rel["origin"] == "EXTRACTED"
        assert rel["confidence"] == 1.0  # max(0.9, 1.0)
        assert rel["interaction_count"] == 2
        assert rel["evidence_ids"] == ["urn:ev:001", "urn:ev:002"]
        assert rel["first_seen"] == dt1.isoformat()
        assert rel["last_seen"] == dt2.isoformat()

        # 4. Strict Provenance Traversal: Native edge -> evidence_ids -> Evidence -> FROM_SOURCE -> SourceRecord
        prov_rows = session.run(
            """
            MATCH (a:Entity)-[r:COMMUNICATED_WITH]->(b:Entity)
            UNWIND r.evidence_ids AS ev_id
            MATCH (ev:Evidence {evidence_id: ev_id})-[:FROM_SOURCE]->(s:SourceRecord)
            RETURN r.relationship_id AS rel_id, ev.raw_snippet AS snippet, s.document_name AS doc
            ORDER BY snippet
            """
        ).data()
        assert len(prov_rows) == 2
        assert prov_rows[0]["snippet"] == "+91-9900000101"
        assert prov_rows[0]["doc"] == "cdr_aug2026.csv"
        assert prov_rows[1]["snippet"] == "+91-9900000102"
        assert prov_rows[1]["doc"] == "cdr_aug2026.csv"

        # 5. Prohibited structures check
        rel_nodes = session.run("MATCH (r:Relationship) RETURN count(r) AS c").single()["c"]
        assert rel_nodes == 0, "No separate Relationship nodes must exist."

        has_ev = session.run("MATCH ()-[r:HAS_EVIDENCE]->() RETURN count(r) AS c").single()["c"]
        assert has_ev == 0, "No HAS_EVIDENCE relationships must exist."

        supp_ev = session.run("MATCH ()-[r:SUPPORTED_BY_EVIDENCE]->() RETURN count(r) AS c").single()["c"]
        assert supp_ev == 0, "No SUPPORTED_BY_EVIDENCE relationships must exist."


def test_idempotency_repeated_load_identical_graph_state(neo4j_driver: Driver):
    """Verify that loading the EXACT same PipelineResult twice yields identical graph state."""
    dt1 = datetime(2026, 8, 10, 1, 15, 0, tzinfo=timezone.utc)
    pipeline_res = _build_test_pipeline_result(ts1=dt1, ts2=None)

    # First load
    load_pipeline_result(pipeline_res, driver=neo4j_driver)

    with neo4j_driver.session() as session:
        node_count_1 = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        rel_count_1 = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        edge_1 = session.run("MATCH ()-[r:COMMUNICATED_WITH]->() RETURN r").single()["r"]

    # Second load with identical PipelineResult
    load_pipeline_result(pipeline_res, driver=neo4j_driver)

    with neo4j_driver.session() as session:
        node_count_2 = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        rel_count_2 = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        edge_2 = session.run("MATCH ()-[r:COMMUNICATED_WITH]->() RETURN r").single()["r"]

    assert node_count_1 == node_count_2, "Node count must not change on duplicate load."
    assert rel_count_1 == rel_count_2, "Relationship count must not change on duplicate load."
    assert edge_1["interaction_count"] == edge_2["interaction_count"] == 2
    assert edge_1["evidence_ids"] == edge_2["evidence_ids"]
    assert edge_1["attributes_json"] == edge_2["attributes_json"]


def test_possible_match_entities_unmerged_with_evaluated_pair(neo4j_driver: Driver):
    """Verify that POSSIBLE_MATCH candidate pairs remain unmerged and linked by [:EVALUATED_PAIR]."""
    pipeline_res = _build_test_pipeline_result(include_possible_match=True)
    load_pipeline_result(pipeline_res, driver=neo4j_driver)

    with neo4j_driver.session() as session:
        # Both distinct PersonEntity nodes must exist independently
        p_a = session.run("MATCH (p:Entity {entity_id: 'urn:entity:person:001'}) RETURN p").single()
        p_b = session.run("MATCH (p:Entity {entity_id: 'urn:entity:person:002'}) RETURN p").single()
        assert p_a is not None
        assert p_b is not None

        # Evaluated pair relationship exists
        pair = session.run(
            """
            MATCH (a:Entity {entity_id: 'urn:entity:person:001'})-[r:EVALUATED_PAIR]->(b:Entity {entity_id: 'urn:entity:person:002'})
            RETURN r
            """
        ).single()
        assert pair is not None
        r = pair["r"]
        assert r["candidate_id"] == "urn:res:cand:001"
        assert r["status"] == "POSSIBLE_MATCH"
        assert r["similarity_score"] == 0.85
        assert r["confidence"] == 0.85


def test_missing_and_partial_timestamps_in_neo4j(neo4j_driver: Driver):
    """Verify missing timestamps persist as null, and partial timestamps record actual min/max."""
    dt_act = datetime(2026, 8, 10, 1, 15, 0, tzinfo=timezone.utc)

    # 1. Both timestamps missing
    res_missing = _build_test_pipeline_result(ts1=None, ts2=None, include_possible_match=False)
    load_pipeline_result(res_missing, driver=neo4j_driver)

    with neo4j_driver.session() as session:
        edge = session.run("MATCH ()-[r:COMMUNICATED_WITH]->() RETURN r").single()["r"]
        assert edge["first_seen"] is None
        assert edge["last_seen"] is None
        assert edge["interaction_count"] == 2

    # 2. Partial timestamps (one actual, one None)
    res_partial = _build_test_pipeline_result(ts1=dt_act, ts2=None, include_possible_match=False)
    load_pipeline_result(res_partial, driver=neo4j_driver)

    with neo4j_driver.session() as session:
        edge = session.run("MATCH ()-[r:COMMUNICATED_WITH]->() RETURN r").single()["r"]
        assert edge["first_seen"] == dt_act.isoformat()
        assert edge["last_seen"] == dt_act.isoformat()
        assert edge["interaction_count"] == 2


def test_unsupported_relationship_type_rejected_by_loader(neo4j_driver: Driver):
    """Verify that an unsupported relationship type raises ValueError before persistence."""
    pipeline_res = _build_test_pipeline_result()
    # Inject unsupported relationship
    bad_rel = Relationship(
        relationship_id="urn:rel:bad:001",
        source_entity_id="urn:entity:phone:001",
        target_entity_id="urn:entity:phone:002",
        relationship_type=RelationshipType.LOCATED_AT,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=1.0,
    )
    pipeline_res.relationships.append(bad_rel)

    with pytest.raises(ValueError, match="Unsupported relationship type"):
        load_pipeline_result(pipeline_res, driver=neo4j_driver)
