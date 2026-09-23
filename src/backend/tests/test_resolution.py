"""Unit Tests for Generic Entity Resolution, Endpoint Remapping, and Determinism."""

from datetime import datetime, timezone
import pytest

from app.schemas.entity import EntityType, PersonEntity, PhoneEntity
from app.schemas.relationship import ResolutionStatus, RelationshipOrigin, Relationship, RelationshipType
from app.pipeline.ingestion import ingest_raw_source
from app.pipeline.normalization import normalize_record
from app.pipeline.extraction import extract_entities_and_relationships
from app.pipeline.resolution import resolve_entities_and_link_relationships

HAWKEYE_CDR_RAW = "CALL,2026-08-10T01:15:00Z,+91-9900000101,+91-9900000102,480s,TOWER_DELHI_NORTH"
HAWKEYE_TOLL_RAW = '{"timestamp":"2026-08-10T02:30:00Z","reg":"DL-01-AB-1234","toll_id":"TOLL_NH48_KM42","owner":"Aarav Sharma"}'
HAWKEYE_FIR_RAW = "FIR #882/2026: Suspect alias 'V. Singh' sighted driving black sedan reg DL-01-AB-1234 near illegal warehouse."
HAWKEYE_BANK_RAW = "TXN,2026-08-10T04:00:00Z,ACC-112233,ACC-998877,450000.00,INR,REMARKS:APEX_SUPPLY"
HAWKEYE_HOTEL_RAW = '{"checkin":"2026-08-10T06:00:00Z","guest":"Vikram Singh","phone":"+91-9900000101","national_id":"IND-98765432","vehicle":"DL-01-AB-1234"}'


def test_phone_phone_high_confidence_resolution():
    """Test that two Phone entities with exact E.164 numbers resolve to HIGH_CONFIDENCE."""
    dt = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    p1 = PhoneEntity(
        entity_id="urn:entity:phone:001",
        entity_type=EntityType.PHONE,
        canonical_name="+91-9900000101",
        phone_number="+91-9900000101",
    )
    p2 = PhoneEntity(
        entity_id="urn:entity:phone:002",
        entity_type=EntityType.PHONE,
        canonical_name="+91-9900000101",
        phone_number="+91-9900000101",
    )

    resolved, cands, decs, rels = resolve_entities_and_link_relationships([p1, p2], [], decided_at=dt)
    assert len(decs) == 1
    assert decs[0].status == ResolutionStatus.HIGH_CONFIDENCE
    assert decs[0].merged_entity_id == "urn:entity:phone:001"
    assert len(resolved) == 1


def test_person_person_national_id_high_confidence():
    """Test that two Person entities with exact matching National IDs resolve to HIGH_CONFIDENCE."""
    dt = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    p1 = PersonEntity(
        entity_id="urn:entity:person:001",
        entity_type=EntityType.PERSON,
        canonical_name="Vikram Singh",
        full_name="Vikram Singh",
        national_id="IND-98765432",
    )
    p2 = PersonEntity(
        entity_id="urn:entity:person:002",
        entity_type=EntityType.PERSON,
        canonical_name="Vikram Singh",
        full_name="Vikram Singh",
        national_id="IND-98765432",
    )

    resolved, cands, decs, rels = resolve_entities_and_link_relationships([p1, p2], [], decided_at=dt)
    assert len(decs) == 1
    assert decs[0].status == ResolutionStatus.HIGH_CONFIDENCE
    assert decs[0].merged_entity_id == "urn:entity:person:001"
    assert len(resolved) == 1


def test_person_person_name_similarity_shared_vehicle_possible_match_unmerged():
    """Test that name similarity + shared vehicle produces POSSIBLE_MATCH and remains UNMERGED."""
    dt = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    p1 = PersonEntity(
        entity_id="urn:entity:person:001",
        entity_type=EntityType.PERSON,
        canonical_name="Vikram Singh",
        full_name="Vikram Singh",
        attributes={"vehicle": "DL-01-AB-1234"},
    )
    p2 = PersonEntity(
        entity_id="urn:entity:person:002",
        entity_type=EntityType.PERSON,
        canonical_name="V. Singh",
        full_name="V. Singh",
        attributes={"vehicle": "DL-01-AB-1234"},
    )

    resolved, cands, decs, rels = resolve_entities_and_link_relationships([p1, p2], [], decided_at=dt)
    assert len(decs) == 1
    assert decs[0].status == ResolutionStatus.POSSIBLE_MATCH
    assert decs[0].merged_entity_id is None  # MUST NOT MERGE
    assert len(resolved) == 2  # Both persons preserved as distinct entities


def test_person_person_mismatched_national_ids_no_match():
    """Test that mismatched National IDs produce NO_MATCH."""
    dt = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    p1 = PersonEntity(
        entity_id="urn:entity:person:001",
        entity_type=EntityType.PERSON,
        canonical_name="Aarav Sharma",
        full_name="Aarav Sharma",
        national_id="IND-11223344",
    )
    p2 = PersonEntity(
        entity_id="urn:entity:person:002",
        entity_type=EntityType.PERSON,
        canonical_name="Vikram Singh",
        full_name="Vikram Singh",
        national_id="IND-98765432",
    )

    resolved, cands, decs, rels = resolve_entities_and_link_relationships([p1, p2], [], decided_at=dt)
    assert len(decs) == 1
    assert decs[0].status == ResolutionStatus.NO_MATCH
    assert decs[0].merged_entity_id is None
    assert len(resolved) == 2


def test_relationship_endpoint_remapping_retains_extracted_origin():
    """Test that relationship endpoints are remapped to canonical entity URNs while retaining EXTRACTED origin."""
    dt = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    p1 = PhoneEntity(
        entity_id="urn:entity:phone:001",
        entity_type=EntityType.PHONE,
        canonical_name="+91-9900000101",
        phone_number="+91-9900000101",
    )
    p2 = PhoneEntity(
        entity_id="urn:entity:phone:002",
        entity_type=EntityType.PHONE,
        canonical_name="+91-9900000101",
        phone_number="+91-9900000101",
    )
    rel = Relationship(
        relationship_id="urn:rel:001",
        source_entity_id="urn:entity:phone:002",  # Will be remapped to 001
        target_entity_id="urn:entity:phone:999",
        relationship_type=RelationshipType.COMMUNICATED_WITH,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=1.0,
    )

    resolved, cands, decs, remapped_rels = resolve_entities_and_link_relationships([p1, p2], [rel], decided_at=dt)
    assert len(remapped_rels) == 1
    assert remapped_rels[0].source_entity_id == "urn:entity:phone:001"
    assert remapped_rels[0].origin == RelationshipOrigin.EXTRACTED


def test_full_pipeline_execution_determinism():
    """Test that executing full generic pipeline twice with identical parameters yields 100% equivalent outputs."""
    dt = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)

    def run_pipeline():
        src = ingest_raw_source(HAWKEYE_CDR_RAW, "CALL_DETAIL_RECORD", "cdr.csv", ingested_at=dt)
        norm = normalize_record(src, normalized_at=dt)
        entities, evidence, rels = extract_entities_and_relationships(norm, src, extracted_at=dt)
        res_entities, cands, decs, final_rels = resolve_entities_and_link_relationships(entities, rels, decided_at=dt)
        return src, norm, res_entities, cands, decs, final_rels

    run1 = run_pipeline()
    run2 = run_pipeline()

    # Compare source, norm, entities, decs, rels
    assert run1[0].source_id == run2[0].source_id
    assert run1[1].record_id == run2[1].record_id
    assert len(run1[2]) == len(run2[2])
    assert run1[2][0].entity_id == run2[2][0].entity_id
    assert len(run1[5]) == len(run2[5])
    assert run1[5][0].relationship_id == run2[5][0].relationship_id
