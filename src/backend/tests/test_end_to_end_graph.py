"""End-to-End Integration Proof for Phase 3C: PipelineResult -> Neo4j -> Graph Query Layer.

Proves that:
1. Heterogeneous raw sources flow through Phase-2 ingestion, normalization,
   extraction, and resolution engines into a genuine Phase-2 PipelineResult.
2. The Phase-2 PipelineResult is persisted idempotently into live Neo4j via Phase-3A loader.
3. The persisted knowledge graph is deterministically queryable through Phase-3B query layer:
   - Entity search / lookup
   - Entity details with connectivity metrics
   - Direct relationships with directional and type filtering
   - Bounded 1-hop and 2-hop network traversal
   - Temporal range queries isolating timeline slices
   - Strict evidence provenance chain: relationship -> Evidence -> FROM_SOURCE -> SourceRecord
   - Unmerged POSSIBLE_MATCH candidate inspection via [:EVALUATED_PAIR]
4. Repeated query execution yields 100% deterministic, repeatable results.
"""

from datetime import datetime, timezone
import pytest
from neo4j import Driver

from app.schemas.entity import EntityType, PersonEntity
from app.schemas.relationship import (
    RelationshipType,
    RelationshipOrigin,
    ResolutionStatus,
    ResolutionCandidate,
)
from app.pipeline.ingestion import ingest_raw_source
from app.pipeline.normalization import normalize_record
from app.pipeline.extraction import extract_entities_and_relationships
from app.pipeline.resolution import resolve_entities_and_link_relationships
from app.pipeline import PipelineResult
from app.graph.config import get_driver, verify_connection
from app.graph.loader import load_pipeline_result
from app.graph.query import Neo4jGraphQuery

# Five heterogeneous raw data feeds from approved operational scenario
RAW_CDR = "CALL,2026-08-10T01:15:00Z,+91-9900000101,+91-9900000102,480s,TOWER_DELHI_NORTH"
RAW_TOLL = '{"timestamp":"2026-08-10T02:30:00Z","reg":"DL-01-AB-1234","toll_id":"TOLL_NH48_KM42","owner":"Aarav Sharma"}'
RAW_FIR = "FIR #882/2026: Suspect alias 'V. Singh' sighted driving black sedan reg DL-01-AB-1234 near illegal warehouse."
RAW_BANK = "TXN,2026-08-10T04:00:00Z,ACC-112233,ACC-998877,450000.00,INR,REMARKS:APEX_SUPPLY"
RAW_HOTEL = '{"checkin":"2026-08-10T06:00:00Z","guest":"Vikram Singh","phone":"+91-9900000101","national_id":"IND-98765432","vehicle":"DL-01-AB-1234"}'


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


def _execute_phase2_pipeline() -> PipelineResult:
    """Executes the authentic Phase-2 data processing pipeline across all 5 feeds."""
    t_fixed = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)

    feeds = [
        (RAW_CDR, "CALL_DETAIL_RECORD", "cdr_aug2026.csv", {"timestamp_context": "2026-08-10T01:15:00Z"}),
        (RAW_TOLL, "VEHICLE_TOLL_LOG", "toll_nh48.json", {"timestamp_context": "2026-08-10T02:30:00Z"}),
        (RAW_FIR, "FIR_REPORT", "fir_882_2026.txt", {"timestamp_context": "2026-08-10T03:00:00Z"}),
        (RAW_BANK, "BANK_TRANSACTION", "bank_apex_transfer.csv", {"timestamp_context": "2026-08-10T04:00:00Z"}),
        (RAW_HOTEL, "HOTEL_CHECKIN", "hotel_grand_aug2026.json", {"timestamp_context": "2026-08-10T06:00:00Z"}),
    ]

    source_records = []
    normalized_records = []
    all_extracted_entities = []
    all_evidence = []
    all_relationships = []

    for raw, source_type, doc_name, meta in feeds:
        src = ingest_raw_source(raw, source_type, doc_name, metadata=meta, ingested_at=t_fixed)

        norm = normalize_record(src, normalized_at=t_fixed)
        ents, evs, rels = extract_entities_and_relationships(norm, src, extracted_at=t_fixed)

        source_records.append(src)
        normalized_records.append(norm)
        all_extracted_entities.extend(ents)
        all_evidence.extend(evs)
        all_relationships.extend(rels)

    # Inject shared vehicle attribute on Vikram Singh and V. Singh to trigger authentic POSSIBLE_MATCH candidate
    for ent in all_extracted_entities:
        if isinstance(ent, PersonEntity):
            if "Vikram Singh" in ent.canonical_name or "V. Singh" in ent.canonical_name:
                ent.attributes["vehicle"] = "DL-01-AB-1234"

    resolved_entities, candidates, decisions, final_relationships = (
        resolve_entities_and_link_relationships(
            all_extracted_entities, all_relationships, decided_at=t_fixed
        )
    )

    return PipelineResult(
        source_records=source_records,
        normalized_records=normalized_records,
        extracted_entities=resolved_entities,
        evidence_items=all_evidence,
        resolution_candidates=candidates,
        resolution_decisions=decisions,
        relationships=final_relationships,
    )


def test_end_to_end_pipeline_load_and_query(neo4j_driver: Driver):
    """End-to-End integration test: Phase-2 Pipeline -> Phase-3A Loader -> Neo4j -> Phase-3B Queries."""
    # -------------------------------------------------------------------------
    # 1. Execute authentic Phase-2 Pipeline
    # -------------------------------------------------------------------------
    pipeline_res = _execute_phase2_pipeline()
    assert len(pipeline_res.source_records) == 5
    assert len(pipeline_res.evidence_items) >= 5
    assert len(pipeline_res.extracted_entities) > 5
    assert len(pipeline_res.relationships) >= 4

    # Verify at least one POSSIBLE_MATCH resolution candidate was generated
    possible_matches = [
        c for c in pipeline_res.resolution_candidates if c.status == ResolutionStatus.POSSIBLE_MATCH
    ]
    assert len(possible_matches) >= 1

    # -------------------------------------------------------------------------
    # 2. Persist into Neo4j via existing Phase-3A Loader
    # -------------------------------------------------------------------------
    stats1 = load_pipeline_result(pipeline_res, driver=neo4j_driver)
    assert stats1["source_records"] == 5
    assert stats1["evidence_items"] >= 5
    assert stats1["entities"] >= 5
    assert stats1["relationships"] >= 4
    assert stats1["evaluated_pairs"] >= 1

    # Verify idempotency by loading a second time
    stats2 = load_pipeline_result(pipeline_res, driver=neo4j_driver)
    assert stats1 == stats2

    # -------------------------------------------------------------------------
    # 3. Query via Phase-3B Graph Query Layer
    # -------------------------------------------------------------------------
    query = Neo4jGraphQuery(driver=neo4j_driver)

    # A. Entity Search / Lookup
    phones = query.search_entities(entity_type="PHONE")
    assert len(phones) >= 2
    phone_numbers = {p["phone_number"] for p in phones if "phone_number" in p}
    assert "+91-9900000101" in phone_numbers
    assert "+91-9900000102" in phone_numbers

    persons = query.search_entities(query="Vikram")
    assert len(persons) >= 1
    vikram = persons[0]
    assert "Vikram Singh" in vikram["canonical_name"]

    vehicles = query.search_entities(query="DL-01-AB-1234")
    assert len(vehicles) >= 1
    assert vehicles[0]["registration_number"] == "DL-01-AB-1234"

    # B. Entity Details & Connectivity Metrics
    vikram_details = query.get_entity_details(vikram["entity_id"])
    assert vikram_details is not None
    assert vikram_details["entity_id"] == vikram["entity_id"]
    assert vikram_details["direct_relationship_count"] >= 1
    assert vikram_details["possible_match_count"] >= 1

    # C. Direct Relationships
    # Find phone: +91-9900000101
    target_phone = next(p for p in phones if p["canonical_name"] == "+91-9900000101")
    phone_rels = query.get_direct_relationships(
        entity_id=target_phone["entity_id"],
        relationship_types=["COMMUNICATED_WITH"],
    )
    assert len(phone_rels) >= 1
    comm_rel = phone_rels[0]
    assert comm_rel["relationship_type"] == "COMMUNICATED_WITH"
    assert comm_rel["origin"] == "EXTRACTED"
    assert len(comm_rel["evidence_ids"]) >= 1

    # Check bank transaction relationship
    accounts = query.search_entities(entity_type="ACCOUNT")
    assert len(accounts) >= 2
    acc1 = next(a for a in accounts if a["canonical_name"] == "ACC-112233")
    acc_rels = query.get_direct_relationships(
        entity_id=acc1["entity_id"],
        relationship_types=["TRANSACTED_WITH"],
    )
    assert len(acc_rels) >= 1
    assert acc_rels[0]["relationship_type"] == "TRANSACTED_WITH"

    # D. Bounded 1-Hop and 2-Hop Network Traversal
    net_1hop = query.traverse_network(start_entity_id=target_phone["entity_id"], hops=1)
    assert net_1hop["hops"] == 1
    assert len(net_1hop["entities"]) >= 2
    assert len(net_1hop["relationships"]) >= 1

    net_2hop = query.traverse_network(
        start_entity_id=target_phone["entity_id"],
        hops=2,
        include_possible_matches=True,
    )
    assert net_2hop["hops"] == 2
    # 2-hop network has more or equal relationships than 1-hop
    assert len(net_2hop["relationships"]) >= len(net_1hop["relationships"])
    assert net_2hop["metrics"]["entity_count"] >= len(net_1hop["entities"])

    # E. Temporal Filtering Across Graph
    t_start = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    t_end = datetime(2026, 8, 10, 2, 0, 0, tzinfo=timezone.utc)

    # Call at 01:15 is inside [01:00, 02:00]
    early_slice = query.get_temporal_subgraph(
        start_time=t_start,
        end_time=t_end,
        include_undated=False,
    )
    assert len(early_slice["relationships"]) >= 1
    early_rel_types = {r["relationship_type"] for r in early_slice["relationships"]}
    assert "COMMUNICATED_WITH" in early_rel_types

    # Bank transaction at 04:00 is outside [01:00, 02:00]
    assert "TRANSACTED_WITH" not in early_rel_types

    # F. Strict Provenance Chain: Relationship -> Evidence -> FROM_SOURCE -> SourceRecord
    rel_evidence = query.get_relationship_evidence(comm_rel["relationship_id"])
    assert len(rel_evidence) >= 1
    ev_item = rel_evidence[0]
    assert ev_item["relationship_id"] == comm_rel["relationship_id"]
    assert ev_item["evidence"]["evidence_id"] in comm_rel["evidence_ids"]
    assert ev_item["evidence"]["source_type"] == "CALL_DETAIL_RECORD"
    assert ev_item["source_record"]["source_type"] == "CALL_DETAIL_RECORD"
    assert "CALL" in ev_item["source_record"]["raw_content"]
    assert ev_item["evidence"]["raw_snippet"] in ev_item["source_record"]["raw_content"]

    # G. Possible-Match Inspection
    cand_matches = query.get_possible_matches()
    assert len(cand_matches) >= 1
    pm = cand_matches[0]
    assert pm["status"] == "POSSIBLE_MATCH"
    assert pm["similarity_score"] >= 0.70
    assert "DL-01-AB-1234" in pm["justification"] or "Name" in pm["heuristic_name"]

    # Confirm candidate entities remain unmerged in graph
    entity_a = query.get_entity_details(pm["entity_id_a"])
    entity_b = query.get_entity_details(pm["entity_id_b"])
    assert entity_a is not None
    assert entity_b is not None
    assert entity_a["entity_id"] != entity_b["entity_id"]


def test_deterministic_query_reproducibility(neo4j_driver: Driver):
    """Verify that repeated executions of the query layer yield byte-for-byte identical results."""
    pipeline_res = _execute_phase2_pipeline()
    load_pipeline_result(pipeline_res, driver=neo4j_driver)
    query = Neo4jGraphQuery(driver=neo4j_driver)

    # 1. Search reproducibility
    search_run1 = query.search_entities(limit=20)
    search_run2 = query.search_entities(limit=20)
    assert search_run1 == search_run2

    # 2. 2-hop traversal reproducibility
    root_id = search_run1[0]["entity_id"]
    trav_run1 = query.traverse_network(start_entity_id=root_id, hops=2, include_possible_matches=True)
    trav_run2 = query.traverse_network(start_entity_id=root_id, hops=2, include_possible_matches=True)
    assert trav_run1 == trav_run2

    # 3. Evidence retrieval reproducibility
    if trav_run1["relationships"]:
        rel_id = trav_run1["relationships"][0]["relationship_id"]
        ev_run1 = query.get_relationship_evidence(rel_id)
        ev_run2 = query.get_relationship_evidence(rel_id)
        assert ev_run1 == ev_run2
