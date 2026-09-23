"""Unit Tests for Pydantic Shared Domain Schemas."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.schemas.record import SourceRecord, NormalizedRecord
from app.schemas.entity import (
    Entity,
    EntityType,
    PersonEntity,
    PhoneEntity,
    VehicleEntity,
    LocationEntity,
    OrganizationEntity,
    AccountEntity,
)
from app.schemas.relationship import (
    ResolutionStatus,
    ResolutionCandidate,
    ResolutionDecision,
    RelationshipType,
    RelationshipOrigin,
    Relationship,
)
from app.schemas.evidence import EvidenceProvenance
from app.schemas.finding import SignalType, AnalyticalSignal, InvestigativeFinding


def test_source_and_normalized_record_validation():
    """Test valid instantiation and extra='forbid' constraint on record schemas."""
    now = datetime.now(timezone.utc)

    source = SourceRecord(
        source_id="urn:source:cdr:001",
        source_type="CALL_DETAIL_RECORD",
        document_name="cdr.csv",
        raw_content="RAW_DATA",
        metadata={"key": "value"},
        ingested_at=now,
    )
    assert source.source_id == "urn:source:cdr:001"

    # Test extra field rejection
    with pytest.raises(ValidationError):
        SourceRecord(
            source_id="urn:source:cdr:001",
            source_type="CALL_DETAIL_RECORD",
            document_name="cdr.csv",
            raw_content="RAW_DATA",
            extra_unauthorized_field="FAIL",
        )

    norm = NormalizedRecord(
        record_id="urn:norm:001",
        source_id="urn:source:cdr:001",
        canonical_text="CANONICAL",
        extracted_fields={"caller": "+919900000101"},
        normalized_at=now,
    )
    assert norm.record_id == "urn:norm:001"


def test_entity_subtypes_instantiation():
    """Test entity base and subtype instantiation."""
    person = PersonEntity(
        entity_id="urn:entity:person:001",
        entity_type=EntityType.PERSON,
        canonical_name="John Doe",
        full_name="John Doe",
        national_id="IND-123456",
    )
    assert person.entity_type == EntityType.PERSON
    assert person.national_id == "IND-123456"

    phone = PhoneEntity(
        entity_id="urn:entity:phone:001",
        entity_type=EntityType.PHONE,
        canonical_name="+919900000101",
        phone_number="+919900000101",
    )
    assert phone.phone_number == "+919900000101"

    vehicle = VehicleEntity(
        entity_id="urn:entity:vehicle:001",
        entity_type=EntityType.VEHICLE,
        canonical_name="DL-01-AB-1234",
        registration_number="DL-01-AB-1234",
    )
    assert vehicle.registration_number == "DL-01-AB-1234"


def test_resolution_and_confidence_score_range_validation():
    """Test confidence and similarity score bounds [0.0, 1.0]."""
    cand = ResolutionCandidate(
        candidate_id="urn:res:cand:001",
        entity_id_a="urn:entity:person:001",
        entity_id_b="urn:entity:person:002",
        similarity_score=0.85,
        heuristic_name="Name_Similarity",
        status=ResolutionStatus.POSSIBLE_MATCH,
        confidence=0.9,
        justification="High name similarity",
    )
    assert cand.confidence == 0.9

    # Out of range similarity score (> 1.0)
    with pytest.raises(ValidationError):
        ResolutionCandidate(
            candidate_id="urn:res:cand:001",
            entity_id_a="urn:entity:person:001",
            entity_id_b="urn:entity:person:002",
            similarity_score=1.5,
            heuristic_name="Invalid",
            status=ResolutionStatus.POSSIBLE_MATCH,
            confidence=0.5,
            justification="Invalid score",
        )

    # Out of range confidence score (< 0.0)
    with pytest.raises(ValidationError):
        Relationship(
            relationship_id="urn:rel:001",
            source_entity_id="urn:entity:person:001",
            target_entity_id="urn:entity:phone:001",
            relationship_type=RelationshipType.ASSOCIATED_WITH,
            origin=RelationshipOrigin.EXTRACTED,
            confidence=-0.1,
        )


def test_evidence_and_finding_traceability_schemas():
    """Test evidence provenance and investigative finding schemas."""
    evidence = EvidenceProvenance(
        evidence_id="urn:ev:001",
        source_record_id="urn:source:cdr:001",
        source_type="CALL_DETAIL_RECORD",
        document_name="cdr.csv",
        raw_snippet="RAW SNIPPET",
        extractor_name="RegexExtractor",
    )
    assert evidence.evidence_id == "urn:ev:001"

    finding = InvestigativeFinding(
        finding_id="urn:finding:001",
        title="Test Finding Title",
        summary="Test explainable summary",
        entity_ids=["urn:entity:person:001"],
        relationship_ids=["urn:rel:001"],
        signal_ids=["urn:signal:001"],
        evidence_ids=["urn:ev:001"],
        confidence=0.95,
        caveats=["Synthetic test caveat"],
    )
    assert finding.confidence == 0.95
    assert len(finding.caveats) == 1
