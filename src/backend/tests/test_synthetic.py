"""Unit Tests for Controlled Synthetic Data Generator and Provenance Traversal."""

from app.synthetic.generator import generate_operation_hawkeye
from app.schemas.relationship import ResolutionStatus


def test_operation_hawkeye_determinism():
    """Test that repeated execution with default seed produces identical datasets."""
    dataset_1 = generate_operation_hawkeye(seed=42)
    dataset_2 = generate_operation_hawkeye(seed=42)

    assert dataset_1["finding"].finding_id == dataset_2["finding"].finding_id
    assert len(dataset_1["sources"]) == len(dataset_2["sources"])
    assert dataset_1["sources"][0].raw_content == dataset_2["sources"][0].raw_content


def test_synthetic_only_status_and_metadata():
    """Test that dataset is explicitly marked synthetic with no real PII/live feeds."""
    dataset = generate_operation_hawkeye(seed=42)

    for source in dataset["sources"]:
        assert source.metadata.get("is_synthetic") is True
        assert source.metadata.get("scenario") == "OPERATION_HAWKEYE"
        assert source.metadata.get("data_classification") == "CONTROLLED_SYNTHETIC_TEST_FIXTURE"


def test_heterogeneous_source_coverage():
    """Test that all 5 approved heterogeneous source types are present."""
    dataset = generate_operation_hawkeye(seed=42)
    source_types = {s.source_type for s in dataset["sources"]}

    expected_types = {
        "CALL_DETAIL_RECORD",
        "VEHICLE_TOLL_LOG",
        "FIR_REPORT",
        "BANK_TRANSACTION",
        "HOTEL_CHECKIN",
    }
    assert expected_types.issubset(source_types)


def test_entity_resolution_three_states():
    """Test that HIGH_CONFIDENCE, POSSIBLE_MATCH, and NO_MATCH resolution cases exist and possible matches are NOT merged."""
    dataset = generate_operation_hawkeye(seed=42)
    candidates = dataset["res_candidates"]
    decisions = dataset["res_decisions"]

    statuses = {c.status for c in candidates}
    assert ResolutionStatus.HIGH_CONFIDENCE in statuses
    assert ResolutionStatus.POSSIBLE_MATCH in statuses
    assert ResolutionStatus.NO_MATCH in statuses

    # Verify POSSIBLE_MATCH decision does NOT merge entities
    possible_decision = next(d for d in decisions if d.status == ResolutionStatus.POSSIBLE_MATCH)
    assert possible_decision.merged_entity_id is None

    # Verify HIGH_CONFIDENCE decision DOES specify merged entity
    high_decision = next(d for d in decisions if d.status == ResolutionStatus.HIGH_CONFIDENCE)
    assert high_decision.merged_entity_id is not None


def test_complete_end_to_end_provenance_traversal():
    """Test full forward and backward linkability:

    FINDING -> SIGNAL -> RELATIONSHIP / ENTITY -> EVIDENCE -> SOURCE RECORD
    """
    dataset = generate_operation_hawkeye(seed=42)

    finding = dataset["finding"]
    signals_dict = {s.signal_id: s for s in dataset["signals"]}
    relationships_dict = {r.relationship_id: r for r in dataset["relationships"]}
    entities_dict = {e.entity_id: e for e in dataset["entities"]}
    evidence_dict = {ev.evidence_id: ev for ev in dataset["evidence"]}
    sources_dict = {s.source_id: s for s in dataset["sources"]}

    # 1. Finding references valid signal IDs
    assert len(finding.signal_ids) > 0
    for signal_id in finding.signal_ids:
        assert signal_id in signals_dict
        signal = signals_dict[signal_id]

        # 2. Signal references valid entity/relationship IDs
        for rel_id in signal.relationship_ids:
            assert rel_id in relationships_dict
            relationship = relationships_dict[rel_id]

            # 3. Relationship references valid source/target entity IDs
            assert relationship.source_entity_id in entities_dict
            assert relationship.target_entity_id in entities_dict

            # 4. Relationship references valid evidence provenance IDs
            assert len(relationship.evidence_ids) > 0
            for ev_id in relationship.evidence_ids:
                assert ev_id in evidence_dict
                evidence = evidence_dict[ev_id]

                # 5. Evidence references valid source record ID
                assert evidence.source_record_id in sources_dict
                source_record = sources_dict[evidence.source_record_id]
                assert source_record.raw_content is not None
                assert len(source_record.raw_content) > 0
