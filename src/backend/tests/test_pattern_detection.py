"""Unit Tests for Phase 4D Deterministic Multi-Signal Pattern Detection.

Tests:
1. Multi-signal requirement: single signals alone do NOT produce patterns; multiple signals required.
2. Direct schema validation: MultiSignalPattern rejects < 2 contributing signals.
3. Deterministic output reproducibility: repeated runs produce identical pattern IDs and properties.
4. Provenance preservation: pattern entity_ids, relationship_ids, and evidence_ids strictly match signals.
5. Neutrality: zero guilt, criminality, or mastermind inferences in explanation/title.
6. Time window: preserves actual observed timestamp boundaries without fabrication.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.schemas.analytics import (
    MultiSignalPattern,
    PatternType,
    StructuralSignal,
    StructuralSignalType,
    TemporalSignal,
    TemporalSignalType,
    TimeWindow,
)
from app.analytics.patterns import PatternDetector, PatternDetectionConfig


def test_schema_rejects_single_signal():
    """Validates that MultiSignalPattern schema strictly rejects fewer than 2 contributing signals."""
    with pytest.raises(ValidationError, match="requires at least 2 contributing signals"):
        MultiSignalPattern(
            pattern_id="urn:pattern:invalid:001",
            pattern_type=PatternType.INTERMEDIARY_HUB_BURST,
            title="Pattern Flagged for Investigation",
            entity_ids=["urn:ent:1"],
            contributing_signal_ids=["urn:sig:single:001"],  # Only 1 signal!
            contributing_signal_types=["BRIDGE_CANDIDATE"],
            relationship_ids=["r1"],
            evidence_ids=["ev1"],
            time_window=None,
            detection_method="heuristic_test",
            explanation="Invalid pattern test with single signal.",
            limitations=["Testing single signal rejection."],
        )


def test_pattern_detector_requires_multi_signals():
    """Tests that PatternDetector does NOT emit patterns for single isolated signals."""
    detector = PatternDetector()

    sig_bridge = StructuralSignal(
        signal_id="urn:sig:bridge:001",
        signal_type=StructuralSignalType.BRIDGE_CANDIDATE,
        entity_ids=["E_HUB"],
        relationship_ids=["r1", "r2"],
        evidence_ids=["ev1"],
        metric_value=0.8,
        method="brandes_betweenness_centrality",
        explanation="Entity acts as a bridge candidate.",
        limitations=["Bounded graph."],
        time_window=None,
    )
    sig_degree = StructuralSignal(
        signal_id="urn:sig:deg:001",
        signal_type=StructuralSignalType.HIGH_DEGREE_CENTRALITY,
        entity_ids=["E_OTHER"],  # Different entity!
        relationship_ids=["r3", "r4"],
        evidence_ids=["ev2"],
        metric_value=4.0,
        method="degree_counter",
        explanation="High degree entity.",
        limitations=["Bounded graph."],
        time_window=None,
    )
    t0 = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 10, 1, 15, 0, tzinfo=timezone.utc)
    sig_burst = TemporalSignal(
        signal_id="urn:sig:burst:001",
        signal_type=TemporalSignalType.BURST_COMMUNICATION_WINDOW,
        entity_ids=["E_ISOLATED_1", "E_ISOLATED_2"],  # Different entities!
        relationship_ids=["r5"],
        evidence_ids=["ev3"],
        metric_value=16.0,
        method="temporal_span_concentration",
        explanation="Burst window between isolated pair.",
        limitations=["Observed timestamps only."],
        time_window=TimeWindow(start_time=t0, end_time=t1),
    )

    # When signals are on disparate entities, no multi-signal convergence exists
    patterns = detector.evaluate_signals(
        structural_signals=[sig_bridge, sig_degree],
        temporal_signals=[sig_burst],
    )
    assert len(patterns) == 0


def test_pattern_convergence_intermediary_hub_burst():
    """Tests detection of INTERMEDIARY_HUB_BURST when structural bridge, degree, and temporal burst converge."""
    detector = PatternDetector()

    t0 = datetime(2026, 8, 10, 2, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 10, 2, 20, 0, tzinfo=timezone.utc)

    # Focal entity: E_HUB
    sig_bridge = StructuralSignal(
        signal_id="urn:sig:bridge:hub",
        signal_type=StructuralSignalType.BRIDGE_CANDIDATE,
        entity_ids=["E_HUB"],
        relationship_ids=["r_hub_left", "r_hub_right"],
        evidence_ids=["ev_bridge"],
        metric_value=0.75,
        method="brandes_betweenness_centrality",
        explanation="Entity E_HUB is a bridge candidate.",
        limitations=["Bounded network."],
        time_window=None,
    )
    sig_degree = StructuralSignal(
        signal_id="urn:sig:deg:hub",
        signal_type=StructuralSignalType.HIGH_DEGREE_CENTRALITY,
        entity_ids=["E_HUB"],
        relationship_ids=["r_hub_left", "r_hub_right", "r_hub_extra"],
        evidence_ids=["ev_deg"],
        metric_value=3.0,
        method="degree_threshold_rule",
        explanation="Entity E_HUB has high degree.",
        limitations=["Bounded network."],
        time_window=None,
    )
    sig_burst = TemporalSignal(
        signal_id="urn:sig:burst:hub_left",
        signal_type=TemporalSignalType.BURST_COMMUNICATION_WINDOW,
        entity_ids=["E_HUB", "E_LEFT"],
        relationship_ids=["r_hub_left"],
        evidence_ids=["ev_burst"],
        metric_value=24.0,  # 8 calls in 20 mins
        method="temporal_span_concentration",
        explanation="8 calls within 20 mins.",
        limitations=["Observed timestamps only."],
        time_window=TimeWindow(start_time=t0, end_time=t1),
    )

    entities = [
        {"entity_id": "E_HUB", "canonical_name": "Coordinator Node"},
        {"entity_id": "E_LEFT", "canonical_name": "Left Satellite"},
        {"entity_id": "E_RIGHT", "canonical_name": "Right Satellite"},
    ]

    patterns = detector.evaluate_signals(
        structural_signals=[sig_bridge, sig_degree],
        temporal_signals=[sig_burst],
        entities=entities,
    )

    assert len(patterns) == 1
    pat = patterns[0]

    # Contract verification
    assert pat.pattern_type == PatternType.INTERMEDIARY_HUB_BURST
    assert "Pattern Flagged for Investigation" in pat.title
    assert "Coordinator Node" in pat.title
    assert "E_HUB" in pat.entity_ids
    assert "E_LEFT" in pat.entity_ids

    # Multiple signals verified
    assert len(pat.contributing_signal_ids) == 3
    assert set(pat.contributing_signal_ids) == {
        "urn:sig:bridge:hub",
        "urn:sig:deg:hub",
        "urn:sig:burst:hub_left",
    }
    assert set(pat.contributing_signal_types) == {
        "BRIDGE_CANDIDATE",
        "HIGH_DEGREE_CENTRALITY",
        "BURST_COMMUNICATION_WINDOW",
    }

    # Provenance traceability
    assert set(pat.relationship_ids) == {"r_hub_left", "r_hub_right", "r_hub_extra"}
    assert set(pat.evidence_ids) == {"ev_bridge", "ev_deg", "ev_burst"}

    # Time window integrity (never fabricated)
    assert pat.time_window is not None
    assert pat.time_window.start_time == t0
    assert pat.time_window.end_time == t1

    # Neutral language verification: no guilt, criminality, or mastermind claims
    lower_exp = pat.explanation.lower()
    for forbidden_word in ["criminal", "guilt", "mastermind", "perpetrator", "culprit", "risk score"]:
        assert forbidden_word not in lower_exp


def test_deterministic_pattern_generation():
    """Verifies that pattern detection is 100% deterministic across multiple invocations."""
    detector = PatternDetector()
    t0 = datetime(2026, 8, 10, 2, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 10, 2, 10, 0, tzinfo=timezone.utc)

    sig_degree = StructuralSignal(
        signal_id="urn:sig:degree:1",
        signal_type=StructuralSignalType.HIGH_DEGREE_CENTRALITY,
        entity_ids=["A"],
        relationship_ids=["r1", "r2"],
        evidence_ids=["ev1", "ev2"],
        metric_value=3.0,
        method="degree",
        explanation="high degree",
        limitations=[],
    )
    sig_bridge = StructuralSignal(
        signal_id="urn:sig:bridge:1",
        signal_type=StructuralSignalType.BRIDGE_CANDIDATE,
        entity_ids=["A"],
        relationship_ids=["r1"],
        evidence_ids=["ev1"],
        metric_value=0.5,
        method="brandes",
        explanation="bridge",
        limitations=[],
    )
    sig_burst = TemporalSignal(
        signal_id="urn:sig:burst:1",
        signal_type=TemporalSignalType.BURST_COMMUNICATION_WINDOW,
        entity_ids=["A", "B"],
        relationship_ids=["r1"],
        evidence_ids=["ev1"],
        metric_value=12.0,
        method="concentration",
        explanation="burst",
        limitations=[],
        time_window=TimeWindow(start_time=t0, end_time=t1),
    )

    run1 = detector.evaluate_signals(
        [sig_bridge, sig_degree],
        [sig_burst],
    )
    run2 = detector.evaluate_signals(
        [sig_bridge, sig_degree],
        [sig_burst],
    )

    assert len(run1) == len(run2) == 1
    p1 = run1[0]
    p2 = run2[0]

    assert p1.pattern_id == p2.pattern_id
    assert p1.title == p2.title
    assert p1.entity_ids == p2.entity_ids
    assert p1.contributing_signal_ids == p2.contributing_signal_ids
    assert p1.evidence_ids == p2.evidence_ids
    assert p1.time_window == p2.time_window
