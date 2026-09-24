"""Focused Integration Tests for Phase 3B Neo4j Graph Query Layer against LIVE Neo4j.

Tests all required query operations:
1. Entity lookup / search with filters and deterministic ordering.
2. Entity details with connectivity metrics.
3. Direct relationships with directional, type, confidence, and temporal filtering.
4. Bounded 1-hop and 2-hop network traversal.
5. Traversal bounds enforcement (prohibition of unbounded traversal).
6. Temporal filtering with strict zero-fabrication semantics.
7. Strict evidence and source record provenance retrieval.
8. POSSIBLE_MATCH candidate inspection via [:EVALUATED_PAIR].
9. Graceful handling of empty or nonexistent entities.
"""

from datetime import datetime, timezone
import pytest
from neo4j import Driver

from app.schemas.record import SourceRecord
from app.schemas.entity import PersonEntity, PhoneEntity, VehicleEntity, EntityType
from app.schemas.evidence import EvidenceProvenance
from app.schemas.relationship import (
    Relationship,
    RelationshipType,
    RelationshipOrigin,
    ResolutionCandidate,
    ResolutionStatus,
)
from app.pipeline import PipelineResult
from app.graph.config import get_driver, verify_connection
from app.graph.loader import load_pipeline_result
from app.graph.query import Neo4jGraphQuery


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


def _setup_multi_entity_graph(neo4j_driver: Driver) -> PipelineResult:
    """Creates and loads a multi-entity connected network for query layer validation."""
    t0 = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 10, 1, 15, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 10, 2, 30, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 8, 10, 4, 0, 0, tzinfo=timezone.utc)

    # 1. Sources
    src_cdr = SourceRecord(
        source_id="urn:source:cdr:001",
        source_type="CALL_DETAIL_RECORD",
        document_name="cdr_aug2026.csv",
        raw_content="CALL,2026-08-10T01:15:00Z,+91-9900000101,+91-9900000102,480s",
        metadata={"feed": "telecom"},
        ingested_at=t0,
    )
    src_toll = SourceRecord(
        source_id="urn:source:toll:001",
        source_type="VEHICLE_TOLL_LOG",
        document_name="toll_aug2026.json",
        raw_content='{"timestamp":"2026-08-10T02:30:00Z","reg":"DL-01-AB-1234"}',
        metadata={"feed": "toll_gateway"},
        ingested_at=t0,
    )

    # 2. Evidence
    ev1 = EvidenceProvenance(
        evidence_id="urn:ev:cdr:001",
        source_record_id=src_cdr.source_id,
        source_type=src_cdr.source_type,
        document_name=src_cdr.document_name,
        raw_snippet="+91-9900000101",
        offset_start=26,
        offset_end=40,
        extractor_name="PhoneExtractor",
        extracted_at=t0,
    )
    ev2 = EvidenceProvenance(
        evidence_id="urn:ev:toll:001",
        source_record_id=src_toll.source_id,
        source_type=src_toll.source_type,
        document_name=src_toll.document_name,
        raw_snippet="DL-01-AB-1234",
        offset_start=45,
        offset_end=58,
        extractor_name="VehicleExtractor",
        extracted_at=t0,
    )

    # 3. Entities
    phone_1 = PhoneEntity(
        entity_id="urn:entity:phone:001",
        entity_type=EntityType.PHONE,
        canonical_name="+91-9900000101",
        phone_number="+91-9900000101",
        aliases=["Target Primary Mobile"],
        source_record_ids=[src_cdr.source_id],
        created_at=t0,
        updated_at=t0,
    )
    phone_2 = PhoneEntity(
        entity_id="urn:entity:phone:002",
        entity_type=EntityType.PHONE,
        canonical_name="+91-9900000102",
        phone_number="+91-9900000102",
        aliases=["Associate Mobile"],
        source_record_ids=[src_cdr.source_id],
        created_at=t0,
        updated_at=t0,
    )
    person_vikram = PersonEntity(
        entity_id="urn:entity:person:001",
        entity_type=EntityType.PERSON,
        canonical_name="Vikram Singh",
        full_name="Vikram Singh",
        aliases=["Vicky"],
        attributes={"clearance": "RESTRICTED"},
        source_record_ids=[src_cdr.source_id, src_toll.source_id],
        created_at=t0,
        updated_at=t0,
    )
    person_suspect_b = PersonEntity(
        entity_id="urn:entity:person:002",
        entity_type=EntityType.PERSON,
        canonical_name="V. Singh",
        full_name="V. Singh",
        aliases=["V.S."],
        source_record_ids=[src_toll.source_id],
        created_at=t0,
        updated_at=t0,
    )
    vehicle_1 = VehicleEntity(
        entity_id="urn:entity:vehicle:001",
        entity_type=EntityType.VEHICLE,
        canonical_name="DL-01-AB-1234",
        registration_number="DL-01-AB-1234",
        make="Hyundai",
        model="Verna",
        source_record_ids=[src_toll.source_id],
        created_at=t0,
        updated_at=t0,
    )

    # 4. Relationships:
    # rel1: phone_1 -> phone_2 (COMMUNICATED_WITH, t1)
    rel1 = Relationship(
        relationship_id="urn:rel:comm:001",
        source_entity_id=phone_1.entity_id,
        target_entity_id=phone_2.entity_id,
        relationship_type=RelationshipType.COMMUNICATED_WITH,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=0.95,
        timestamp_context=t1,
        attributes={"duration_sec": 480},
        evidence_ids=[ev1.evidence_id],
    )
    # rel2: person_vikram -> phone_1 (ASSOCIATED_WITH, t0)
    rel2 = Relationship(
        relationship_id="urn:rel:assoc:001",
        source_entity_id=person_vikram.entity_id,
        target_entity_id=phone_1.entity_id,
        relationship_type=RelationshipType.ASSOCIATED_WITH,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=0.90,
        timestamp_context=t0,
        attributes={"relationship_role": "subscriber"},
        evidence_ids=[ev1.evidence_id],
    )
    # rel3: person_vikram -> vehicle_1 (OWNED_BY, t2)
    rel3 = Relationship(
        relationship_id="urn:rel:owned:001",
        source_entity_id=person_vikram.entity_id,
        target_entity_id=vehicle_1.entity_id,
        relationship_type=RelationshipType.OWNED_BY,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=0.85,
        timestamp_context=t2,
        attributes={"ownership_status": "registered"},
        evidence_ids=[ev2.evidence_id],
    )
    # rel4: Undated relationship: phone_2 -> vehicle_1 (ASSOCIATED_WITH, None timestamp)
    rel4 = Relationship(
        relationship_id="urn:rel:assoc:002",
        source_entity_id=phone_2.entity_id,
        target_entity_id=vehicle_1.entity_id,
        relationship_type=RelationshipType.ASSOCIATED_WITH,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=0.70,
        timestamp_context=None,
        attributes={"notes": "toll_co_location"},
        evidence_ids=[],
    )

    # 5. POSSIBLE_MATCH candidate pair between Vikram Singh and V. Singh
    cand = ResolutionCandidate(
        candidate_id="urn:res:cand:001",
        entity_id_a=person_vikram.entity_id,
        entity_id_b=person_suspect_b.entity_id,
        similarity_score=0.88,
        heuristic_name="NameSimilarity_SharedVehicle",
        status=ResolutionStatus.POSSIBLE_MATCH,
        confidence=0.85,
        justification="High name sequence similarity and shared vehicle presence.",
    )

    pipeline_res = PipelineResult(
        source_records=[src_cdr, src_toll],
        normalized_records=[],
        extracted_entities=[phone_1, phone_2, person_vikram, person_suspect_b, vehicle_1],
        evidence_items=[ev1, ev2],
        resolution_candidates=[cand],
        resolution_decisions=[],
        relationships=[rel1, rel2, rel3, rel4],
    )

    load_pipeline_result(pipeline_res, driver=neo4j_driver)
    return pipeline_res


def test_entity_lookup_and_search(neo4j_driver: Driver):
    """Verify entity lookup and search with substring, alias, type filtering, and ordering."""
    _setup_multi_entity_graph(neo4j_driver)
    query_layer = Neo4jGraphQuery(driver=neo4j_driver)

    # 1. Search by canonical name substring (case-insensitive)
    results = query_layer.search_entities(query="vikram")
    assert len(results) == 1
    assert results[0]["entity_id"] == "urn:entity:person:001"
    assert results[0]["canonical_name"] == "Vikram Singh"
    assert results[0]["attributes"]["clearance"] == "RESTRICTED"

    # 2. Search by alias
    results_alias = query_layer.search_entities(query="Vicky")
    assert len(results_alias) == 1
    assert results_alias[0]["entity_id"] == "urn:entity:person:001"

    # 3. Search by phone number
    results_phone = query_layer.search_entities(query="+91-9900000102")
    assert len(results_phone) == 1
    assert results_phone[0]["entity_id"] == "urn:entity:phone:002"

    # 4. Filter by entity type
    all_phones = query_layer.search_entities(entity_type="PHONE")
    assert len(all_phones) == 2
    assert {p["canonical_name"] for p in all_phones} == {"+91-9900000101", "+91-9900000102"}

    # 5. Invalid entity type raises ValueError
    with pytest.raises(ValueError, match="Invalid entity_type"):
        query_layer.search_entities(entity_type="INVALID_TYPE")

    # 6. Non-matching query returns empty list
    non_existent = query_layer.search_entities(query="NON_EXISTENT_NAME_XYZ")
    assert non_existent == []


def test_entity_details_and_connectivity_metrics(neo4j_driver: Driver):
    """Verify full property retrieval and connectivity counts for an entity."""
    _setup_multi_entity_graph(neo4j_driver)
    query_layer = Neo4jGraphQuery(driver=neo4j_driver)

    # Existing entity
    details = query_layer.get_entity_details("urn:entity:person:001")
    assert details is not None
    assert details["entity_id"] == "urn:entity:person:001"
    assert details["canonical_name"] == "Vikram Singh"
    assert details["full_name"] == "Vikram Singh"
    assert details["direct_relationship_count"] == 2  # rel2 and rel3
    assert details["possible_match_count"] == 1       # cand with V. Singh

    # Non-existent entity
    missing = query_layer.get_entity_details("urn:entity:person:999")
    assert missing is None

    # Empty entity_id raises ValueError
    with pytest.raises(ValueError, match="entity_id must be a non-empty string"):
        query_layer.get_entity_details("")


def test_direct_relationships_direction_and_type_filtering(neo4j_driver: Driver):
    """Verify direct relationship retrieval with directional and whitelisted type filtering."""
    _setup_multi_entity_graph(neo4j_driver)
    query_layer = Neo4jGraphQuery(driver=neo4j_driver)

    # 1. Both directions for Vikram Singh
    both_rels = query_layer.get_direct_relationships("urn:entity:person:001", direction="BOTH")
    assert len(both_rels) == 2
    rel_ids = {r["relationship_id"] for r in both_rels}
    assert rel_ids == {"urn:rel:assoc:001", "urn:rel:owned:001"}

    # 2. Outgoing direction
    out_rels = query_layer.get_direct_relationships("urn:entity:person:001", direction="OUTGOING")
    assert len(out_rels) == 2

    # 3. Incoming direction (person_001 has no incoming native relationships)
    in_rels = query_layer.get_direct_relationships("urn:entity:person:001", direction="INCOMING")
    assert len(in_rels) == 0

    # 4. Type filtering: only OWNED_BY
    owned_rels = query_layer.get_direct_relationships(
        "urn:entity:person:001", relationship_types=["OWNED_BY"]
    )
    assert len(owned_rels) == 1
    assert owned_rels[0]["relationship_id"] == "urn:rel:owned:001"
    assert owned_rels[0]["target_name"] == "DL-01-AB-1234"

    # 5. Unsupported relationship type raises ValueError
    with pytest.raises(ValueError, match="Unsupported relationship type"):
        query_layer.get_direct_relationships(
            "urn:entity:person:001", relationship_types=["LOCATED_AT"]
        )

    # 6. Invalid direction raises ValueError
    with pytest.raises(ValueError, match="direction must be 'BOTH', 'OUTGOING', or 'INCOMING'"):
        query_layer.get_direct_relationships("urn:entity:person:001", direction="ANYWHERE")


def test_bounded_1_hop_and_2_hop_network_traversal(neo4j_driver: Driver):
    """Verify strictly bounded 1-hop and 2-hop traversals and prohibition of unbounded traversal."""
    _setup_multi_entity_graph(neo4j_driver)
    query_layer = Neo4jGraphQuery(driver=neo4j_driver)

    # 1. 1-hop traversal from Vikram Singh
    # Connections: Vikram Singh -> phone:001 and vehicle:001
    net_1hop = query_layer.traverse_network("urn:entity:person:001", hops=1)
    assert net_1hop["start_entity_id"] == "urn:entity:person:001"
    assert net_1hop["hops"] == 1
    assert len(net_1hop["relationships"]) == 2
    ent_ids_1hop = {e["entity_id"] for e in net_1hop["entities"]}
    assert ent_ids_1hop == {
        "urn:entity:person:001",
        "urn:entity:phone:001",
        "urn:entity:vehicle:001",
    }

    # 2. 2-hop traversal from Vikram Singh
    # Vikram -> phone:001 -> phone:002
    # Vikram -> vehicle:001 <- phone:002
    net_2hop = query_layer.traverse_network(
        "urn:entity:person:001", hops=2, include_possible_matches=True
    )
    assert net_2hop["hops"] == 2
    assert len(net_2hop["relationships"]) == 4  # all 4 relationships discovered
    ent_ids_2hop = {e["entity_id"] for e in net_2hop["entities"]}
    assert "urn:entity:phone:002" in ent_ids_2hop

    # 3. Unbounded traversal attempt strictly prohibited
    with pytest.raises(ValueError, match="hops must be 1 or 2"):
        query_layer.traverse_network("urn:entity:person:001", hops=3)

    with pytest.raises(ValueError, match="hops must be 1 or 2"):
        query_layer.traverse_network("urn:entity:person:001", hops=0)

    # 4. Limit constraint enforcement
    net_limited = query_layer.traverse_network("urn:entity:person:001", hops=2, limit=2)
    assert len(net_limited["relationships"]) <= 2

    # 5. Non-existent start entity returns clean empty structure
    net_empty = query_layer.traverse_network("urn:entity:person:nonexistent", hops=1)
    assert net_empty["metrics"]["entity_count"] == 0
    assert net_empty["metrics"]["relationship_count"] == 0


def test_temporal_filtering_and_zero_fabrication(neo4j_driver: Driver):
    """Verify temporal range filtering and strict preservation of missing timestamps."""
    _setup_multi_entity_graph(neo4j_driver)
    query_layer = Neo4jGraphQuery(driver=neo4j_driver)

    t_early = datetime(2026, 8, 10, 1, 10, 0, tzinfo=timezone.utc)
    t_mid = datetime(2026, 8, 10, 1, 30, 0, tzinfo=timezone.utc)

    # 1. Temporal filter: window between 01:10 and 01:30 (captures rel1 at 01:15)
    dated_rels = query_layer.get_direct_relationships(
        entity_id="urn:entity:phone:001",
        start_time=t_early,
        end_time=t_mid,
        include_undated=False,
    )
    assert len(dated_rels) == 1
    assert dated_rels[0]["relationship_id"] == "urn:rel:comm:001"
    assert dated_rels[0]["first_seen"] == datetime(2026, 8, 10, 1, 15, 0, tzinfo=timezone.utc).isoformat()

    # 2. Window outside rel1 (e.g. after 03:00)
    t_late = datetime(2026, 8, 10, 3, 0, 0, tzinfo=timezone.utc)
    late_rels = query_layer.get_direct_relationships(
        entity_id="urn:entity:phone:001",
        start_time=t_late,
        include_undated=False,
    )
    assert len(late_rels) == 0

    # 3. Undated relationship handling: rel4 has timestamp_context=None
    # When include_undated=False: rel4 must be excluded
    undated_excluded = query_layer.get_direct_relationships(
        entity_id="urn:entity:phone:002",
        start_time=t_early,
        include_undated=False,
    )
    rel_ids_excluded = [r["relationship_id"] for r in undated_excluded]
    assert "urn:rel:assoc:002" not in rel_ids_excluded

    # When include_undated=True: rel4 is included, and first_seen remains None (no fabrication!)
    undated_included = query_layer.get_direct_relationships(
        entity_id="urn:entity:phone:002",
        start_time=t_early,
        include_undated=True,
    )
    rel_ids_included = [r["relationship_id"] for r in undated_included]
    assert "urn:rel:assoc:002" in rel_ids_included
    rel4_data = next(r for r in undated_included if r["relationship_id"] == "urn:rel:assoc:002")
    assert rel4_data["first_seen"] is None
    assert rel4_data["last_seen"] is None

    # 4. Global temporal slice query
    subgraph = query_layer.get_temporal_subgraph(
        start_time=t_early,
        end_time=t_mid,
        include_undated=False,
    )
    assert len(subgraph["relationships"]) == 1
    assert subgraph["relationships"][0]["relationship_id"] == "urn:rel:comm:001"
    assert len(subgraph["entities"]) == 2


def test_evidence_and_source_retrieval_provenance_chain(neo4j_driver: Driver):
    """Verify strict provenance traversal: relationship -> Evidence -> FROM_SOURCE -> SourceRecord."""
    _setup_multi_entity_graph(neo4j_driver)
    query_layer = Neo4jGraphQuery(driver=neo4j_driver)

    # 1. Retrieve evidence by relationship_id
    rel_ev = query_layer.get_relationship_evidence("urn:rel:comm:001")
    assert len(rel_ev) == 1
    item = rel_ev[0]
    assert item["relationship_id"] == "urn:rel:comm:001"
    assert item["source_entity_id"] == "urn:entity:phone:001"
    assert item["target_entity_id"] == "urn:entity:phone:002"

    evidence = item["evidence"]
    assert evidence["evidence_id"] == "urn:ev:cdr:001"
    assert evidence["raw_snippet"] == "+91-9900000101"
    assert evidence["offset_start"] == 26
    assert evidence["offset_end"] == 40
    assert evidence["document_name"] == "cdr_aug2026.csv"

    source = item["source_record"]
    assert source["source_id"] == "urn:source:cdr:001"
    assert source["source_type"] == "CALL_DETAIL_RECORD"
    assert "CALL,2026-08-10T01:15:00Z" in source["raw_content"]
    assert source["metadata"]["feed"] == "telecom"

    # 2. Retrieve evidence by entity_id
    ent_ev = query_layer.get_entity_evidence("urn:entity:person:001")
    assert ent_ev["entity_id"] == "urn:entity:person:001"
    assert len(ent_ev["source_records"]) == 2  # cdr and toll
    assert len(ent_ev["relationship_evidence"]) == 2  # rel2 and rel3

    # 3. Direct evidence lookup by ID
    single_ev = query_layer.get_evidence_by_id("urn:ev:toll:001")
    assert single_ev is not None
    assert single_ev["evidence"]["evidence_id"] == "urn:ev:toll:001"
    assert single_ev["source_record"]["source_id"] == "urn:source:toll:001"

    # 4. Non-existent evidence ID returns None
    assert query_layer.get_evidence_by_id("urn:ev:missing:999") is None


def test_possible_match_candidate_inspection(neo4j_driver: Driver):
    """Verify inspection of unresolved candidate pairs without silent merging."""
    _setup_multi_entity_graph(neo4j_driver)
    query_layer = Neo4jGraphQuery(driver=neo4j_driver)

    # 1. Global possible matches query
    matches = query_layer.get_possible_matches(min_similarity=0.8)
    assert len(matches) == 1
    match = matches[0]
    assert match["candidate_id"] == "urn:res:cand:001"
    assert match["status"] == "POSSIBLE_MATCH"
    assert match["similarity_score"] == 0.88
    assert match["entity_id_a"] == "urn:entity:person:001"
    assert match["name_a"] == "Vikram Singh"
    assert match["entity_id_b"] == "urn:entity:person:002"
    assert match["name_b"] == "V. Singh"

    # Higher threshold excludes match
    assert len(query_layer.get_possible_matches(min_similarity=0.95)) == 0

    # 2. Entity-specific possible matches
    v_matches = query_layer.get_entity_possible_matches("urn:entity:person:001")
    assert len(v_matches) == 1
    assert v_matches[0]["candidate_id"] == "urn:res:cand:001"

    # Entity without possible matches returns empty list
    p2_matches = query_layer.get_entity_possible_matches("urn:entity:phone:002")
    assert p2_matches == []
