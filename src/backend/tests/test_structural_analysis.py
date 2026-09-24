"""Unit and Integration Tests for Phase 4B Structural and Network Analysis.

Tests:
1. Degree & connection count (in, out, total, unique neighbors, HIGH_DEGREE_CENTRALITY signal)
2. Relationship-type distribution across approved types and directions
3. Betweenness centrality using Brandes' algorithm and BRIDGE_CANDIDATE identification
4. Deterministic community detection using Girvan-Newman edge-betweenness community detection (partitions, density, modularity Q)
5. Live Neo4j integration against loaded knowledge graph
"""

from datetime import datetime, timezone
import pytest
from neo4j import Driver

from app.schemas.entity import EntityType, PersonEntity, PhoneEntity, VehicleEntity
from app.schemas.relationship import RelationshipType, RelationshipOrigin, Relationship
from app.schemas.evidence import EvidenceProvenance
from app.schemas.record import SourceRecord
from app.schemas.analytics import StructuralSignalType
from app.pipeline import PipelineResult
from app.graph.config import get_driver, verify_connection
from app.graph.loader import load_pipeline_result
from app.graph.query import Neo4jGraphQuery
from app.analytics.structural import StructuralAnalyzer


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


def _build_synthetic_topology():
    """Builds a deterministic in-memory graph topology for algorithmic unit testing.

    Topology:
    Two 3-node cliques connected by bridge node B:
    Clique 1: [A1, A2, A3] (all connected)
    Bridge: [B] (connected to A1 and C1)
    Clique 2: [C1, C2, C3] (all connected)
    Isolated: [ISO] (0 edges)
    """
    entities = [
        {"entity_id": "A1", "canonical_name": "Node A1"},
        {"entity_id": "A2", "canonical_name": "Node A2"},
        {"entity_id": "A3", "canonical_name": "Node A3"},
        {"entity_id": "B", "canonical_name": "Bridge B"},
        {"entity_id": "C1", "canonical_name": "Node C1"},
        {"entity_id": "C2", "canonical_name": "Node C2"},
        {"entity_id": "C3", "canonical_name": "Node C3"},
        {"entity_id": "ISO", "canonical_name": "Isolated Node"},
    ]

    relationships = [
        # Clique 1
        {"relationship_id": "r_a1_a2", "source_entity_id": "A1", "target_entity_id": "A2", "relationship_type": "COMMUNICATED_WITH", "interaction_count": 3, "evidence_ids": ["ev_a12"]},
        {"relationship_id": "r_a2_a3", "source_entity_id": "A2", "target_entity_id": "A3", "relationship_type": "COMMUNICATED_WITH", "interaction_count": 2, "evidence_ids": ["ev_a23"]},
        {"relationship_id": "r_a1_a3", "source_entity_id": "A1", "target_entity_id": "A3", "relationship_type": "ASSOCIATED_WITH", "interaction_count": 1, "evidence_ids": ["ev_a13"]},
        # Bridge connections
        {"relationship_id": "r_a1_b", "source_entity_id": "A1", "target_entity_id": "B", "relationship_type": "COMMUNICATED_WITH", "interaction_count": 5, "evidence_ids": ["ev_ab"]},
        {"relationship_id": "r_b_c1", "source_entity_id": "B", "target_entity_id": "C1", "relationship_type": "COMMUNICATED_WITH", "interaction_count": 4, "evidence_ids": ["ev_bc"]},
        # Clique 2
        {"relationship_id": "r_c1_c2", "source_entity_id": "C1", "target_entity_id": "C2", "relationship_type": "TRANSACTED_WITH", "interaction_count": 1, "evidence_ids": ["ev_c12"]},
        {"relationship_id": "r_c2_c3", "source_entity_id": "C2", "target_entity_id": "C3", "relationship_type": "TRANSACTED_WITH", "interaction_count": 2, "evidence_ids": ["ev_c23"]},
        {"relationship_id": "r_c1_c3", "source_entity_id": "C1", "target_entity_id": "C3", "relationship_type": "OWNED_BY", "interaction_count": 1, "evidence_ids": ["ev_c13"]},
    ]

    return {"entities": entities, "relationships": relationships}


# -----------------------------------------------------------------------------
# Unit Tests (Algorithmic Verification)
# -----------------------------------------------------------------------------

def test_degree_and_connection_counts():
    """Tests degree counting, neighbor uniqueness, and isolated node handling."""
    subgraph = _build_synthetic_topology()
    analyzer = StructuralAnalyzer(query=None)

    # Test single entity B
    res_b = analyzer.compute_degree_metrics(entity_id="B", subgraph=subgraph)
    deg_b = res_b["degrees"]["B"]
    assert deg_b["in_degree"] == 1  # A1 -> B
    assert deg_b["out_degree"] == 1  # B -> C1
    assert deg_b["total_degree"] == 2
    assert deg_b["connection_count"] == 2
    assert sorted(deg_b["relationship_ids"]) == ["r_a1_b", "r_b_c1"]
    assert sorted(deg_b["evidence_ids"]) == ["ev_ab", "ev_bc"]

    # Test isolated node
    res_iso = analyzer.compute_degree_metrics(entity_id="ISO", subgraph=subgraph)
    deg_iso = res_iso["degrees"]["ISO"]
    assert deg_iso["total_degree"] == 0
    assert deg_iso["connection_count"] == 0
    assert deg_iso["relationship_ids"] == []

    # Test full network with threshold trigger
    res_all = analyzer.compute_degree_metrics(subgraph=subgraph, high_degree_threshold=3)
    # A1 has edges to A2, A3, B (total 3)
    # C1 has edges to B, C2, C3 (total 3)
    assert len(res_all["signals"]) == 2
    signal_entities = {s.entity_ids[0] for s in res_all["signals"]}
    assert signal_entities == {"A1", "C1"}
    for sig in res_all["signals"]:
        assert sig.signal_type == StructuralSignalType.HIGH_DEGREE_CENTRALITY
        assert sig.metric_value == 3.0


def test_relationship_type_distribution():
    """Tests categorical and directional distribution of relationship types."""
    subgraph = _build_synthetic_topology()
    analyzer = StructuralAnalyzer(query=None)

    # Overall network distribution
    dist_metric = analyzer.compute_relationship_distribution(subgraph=subgraph)
    val = dist_metric.value

    # Total 8 relationships: 4 COMMUNICATED_WITH, 1 ASSOCIATED_WITH, 2 TRANSACTED_WITH, 1 OWNED_BY
    assert val["total_relationships"] == 8
    assert val["type_counts"]["COMMUNICATED_WITH"] == 4
    assert val["type_counts"]["ASSOCIATED_WITH"] == 1
    assert val["type_counts"]["TRANSACTED_WITH"] == 2
    assert val["type_counts"]["OWNED_BY"] == 1

    assert val["type_percentages"]["COMMUNICATED_WITH"] == 50.0
    assert val["type_percentages"]["TRANSACTED_WITH"] == 25.0

    # Interaction count sum: 3+2+1+5+4+1+2+1 = 19
    assert sum(val["interaction_counts"].values()) == 19

    # Entity-specific distribution for C1:
    # r_b_c1 (incoming COMMUNICATED_WITH)
    # r_c1_c2 (outgoing TRANSACTED_WITH)
    # r_c1_c3 (outgoing OWNED_BY)
    c1_metric = analyzer.compute_relationship_distribution(entity_id="C1", subgraph=subgraph)
    c1_val = c1_metric.value
    assert c1_val["total_relationships"] == 3
    assert c1_val["directional_counts"]["incoming"]["COMMUNICATED_WITH"] == 1
    assert c1_val["directional_counts"]["outgoing"]["TRANSACTED_WITH"] == 1
    assert c1_val["directional_counts"]["outgoing"]["OWNED_BY"] == 1


def test_betweenness_centrality_and_bridge_candidate():
    """Tests Brandes' betweenness centrality algorithm and BRIDGE_CANDIDATE signal emission."""
    subgraph = _build_synthetic_topology()
    analyzer = StructuralAnalyzer(query=None)

    res = analyzer.compute_betweenness_centrality(subgraph=subgraph, bridge_threshold=0.0)
    scores = res["scores"]

    # In our bridge topology:
    # All paths between Clique 1 {A1, A2, A3} and Clique 2 {C1, C2, C3} must pass through B!
    # Specifically: A1 -> B -> C1 is the unique path connecting both clusters.
    # Therefore, B, A1, and C1 must have high betweenness, with B being the central bottleneck.
    assert scores["B"]["normalized"] > 0.0
    assert scores["A1"]["normalized"] > 0.0
    assert scores["C1"]["normalized"] > 0.0

    # Peripheral nodes inside cliques have betweenness 0.0 (all other nodes in clique are directly connected)
    assert scores["A2"]["normalized"] == 0.0
    assert scores["A3"]["normalized"] == 0.0
    assert scores["C2"]["normalized"] == 0.0
    assert scores["C3"]["normalized"] == 0.0
    assert scores["ISO"]["normalized"] == 0.0

    # Node B has betweenness score connecting 3 nodes on left with 3 nodes on right (3 * 3 = 9 pairs)
    assert scores["B"]["raw"] == 9.0

    # Bridge candidates must include B as the highest ranked
    candidates = res["bridge_candidates"]
    assert len(candidates) >= 1
    assert candidates[0].entity_ids[0] == "B"
    assert candidates[0].signal_type == StructuralSignalType.BRIDGE_CANDIDATE
    assert "BRIDGE_CANDIDATE" in candidates[0].explanation
    assert candidates[0].metric_value == scores["B"]["normalized"]


def test_deterministic_betweenness_centrality_reproducibility():
    """Tests that betweenness centrality calculation is 100% deterministic across multiple runs."""
    subgraph = _build_synthetic_topology()
    analyzer = StructuralAnalyzer(query=None)

    run1 = analyzer.compute_betweenness_centrality(subgraph=subgraph)
    run2 = analyzer.compute_betweenness_centrality(subgraph=subgraph)

    assert run1["scores"] == run2["scores"]
    assert len(run1["bridge_candidates"]) == len(run2["bridge_candidates"])
    for s1, s2 in zip(run1["bridge_candidates"], run2["bridge_candidates"]):
        assert s1.signal_id == s2.signal_id
        assert s1.entity_ids == s2.entity_ids
        assert s1.metric_value == s2.metric_value


def test_deterministic_community_detection():
    """Tests Girvan-Newman edge-betweenness community detection, partition density, and modularity."""
    subgraph = _build_synthetic_topology()
    analyzer = StructuralAnalyzer(query=None)

    res = analyzer.detect_communities(subgraph=subgraph)
    comms = res["communities"]

    # We expect 3 communities: Clique 1 (plus/or bridge), Clique 2, and Isolated node
    assert res["community_count"] >= 2
    assert res["modularity"] > 0.0  # Graph exhibits significant modular structure

    # Find isolated node's community
    iso_comm = next(c for c in comms if "ISO" in c.entity_ids)
    assert iso_comm.member_count == 1
    assert iso_comm.density == 0.0
    assert iso_comm.internal_relationship_ids == []

    # Validate determinism
    res2 = analyzer.detect_communities(subgraph=subgraph)
    assert res["community_count"] == res2["community_count"]
    assert res["modularity"] == res2["modularity"]
    for c1, c2 in zip(res["communities"], res2["communities"]):
        assert c1.community_id == c2.community_id
        assert c1.entity_ids == c2.entity_ids
        assert c1.density == c2.density


# -----------------------------------------------------------------------------
# Integration Tests (Live Neo4j Graph Integration)
# -----------------------------------------------------------------------------

def test_live_neo4j_structural_analysis(neo4j_driver: Driver):
    """Integrates StructuralAnalyzer with live Neo4j database using loaded pipeline result."""
    t0 = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 10, 2, 0, 0, tzinfo=timezone.utc)

    # Construct test pipeline result
    src = SourceRecord(
        source_id="urn:src:struct:001",
        source_type="CALL_DETAIL_RECORD",
        document_name="test_struct.csv",
        raw_content="CALL,test",
        ingested_at=t0,
    )
    ev = EvidenceProvenance(
        evidence_id="urn:ev:struct:001",
        source_record_id=src.source_id,
        source_type=src.source_type,
        document_name=src.document_name,
        raw_snippet="test",
        extractor_name="TestExtractor",
        extracted_at=t0,
    )
    p_center = PersonEntity(
        entity_id="urn:ent:center",
        entity_type=EntityType.PERSON,
        canonical_name="Central Coordinator",
        full_name="Central Coordinator",
        created_at=t0,
        updated_at=t0,
    )
    p_left = PhoneEntity(
        entity_id="urn:ent:left",
        entity_type=EntityType.PHONE,
        canonical_name="+91-1111111111",
        phone_number="+91-1111111111",
        created_at=t0,
        updated_at=t0,
    )
    p_right = VehicleEntity(
        entity_id="urn:ent:right",
        entity_type=EntityType.VEHICLE,
        canonical_name="DL-99-ZZ-9999",
        registration_number="DL-99-ZZ-9999",
        created_at=t0,
        updated_at=t0,
    )

    r1 = Relationship(
        relationship_id="urn:rel:c_to_l",
        source_entity_id=p_center.entity_id,
        target_entity_id=p_left.entity_id,
        relationship_type=RelationshipType.COMMUNICATED_WITH,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=0.9,
        timestamp_context=t0,
        attributes={"duration": 120},
        evidence_ids=[ev.evidence_id],
    )
    r2 = Relationship(
        relationship_id="urn:rel:c_to_r",
        source_entity_id=p_center.entity_id,
        target_entity_id=p_right.entity_id,
        relationship_type=RelationshipType.OWNED_BY,
        origin=RelationshipOrigin.EXTRACTED,
        confidence=0.95,
        timestamp_context=t1,
        attributes={"role": "owner"},
        evidence_ids=[ev.evidence_id],
    )

    pipe = PipelineResult(
        source_records=[src],
        normalized_records=[],
        extracted_entities=[p_center, p_left, p_right],
        evidence_items=[ev],
        relationships=[r1, r2],
        resolution_candidates=[],
        resolution_decisions=[],
    )

    load_pipeline_result(pipe, driver=neo4j_driver)

    query = Neo4jGraphQuery(driver=neo4j_driver)
    with StructuralAnalyzer(query=query) as analyzer:
        # 1. Degree metrics against live Neo4j
        deg = analyzer.compute_degree_metrics(entity_id=p_center.entity_id)
        c_deg = deg["degrees"][p_center.entity_id]
        assert c_deg["out_degree"] == 2
        assert c_deg["in_degree"] == 0
        assert c_deg["total_degree"] == 2
        assert c_deg["connection_count"] == 2
        assert sorted(c_deg["relationship_ids"]) == ["urn:rel:c_to_l", "urn:rel:c_to_r"]
        assert c_deg["evidence_ids"] == [ev.evidence_id]

        # 2. Relationship distribution against live Neo4j
        dist = analyzer.compute_relationship_distribution(entity_id=p_center.entity_id)
        assert dist.value["total_relationships"] == 2
        assert dist.value["type_counts"]["COMMUNICATED_WITH"] == 1
        assert dist.value["type_counts"]["OWNED_BY"] == 1

        # 3. Betweenness centrality against live Neo4j
        # Center connects left and right on path: Left - Center - Right
        # Center has betweenness 1.0!
        bc = analyzer.compute_betweenness_centrality()
        assert bc["scores"][p_center.entity_id]["normalized"] == 1.0
        assert bc["scores"][p_left.entity_id]["normalized"] == 0.0
        assert bc["scores"][p_right.entity_id]["normalized"] == 0.0

        bridge_cands = bc["bridge_candidates"]
        assert len(bridge_cands) == 1
        assert bridge_cands[0].entity_ids == [p_center.entity_id]
        assert bridge_cands[0].signal_type == StructuralSignalType.BRIDGE_CANDIDATE

        # 4. Community detection against live Neo4j
        comms = analyzer.detect_communities()
        assert comms["community_count"] >= 1
