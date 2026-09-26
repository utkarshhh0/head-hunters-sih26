"""Deterministic Demo Bootstrap Script for Round-2 Vertical Slice.

Populates the local Neo4j database by executing the existing generic data pipeline
end-to-end using controlled, deterministic heterogeneous synthetic data.

Pipeline flow:
RAW CONTROLLED MULTI-SOURCE DATA
-> ingest_raw_source()
-> normalize_record()
-> extract_entities_and_relationships()
-> resolve_entities_and_link_relationships()
-> PipelineResult
-> load_pipeline_result()
-> Neo4j
"""

from datetime import datetime, timezone
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Suppress driver notification warnings for clean CLI output
warnings.filterwarnings("ignore")

# Ensure src/backend is on sys.path for direct script execution
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.pipeline.ingestion import ingest_raw_source
from app.pipeline.normalization import normalize_record
from app.pipeline.extraction import extract_entities_and_relationships
from app.pipeline.resolution import resolve_entities_and_link_relationships
from app.pipeline import PipelineResult
from app.graph.loader import load_pipeline_result
from app.graph.query import Neo4jGraphQuery
from app.analytics.patterns import PatternDetector

CENTRAL_PHONE = "+91-9000000001"
PERIPHERAL_PHONES = [
    "+91-9000000002",
    "+91-9000000003",
    "+91-9000000004",
    "+91-9000000005",
]

# Fixed UTC decision timestamp for entity resolution
DECISION_TIMESTAMP = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)

# 23 controlled deterministic synthetic records spanning:
# HOTEL_CHECKIN, VEHICLE_TOLL_LOG, FIR_REPORT, BANK_TRANSACTION, CALL_DETAIL_RECORD
# Concentrated time window: 2026-08-15 08:00:00 UTC to 2026-08-15 11:00:00 UTC
SYNTHETIC_INVESTIGATION_DATA: List[Tuple[str, str, str, str, datetime]] = [
    # -------------------------------------------------------------------------
    # 1. HOTEL CHECK-INS (PERSON, PHONE, VEHICLE, ASSOCIATED_WITH)
    # -------------------------------------------------------------------------
    (
        "HOTEL_CHECKIN",
        '{"guest":"Vikram Singh","phone":"+91-9000000001","national_id":"IND-98765432","vehicle":"DL-01-AB-1234"}',
        "synthetic_hotel_delhi_001.json",
        "2026-08-15T08:00:00Z",
        datetime(2026, 8, 15, 8, 0, 0, tzinfo=timezone.utc),
    ),
    (
        "HOTEL_CHECKIN",
        '{"guest":"Aarav Sharma","phone":"+91-9000000002","national_id":"IND-11223344","vehicle":"HR-26-DK-5678"}',
        "synthetic_hotel_gurgaon_002.json",
        "2026-08-15T08:15:00Z",
        datetime(2026, 8, 15, 8, 15, 0, tzinfo=timezone.utc),
    ),
    (
        "HOTEL_CHECKIN",
        '{"guest":"Pooja Verma","phone":"+91-9000000003","national_id":"IND-33445566","vehicle":"DL-01-AB-1234"}',
        "synthetic_hotel_delhi_003.json",
        "2026-08-15T08:20:00Z",
        datetime(2026, 8, 15, 8, 20, 0, tzinfo=timezone.utc),
    ),
    (
        "HOTEL_CHECKIN",
        '{"guest":"Rohan Verma","phone":"+91-9000000004","national_id":"IND-55667788","vehicle":"UP-16-XY-9999"}',
        "synthetic_hotel_noida_004.json",
        "2026-08-15T08:25:00Z",
        datetime(2026, 8, 15, 8, 25, 0, tzinfo=timezone.utc),
    ),
    (
        "HOTEL_CHECKIN",
        '{"guest":"Sunil Mehta","phone":"+91-9000000005","national_id":"IND-77889900","vehicle":"UP-16-XY-9999"}',
        "synthetic_hotel_noida_005.json",
        "2026-08-15T08:30:00Z",
        datetime(2026, 8, 15, 8, 30, 0, tzinfo=timezone.utc),
    ),

    # -------------------------------------------------------------------------
    # 2. VEHICLE TOLL LOGS (VEHICLE, PERSON, LOCATION, OWNED_BY)
    # -------------------------------------------------------------------------
    (
        "VEHICLE_TOLL_LOG",
        '{"timestamp":"2026-08-15T08:35:00Z","reg":"DL-01-AB-1234","toll_id":"Toll Plaza NH48 KM42","owner":"Vikram Singh"}',
        "synthetic_toll_nh48_001.json",
        "2026-08-15T08:35:00Z",
        datetime(2026, 8, 15, 8, 35, 0, tzinfo=timezone.utc),
    ),
    (
        "VEHICLE_TOLL_LOG",
        '{"timestamp":"2026-08-15T08:40:00Z","reg":"HR-26-DK-5678","toll_id":"Toll Plaza NH48 KM42","owner":"Aarav Sharma"}',
        "synthetic_toll_nh48_002.json",
        "2026-08-15T08:40:00Z",
        datetime(2026, 8, 15, 8, 40, 0, tzinfo=timezone.utc),
    ),
    (
        "VEHICLE_TOLL_LOG",
        '{"timestamp":"2026-08-15T08:45:00Z","reg":"UP-16-XY-9999","toll_id":"Toll Plaza NH48 KM42","owner":"Rohan Verma"}',
        "synthetic_toll_nh48_003.json",
        "2026-08-15T08:45:00Z",
        datetime(2026, 8, 15, 8, 45, 0, tzinfo=timezone.utc),
    ),

    # -------------------------------------------------------------------------
    # 3. FIR SIGHTING REPORT (PERSON, VEHICLE, LOCATION, ASSOCIATED_WITH)
    # -------------------------------------------------------------------------
    (
        "FIR_REPORT",
        "FIR #882/2026: Suspect alias 'Vikram Singh' sighted driving black sedan reg DL-01-AB-1234 near Warehouse Sector 18 Gurgaon.",
        "synthetic_fir_gurgaon_882.txt",
        "2026-08-15T08:50:00Z",
        datetime(2026, 8, 15, 8, 50, 0, tzinfo=timezone.utc),
    ),

    # -------------------------------------------------------------------------
    # 4. BANK TRANSACTIONS (ACCOUNT, ORGANIZATION, TRANSACTED_WITH)
    # -------------------------------------------------------------------------
    (
        "BANK_TRANSACTION",
        "TXN,2026-08-15T09:10:00Z,ACC-100001,ACC-200002,450000.00,INR,REMARKS:APEX_LOGISTICS",
        "synthetic_bank_txn_001.csv",
        "2026-08-15T09:10:00Z",
        datetime(2026, 8, 15, 9, 10, 0, tzinfo=timezone.utc),
    ),
    (
        "BANK_TRANSACTION",
        "TXN,2026-08-15T09:40:00Z,ACC-100001,ACC-200002,280000.00,INR,REMARKS:APEX_LOGISTICS",
        "synthetic_bank_txn_002.csv",
        "2026-08-15T09:40:00Z",
        datetime(2026, 8, 15, 9, 40, 0, tzinfo=timezone.utc),
    ),

    # -------------------------------------------------------------------------
    # 5. CALL DETAIL RECORDS (PHONE, COMMUNICATED_WITH, TEMPORAL BURSTS)
    # -------------------------------------------------------------------------
    # Central phone to Peripheral 1 (repeated interactions: 3 calls, burst window)
    (
        "CALL_DETAIL_RECORD",
        f"CALL,2026-08-15T09:00:00Z,{CENTRAL_PHONE},{PERIPHERAL_PHONES[0]},180s,TOWER_DELHI_01",
        "synthetic_cdr_20260815_001.csv",
        "2026-08-15T09:00:00Z",
        datetime(2026, 8, 15, 9, 0, 0, tzinfo=timezone.utc),
    ),
    (
        "CALL_DETAIL_RECORD",
        f"CALL,2026-08-15T09:15:00Z,{CENTRAL_PHONE},{PERIPHERAL_PHONES[0]},240s,TOWER_DELHI_01",
        "synthetic_cdr_20260815_002.csv",
        "2026-08-15T09:15:00Z",
        datetime(2026, 8, 15, 9, 15, 0, tzinfo=timezone.utc),
    ),
    (
        "CALL_DETAIL_RECORD",
        f"CALL,2026-08-15T09:30:00Z,{CENTRAL_PHONE},{PERIPHERAL_PHONES[0]},300s,TOWER_DELHI_01",
        "synthetic_cdr_20260815_003.csv",
        "2026-08-15T09:30:00Z",
        datetime(2026, 8, 15, 9, 30, 0, tzinfo=timezone.utc),
    ),
    # Central phone to Peripheral 2 (repeated interactions: 2 calls)
    (
        "CALL_DETAIL_RECORD",
        f"CALL,2026-08-15T09:45:00Z,{CENTRAL_PHONE},{PERIPHERAL_PHONES[1]},120s,TOWER_DELHI_02",
        "synthetic_cdr_20260815_004.csv",
        "2026-08-15T09:45:00Z",
        datetime(2026, 8, 15, 9, 45, 0, tzinfo=timezone.utc),
    ),
    (
        "CALL_DETAIL_RECORD",
        f"CALL,2026-08-15T10:00:00Z,{CENTRAL_PHONE},{PERIPHERAL_PHONES[1]},450s,TOWER_DELHI_02",
        "synthetic_cdr_20260815_005.csv",
        "2026-08-15T10:00:00Z",
        datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc),
    ),
    # Central phone to Peripheral 3 (repeated interactions: 2 calls)
    (
        "CALL_DETAIL_RECORD",
        f"CALL,2026-08-15T10:15:00Z,{CENTRAL_PHONE},{PERIPHERAL_PHONES[2]},210s,TOWER_DELHI_03",
        "synthetic_cdr_20260815_006.csv",
        "2026-08-15T10:15:00Z",
        datetime(2026, 8, 15, 10, 15, 0, tzinfo=timezone.utc),
    ),
    (
        "CALL_DETAIL_RECORD",
        f"CALL,2026-08-15T10:30:00Z,{CENTRAL_PHONE},{PERIPHERAL_PHONES[2]},190s,TOWER_DELHI_03",
        "synthetic_cdr_20260815_007.csv",
        "2026-08-15T10:30:00Z",
        datetime(2026, 8, 15, 10, 30, 0, tzinfo=timezone.utc),
    ),
    # Central phone to Peripheral 4 (repeated interactions: 2 calls)
    (
        "CALL_DETAIL_RECORD",
        f"CALL,2026-08-15T10:45:00Z,{CENTRAL_PHONE},{PERIPHERAL_PHONES[3]},320s,TOWER_DELHI_04",
        "synthetic_cdr_20260815_008.csv",
        "2026-08-15T10:45:00Z",
        datetime(2026, 8, 15, 10, 45, 0, tzinfo=timezone.utc),
    ),
    (
        "CALL_DETAIL_RECORD",
        f"CALL,2026-08-15T11:00:00Z,{CENTRAL_PHONE},{PERIPHERAL_PHONES[3]},280s,TOWER_DELHI_04",
        "synthetic_cdr_20260815_009.csv",
        "2026-08-15T11:00:00Z",
        datetime(2026, 8, 15, 11, 0, 0, tzinfo=timezone.utc),
    ),
    # Peripheral 1 to Peripheral 2 (Primary Cluster edge)
    (
        "CALL_DETAIL_RECORD",
        f"CALL,2026-08-15T09:35:00Z,{PERIPHERAL_PHONES[0]},{PERIPHERAL_PHONES[1]},150s,TOWER_DELHI_02",
        "synthetic_cdr_20260815_010.csv",
        "2026-08-15T09:35:00Z",
        datetime(2026, 8, 15, 9, 35, 0, tzinfo=timezone.utc),
    ),
    # Peripheral 3 to Peripheral 4 (Secondary Cluster edge, repeated interactions: 2 calls)
    (
        "CALL_DETAIL_RECORD",
        f"CALL,2026-08-15T10:35:00Z,{PERIPHERAL_PHONES[2]},{PERIPHERAL_PHONES[3]},160s,TOWER_DELHI_04",
        "synthetic_cdr_20260815_011.csv",
        "2026-08-15T10:35:00Z",
        datetime(2026, 8, 15, 10, 35, 0, tzinfo=timezone.utc),
    ),
    (
        "CALL_DETAIL_RECORD",
        f"CALL,2026-08-15T10:50:00Z,{PERIPHERAL_PHONES[2]},{PERIPHERAL_PHONES[3]},220s,TOWER_DELHI_04",
        "synthetic_cdr_20260815_012.csv",
        "2026-08-15T10:50:00Z",
        datetime(2026, 8, 15, 10, 50, 0, tzinfo=timezone.utc),
    ),
]


def build_bootstrap_pipeline_result() -> PipelineResult:
    """Executes the authentic Phase-2 data pipeline end-to-end over the synthetic multi-source dataset."""
    source_records = []
    normalized_records = []
    all_extracted_entities = []
    all_evidence = []
    all_relationships = []

    for source_type, raw_content, doc_name, iso_ts, dt_obj in SYNTHETIC_INVESTIGATION_DATA:
        source = ingest_raw_source(
            raw_content=raw_content,
            source_type=source_type,
            document_name=doc_name,
            metadata={
                "timestamp_context": iso_ts,
                "is_synthetic": True,
            },
            ingested_at=dt_obj,
        )

        normalized = normalize_record(
            source,
            normalized_at=dt_obj,
        )

        entities, evidence, relationships = extract_entities_and_relationships(
            normalized,
            source,
            extracted_at=dt_obj,
        )

        source_records.append(source)
        normalized_records.append(normalized)
        all_extracted_entities.extend(entities)
        all_evidence.extend(evidence)
        all_relationships.extend(relationships)

    resolved_entities, candidates, decisions, resolved_relationships = (
        resolve_entities_and_link_relationships(
            all_extracted_entities,
            all_relationships,
            decided_at=DECISION_TIMESTAMP,
        )
    )

    return PipelineResult(
        source_records=source_records,
        normalized_records=normalized_records,
        extracted_entities=resolved_entities,
        evidence_items=all_evidence,
        resolution_candidates=candidates,
        resolution_decisions=decisions,
        relationships=resolved_relationships,
    )


def verify_bootstrap(query: Neo4jGraphQuery) -> Dict[str, Any]:
    """Performs read-only verification of the persisted heterogeneous graph state using existing query functionality."""
    with query.driver.session() as session:
        src_count = session.run("MATCH (s:SourceRecord) RETURN count(s) AS c").single()["c"]
        ev_count = session.run("MATCH (e:Evidence) RETURN count(e) AS c").single()["c"]
        ent_count = session.run("MATCH (n:Entity) RETURN count(n) AS c").single()["c"]
        rel_count = session.run(
            "MATCH ()-[r]->() WHERE type(r) <> 'FROM_SOURCE' AND type(r) <> 'EVALUATED_PAIR' RETURN count(r) AS c"
        ).single()["c"]
        type_counts = {
            r["t"]: r["c"]
            for r in session.run("MATCH (n:Entity) RETURN n.entity_type AS t, count(n) AS c").data()
        }
        edge_type_counts = {
            r["t"]: r["c"]
            for r in session.run(
                "MATCH ()-[r]->() WHERE type(r) <> 'FROM_SOURCE' AND type(r) <> 'EVALUATED_PAIR' "
                "RETURN type(r) AS t, count(r) AS c"
            ).data()
        }

    # 1. Verification of counts > 0
    if src_count <= 0:
        raise ValueError(f"Verification failed: Source records count is {src_count} (expected > 0)")
    if ev_count <= 0:
        raise ValueError(f"Verification failed: Evidence items count is {ev_count} (expected > 0)")
    if ent_count < 15 or ent_count > 25:
        raise ValueError(f"Verification failed: Entity count is {ent_count} (expected 15-25 canonical entities)")
    if rel_count <= 0:
        raise ValueError(f"Verification failed: Relationship count is {rel_count} (expected > 0)")

    # 2. Heterogeneous entity types verification across all 6 supported types
    expected_entity_types = {"PERSON", "PHONE", "VEHICLE", "LOCATION", "ACCOUNT", "ORGANIZATION"}
    missing_ent_types = expected_entity_types - set(type_counts.keys())
    if missing_ent_types:
        raise ValueError(f"Verification failed: Missing expected entity types: {missing_ent_types}")

    # 3. Heterogeneous relationship types verification across all 4 approved types
    expected_rel_types = {"COMMUNICATED_WITH", "OWNED_BY", "ASSOCIATED_WITH", "TRANSACTED_WITH"}
    missing_rel_types = expected_rel_types - set(edge_type_counts.keys())
    if missing_rel_types:
        raise ValueError(f"Verification failed: Missing expected relationship types: {missing_rel_types}")

    # 4. Central phone lookup
    central_entities = query.search_entities(query=CENTRAL_PHONE)
    if not central_entities:
        raise ValueError(f"Verification failed: Central entity for {CENTRAL_PHONE} not found")
    central_id = central_entities[0]["entity_id"]

    # 5. Central phone degree >= 4
    details = query.get_entity_details(central_id)
    if not details:
        raise ValueError(f"Verification failed: Details for entity {central_id} not found")
    degree = details.get("direct_relationship_count", 0)
    if degree < 4:
        raise ValueError(f"Verification failed: Central phone degree is {degree} (expected >= 4)")

    # 6. Direct relationships checks
    direct_rels = query.get_direct_relationships(central_id, direction="BOTH")
    if not direct_rels:
        raise ValueError("Verification failed: No direct relationships found for central phone")

    # 7. At least one relationship has interaction_count > 1
    max_interactions = max(r.get("interaction_count", 1) for r in direct_rels)
    if max_interactions <= 1:
        raise ValueError(
            f"Verification failed: Max interaction count is {max_interactions} (expected > 1)"
        )

    # 8. Relationships have first_seen/last_seen
    missing_timestamps = [
        r["relationship_id"]
        for r in direct_rels
        if r.get("first_seen") is None or r.get("last_seen") is None
    ]
    if missing_timestamps:
        raise ValueError(
            f"Verification failed: Relationships missing timestamps: {missing_timestamps}"
        )

    # 9. evidence_ids are populated
    missing_evidence = [
        r["relationship_id"] for r in direct_rels if not r.get("evidence_ids")
    ]
    if missing_evidence:
        raise ValueError(
            f"Verification failed: Relationships with empty evidence_ids: {missing_evidence}"
        )

    # 10. Evidence traverses to SourceRecord
    verified_traversals = 0
    for r in direct_rels:
        evidence_records = query.get_relationship_evidence(r["relationship_id"])
        if not evidence_records:
            raise ValueError(
                f"Verification failed: Relationship {r['relationship_id']} has no evidence traversals"
            )
        for ev_rec in evidence_records:
            ev = ev_rec.get("evidence", {})
            sr = ev_rec.get("source_record", {})
            if not ev.get("evidence_id"):
                raise ValueError("Verification failed: Evidence node missing evidence_id")
            if not sr.get("source_id"):
                raise ValueError("Verification failed: SourceRecord node missing source_id")
            if ev.get("source_record_id") != sr.get("source_id"):
                raise ValueError(
                    f"Verification failed: Provenance mismatch: evidence source_record_id "
                    f"({ev.get('source_record_id')}) != source_record source_id ({sr.get('source_id')})"
                )
            verified_traversals += 1

    # 11. Bounded 2-hop neighborhood contains heterogeneous entity types
    nb_2hop = query.traverse_network(start_entity_id=central_id, hops=2)
    nb_types = {e["entity_type"] for e in nb_2hop.get("entities", [])}
    if len(nb_types) < 2:
        raise ValueError(f"Verification failed: 2-hop neighborhood lacks heterogeneity: {nb_types}")

    # 12. Pattern detector produces meaningful analytical findings
    with PatternDetector(query=query) as detector:
        patterns = detector.detect_patterns()
        if not patterns:
            raise ValueError("Verification failed: PatternDetector produced 0 patterns on demo graph")

    return {
        "source_records": src_count,
        "evidence_items": ev_count,
        "entities": ent_count,
        "relationships": rel_count,
        "central_degree": degree,
        "max_interactions": max_interactions,
        "provenance_traversals": verified_traversals,
        "entity_types": type_counts,
        "edge_types": edge_type_counts,
        "pattern_count": len(patterns),
    }


def run_bootstrap() -> Dict[str, Any]:
    """Executes the pipeline, loads into Neo4j, prints deterministic summary, and runs verification."""
    pipeline_result = build_bootstrap_pipeline_result()
    stats = load_pipeline_result(pipeline_result)

    print("Demo bootstrap complete.")
    print(f"Source records: {stats['source_records']}")
    print(f"Evidence items: {stats['evidence_items']}")
    print(f"Entities: {stats['entities']}")
    print(f"Relationships: {stats['relationships']}")
    print(f"Evaluated pairs: {stats['evaluated_pairs']}")
    print()

    # Read-only verification using existing graph/query functionality
    with Neo4jGraphQuery() as query:
        v = verify_bootstrap(query)
        print("Read-only verification:")
        print(f"- Source records: {v['source_records']} (> 0) [PASS]")
        print(f"- Evidence items: {v['evidence_items']} (> 0) [PASS]")
        print(f"- Entities: {v['entities']} in graph across {len(v['entity_types'])} types: {dict(v['entity_types'])} [PASS]")
        print(f"- Relationships: {v['relationships']} across {len(v['edge_types'])} types: {dict(v['edge_types'])} [PASS]")
        print(f"- Central phone ({CENTRAL_PHONE}) degree: {v['central_degree']} (>= 4) [PASS]")
        print(f"- Repeated interactions: max interaction_count = {v['max_interactions']} (> 1) [PASS]")
        print("- Temporal bounds: first_seen and last_seen populated on all relationships [PASS]")
        print("- Evidence IDs: populated on all relationships [PASS]")
        print(f"- Provenance traversal: {v['provenance_traversals']} evidence link(s) traverse to SourceRecord [PASS]")
        print(f"- Pattern detection: {v['pattern_count']} multi-signal pattern(s) detected [PASS]")
        print("Verification status: ALL CHECKS PASSED")

    return stats


if __name__ == "__main__":
    run_bootstrap()
