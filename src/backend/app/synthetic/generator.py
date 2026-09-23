"""Deterministic Synthetic Data Generator for Operation Hawkeye Scenario."""

import random
from datetime import datetime
from typing import Dict, List, Any
from faker import Faker

from app.schemas.record import SourceRecord, NormalizedRecord
from app.schemas.entity import (
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


def generate_operation_hawkeye(seed: int = 42) -> Dict[str, Any]:
    """Generates the synthetic 'OPERATION HAWKEYE' multi-source investigative dataset.

    This function is completely deterministic when run with the default seed.
    No real personal data, live government feeds, or external APIs are used.
    """
    random.seed(seed)
    fake = Faker()
    Faker.seed(seed)

    base_time = datetime(2026, 8, 10, 1, 0, 0)
    meta_synthetic = {
        "is_synthetic": True,
        "scenario": "OPERATION_HAWKEYE",
        "generated_by": "HeadHunters_SyntheticGenerator",
        "data_classification": "CONTROLLED_SYNTHETIC_TEST_FIXTURE",
    }

    # -------------------------------------------------------------------------
    # 1. SOURCE RECORDS (5 Heterogeneous Source Types)
    # -------------------------------------------------------------------------
    sources: List[SourceRecord] = [
        SourceRecord(
            source_id="urn:source:cdr:001",
            source_type="CALL_DETAIL_RECORD",
            document_name="telecom_cdr_delhi_circle_20260810.csv",
            raw_content="CALL,2026-08-10T01:15:00Z,+91-9900000101,+91-9900000102,480s,TOWER_DELHI_NORTH",
            metadata=meta_synthetic,
            ingested_at=base_time,
        ),
        SourceRecord(
            source_id="urn:source:toll:002",
            source_type="VEHICLE_TOLL_LOG",
            document_name="highway_nh48_toll_pass_20260810.json",
            raw_content='{"timestamp":"2026-08-10T02:30:00Z","reg":"DL-01-AB-1234","toll_id":"TOLL_NH48_KM42","owner":"Aarav Sharma"}',
            metadata=meta_synthetic,
            ingested_at=base_time,
        ),
        SourceRecord(
            source_id="urn:source:fir:003",
            source_type="FIR_REPORT",
            document_name="jaipur_police_fir_882_2026.txt",
            raw_content="FIR #882/2026: Suspect alias 'V. Singh' sighted driving black sedan reg DL-01-AB-1234 near illegal warehouse.",
            metadata=meta_synthetic,
            ingested_at=base_time,
        ),
        SourceRecord(
            source_id="urn:source:bank:004",
            source_type="BANK_TRANSACTION",
            document_name="apex_logistics_bank_statement_202608.csv",
            raw_content="TXN,2026-08-10T04:00:00Z,ACC-112233,ACC-998877,450000.00,INR,REMARKS:APEX_SUPPLY",
            metadata=meta_synthetic,
            ingested_at=base_time,
        ),
        SourceRecord(
            source_id="urn:source:hotel:005",
            source_type="HOTEL_CHECKIN",
            document_name="mumbai_grand_hotel_registry_20260810.json",
            raw_content='{"checkin":"2026-08-10T06:00:00Z","guest":"Vikram Singh","phone":"+91-9900000101","national_id":"IND-98765432","vehicle":"DL-01-AB-1234"}',
            metadata=meta_synthetic,
            ingested_at=base_time,
        ),
    ]

    # -------------------------------------------------------------------------
    # 2. NORMALIZED RECORDS
    # -------------------------------------------------------------------------
    normalized: List[NormalizedRecord] = [
        NormalizedRecord(
            record_id="urn:norm:001",
            source_id="urn:source:cdr:001",
            canonical_text="CALL FROM +91-9900000101 TO +91-9900000102 DURATION 480S",
            extracted_fields={"caller": "+91-9900000101", "receiver": "+91-9900000102", "duration_sec": 480},
            timestamp_context=datetime(2026, 8, 10, 1, 15, 0),
            normalized_at=base_time,
        ),
        NormalizedRecord(
            record_id="urn:norm:002",
            source_id="urn:source:toll:002",
            canonical_text="VEHICLE DL-01-AB-1234 PASSED TOLL_NH48_KM42 OWNER AARAV SHARMA",
            extracted_fields={"vehicle_reg": "DL-01-AB-1234", "owner_name": "Aarav Sharma", "toll_booth": "TOLL_NH48_KM42"},
            timestamp_context=datetime(2026, 8, 10, 2, 30, 0),
            normalized_at=base_time,
        ),
        NormalizedRecord(
            record_id="urn:norm:003",
            source_id="urn:source:fir:003",
            canonical_text="INCIDENT FIR SUSPECT V. SINGH VEHICLE DL-01-AB-1234 LOCATION JAIPUR WAREHOUSE",
            extracted_fields={"suspect_alias": "V. Singh", "vehicle_reg": "DL-01-AB-1234", "location": "Jaipur Warehouse"},
            timestamp_context=datetime(2026, 8, 10, 3, 0, 0),
            normalized_at=base_time,
        ),
        NormalizedRecord(
            record_id="urn:norm:004",
            source_id="urn:source:bank:004",
            canonical_text="TRANSFER ACC-112233 TO ACC-998877 AMOUNT 450000 INR REMARKS APEX_SUPPLY",
            extracted_fields={"from_acc": "ACC-112233", "to_acc": "ACC-998877", "amount": 450000.0, "currency": "INR"},
            timestamp_context=datetime(2026, 8, 10, 4, 0, 0),
            normalized_at=base_time,
        ),
        NormalizedRecord(
            record_id="urn:norm:005",
            source_id="urn:source:hotel:005",
            canonical_text="CHECKIN GUEST VIKRAM SINGH PHONE +91-9900000101 ID IND-98765432 VEHICLE DL-01-AB-1234",
            extracted_fields={
                "guest_name": "Vikram Singh",
                "phone": "+91-9900000101",
                "national_id": "IND-98765432",
                "vehicle_reg": "DL-01-AB-1234",
            },
            timestamp_context=datetime(2026, 8, 10, 6, 0, 0),
            normalized_at=base_time,
        ),
    ]

    # -------------------------------------------------------------------------
    # 3. ENTITIES
    # -------------------------------------------------------------------------
    person_vikram = PersonEntity(
        entity_id="urn:entity:person:vikram_singh",
        entity_type=EntityType.PERSON,
        canonical_name="Vikram Singh",
        aliases=["V. Singh", "Vikram"],
        attributes={"risk_profile": "SUSPECTED_RING_OPERATOR"},
        source_record_ids=["urn:source:hotel:005", "urn:source:cdr:001", "urn:source:fir:003"],
        full_name="Vikram Singh",
        national_id="IND-98765432",
        gender="MALE",
        created_at=base_time,
        updated_at=base_time,
    )

    person_aarav = PersonEntity(
        entity_id="urn:entity:person:aarav_sharma",
        entity_type=EntityType.PERSON,
        canonical_name="Aarav Sharma",
        aliases=["A. Sharma"],
        attributes={"risk_profile": "VEHICLE_OWNER_FINANCIER"},
        source_record_ids=["urn:source:toll:002", "urn:source:bank:004"],
        full_name="Aarav Sharma",
        national_id="IND-11223344",
        gender="MALE",
        created_at=base_time,
        updated_at=base_time,
    )

    phone_01 = PhoneEntity(
        entity_id="urn:entity:phone:9900000101",
        entity_type=EntityType.PHONE,
        canonical_name="+91-9900000101",
        aliases=[],
        attributes={"line_type": "PREPAID_BURNER"},
        source_record_ids=["urn:source:cdr:001", "urn:source:hotel:005"],
        phone_number="+91-9900000101",
        carrier="MockTelecom",
        created_at=base_time,
        updated_at=base_time,
    )

    phone_02 = PhoneEntity(
        entity_id="urn:entity:phone:9900000102",
        entity_type=EntityType.PHONE,
        canonical_name="+91-9900000102",
        aliases=[],
        attributes={"line_type": "PREPAID_BURNER"},
        source_record_ids=["urn:source:cdr:001"],
        phone_number="+91-9900000102",
        carrier="MockTelecom",
        created_at=base_time,
        updated_at=base_time,
    )

    vehicle_dl01 = VehicleEntity(
        entity_id="urn:entity:vehicle:dl01ab1234",
        entity_type=EntityType.VEHICLE,
        canonical_name="DL-01-AB-1234",
        aliases=[],
        attributes={"body_type": "SEDAN", "color": "BLACK"},
        source_record_ids=["urn:source:toll:002", "urn:source:fir:003", "urn:source:hotel:005"],
        registration_number="DL-01-AB-1234",
        make="MockMotors",
        color="BLACK",
        created_at=base_time,
        updated_at=base_time,
    )

    loc_jaipur = LocationEntity(
        entity_id="urn:entity:location:jaipur_warehouse",
        entity_type=EntityType.LOCATION,
        canonical_name="Jaipur Illegal Warehouse",
        aliases=["Jaipur Warehouse"],
        attributes={"location_risk": "HIGH"},
        source_record_ids=["urn:source:fir:003"],
        address="NH48 Industrial Area, Jaipur",
        city="Jaipur",
        state="Rajasthan",
        location_type="HIDE_OUT",
        created_at=base_time,
        updated_at=base_time,
    )

    org_apex = OrganizationEntity(
        entity_id="urn:entity:org:apex_logistics",
        entity_type=EntityType.ORGANIZATION,
        canonical_name="Apex Logistics",
        aliases=["Apex Supply"],
        attributes={"company_status": "SHELL_COMPANY_SUSPECTED"},
        source_record_ids=["urn:source:bank:004"],
        org_name="Apex Logistics Ltd",
        registration_id="REG-APEX-99",
        org_type="LOGISTICS",
        created_at=base_time,
        updated_at=base_time,
    )

    acc_112233 = AccountEntity(
        entity_id="urn:entity:account:112233",
        entity_type=EntityType.ACCOUNT,
        canonical_name="ACC-112233",
        aliases=[],
        attributes={},
        source_record_ids=["urn:source:bank:004"],
        account_number="ACC-112233",
        bank_name="National Bank",
        account_type="SAVINGS",
        created_at=base_time,
        updated_at=base_time,
    )

    acc_998877 = AccountEntity(
        entity_id="urn:entity:account:998877",
        entity_type=EntityType.ACCOUNT,
        canonical_name="ACC-998877",
        aliases=[],
        attributes={},
        source_record_ids=["urn:source:bank:004"],
        account_number="ACC-998877",
        bank_name="National Bank",
        account_type="CURRENT",
        created_at=base_time,
        updated_at=base_time,
    )

    entities: List[Any] = [
        person_vikram,
        person_aarav,
        phone_01,
        phone_02,
        vehicle_dl01,
        loc_jaipur,
        org_apex,
        acc_112233,
        acc_998877,
    ]

    # -------------------------------------------------------------------------
    # 4. ENTITY RESOLUTION CASES (HIGH_CONFIDENCE, POSSIBLE_MATCH, NO_MATCH)
    # -------------------------------------------------------------------------
    res_candidates: List[ResolutionCandidate] = [
        # Case A: HIGH_CONFIDENCE (Exact National ID + Phone match between CDR caller & Hotel guest)
        ResolutionCandidate(
            candidate_id="urn:res:cand:001_high",
            entity_id_a="urn:entity:person:vikram_singh",
            entity_id_b="urn:entity:person:vikram_singh",  # Reference same physical identity
            similarity_score=1.0,
            heuristic_name="Exact_National_ID_And_Phone_Match",
            status=ResolutionStatus.HIGH_CONFIDENCE,
            confidence=1.0,
            justification="Identical National ID (IND-98765432) and E.164 phone number (+91-9900000101) across hotel log and CDR.",
            analyst_override=True,
        ),
        # Case B: POSSIBLE_MATCH (FIR suspect 'V. Singh' vs Hotel guest 'Vikram Singh' sharing vehicle DL-01-AB-1234)
        ResolutionCandidate(
            candidate_id="urn:res:cand:002_possible",
            entity_id_a="urn:entity:person:vikram_singh",
            entity_id_b="urn:entity:person:aarav_sharma",  # Related by shared vehicle, NOT merged
            similarity_score=0.72,
            heuristic_name="Name_Similarity_And_Shared_Vehicle_Overlap",
            status=ResolutionStatus.POSSIBLE_MATCH,
            confidence=0.72,
            justification="Suspect alias 'V. Singh' drives vehicle DL-01-AB-1234 registered under Aarav Sharma. Requires manual analyst review. NOT merged.",
            analyst_override=None,  # Pending review
        ),
        # Case C: NO_MATCH (Aarav Sharma vs Vikram Singh - distinct IDs and accounts)
        ResolutionCandidate(
            candidate_id="urn:res:cand:003_no_match",
            entity_id_a="urn:entity:person:aarav_sharma",
            entity_id_b="urn:entity:person:vikram_singh",
            similarity_score=0.15,
            heuristic_name="Deterministic_National_ID_Mismatch",
            status=ResolutionStatus.NO_MATCH,
            confidence=0.95,
            justification="Distinct National IDs (IND-11223344 vs IND-98765432) and separate accounts. Maintained as separate entities.",
            analyst_override=False,
        ),
    ]

    res_decisions: List[ResolutionDecision] = [
        ResolutionDecision(
            decision_id="urn:res:dec:001_high",
            candidate_id="urn:res:cand:001_high",
            status=ResolutionStatus.HIGH_CONFIDENCE,
            merged_entity_id="urn:entity:person:vikram_singh",
            reasoning="Confirmed deterministic identity match across records.",
            decided_at=base_time,
        ),
        ResolutionDecision(
            decision_id="urn:res:dec:002_possible",
            candidate_id="urn:res:cand:002_possible",
            status=ResolutionStatus.POSSIBLE_MATCH,
            merged_entity_id=None,  # MUST NOT merge possible match
            reasoning="Flagged for investigator review; preserved as distinct entities.",
            decided_at=base_time,
        ),
        ResolutionDecision(
            decision_id="urn:res:dec:003_no_match",
            candidate_id="urn:res:cand:003_no_match",
            status=ResolutionStatus.NO_MATCH,
            merged_entity_id=None,
            reasoning="Confirmed non-matching distinct individuals.",
            decided_at=base_time,
        ),
    ]

    # -------------------------------------------------------------------------
    # 5. RELATIONSHIPS
    # -------------------------------------------------------------------------
    rel_comm = Relationship(
        relationship_id="urn:rel:001_comm",
        source_entity_id="urn:entity:phone:9900000101",
        target_entity_id="urn:entity:phone:9900000102",
        relationship_type=RelationshipType.COMMUNICATED_WITH,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=1.0,
        timestamp_context=datetime(2026, 8, 10, 1, 15, 0),
        attributes={"call_duration_sec": 480},
        evidence_ids=["urn:ev:001_cdr"],
    )

    rel_owned = Relationship(
        relationship_id="urn:rel:002_owned",
        source_entity_id="urn:entity:person:aarav_sharma",
        target_entity_id="urn:entity:vehicle:dl01ab1234",
        relationship_type=RelationshipType.OWNED_BY,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=0.95,
        timestamp_context=datetime(2026, 8, 10, 2, 30, 0),
        attributes={"registration_status": "ACTIVE"},
        evidence_ids=["urn:ev:002_toll"],
    )

    rel_assoc = Relationship(
        relationship_id="urn:rel:003_assoc",
        source_entity_id="urn:entity:person:vikram_singh",
        target_entity_id="urn:entity:vehicle:dl01ab1234",
        relationship_type=RelationshipType.ASSOCIATED_WITH,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=0.85,
        timestamp_context=datetime(2026, 8, 10, 3, 0, 0),
        attributes={"sighting_type": "FIR_SUSPECT_SIGHTING"},
        evidence_ids=["urn:ev:003_fir", "urn:ev:005_hotel"],
    )

    rel_txn = Relationship(
        relationship_id="urn:rel:004_txn",
        source_entity_id="urn:entity:account:112233",
        target_entity_id="urn:entity:account:998877",
        relationship_type=RelationshipType.TRANSACTED_WITH,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=1.0,
        timestamp_context=datetime(2026, 8, 10, 4, 0, 0),
        attributes={"amount": 450000.0, "currency": "INR"},
        evidence_ids=["urn:ev:004_bank"],
    )

    rel_inferred_colocation = Relationship(
        relationship_id="urn:rel:005_inferred",
        source_entity_id="urn:entity:person:vikram_singh",
        target_entity_id="urn:entity:person:aarav_sharma",
        relationship_type=RelationshipType.CO_OCCURRED_WITH,
        origin=RelationshipOrigin.ANALYTICALLY_INFERRED,
        confidence=0.78,
        timestamp_context=datetime(2026, 8, 10, 6, 0, 0),
        attributes={"inference_rule": "SHARED_VEHICLE_AND_FINANCIAL_BURST_CORRELATION"},
        evidence_ids=["urn:ev:002_toll", "urn:ev:003_fir", "urn:ev:004_bank"],
    )

    relationships: List[Relationship] = [
        rel_comm,
        rel_owned,
        rel_assoc,
        rel_txn,
        rel_inferred_colocation,
    ]

    # -------------------------------------------------------------------------
    # 6. EVIDENCE PROVENANCE
    # -------------------------------------------------------------------------
    evidence_items: List[EvidenceProvenance] = [
        EvidenceProvenance(
            evidence_id="urn:ev:001_cdr",
            source_record_id="urn:source:cdr:001",
            source_type="CALL_DETAIL_RECORD",
            document_name="telecom_cdr_delhi_circle_20260810.csv",
            raw_snippet="CALL,2026-08-10T01:15:00Z,+91-9900000101,+91-9900000102,480s",
            offset_start=0,
            offset_end=58,
            extractor_name="RegexCdrExtractor",
            extracted_at=base_time,
        ),
        EvidenceProvenance(
            evidence_id="urn:ev:002_toll",
            source_record_id="urn:source:toll:002",
            source_type="VEHICLE_TOLL_LOG",
            document_name="highway_nh48_toll_pass_20260810.json",
            raw_snippet='"reg":"DL-01-AB-1234","toll_id":"TOLL_NH48_KM42","owner":"Aarav Sharma"',
            offset_start=34,
            offset_end=104,
            extractor_name="JsonTollLogExtractor",
            extracted_at=base_time,
        ),
        EvidenceProvenance(
            evidence_id="urn:ev:003_fir",
            source_record_id="urn:source:fir:003",
            source_type="FIR_REPORT",
            document_name="jaipur_police_fir_882_2026.txt",
            raw_snippet="Suspect alias 'V. Singh' sighted driving black sedan reg DL-01-AB-1234",
            offset_start=14,
            offset_end=84,
            extractor_name="SpacyFirExtractor",
            extracted_at=base_time,
        ),
        EvidenceProvenance(
            evidence_id="urn:ev:004_bank",
            source_record_id="urn:source:bank:004",
            source_type="BANK_TRANSACTION",
            document_name="apex_logistics_bank_statement_202608.csv",
            raw_snippet="TXN,2026-08-10T04:00:00Z,ACC-112233,ACC-998877,450000.00,INR",
            offset_start=0,
            offset_end=59,
            extractor_name="CsvBankStatementExtractor",
            extracted_at=base_time,
        ),
        EvidenceProvenance(
            evidence_id="urn:ev:005_hotel",
            source_record_id="urn:source:hotel:005",
            source_type="HOTEL_CHECKIN",
            document_name="mumbai_grand_hotel_registry_20260810.json",
            raw_snippet='"guest":"Vikram Singh","phone":"+91-9900000101","national_id":"IND-98765432"',
            offset_start=32,
            offset_end=108,
            extractor_name="JsonHotelRegistryExtractor",
            extracted_at=base_time,
        ),
    ]

    # -------------------------------------------------------------------------
    # 7. ANALYTICAL SIGNALS
    # -------------------------------------------------------------------------
    signals: List[AnalyticalSignal] = [
        AnalyticalSignal(
            signal_id="urn:signal:001_burst",
            signal_type=SignalType.BURST_COMMUNICATION_WINDOW,
            entity_ids=["urn:entity:phone:9900000101", "urn:entity:phone:9900000102"],
            relationship_ids=["urn:rel:001_comm"],
            metric_value=480.0,
            rule_description="480-second call burst between prepaid burner phones during midnight window.",
        ),
        AnalyticalSignal(
            signal_id="urn:signal:002_financial",
            signal_type=SignalType.SHARED_FINANCIAL_ACCOUNT,
            entity_ids=["urn:entity:account:112233", "urn:entity:account:998877", "urn:entity:org:apex_logistics"],
            relationship_ids=["urn:rel:004_txn"],
            metric_value=450000.0,
            rule_description="Rapid high-value transaction (₹4,50,000) to suspected shell logistics account.",
        ),
        AnalyticalSignal(
            signal_id="urn:signal:003_colocation",
            signal_type=SignalType.CO_LOCATION_RECURRENCE,
            entity_ids=["urn:entity:person:vikram_singh", "urn:entity:person:aarav_sharma", "urn:entity:vehicle:dl01ab1234"],
            relationship_ids=["urn:rel:002_owned", "urn:rel:003_assoc", "urn:rel:005_inferred"],
            metric_value=0.78,
            rule_description="Co-location and shared vehicle usage correlation between suspect Vikram Singh and owner Aarav Sharma.",
        ),
    ]

    # -------------------------------------------------------------------------
    # 8. INVESTIGATIVE FINDING (Provenanced & Deterministic)
    # -------------------------------------------------------------------------
    finding = InvestigativeFinding(
        finding_id="urn:finding:001_hawkeye",
        title="Operation Hawkeye: Coordinated Smuggling Ring & Shared Vehicle Financial Pattern",
        summary=(
            "Deterministic analysis of 5 heterogeneous feeds revealed an illicit operational network. "
            "Suspect Vikram Singh (using burner phone +91-9900000101) was sighted near a Jaipur warehouse "
            "driving vehicle DL-01-AB-1234 registered to Aarav Sharma. Following midnight communication bursts, "
            "a rapid financial transfer of ₹4,50,000 was executed to shell firm Apex Logistics. "
            "Entity resolution identified 1 HIGH_CONFIDENCE match, 1 POSSIBLE_MATCH (flagged for review), and 1 NO_MATCH."
        ),
        entity_ids=[e.entity_id for e in entities],
        relationship_ids=[r.relationship_id for r in relationships],
        signal_ids=[s.signal_id for s in signals],
        evidence_ids=[ev.evidence_id for ev in evidence_items],
        confidence=0.88,
        caveats=[
            "TEST_ONLY_SYNTHETIC_FIXTURE: This finding is derived strictly from controlled synthetic data for Phase 1 verification.",
            "POSSIBLE_MATCH candidate (urn:res:cand:002_possible) requires explicit human analyst review prior to graph merging.",
            "No real-world PII, live intelligence, or actual police records were used.",
        ],
        created_at=base_time,
    )

    return {
        "scenario": "OPERATION_HAWKEYE",
        "sources": sources,
        "normalized": normalized,
        "entities": entities,
        "res_candidates": res_candidates,
        "res_decisions": res_decisions,
        "relationships": relationships,
        "evidence": evidence_items,
        "signals": signals,
        "finding": finding,
    }
