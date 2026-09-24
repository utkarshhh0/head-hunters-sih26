"""Unit Tests for Phase 4A Analytical Domain Contracts."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.schemas.analytics import (
    TimeWindow,
    StructuralSignalType,
    TemporalSignalType,
    AnalyticalMetric,
    StructuralSignal,
    TemporalSignal,
    CommunityResult,
    TemporalSummary,
)
from app.schemas.finding import SignalType, AnalyticalSignal


def test_time_window_validation():
    """Validates chronological order and bounds on TimeWindow."""
    t0 = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 10, 2, 0, 0, tzinfo=timezone.utc)

    # Valid window
    w = TimeWindow(start_time=t0, end_time=t1)
    assert w.start_time == t0
    assert w.end_time == t1

    # Single bound or open-ended
    w_start_only = TimeWindow(start_time=t0)
    assert w_start_only.start_time == t0
    assert w_start_only.end_time is None

    w_empty = TimeWindow()
    assert w_empty.start_time is None
    assert w_empty.end_time is None

    # Invalid window: start > end
    with pytest.raises(ValidationError, match="start_time cannot be after end_time"):
        TimeWindow(start_time=t1, end_time=t0)


def test_analytical_metric_contract():
    """Validates AnalyticalMetric structural contract, extra='forbid', and metadata."""
    metric = AnalyticalMetric(
        metric_name="degree_centrality",
        entity_ids=["urn:entity:person:001"],
        relationship_ids=["urn:rel:comm:001", "urn:rel:assoc:001"],
        evidence_ids=["urn:ev:cdr:001"],
        value={"in_degree": 1, "out_degree": 2, "total_degree": 3, "connection_count": 2},
        method="degree_centrality_counter",
        explanation="Entity has 3 relationships connecting to 2 distinct entities.",
        limitations=["Restricted to active graph boundary.", "Unrecorded interactions not reflected."],
        time_window=TimeWindow(
            start_time=datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 8, 10, 3, 0, 0, tzinfo=timezone.utc),
        ),
    )

    assert metric.metric_name == "degree_centrality"
    assert len(metric.entity_ids) == 1
    assert len(metric.relationship_ids) == 2
    assert len(metric.evidence_ids) == 1
    assert metric.value["total_degree"] == 3
    assert len(metric.limitations) == 2
    assert metric.time_window is not None

    # Extra attributes must be forbidden
    with pytest.raises(ValidationError):
        AnalyticalMetric(
            metric_name="test",
            value=1.0,
            method="test_method",
            explanation="test",
            arbitrary_field="invalid",
        )


def test_structural_signal_and_phase1_compatibility():
    """Validates StructuralSignal contract and backward compatibility with Phase-1 AnalyticalSignal."""
    sig = StructuralSignal(
        signal_id="urn:sig:struct:bridge:001",
        signal_type=StructuralSignalType.BRIDGE_CANDIDATE,
        entity_ids=["urn:entity:person:001"],
        relationship_ids=["urn:rel:comm:001", "urn:rel:assoc:001"],
        evidence_ids=["urn:ev:cdr:001", "urn:ev:toll:001"],
        metric_value=0.75,
        method="brandes_betweenness_centrality",
        explanation="Entity sits on 75% of shortest paths between disparate clusters.",
        limitations=["Subject to boundary effects of current graph slice."],
        time_window=None,
    )

    assert sig.signal_type == StructuralSignalType.BRIDGE_CANDIDATE
    assert sig.metric_value == 0.75
    assert len(sig.evidence_ids) == 2

    # Verify Phase-1 conversion
    p1_sig = sig.to_phase1_signal()
    assert isinstance(p1_sig, AnalyticalSignal)
    assert p1_sig.signal_id == sig.signal_id
    assert p1_sig.signal_type == SignalType.BRIDGE_ACTOR
    assert p1_sig.metric_value == 0.75
    assert p1_sig.rule_description == sig.explanation


def test_temporal_signal_and_phase1_compatibility():
    """Validates TemporalSignal contract and conversion to Phase-1 AnalyticalSignal."""
    t0 = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 10, 1, 30, 0, tzinfo=timezone.utc)

    sig = TemporalSignal(
        signal_id="urn:sig:temp:burst:001",
        signal_type=TemporalSignalType.BURST_COMMUNICATION_WINDOW,
        entity_ids=["urn:entity:phone:001", "urn:entity:phone:002"],
        relationship_ids=["urn:rel:comm:001"],
        evidence_ids=["urn:ev:cdr:001"],
        metric_value=12.0,  # 12 calls/hour
        method="temporal_span_concentration",
        explanation="6 calls exchanged within 30 minutes (rate: 12.00 interactions/hr).",
        limitations=["Only evaluated over edges with explicit timestamps."],
        time_window=TimeWindow(start_time=t0, end_time=t1),
    )

    assert sig.signal_type == TemporalSignalType.BURST_COMMUNICATION_WINDOW
    assert sig.metric_value == 12.0
    assert sig.time_window.start_time == t0

    # Verify Phase-1 conversion
    p1_sig = sig.to_phase1_signal()
    assert isinstance(p1_sig, AnalyticalSignal)
    assert p1_sig.signal_id == sig.signal_id
    assert p1_sig.signal_type == SignalType.BURST_COMMUNICATION_WINDOW
    assert p1_sig.metric_value == 12.0


def test_community_result_contract():
    """Validates CommunityResult structural schema."""
    comm = CommunityResult(
        community_id="urn:comm:001",
        entity_ids=["urn:entity:person:001", "urn:entity:phone:001", "urn:entity:vehicle:001"],
        internal_relationship_ids=["urn:rel:assoc:001", "urn:rel:owned:001"],
        external_relationship_ids=["urn:rel:comm:001"],
        evidence_ids=["urn:ev:cdr:001", "urn:ev:toll:001"],
        density=0.667,
        member_count=3,
        explanation="Cohesive cell of 3 entities with 2 internal relationships.",
        limitations=["Derived via deterministic label propagation."],
    )

    assert comm.member_count == 3
    assert comm.density == 0.667
    assert len(comm.internal_relationship_ids) == 2
    assert len(comm.external_relationship_ids) == 1


def test_temporal_summary_contract():
    """Validates TemporalSummary schema preserving undated edge counts without date fabrication."""
    t0 = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 10, 4, 0, 0, tzinfo=timezone.utc)

    summary = TemporalSummary(
        entity_id="urn:entity:person:001",
        first_seen=t0,
        last_seen=t1,
        active_span_seconds=10800.0,
        total_interactions=15,
        dated_relationship_count=3,
        undated_relationship_count=1,
        relationship_ids=["r1", "r2", "r3", "r4"],
        evidence_ids=["ev1", "ev2"],
        explanation="Activity observed across 3 dated relationships spanning 3.0 hours, with 1 undated relationship.",
        limitations=["1 undated relationship excluded from span duration."],
    )

    assert summary.active_span_seconds == 10800.0
    assert summary.undated_relationship_count == 1
    assert summary.total_interactions == 15
    assert len(summary.relationship_ids) == 4
