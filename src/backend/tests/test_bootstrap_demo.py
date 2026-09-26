"""Unit tests for deterministic demo bootstrap construction."""

from scripts.bootstrap_demo import (
    CENTRAL_PHONE,
    PERIPHERAL_PHONES,
    build_bootstrap_pipeline_result,
)
from app.schemas.entity import EntityType
from app.schemas.relationship import RelationshipType, RelationshipOrigin
from app.graph.pre_aggregation import pre_aggregate_relationships


def test_bootstrap_pipeline_result_construction():
    """Verifies that the demo bootstrap constructs a strictly compliant PipelineResult."""
    result = build_bootstrap_pipeline_result()

    # 1. Source records
    assert len(result.source_records) == 23
    source_types = {src.source_type for src in result.source_records}
    expected_source_types = {
        "HOTEL_CHECKIN",
        "VEHICLE_TOLL_LOG",
        "FIR_REPORT",
        "BANK_TRANSACTION",
        "CALL_DETAIL_RECORD",
    }
    assert expected_source_types.issubset(source_types)

    for src in result.source_records:
        assert src.metadata.get("is_synthetic") is True
        assert src.metadata.get("timestamp_context") is not None
        assert src.ingested_at is not None

    # 2. Evidence items
    assert len(result.evidence_items) == 35
    for ev in result.evidence_items:
        assert ev.source_type in expected_source_types
        assert ev.offset_start is not None
        assert ev.offset_end is not None

    # 3. Canonical entities across all 6 supported types
    assert len(result.extracted_entities) > 0
    entity_types = {e.entity_type for e in result.extracted_entities}
    expected_entity_types = {
        EntityType.PERSON,
        EntityType.PHONE,
        EntityType.VEHICLE,
        EntityType.LOCATION,
        EntityType.ORGANIZATION,
        EntityType.ACCOUNT,
    }
    assert expected_entity_types.issubset(entity_types)

    canonical_names = {e.canonical_name for e in result.extracted_entities}
    assert CENTRAL_PHONE in canonical_names
    for p in PERIPHERAL_PHONES:
        assert p in canonical_names
    assert "Vikram Singh" in canonical_names
    assert "DL-01-AB-1234" in canonical_names
    assert "ACC-100001" in canonical_names
    assert "Apex Logistics" in canonical_names
    assert "Toll Plaza NH48 KM42" in canonical_names

    # 4. Extracted relationships across all 4 approved types
    assert len(result.relationships) == 23
    rel_types = {rel.relationship_type for rel in result.relationships}
    expected_rel_types = {
        RelationshipType.COMMUNICATED_WITH,
        RelationshipType.OWNED_BY,
        RelationshipType.ASSOCIATED_WITH,
        RelationshipType.TRANSACTED_WITH,
    }
    assert expected_rel_types == rel_types

    for rel in result.relationships:
        assert rel.origin == RelationshipOrigin.EXTRACTED
        assert rel.confidence > 0.0
        assert rel.timestamp_context is not None
        assert len(rel.evidence_ids) > 0

    # 5. Pre-aggregation evaluation
    aggregates = pre_aggregate_relationships(result.relationships)
    assert len(aggregates) == 16

    # Verify central phone degree in aggregates (5 distinct neighbors: 4 phones + 1 person)
    central_urn = None
    for e in result.extracted_entities:
        if getattr(e, "phone_number", e.canonical_name) == CENTRAL_PHONE:
            central_urn = e.entity_id
            break
    assert central_urn is not None

    central_incident = [
        agg for agg in aggregates
        if agg.source_entity_id == central_urn or agg.target_entity_id == central_urn
    ]
    assert len(central_incident) == 5

    # Verify repeated observations on central relationships (calls)
    max_interactions = max(agg.interaction_count for agg in central_incident)
    assert max_interactions == 3
    assert any(agg.interaction_count > 1 for agg in central_incident)

    # Verify repeated observations on financial transactions
    txn_aggregates = [
        agg for agg in aggregates
        if agg.relationship_type == RelationshipType.TRANSACTED_WITH.value
    ]
    assert len(txn_aggregates) == 1
    assert txn_aggregates[0].interaction_count == 2

    # Verify temporal bounds and evidence
    for agg in aggregates:
        assert agg.first_seen is not None
        assert agg.last_seen is not None
        assert agg.first_seen <= agg.last_seen
        assert len(agg.evidence_ids) >= 1


def test_bootstrap_determinism():
    """Verifies that bootstrap construction produces 100% deterministic outputs across runs."""
    run1 = build_bootstrap_pipeline_result()
    run2 = build_bootstrap_pipeline_result()

    assert [s.source_id for s in run1.source_records] == [s.source_id for s in run2.source_records]
    assert [e.evidence_id for e in run1.evidence_items] == [e.evidence_id for e in run2.evidence_items]
    assert [ent.entity_id for ent in run1.extracted_entities] == [ent.entity_id for ent in run2.extracted_entities]
    assert [r.relationship_id for r in run1.relationships] == [r.relationship_id for r in run2.relationships]
