"""Unit Tests for Relationship Pre-Aggregation Engine.

Verifies:
1. Multiple observations with same relationship_id aggregate into exactly one native edge.
2. Missing timestamp_context -> first_seen and last_seen remain None.
3. Partial timestamps -> actual timestamps used; interaction_count matches count.
4. Multiple timestamps -> correct min/max calculations.
5. interaction_count equals exact contributing observations count.
6. evidence_ids deduplication.
7. Deterministic numeric attribute aggregation (sum, min, max, count).
8. Deterministic nonnumeric attribute preservation.
9. Unsupported relationship types raise ValueError.
10. All 4 approved Phase-2 relationship types are accepted.
"""

import json
from datetime import datetime, timezone
import pytest

from app.schemas.relationship import (
    Relationship,
    RelationshipType,
    RelationshipOrigin,
)
from app.graph.pre_aggregation import (
    AggregatedRelationship,
    pre_aggregate_relationships,
    APPROVED_RELATIONSHIP_TYPES,
)


def _make_rel(
    rel_id: str = "urn:rel:001",
    src: str = "urn:entity:person:001",
    tgt: str = "urn:entity:phone:001",
    rel_type: RelationshipType = RelationshipType.COMMUNICATED_WITH,
    origin: RelationshipOrigin = RelationshipOrigin.EXTRACTED,
    confidence: float = 1.0,
    ts: datetime | None = None,
    attrs: dict | None = None,
    evidence: list[str] | None = None,
) -> Relationship:
    return Relationship(
        relationship_id=rel_id,
        source_entity_id=src,
        target_entity_id=tgt,
        relationship_type=rel_type,
        origin=origin,
        confidence=confidence,
        timestamp_context=ts,
        attributes=attrs or {},
        evidence_ids=evidence or [],
    )


def test_same_relationship_id_single_aggregate():
    """Verify that multiple observations with the same relationship_id yield one aggregate."""
    dt1 = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    dt2 = datetime(2026, 8, 10, 2, 0, 0, tzinfo=timezone.utc)

    r1 = _make_rel(rel_id="urn:rel:cdr:01", ts=dt1, evidence=["ev:01"])
    r2 = _make_rel(rel_id="urn:rel:cdr:01", ts=dt2, evidence=["ev:02"])

    aggregates = pre_aggregate_relationships([r1, r2])
    assert len(aggregates) == 1
    agg = aggregates[0]
    assert agg.relationship_id == "urn:rel:cdr:01"
    assert agg.interaction_count == 2
    assert agg.evidence_ids == ["ev:01", "ev:02"]


def test_missing_timestamps_result_in_null():
    """Verify that missing timestamp_context results in None (Neo4j null) with no fabrication."""
    r1 = _make_rel(rel_id="urn:rel:cdr:01", ts=None)
    r2 = _make_rel(rel_id="urn:rel:cdr:01", ts=None)

    aggregates = pre_aggregate_relationships([r1, r2])
    assert len(aggregates) == 1
    agg = aggregates[0]
    assert agg.first_seen is None
    assert agg.last_seen is None
    assert agg.interaction_count == 2


def test_partial_timestamps_actual_only():
    """Verify that when one timestamp is present and one is None, only actual timestamp is used."""
    dt1 = datetime(2026, 8, 10, 1, 15, 0, tzinfo=timezone.utc)
    r1 = _make_rel(rel_id="urn:rel:cdr:01", ts=dt1)
    r2 = _make_rel(rel_id="urn:rel:cdr:01", ts=None)

    aggregates = pre_aggregate_relationships([r1, r2])
    assert len(aggregates) == 1
    agg = aggregates[0]
    assert agg.first_seen == dt1
    assert agg.last_seen == dt1
    assert agg.interaction_count == 2


def test_first_last_seen_min_max():
    """Verify that first_seen and last_seen correctly take min and max of actual timestamps."""
    t_min = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    t_mid = datetime(2026, 8, 10, 3, 0, 0, tzinfo=timezone.utc)
    t_max = datetime(2026, 8, 10, 5, 0, 0, tzinfo=timezone.utc)

    # Supply out of chronological order
    r1 = _make_rel(rel_id="urn:rel:cdr:01", ts=t_mid)
    r2 = _make_rel(rel_id="urn:rel:cdr:01", ts=t_max)
    r3 = _make_rel(rel_id="urn:rel:cdr:01", ts=t_min)

    aggregates = pre_aggregate_relationships([r1, r2, r3])
    assert len(aggregates) == 1
    agg = aggregates[0]
    assert agg.first_seen == t_min
    assert agg.last_seen == t_max
    assert agg.interaction_count == 3


def test_interaction_count_counts_every_observation():
    """Verify that interaction_count accurately reflects all contributing observations."""
    dt = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    rels = [
        _make_rel(rel_id="urn:rel:01", ts=dt),
        _make_rel(rel_id="urn:rel:01", ts=None),
        _make_rel(rel_id="urn:rel:01", ts=None),
        _make_rel(rel_id="urn:rel:01", ts=dt),
    ]
    aggregates = pre_aggregate_relationships(rels)
    assert len(aggregates) == 1
    assert aggregates[0].interaction_count == 4


def test_evidence_ids_deduplication():
    """Verify evidence_ids are complete, deterministically ordered, and deduplicated."""
    r1 = _make_rel(rel_id="urn:rel:01", evidence=["ev:02", "ev:01"])
    r2 = _make_rel(rel_id="urn:rel:01", evidence=["ev:03", "ev:01"])

    aggregates = pre_aggregate_relationships([r1, r2])
    assert len(aggregates) == 1
    assert aggregates[0].evidence_ids == ["ev:01", "ev:02", "ev:03"]


def test_numeric_attribute_aggregation():
    """Verify that numeric attributes safely aggregate sum/min/max/count deterministically."""
    r1 = _make_rel(
        rel_id="urn:rel:01",
        rel_type=RelationshipType.COMMUNICATED_WITH,
        attrs={"call_duration_sec": 120},
    )
    r2 = _make_rel(
        rel_id="urn:rel:01",
        rel_type=RelationshipType.COMMUNICATED_WITH,
        attrs={"call_duration_sec": 480},
    )

    aggregates = pre_aggregate_relationships([r1, r2])
    agg = aggregates[0]
    attrs = json.loads(agg.attributes_json)

    assert "call_duration_sec" in attrs
    call_stats = attrs["call_duration_sec"]
    assert call_stats["sum"] == 600
    assert call_stats["min"] == 120
    assert call_stats["max"] == 480
    assert call_stats["count"] == 2


def test_nonnumeric_attribute_preservation():
    """Verify that categorical/string attributes are preserved without data loss."""
    r1 = _make_rel(
        rel_id="urn:rel:bank:01",
        src="urn:entity:account:01",
        tgt="urn:entity:account:02",
        rel_type=RelationshipType.TRANSACTED_WITH,
        attrs={"amount": 100000.0, "currency": "INR"},
    )
    r2 = _make_rel(
        rel_id="urn:rel:bank:01",
        src="urn:entity:account:01",
        tgt="urn:entity:account:02",
        rel_type=RelationshipType.TRANSACTED_WITH,
        attrs={"amount": 50000.0, "currency": "INR"},
    )

    aggregates = pre_aggregate_relationships([r1, r2])
    attrs = json.loads(aggregates[0].attributes_json)
    assert attrs["currency"] == "INR"
    assert attrs["amount"]["sum"] == 150000.0
    assert attrs["amount"]["min"] == 50000.0
    assert attrs["amount"]["max"] == 100000.0


def test_unsupported_relationship_type_rejected():
    """Verify that relationship types outside the approved Phase-2 set raise ValueError."""
    unsupported_types = [
        RelationshipType.MEMBER_OF,
        RelationshipType.LOCATED_AT,
        RelationshipType.CO_OCCURRED_WITH,
    ]
    for utype in unsupported_types:
        rel = _make_rel(rel_id="urn:rel:unsupported", rel_type=utype)
        with pytest.raises(ValueError, match="Unsupported relationship type"):
            pre_aggregate_relationships([rel])


def test_all_four_approved_relationship_types_accepted():
    """Verify that all four approved Phase-2 relationship types are accepted."""
    approved = [
        (RelationshipType.COMMUNICATED_WITH, "urn:rel:c1"),
        (RelationshipType.OWNED_BY, "urn:rel:o1"),
        (RelationshipType.ASSOCIATED_WITH, "urn:rel:a1"),
        (RelationshipType.TRANSACTED_WITH, "urn:rel:t1"),
    ]
    rels = [_make_rel(rel_id=rid, rel_type=rtype) for rtype, rid in approved]
    aggregates = pre_aggregate_relationships(rels)
    assert len(aggregates) == 4
    output_types = {agg.relationship_type for agg in aggregates}
    assert output_types == {
        "COMMUNICATED_WITH",
        "OWNED_BY",
        "ASSOCIATED_WITH",
        "TRANSACTED_WITH",
    }


def test_endpoint_inconsistency_raises_error():
    """Verify that different endpoints for the same relationship_id raises ValueError."""
    r1 = _make_rel(rel_id="urn:rel:dup", src="urn:entity:person:01", tgt="urn:entity:person:02")
    r2 = _make_rel(rel_id="urn:rel:dup", src="urn:entity:person:01", tgt="urn:entity:person:99")

    with pytest.raises(ValueError, match="Inconsistent endpoints"):
        pre_aggregate_relationships([r1, r2])
