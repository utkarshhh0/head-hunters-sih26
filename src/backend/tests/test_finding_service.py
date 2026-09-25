"""Unit Tests for Finding Synthesizer and Domain Contracts (Phase 5).

Verifies:
- Both Phase-4 pattern types (INTERMEDIARY_HUB_BURST, DENSE_COMMUNITY_BURST) synthesize valid findings
- Deterministic finding generation (reproducible IDs, titles, summaries)
- Backward-compatible InvestigativeFinding construction
- Entity, relationship, signal, and evidence propagation
- Time-window preservation and zero timestamp fabrication
- Neutral finding language (no claims of guilt, illicit intent, or mastermind status)
- Nominal confidence handling (no arbitrary 0.85/0.75 scores or risk scores)
"""

from datetime import datetime, timezone
import pytest

from app.schemas.finding import FindingStatus, InvestigativeFinding, SignalType
from app.schemas.analytics import (
    MultiSignalPattern,
    PatternType,
    TimeWindow,
)
from app.services.finding_service import FindingSynthesizer


@pytest.fixture
def synthesizer() -> FindingSynthesizer:
    return FindingSynthesizer()


@pytest.fixture
def hub_burst_pattern() -> MultiSignalPattern:
    return MultiSignalPattern(
        pattern_id="urn:pattern:hub_burst:test001",
        pattern_type=PatternType.INTERMEDIARY_HUB_BURST,
        title="Pattern Flagged for Investigation: Intermediary Hub with Concentrated Activity (Test Actor)",
        entity_ids=["urn:entity:person:001", "urn:entity:person:002", "urn:entity:person:003"],
        contributing_signal_ids=["urn:sig:struct:bridge:001", "urn:sig:struct:deg:001", "urn:sig:temp:burst:001"],
        contributing_signal_types=["BRIDGE_CANDIDATE", "HIGH_DEGREE_CENTRALITY", "BURST_COMMUNICATION_WINDOW"],
        relationship_ids=["urn:rel:comm:001", "urn:rel:comm:002"],
        evidence_ids=["urn:ev:001", "urn:ev:002"],
        time_window=TimeWindow(
            start_time=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        ),
        detection_method="heuristic_multi_signal_convergence:intermediary_hub_burst",
        explanation="Entity 'Test Actor' exhibits multi-signal topological and temporal convergence.",
        limitations=["Deterministic heuristic rule linking independent structural and temporal signals."],
    )


@pytest.fixture
def comm_burst_pattern() -> MultiSignalPattern:
    return MultiSignalPattern(
        pattern_id="urn:pattern:comm_burst:test002",
        pattern_type=PatternType.DENSE_COMMUNITY_BURST,
        title="Pattern Flagged for Investigation: Dense Cluster with Concentrated Activity (Size 3)",
        entity_ids=["urn:entity:person:010", "urn:entity:person:020", "urn:entity:person:030"],
        contributing_signal_ids=["urn:sig:struct:comm:001", "urn:sig:temp:burst:002"],
        contributing_signal_types=["DENSE_COMMUNITY", "BURST_COMMUNICATION_WINDOW"],
        relationship_ids=["urn:rel:comm:010", "urn:rel:comm:020"],
        evidence_ids=["urn:ev:010", "urn:ev:020"],
        time_window=TimeWindow(
            start_time=datetime(2026, 2, 1, 8, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 1, 9, 30, 0, tzinfo=timezone.utc),
        ),
        detection_method="heuristic_multi_signal_convergence:dense_community_burst",
        explanation="Cohesive operational cluster coincides with internal burst communication events.",
        limitations=["Deterministic rule joining dense community structure with internal temporal bursts."],
    )


def test_both_phase4_pattern_types_synthesize_valid_findings(
    synthesizer: FindingSynthesizer,
    hub_burst_pattern: MultiSignalPattern,
    comm_burst_pattern: MultiSignalPattern,
):
    """Verifies that both INTERMEDIARY_HUB_BURST and DENSE_COMMUNITY_BURST synthesize valid findings."""
    f1 = synthesizer.synthesize_finding(hub_burst_pattern)
    assert isinstance(f1, InvestigativeFinding)
    assert f1.finding_id.startswith("urn:finding:intermediary_hub_burst:")
    assert f1.status == FindingStatus.OPEN
    assert f1.pattern_type == "INTERMEDIARY_HUB_BURST"
    assert f1.pattern_id == hub_burst_pattern.pattern_id

    f2 = synthesizer.synthesize_finding(comm_burst_pattern)
    assert isinstance(f2, InvestigativeFinding)
    assert f2.finding_id.startswith("urn:finding:dense_community_burst:")
    assert f2.status == FindingStatus.OPEN
    assert f2.pattern_type == "DENSE_COMMUNITY_BURST"
    assert f2.pattern_id == comm_burst_pattern.pattern_id


def test_deterministic_finding_generation(
    synthesizer: FindingSynthesizer,
    hub_burst_pattern: MultiSignalPattern,
):
    """Verifies that synthesizing a finding multiple times produces 100% identical outputs."""
    f1 = synthesizer.synthesize_finding(hub_burst_pattern)
    f2 = synthesizer.synthesize_finding(hub_burst_pattern)

    assert f1.finding_id == f2.finding_id
    assert f1.title == f2.title
    assert f1.summary == f2.summary
    assert f1.entity_ids == f2.entity_ids
    assert f1.relationship_ids == f2.relationship_ids
    assert f1.signal_ids == f2.signal_ids
    assert f1.evidence_ids == f2.evidence_ids
    assert f1.caveats == f2.caveats


def test_backward_compatible_investigative_finding_construction():
    """Verifies that Phase 1 construction of InvestigativeFinding without Phase 5 arguments works unchanged."""
    finding = InvestigativeFinding(
        finding_id="urn:finding:legacy:001",
        title="Legacy Finding Title",
        summary="Legacy summary of signals",
        entity_ids=["urn:entity:person:001"],
        relationship_ids=["urn:rel:001"],
        signal_ids=["urn:sig:001"],
        evidence_ids=["urn:ev:001"],
        confidence=0.9,
        caveats=["Test caveat"],
    )

    assert finding.finding_id == "urn:finding:legacy:001"
    assert finding.confidence == 0.9
    assert finding.status == FindingStatus.OPEN  # Defaulted
    assert finding.pattern_id is None  # Defaulted
    assert finding.pattern_type is None  # Defaulted
    assert finding.time_window is None  # Defaulted
    assert finding.investigator_notes is None  # Defaulted


def test_entity_relationship_signal_evidence_propagation(
    synthesizer: FindingSynthesizer,
    hub_burst_pattern: MultiSignalPattern,
):
    """Verifies complete preservation of entities, relationships, signals, and evidence."""
    finding = synthesizer.synthesize_finding(hub_burst_pattern)

    assert finding.entity_ids == sorted(hub_burst_pattern.entity_ids)
    assert finding.relationship_ids == sorted(hub_burst_pattern.relationship_ids)
    assert finding.signal_ids == sorted(hub_burst_pattern.contributing_signal_ids)
    assert finding.evidence_ids == sorted(hub_burst_pattern.evidence_ids)


def test_time_window_preservation_and_zero_fabrication(
    synthesizer: FindingSynthesizer,
    hub_burst_pattern: MultiSignalPattern,
):
    """Verifies that the exact time window is preserved without timestamp fabrication."""
    finding = synthesizer.synthesize_finding(hub_burst_pattern)

    assert finding.time_window is not None
    assert finding.time_window.start_time == hub_burst_pattern.time_window.start_time
    assert finding.time_window.end_time == hub_burst_pattern.time_window.end_time

    # Undated pattern test: when time_window is None, finding must remain None
    undated_pattern = hub_burst_pattern.model_copy(update={"time_window": None})
    undated_finding = synthesizer.synthesize_finding(undated_pattern)
    assert undated_finding.time_window is None


def test_neutral_finding_language(
    synthesizer: FindingSynthesizer,
    hub_burst_pattern: MultiSignalPattern,
    comm_burst_pattern: MultiSignalPattern,
):
    """Verifies that findings adhere to strict neutral investigative language.

    Forbidden words: mastermind, criminal, guilty, illicit intent, conspiracy, culprit, perpetrator.
    """
    forbidden_terms = [
        "mastermind",
        "criminal",
        "guilty",
        "illicit intent",
        "conspiracy",
        "culprit",
        "perpetrator",
    ]

    for pat in [hub_burst_pattern, comm_burst_pattern]:
        finding = synthesizer.synthesize_finding(pat)
        full_text = f"{finding.title} {finding.summary} {' '.join(finding.caveats)}".lower()
        for term in forbidden_terms:
            assert term not in full_text, f"Forbidden non-neutral term '{term}' found in finding!"


def test_no_arbitrary_confidence_scoring(
    synthesizer: FindingSynthesizer,
    hub_burst_pattern: MultiSignalPattern,
    comm_burst_pattern: MultiSignalPattern,
):
    """Verifies that findings preserve confidence as nominal 1.0 without inventing arbitrary decimals."""
    f1 = synthesizer.synthesize_finding(hub_burst_pattern)
    f2 = synthesizer.synthesize_finding(comm_burst_pattern)

    # Must be nominal 1.0, not arbitrary invented values like 0.85 or 0.75
    assert f1.confidence == 1.0
    assert f2.confidence == 1.0
