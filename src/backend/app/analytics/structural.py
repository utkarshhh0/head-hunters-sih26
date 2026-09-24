"""Deterministic Structural and Network Analysis Engine.

Provides Phase 4B graph analytics against the Neo4j knowledge graph:
1. Degree & Connection Count: in-degree, out-degree, total degree, unique neighbor count,
   with optional HIGH_DEGREE_CENTRALITY signal generation.
2. Relationship-Type Distribution: categorical and directional breakdown of relationship types.
3. Bridge / Intermediary Analysis: Ulrik Brandes' betweenness centrality algorithm with
   deterministic tie-breaking, emitting BRIDGE_CANDIDATE signals for key intermediary entities.
4. Deterministic Community Detection: Label Propagation with strict lexicographical tie-breaking,
   computing community partitions, density, internal/external relationships, and modularity Q.

All outputs are purely descriptive, explainable, and retain full evidence provenance references.
No universal risk scores, criminality judgments, or LLMs are used.
"""

from collections import defaultdict, deque
from datetime import datetime
import hashlib
from typing import Any, Dict, List, Optional, Set, Tuple

from neo4j import Driver

from app.schemas.analytics import (
    AnalyticalMetric,
    CommunityResult,
    StructuralSignal,
    StructuralSignalType,
    TimeWindow,
)
from app.graph.config import Neo4jConfig, get_driver
from app.graph.query import Neo4jGraphQuery
from app.graph.pre_aggregation import APPROVED_RELATIONSHIP_TYPES


def _deterministic_hash(val: str, length: int = 12) -> str:
    """Generates a deterministic hex hash prefix from an input string."""
    return hashlib.sha256(val.encode("utf-8")).hexdigest()[:length]


class StructuralAnalyzer:
    """Investigative structural and network analysis engine."""

    def __init__(
        self,
        query: Optional[Neo4jGraphQuery] = None,
        driver: Optional[Driver] = None,
        config: Optional[Neo4jConfig] = None,
    ):
        if query is not None:
            self.query: Neo4jGraphQuery = query
            self._owned_query: bool = False
        else:
            self.query = Neo4jGraphQuery(driver=driver, config=config)
            self._owned_query = True

    def close(self) -> None:
        """Closes the underlying query layer if internally owned."""
        if self._owned_query and self.query:
            self.query.close()

    def __enter__(self) -> "StructuralAnalyzer":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _resolve_subgraph(
        self,
        entity_id: Optional[str] = None,
        subgraph: Optional[Dict[str, Any]] = None,
        hops: int = 1,
        limit: int = 500,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Resolves entities and relationships from caller-supplied subgraph or live Neo4j."""
        if subgraph is not None:
            entities = subgraph.get("entities", [])
            relationships = subgraph.get("relationships", [])
            return entities, relationships

        if entity_id is not None:
            trav = self.query.traverse_network(
                start_entity_id=entity_id,
                hops=hops,
                limit=limit,
            )
            return trav.get("entities", []), trav.get("relationships", [])

        # Entire active graph slice within query limit
        temp_sub = self.query.get_temporal_subgraph(
            include_undated=True,
            limit=limit,
        )
        entities = temp_sub.get("entities", [])
        relationships = temp_sub.get("relationships", [])

        # Ensure isolated nodes without relationships are also retrieved
        all_ents = self.query.search_entities(limit=limit)
        ent_ids = {e["entity_id"] for e in entities}
        for e in all_ents:
            if e["entity_id"] not in ent_ids:
                entities.append(e)
                ent_ids.add(e["entity_id"])

        return entities, relationships

    # -------------------------------------------------------------------------
    # 1. Degree & Connection Count
    # -------------------------------------------------------------------------
    def compute_degree_metrics(
        self,
        entity_id: Optional[str] = None,
        subgraph: Optional[Dict[str, Any]] = None,
        high_degree_threshold: Optional[int] = None,
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Calculates in-degree, out-degree, total degree, and unique connection count.

        Preserves entity IDs, incident relationship IDs, and evidence references.
        Optionally emits HIGH_DEGREE_CENTRALITY signals when threshold is exceeded.
        """
        entities, relationships = self._resolve_subgraph(
            entity_id=entity_id,
            subgraph=subgraph,
            hops=1 if entity_id else 2,
            limit=limit,
        )

        in_degree: Dict[str, int] = defaultdict(int)
        out_degree: Dict[str, int] = defaultdict(int)
        connected_neighbors: Dict[str, Set[str]] = defaultdict(set)
        incident_relationships: Dict[str, List[str]] = defaultdict(list)
        incident_evidence: Dict[str, Set[str]] = defaultdict(set)
        entity_names: Dict[str, str] = {}

        for ent in entities:
            eid = ent["entity_id"]
            entity_names[eid] = ent.get("canonical_name", eid)
            # Ensure initialization
            _ = in_degree[eid]
            _ = out_degree[eid]
            _ = connected_neighbors[eid]

        for rel in relationships:
            src = rel["source_entity_id"]
            tgt = rel["target_entity_id"]
            rel_id = rel["relationship_id"]
            ev_ids = rel.get("evidence_ids", [])

            out_degree[src] += 1
            in_degree[tgt] += 1

            if src != tgt:
                connected_neighbors[src].add(tgt)
                connected_neighbors[tgt].add(src)

            incident_relationships[src].append(rel_id)
            incident_relationships[tgt].append(rel_id)

            for ev in ev_ids:
                incident_evidence[src].add(ev)
                incident_evidence[tgt].add(ev)

        degree_table: Dict[str, Dict[str, Any]] = {}
        metrics: List[AnalyticalMetric] = []
        signals: List[StructuralSignal] = []

        target_ids = [entity_id] if entity_id else sorted(entities, key=lambda x: x["entity_id"])
        target_ids_clean = [eid if isinstance(eid, str) else eid["entity_id"] for eid in target_ids]

        for eid in target_ids_clean:
            in_d = in_degree[eid]
            out_d = out_degree[eid]
            tot_d = in_d + out_d
            conn_c = len(connected_neighbors[eid])
            rel_ids = sorted(list(set(incident_relationships[eid])))
            ev_ids = sorted(list(incident_evidence[eid]))
            name = entity_names.get(eid, eid)

            entry = {
                "entity_id": eid,
                "canonical_name": name,
                "in_degree": in_d,
                "out_degree": out_d,
                "total_degree": tot_d,
                "connection_count": conn_c,
                "relationship_ids": rel_ids,
                "evidence_ids": ev_ids,
            }
            degree_table[eid] = entry

            explanation = (
                f"Entity '{name}' (ID: {eid}) has {tot_d} direct relationships "
                f"({in_d} incoming, {out_d} outgoing) across {conn_c} unique connected entities."
            )
            limitations = [
                "Degree count calculated strictly within active graph slice.",
                "Does not reflect unrecorded real-world or offline interactions.",
            ]

            metric = AnalyticalMetric(
                metric_name="degree_metrics",
                entity_ids=[eid],
                relationship_ids=rel_ids,
                evidence_ids=ev_ids,
                value={
                    "in_degree": in_d,
                    "out_degree": out_d,
                    "total_degree": tot_d,
                    "connection_count": conn_c,
                },
                method="graph_degree_counter",
                explanation=explanation,
                limitations=limitations,
            )
            metrics.append(metric)

            # Signal if threshold is exceeded
            if high_degree_threshold is not None and tot_d >= high_degree_threshold:
                sig_id = f"urn:sig:deg:{_deterministic_hash(f'{eid}:{tot_d}')}"
                sig = StructuralSignal(
                    signal_id=sig_id,
                    signal_type=StructuralSignalType.HIGH_DEGREE_CENTRALITY,
                    entity_ids=[eid],
                    relationship_ids=rel_ids,
                    evidence_ids=ev_ids,
                    metric_value=float(tot_d),
                    method="high_degree_threshold_rule",
                    explanation=(
                        f"Entity '{name}' exhibits high degree centrality with {tot_d} relationships "
                        f"exceeding threshold of {high_degree_threshold}."
                    ),
                    limitations=limitations,
                )
                signals.append(sig)

        # Sort metrics by total_degree descending, then entity_id ascending
        sorted_metrics = sorted(
            metrics,
            key=lambda m: (-m.value["total_degree"], m.entity_ids[0]),
        )

        return {
            "entity_id": entity_id,
            "degrees": degree_table,
            "metrics": sorted_metrics,
            "signals": signals,
        }

    # -------------------------------------------------------------------------
    # 2. Relationship-Type Distribution
    # -------------------------------------------------------------------------
    def compute_relationship_distribution(
        self,
        entity_id: Optional[str] = None,
        subgraph: Optional[Dict[str, Any]] = None,
        limit: int = 500,
    ) -> AnalyticalMetric:
        """Calculates the categorical and directional distribution of relationship types."""
        entities, relationships = self._resolve_subgraph(
            entity_id=entity_id,
            subgraph=subgraph,
            hops=1 if entity_id else 2,
            limit=limit,
        )

        # Filter to target entity relationships if entity_id specified
        if entity_id:
            rels_to_evaluate = [
                r for r in relationships
                if r["source_entity_id"] == entity_id or r["target_entity_id"] == entity_id
            ]
        else:
            rels_to_evaluate = relationships

        total_rels = len(rels_to_evaluate)
        type_counts: Dict[str, int] = {t: 0 for t in sorted(APPROVED_RELATIONSHIP_TYPES)}
        interaction_counts: Dict[str, int] = {t: 0 for t in sorted(APPROVED_RELATIONSHIP_TYPES)}
        incoming_counts: Dict[str, int] = {t: 0 for t in sorted(APPROVED_RELATIONSHIP_TYPES)}
        outgoing_counts: Dict[str, int] = {t: 0 for t in sorted(APPROVED_RELATIONSHIP_TYPES)}

        rel_ids: List[str] = []
        evidence_ids_set: Set[str] = set()

        for r in rels_to_evaluate:
            rtype = r.get("relationship_type") or r.get("type")
            rel_id = r["relationship_id"]
            rel_ids.append(rel_id)

            for ev in r.get("evidence_ids", []):
                evidence_ids_set.add(ev)

            if rtype in type_counts:
                type_counts[rtype] += 1
                interaction_counts[rtype] += int(r.get("interaction_count", 1))

                if entity_id:
                    if r["target_entity_id"] == entity_id:
                        incoming_counts[rtype] += 1
                    if r["source_entity_id"] == entity_id:
                        outgoing_counts[rtype] += 1

        # Calculate percentages
        type_percentages: Dict[str, float] = {}
        for t, count in type_counts.items():
            pct = round((count / total_rels * 100.0), 2) if total_rels > 0 else 0.0
            type_percentages[t] = pct

        parts = [
            f"{t}: {type_counts[t]} ({type_percentages[t]}%)"
            for t in sorted(type_counts.keys())
            if type_counts[t] > 0
        ]
        breakdown_str = ", ".join(parts) if parts else "none"

        scope_desc = f"Entity '{entity_id}'" if entity_id else "Evaluated network slice"
        explanation = (
            f"{scope_desc} has {total_rels} total relationships. "
            f"Type distribution: {breakdown_str}."
        )

        return AnalyticalMetric(
            metric_name="relationship_type_distribution",
            entity_ids=[entity_id] if entity_id else sorted([e["entity_id"] for e in entities]),
            relationship_ids=sorted(rel_ids),
            evidence_ids=sorted(list(evidence_ids_set)),
            value={
                "total_relationships": total_rels,
                "type_counts": type_counts,
                "type_percentages": type_percentages,
                "interaction_counts": interaction_counts,
                "directional_counts": {
                    "incoming": incoming_counts,
                    "outgoing": outgoing_counts,
                } if entity_id else {},
            },
            method="frequency_distribution",
            explanation=explanation,
            limitations=[
                "Restricted to authorized Phase-3 relationship types.",
                "Includes all pre-aggregated relationship instances within query scope.",
            ],
        )

    # -------------------------------------------------------------------------
    # 3. Betweenness Centrality & Bridge Candidate Analysis
    # -------------------------------------------------------------------------
    def compute_betweenness_centrality(
        self,
        subgraph: Optional[Dict[str, Any]] = None,
        bridge_threshold: float = 0.0,
        directed: bool = False,
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Calculates exact betweenness centrality using Ulrik Brandes' algorithm.

        Deterministic tie-breaking: Node and neighbor traversals follow strict lexicographical ordering.
        Identifies BRIDGE_CANDIDATE entities sitting on shortest paths between network clusters.
        """
        entities, relationships = self._resolve_subgraph(
            subgraph=subgraph,
            limit=limit,
        )

        node_list: List[str] = sorted(list({e["entity_id"] for e in entities}))
        entity_name_map: Dict[str, str] = {
            e["entity_id"]: e.get("canonical_name", e["entity_id"]) for e in entities
        }

        # Build deterministic adjacency list
        adj: Dict[str, Set[str]] = {v: set() for v in node_list}
        incident_relationships: Dict[str, List[str]] = defaultdict(list)
        incident_evidence: Dict[str, Set[str]] = defaultdict(set)

        for rel in relationships:
            src = rel["source_entity_id"]
            tgt = rel["target_entity_id"]
            rel_id = rel["relationship_id"]
            ev_ids = rel.get("evidence_ids", [])

            if src in adj and tgt in adj and src != tgt:
                adj[src].add(tgt)
                if not directed:
                    adj[tgt].add(src)

            if src in node_list:
                incident_relationships[src].append(rel_id)
                for ev in ev_ids:
                    incident_evidence[src].add(ev)
            if tgt in node_list:
                incident_relationships[tgt].append(rel_id)
                for ev in ev_ids:
                    incident_evidence[tgt].add(ev)

        # Brandes' Algorithm (O(V * E) for unweighted graphs)
        cb: Dict[str, float] = {v: 0.0 for v in node_list}

        for s in node_list:
            stack: List[str] = []
            pred: Dict[str, List[str]] = {w: [] for w in node_list}
            sigma: Dict[str, int] = {w: 0 for w in node_list}
            sigma[s] = 1
            dist: Dict[str, int] = {w: -1 for w in node_list}
            dist[s] = 0

            queue: deque = deque([s])

            while queue:
                v = queue.popleft()
                stack.append(v)
                # Strict sorted iteration for deterministic shortest path counting
                for w in sorted(list(adj[v])):
                    if dist[w] < 0:
                        dist[w] = dist[v] + 1
                        queue.append(w)
                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        pred[w].append(v)

            delta: Dict[str, float] = {w: 0.0 for w in node_list}
            while stack:
                w = stack.pop()
                for v in pred[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
                if w != s:
                    cb[w] += delta[w]

        # In undirected graphs, each pair (s, t) is traversed twice
        if not directed:
            for v in node_list:
                cb[v] /= 2.0

        n = len(node_list)
        norm_factor = 1.0
        if n > 2:
            if not directed:
                norm_factor = 2.0 / ((n - 1) * (n - 2))
            else:
                norm_factor = 1.0 / ((n - 1) * (n - 2))

        normalized_cb: Dict[str, float] = {
            v: round(cb[v] * norm_factor, 4) for v in node_list
        }

        # Build Bridge Candidate Signals
        signals: List[StructuralSignal] = []
        for eid in node_list:
            norm_val = normalized_cb[eid]
            if norm_val > bridge_threshold:
                name = entity_name_map.get(eid, eid)
                rel_ids = sorted(list(set(incident_relationships[eid])))
                ev_ids = sorted(list(incident_evidence[eid]))

                sig_id = f"urn:sig:bridge:{_deterministic_hash(f'{eid}:{norm_val}')}"
                sig = StructuralSignal(
                    signal_id=sig_id,
                    signal_type=StructuralSignalType.BRIDGE_CANDIDATE,
                    entity_ids=[eid],
                    relationship_ids=rel_ids,
                    evidence_ids=ev_ids,
                    metric_value=norm_val,
                    method="brandes_betweenness_centrality",
                    explanation=(
                        f"Entity '{name}' (ID: {eid}) is identified as a BRIDGE_CANDIDATE "
                        f"with normalized betweenness centrality of {norm_val:.4f}, acting as a "
                        f"critical intermediary on shortest paths between network nodes."
                    ),
                    limitations=[
                        "Centrality scores depend on the completeness of observed connections in the graph.",
                        "Unobserved edges or missing intermediary nodes may alter shortest-path distribution.",
                    ],
                )
                signals.append(sig)

        # Sort signals by metric_value descending, entity_id ascending
        signals = sorted(signals, key=lambda s: (-s.metric_value, s.entity_ids[0]))

        scores_table: Dict[str, Dict[str, float]] = {
            eid: {
                "raw": round(cb[eid], 4),
                "normalized": normalized_cb[eid],
            }
            for eid in node_list
        }

        metric = AnalyticalMetric(
            metric_name="betweenness_centrality",
            entity_ids=node_list,
            relationship_ids=sorted(list({r["relationship_id"] for r in relationships})),
            evidence_ids=sorted(list({ev for r in relationships for ev in r.get("evidence_ids", [])})),
            value={
                "node_count": n,
                "scores": scores_table,
                "bridge_candidate_count": len(signals),
            },
            method="brandes_betweenness_centrality",
            explanation=(
                f"Calculated Brandes betweenness centrality across {n} nodes. "
                f"Identified {len(signals)} bridge candidate(s) above threshold {bridge_threshold}."
            ),
            limitations=[
                "Exact betweenness computed over bounded graph slice.",
                "Shortest path metrics can fluctuate if external unobserved relations exist.",
            ],
        )

        return {
            "node_count": n,
            "scores": scores_table,
            "bridge_candidates": signals,
            "metric": metric,
        }

    # -------------------------------------------------------------------------
    # 4. Deterministic Community Detection
    # -------------------------------------------------------------------------
    def detect_communities(
        self,
        subgraph: Optional[Dict[str, Any]] = None,
        max_iterations: int = 50,
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Detects network communities using deterministic Girvan-Newman edge-betweenness partitioning.

        Iteratively identifies and removes communication bottleneck edges with maximum edge betweenness
        centrality to partition the graph into cohesive operational communities, optimizing modularity Q.
        Deterministic tie-breaking: ties are broken lexicographically by node/edge identifier pairs.
        """
        entities, relationships = self._resolve_subgraph(
            subgraph=subgraph,
            limit=limit,
        )

        node_list: List[str] = sorted(list({e["entity_id"] for e in entities}))
        if not node_list:
            return {
                "communities": [],
                "community_count": 0,
                "modularity": 0.0,
                "signals": [],
                "metric": AnalyticalMetric(
                    metric_name="community_partition",
                    entity_ids=[],
                    relationship_ids=[],
                    evidence_ids=[],
                    value={"community_count": 0, "modularity": 0.0},
                    method="girvan_newman_betweenness_partitioning",
                    explanation="Empty graph slice; 0 communities detected.",
                    limitations=["Evaluated on empty node set."],
                ),
            }

        # Build original undirected edges and degree counts
        orig_edges_set: Set[Tuple[str, str]] = set()
        orig_adj: Dict[str, Set[str]] = {v: set() for v in node_list}

        for rel in relationships:
            src = rel["source_entity_id"]
            tgt = rel["target_entity_id"]
            if src in orig_adj and tgt in orig_adj and src != tgt:
                edge_tuple = tuple(sorted([src, tgt]))
                orig_edges_set.add(edge_tuple)
                orig_adj[src].add(tgt)
                orig_adj[tgt].add(src)

        orig_degrees = {v: len(orig_adj[v]) for v in node_list}
        total_m = len(orig_edges_set)

        def _get_components(nodes: List[str], active_edges: Set[Tuple[str, str]]) -> List[List[str]]:
            curr_adj: Dict[str, Set[str]] = {v: set() for v in nodes}
            for u, v in active_edges:
                curr_adj[u].add(v)
                curr_adj[v].add(u)
            visited: Set[str] = set()
            comps: List[List[str]] = []
            for v in nodes:
                if v not in visited:
                    comp: List[str] = []
                    q: deque = deque([v])
                    visited.add(v)
                    while q:
                        curr = q.popleft()
                        comp.append(curr)
                        for nb in sorted(list(curr_adj[curr])):
                            if nb not in visited:
                                visited.add(nb)
                                q.append(nb)
                    comps.append(sorted(comp))
            return sorted(comps, key=lambda c: (-len(c), c[0]))

        def _compute_modularity(comps: List[List[str]]) -> float:
            if total_m == 0:
                return 0.0
            q_val = 0.0
            for comp in comps:
                comp_set = set(comp)
                internal_count = sum(1 for u, v in orig_edges_set if u in comp_set and v in comp_set)
                degree_sum = sum(orig_degrees[v] for v in comp)
                q_val += (internal_count / total_m) - ((degree_sum / (2.0 * total_m)) ** 2)
            return q_val

        def _edge_betweenness(nodes: List[str], active_edges: Set[Tuple[str, str]]) -> Dict[Tuple[str, str], float]:
            eb: Dict[Tuple[str, str], float] = defaultdict(float)
            curr_adj: Dict[str, Set[str]] = {v: set() for v in nodes}
            for u, v in active_edges:
                curr_adj[u].add(v)
                curr_adj[v].add(u)
            for s in nodes:
                stack: List[str] = []
                pred: Dict[str, List[str]] = {w: [] for w in nodes}
                sigma: Dict[str, int] = {w: 0 for w in nodes}
                sigma[s] = 1
                dist: Dict[str, int] = {w: -1 for w in nodes}
                dist[s] = 0
                queue: deque = deque([s])
                while queue:
                    v = queue.popleft()
                    stack.append(v)
                    for w in sorted(list(curr_adj[v])):
                        if dist[w] < 0:
                            dist[w] = dist[v] + 1
                            queue.append(w)
                        if dist[w] == dist[v] + 1:
                            sigma[w] += sigma[v]
                            pred[w].append(v)
                delta: Dict[str, float] = {w: 0.0 for w in nodes}
                while stack:
                    w = stack.pop()
                    for v in pred[w]:
                        c = (sigma[v] / sigma[w]) * (1.0 + delta[w])
                        e_key = tuple(sorted([v, w]))
                        eb[e_key] += c / 2.0
                        delta[v] += c
            return eb

        # Girvan-Newman Edge Removal Loop
        active_edges = set(orig_edges_set)
        init_comps = _get_components(node_list, active_edges)
        best_partition = init_comps
        best_q = _compute_modularity(init_comps)

        iterations_count = 0
        while active_edges and iterations_count < max_iterations:
            eb = _edge_betweenness(node_list, active_edges)
            if not eb:
                break
            max_eb = max(eb.values())
            # Deterministic tie-breaking: pick lexicographically smallest edge
            candidates = sorted([e for e, val in eb.items() if val == max_eb])
            edge_to_remove = candidates[0]
            active_edges.remove(edge_to_remove)
            iterations_count += 1

            comps = _get_components(node_list, active_edges)
            q = _compute_modularity(comps)
            if q > best_q:
                best_q = q
                best_partition = comps

        best_q = round(max(-1.0, min(1.0, best_q)), 4)

        # Build CommunityResult objects and signals
        community_results: List[CommunityResult] = []
        signals: List[StructuralSignal] = []

        for idx, members in enumerate(best_partition):
            sorted_m = sorted(members)
            m_set = set(sorted_m)
            min_id = sorted_m[0]
            comm_id = f"urn:comm:{idx}:{_deterministic_hash(min_id, 8)}"

            internal_rels: List[str] = []
            external_rels: List[str] = []
            ev_ids_set: Set[str] = set()

            for rel in relationships:
                src = rel["source_entity_id"]
                tgt = rel["target_entity_id"]
                rid = rel["relationship_id"]
                in_src = src in m_set
                in_tgt = tgt in m_set

                if in_src and in_tgt:
                    internal_rels.append(rid)
                    for ev in rel.get("evidence_ids", []):
                        ev_ids_set.add(ev)
                elif in_src or in_tgt:
                    external_rels.append(rid)

            internal_rels_sorted = sorted(list(set(internal_rels)))
            external_rels_sorted = sorted(list(set(external_rels)))
            ev_ids_sorted = sorted(list(ev_ids_set))

            num_members = len(sorted_m)
            if num_members > 1:
                possible_edges = num_members * (num_members - 1) / 2.0
                density = round(len(internal_rels_sorted) / possible_edges, 3)
            else:
                density = 0.0

            explanation = (
                f"Deterministic community comprising {num_members} entities with "
                f"{len(internal_rels_sorted)} internal connections and "
                f"{len(external_rels_sorted)} external connections (density: {density:.3f})."
            )
            limitations = [
                "Partition generated via deterministic Girvan-Newman edge-betweenness community detection.",
                "Communities reflect observed graph structure and may be influenced by missing edges.",
            ]

            comm_res = CommunityResult(
                community_id=comm_id,
                entity_ids=sorted_m,
                internal_relationship_ids=internal_rels_sorted,
                external_relationship_ids=external_rels_sorted,
                evidence_ids=ev_ids_sorted,
                density=density,
                member_count=num_members,
                explanation=explanation,
                limitations=limitations,
            )
            community_results.append(comm_res)

            # Signal for cohesive, dense communities
            if num_members >= 3 and density >= 0.5:
                sig_id = f"urn:sig:comm:{_deterministic_hash(f'{comm_id}:{density}')}"
                sig = StructuralSignal(
                    signal_id=sig_id,
                    signal_type=StructuralSignalType.DENSE_COMMUNITY,
                    entity_ids=sorted_m,
                    relationship_ids=internal_rels_sorted,
                    evidence_ids=ev_ids_sorted,
                    metric_value=density,
                    method="dense_community_threshold_rule",
                    explanation=(
                        f"Dense operational cluster detected: community '{comm_id}' exhibits "
                        f"internal edge density of {density:.3f} across {num_members} entities."
                    ),
                    limitations=limitations,
                )
                signals.append(sig)

        metric = AnalyticalMetric(
            metric_name="community_partition",
            entity_ids=node_list,
            relationship_ids=sorted(list({r["relationship_id"] for r in relationships})),
            evidence_ids=sorted(list({ev for r in relationships for ev in r.get("evidence_ids", [])})),
            value={
                "community_count": len(community_results),
                "modularity": best_q,
                "communities": [c.model_dump() for c in community_results],
            },
            method="girvan_newman_betweenness_partitioning",
            explanation=(
                f"Partitioned network of {len(node_list)} entities into {len(community_results)} "
                f"communities with modularity score Q = {best_q:.4f}."
            ),
            limitations=[
                "Girvan-Newman betweenness community detection is subject to network resolution limits.",
                "Modularity is computed assuming unweighted undirected topology.",
            ],
        )

        return {
            "communities": community_results,
            "community_count": len(community_results),
            "modularity": best_q,
            "signals": signals,
            "metric": metric,
        }
