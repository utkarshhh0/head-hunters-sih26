"""Unit and Integration Tests for Phase 4C Temporal Analysis.

Tests:
1. Activity within supplied time window (window filtering, undated exclusion, zero fabrication)
2. Interaction / activity concentration (BURST_COMMUNICATION_WINDOW signal detection)
3. Temporal relationship / activity summaries (lifespan, dated vs undated accounting)
4. Deterministic output reproducibility
5. Live Neo4j integration against loaded knowledge graph
"""

from datetime import datetime, timezone
import pytest
from neo4j import Driver

from app.schemas.entity import EntityType, PersonEntity, PhoneEntity
from app.schemas.relationship import RelationshipType, RelationshipOrigin, Relationship
from app.schemas.evidence import EvidenceProvenance
from app.schemas.record import SourceRecord
from app.schemas.analytics import TemporalSignalType, TimeWindow
from app.pipeline import PipelineResult
from app.graph.config import get_driver, verify_connection
from app.graph.loader import load_pipeline_result
from app.graph.query import Neo4jGraphQuery
from app.analytics.temporal import TemporalAnalyzer


@pytest.fixture(scope="module")
def neo4j_driver():
    """Provides a live Neo4j driver or fails if unavailable."""
    if not verify_connection():
        pytest.fail("BLOCKED — LIVE NEO4J TEST ENVIRONMENT UNAVAILABLE")
    driver = get_driver()
    yield driver
    driver.close()


@pytest.fixture(autouse=True)
def clean_graph(neo4j_driver: Driver):
    """Cleans up the database before and after each test."""
    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield
    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")


def _build_synthetic_temporal_subgraph():
    """Builds a deterministic in-memory graph with distinct temporal patterns.

    Edges:
    1. Burst edge: 10 calls in 15 minutes (t1 to t2)
    2. Spread edge: 3 calls spanning 6 hours (t0 to t4)
    3. Old edge: 1 call at t_old (earlier day)
    4. Undated edge: interaction_count=2, first_seen=None, last_seen=None
    """
    t_old = "2026-08-01T12:00:00+00:00"
    t0 = "2026-08-10T01:00:00+00:00"
    t1 = "2026-08-10T02:00:00+00:00"
    t2 = "2026-08-10T02:15:00+00:00"
    t4 = "2026-08-10T07:00:00+00:00"

    entities = [
        {"entity_id": "P1", "canonical_name": "Target Alpha"},
        {"entity_id": "P2", "canonical_name": "Associate Beta"},
        {"entity_id": "P3", "canonical_name": "Associate Gamma"},
        {"entity_id": "P4", "canonical_name": "Old Contact"},
    ]

    relationships = [
        # Burst edge between P1 and P2
        {
            "relationship_id": "rel_burst",
            "source_entity_id": "P1",
            "target_entity_id": "P2",
            "relationship_type": "COMMUNICATED_WITH",
            "first_seen": t1,
            "last_seen": t2,
            "interaction_count": 10,
            "evidence_ids": ["ev_burst_1", "ev_burst_2"],
        },
        # Spread edge between P1 and P3
        {
            "relationship_id": "rel_spread",
            "source_entity_id": "P1",
            "target_entity_id": "P3",
            "relationship_type": "COMMUNICATED_WITH",
            "first_seen": t0,
            "last_seen": t4,
            "interaction_count": 3,
            "evidence_ids": ["ev_spread"],
        },
        # Old edge between P1 and P4
        {
            "relationship_id": "rel_old",
            "source_entity_id": "P1",
            "target_entity_id": "P4",
            "relationship_type": "COMMUNICATED_WITH",
            "first_seen": t_old,
            "last_seen": t_old,
            "interaction_count": 1,
            "evidence_ids": ["ev_old"],
        },
        # Undated edge between P2 and P3
        {
            "relationship_id": "rel_undated",
            "source_entity_id": "P2",
            "target_entity_id": "P3",
            "relationship_type": "ASSOCIATED_WITH",
            "first_seen": None,
            "last_seen": None,
            "interaction_count": 2,
            "evidence_ids": ["ev_undated"],
        },
    ]

    return {"entities": entities, "relationships": relationships}


# -----------------------------------------------------------------------------
# Unit Tests (Algorithmic & Constraint Verification)
# -----------------------------------------------------------------------------

def test_window_activity_analysis():
    """Tests temporal filtering strictly within window and zero timestamp fabrication."""
    subgraph = _build_synthetic_temporal_subgraph()
    analyzer = TemporalAnalyzer(query=None)

    # Window covering Aug 10, 01:30 to 03:00
    # Should include rel_burst (02:00 - 02:15) and rel_spread (active across 01:00 - 07:00)
    # Should exclude rel_old (Aug 01)
    # Undated rel_undated should be counted as excluded without fabrication
    w = TimeWindow(
        start_time=datetime(2026, 8, 10, 1, 30, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 10, 3, 0, 0, tzinfo=timezone.utc),
    )

    res = analyzer.analyze_window_activity(time_window=w, subgraph=subgraph)

    assert sorted(res["active_relationship_ids"]) == ["rel_burst", "rel_spread"]
    assert sorted(res["active_entity_ids"]) == ["P1", "P2", "P3"]
    assert res["total_interactions"] == 13  # 10 on burst + 3 on spread
    assert res["undated_relationships_excluded_count"] == 1

    # Check evidence traceability
    assert set(res["evidence_ids"]) == {"ev_burst_1", "ev_burst_2", "ev_spread"}

    # Narrow window before burst (Aug 10, 00:00 to 01:30)
    # Only rel_spread active
    w_early = TimeWindow(
        start_time=datetime(2026, 8, 10, 0, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 10, 1, 30, 0, tzinfo=timezone.utc),
    )
    res_early = analyzer.analyze_window_activity(time_window=w_early, subgraph=subgraph)
    assert res_early["active_relationship_ids"] == ["rel_spread"]
    assert res_early["total_interactions"] == 3


def test_interaction_concentration_and_burst_detection():
    """Tests identification of burst communication windows without synthetic dates."""
    subgraph = _build_synthetic_temporal_subgraph()
    analyzer = TemporalAnalyzer(query=None)

    res = analyzer.analyze_interaction_concentration(
        subgraph=subgraph,
        min_interactions=2,
        max_span_seconds=1800.0,  # 30 minutes
    )

    signals = res["signals"]
    # Only rel_burst has 10 calls in 15 mins (900s <= 1800s)
    # rel_spread has 3 calls in 6 hours (21600s > 1800s)
    assert len(signals) == 1
    burst_sig = signals[0]
    assert burst_sig.signal_type == TemporalSignalType.BURST_COMMUNICATION_WINDOW
    assert burst_sig.relationship_ids == ["rel_burst"]
    assert sorted(burst_sig.entity_ids) == ["P1", "P2"]
    assert set(burst_sig.evidence_ids) == {"ev_burst_1", "ev_burst_2"}
    assert burst_sig.metric_value == 40.0  # 10 calls in 0.25 hrs = 40.0 calls/hr
    assert "Burst communication window" in burst_sig.explanation
    assert burst_sig.time_window is not None
    assert burst_sig.time_window.start_time == datetime(2026, 8, 10, 2, 0, 0, tzinfo=timezone.utc)
    assert burst_sig.time_window.end_time == datetime(2026, 8, 10, 2, 15, 0, tzinfo=timezone.utc)


def test_temporal_activity_summary():
    """Tests temporal summary accounting for dated and undated edges without synthetic timestamps."""
    subgraph = _build_synthetic_temporal_subgraph()
    analyzer = TemporalAnalyzer(query=None)

    # Global summary across entire subgraph
    summary = analyzer.summarize_temporal_activity(subgraph=subgraph)

    # 3 dated edges (rel_old, rel_burst, rel_spread) and 1 undated edge (rel_undated)
    assert summary.dated_relationship_count == 3
    assert summary.undated_relationship_count == 1
    assert summary.total_interactions == 16  # 10 + 3 + 1 + 2

    # Earliest timestamp is Aug 1, latest is Aug 10, 07:00
    assert summary.first_seen == datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert summary.last_seen == datetime(2026, 8, 10, 7, 0, 0, tzinfo=timezone.utc)
    assert summary.active_span_seconds is not None
    assert summary.active_span_seconds > 0

    # Summary specifically for P2:
    # Incident relationships: rel_burst (dated) and rel_undated (undated)
    p2_summary = analyzer.summarize_temporal_activity(entity_id="P2", subgraph=subgraph)
    assert p2_summary.dated_relationship_count == 1
    assert p2_summary.undated_relationship_count == 1
    assert p2_summary.total_interactions == 12  # 10 on burst, 2 on undated
    assert p2_summary.first_seen == datetime(2026, 8, 10, 2, 0, 0, tzinfo=timezone.utc)
    assert p2_summary.last_seen == datetime(2026, 8, 10, 2, 15, 0, tzinfo=timezone.utc)
    assert p2_summary.active_span_seconds == 900.0  # 15 minutes


def test_only_undated_relationships_zero_fabrication():
    """Verifies that an entity with exclusively undated relationships has None timestamps."""
    subgraph = {
        "entities": [{"entity_id": "U1"}, {"entity_id": "U2"}],
        "relationships": [
            {
                "relationship_id": "r_u",
                "source_entity_id": "U1",
                "target_entity_id": "U2",
                "relationship_type": "ASSOCIATED_WITH",
                "first_seen": None,
                "last_seen": None,
                "interaction_count": 5,
                "evidence_ids": [],
            }
        ],
    }
    analyzer = TemporalAnalyzer(query=None)
    summary = analyzer.summarize_temporal_activity(entity_id="U1", subgraph=subgraph)

    assert summary.dated_relationship_count == 0
    assert summary.undated_relationship_count == 1
    assert summary.first_seen is None
    assert summary.last_seen is None
    assert summary.active_span_seconds is None
    assert summary.total_interactions == 5


# -----------------------------------------------------------------------------
# Integration Tests (Live Neo4j Graph Integration)
# -----------------------------------------------------------------------------

def test_live_neo4j_temporal_analysis(neo4j_driver: Driver):
    """Integrates TemporalAnalyzer with live Neo4j graph data."""
    t0 = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 10, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 10, 1, 20, 0, tzinfo=timezone.utc)

    src = SourceRecord(
        source_id="urn:src:temp:001",
        source_type="CALL_DETAIL_RECORD",
        document_name="cdr_temp.csv",
        raw_content="CALL,temp",
        ingested_at=t0,
    )
    ev = EvidenceProvenance(
        evidence_id="urn:ev:temp:001",
        source_record_id=src.source_id,
        source_type=src.source_type,
        document_name=src.document_name,
        raw_snippet="temp",
        extractor_name="TempExtractor",
        extracted_at=t0,
    )
    p1 = PhoneEntity(
        entity_id="urn:ent:phone:A",
        entity_type=EntityType.PHONE,
        canonical_name="+91-5555555555",
        phone_number="+91-5555555555",
        created_at=t0,
        updated_at=t0,
    )
    p2 = PhoneEntity(
        entity_id="urn:ent:phone:B",
        entity_type=EntityType.PHONE,
        canonical_name="+91-6666666666",
        phone_number="+91-6666666666",
        created_at=t0,
        updated_at=t0,
    )

    # 3 call records between A and B in 10 minutes -> pre-aggregated into 1 edge with 3 interactions
    obs1 = Relationship(
        relationship_id="urn:rel:burst:ab",
        source_entity_id=p1.entity_id,
        target_entity_id=p2.entity_id,
        relationship_type=RelationshipType.COMMUNICATED_WITH,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=0.9,
        timestamp_context=t1,
        evidence_ids=[ev.evidence_id],
    )
    obs2 = Relationship(
        relationship_id="urn:rel:burst:ab",
        source_entity_id=p1.entity_id,
        target_entity_id=p2.entity_id,
        relationship_type=RelationshipType.COMMUNICATED_WITH,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=0.9,
        timestamp_context=t2,
        evidence_ids=[ev.evidence_id],
    )

    pipe = PipelineResult(
        source_records=[src],
        normalized_records=[],
        extracted_entities=[p1, p2],
        evidence_items=[ev],
        relationships=[obs1, obs2],
        resolution_candidates=[],
        resolution_decisions=[],
    )

    load_pipeline_result(pipe, driver=neo4j_driver)

    query = Neo4jGraphQuery(driver=neo4j_driver)
    with TemporalAnalyzer(query=query) as analyzer:
        # 1. Window Activity
        w = TimeWindow(start_time=t0, end_time=t2)
        win_res = analyzer.analyze_window_activity(time_window=w)
        assert win_res["active_relationship_ids"] == ["urn:rel:burst:ab"]
        assert win_res["total_interactions"] == 2
        assert set(win_res["active_entity_ids"]) == {p1.entity_id, p2.entity_id}

        # 2. Burst communication detection
        burst_res = analyzer.analyze_interaction_concentration(min_interactions=2, max_span_seconds=1200.0)
        assert burst_res["signal_count"] == 1
        sig = burst_res["signals"][0]
        assert sig.signal_type == TemporalSignalType.BURST_COMMUNICATION_WINDOW
        assert sig.relationship_ids == ["urn:rel:burst:ab"]
        assert sig.metric_value == 12.0  # 2 calls in 10 mins (1/6 hr) = 12 calls/hr

        # 3. Temporal summary
        summary = analyzer.summarize_temporal_activity(entity_id=p1.entity_id)
        assert summary.dated_relationship_count == 1
        assert summary.undated_relationship_count == 0
        assert summary.total_interactions == 2
        assert summary.active_span_seconds == 600.0  # 10 minutes
