"""Unit Tests for Generic Entity Extraction and Evidence Provenance Engine."""

from datetime import datetime, timezone
import pytest

from app.schemas.entity import EntityType
from app.schemas.relationship import RelationshipOrigin, RelationshipType
from app.pipeline.ingestion import ingest_raw_source
from app.pipeline.normalization import normalize_record
from app.pipeline.extraction import extract_entities_and_relationships

HAWKEYE_CDR_RAW = "CALL,2026-08-10T01:15:00Z,+91-9900000101,+91-9900000102,480s,TOWER_DELHI_NORTH"
HAWKEYE_TOLL_RAW = '{"timestamp":"2026-08-10T02:30:00Z","reg":"DL-01-AB-1234","toll_id":"TOLL_NH48_KM42","owner":"Aarav Sharma"}'
HAWKEYE_FIR_RAW = "FIR #882/2026: Suspect alias 'V. Singh' sighted driving black sedan reg DL-01-AB-1234 near illegal warehouse."
HAWKEYE_BANK_RAW = "TXN,2026-08-10T04:00:00Z,ACC-112233,ACC-998877,450000.00,INR,REMARKS:APEX_SUPPLY"
HAWKEYE_HOTEL_RAW = '{"checkin":"2026-08-10T06:00:00Z","guest":"Vikram Singh","phone":"+91-9900000101","national_id":"IND-98765432","vehicle":"DL-01-AB-1234"}'


def test_extraction_all_six_entity_categories():
    """Test that all 6 Phase-1 entity categories are extracted across raw feeds."""
    dt = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    all_extracted_entities = []

    feeds = [
        (HAWKEYE_CDR_RAW, "CALL_DETAIL_RECORD", "cdr.csv"),
        (HAWKEYE_TOLL_RAW, "VEHICLE_TOLL_LOG", "toll.json"),
        (HAWKEYE_FIR_RAW, "FIR_REPORT", "fir.txt"),
        (HAWKEYE_BANK_RAW, "BANK_TRANSACTION", "bank.csv"),
        (HAWKEYE_HOTEL_RAW, "HOTEL_CHECKIN", "hotel.json"),
    ]

    for raw, stype, dname in feeds:
        src = ingest_raw_source(raw, stype, dname, ingested_at=dt)
        norm = normalize_record(src, normalized_at=dt)
        entities, evidence, rels = extract_entities_and_relationships(norm, src, extracted_at=dt)
        all_extracted_entities.extend(entities)

    extracted_types = {e.entity_type for e in all_extracted_entities}
    expected_types = {
        EntityType.PERSON,
        EntityType.PHONE,
        EntityType.VEHICLE,
        EntityType.LOCATION,
        EntityType.ORGANIZATION,
        EntityType.ACCOUNT,
    }
    assert expected_types.issubset(extracted_types)


def test_evidence_provenance_character_offsets():
    """Test that evidence raw_snippet corresponds exactly to raw_content[offset_start:offset_end]."""
    dt = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    src = ingest_raw_source(HAWKEYE_CDR_RAW, "CALL_DETAIL_RECORD", "cdr.csv", ingested_at=dt)
    norm = normalize_record(src, normalized_at=dt)
    entities, evidence_list, rels = extract_entities_and_relationships(norm, src, extracted_at=dt)

    assert len(evidence_list) > 0
    for ev in evidence_list:
        assert ev.source_record_id == src.source_id
        if ev.offset_start is not None and ev.offset_end is not None:
            snippet_from_raw = src.raw_content[ev.offset_start:ev.offset_end]
            assert snippet_from_raw == ev.raw_snippet


def test_source_observed_relationships_have_extracted_origin():
    """Test that extracted relationships carry origin=RelationshipOrigin.EXTRACTED and no inferred edges exist."""
    dt = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    src = ingest_raw_source(HAWKEYE_BANK_RAW, "BANK_TRANSACTION", "bank.csv", ingested_at=dt)
    norm = normalize_record(src, normalized_at=dt)
    entities, evidence, rels = extract_entities_and_relationships(norm, src, extracted_at=dt)

    assert len(rels) == 1
    rel = rels[0]
    assert rel.relationship_type == RelationshipType.TRANSACTED_WITH
    assert rel.origin == RelationshipOrigin.EXTRACTED
