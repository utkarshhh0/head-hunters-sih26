"""Deterministic Multi-Signal Pattern Detection Engine (Phase 4D).

Correlates independent structural and temporal signals to detect meaningful investigative
patterns across the knowledge graph.

Key Invariants:
1. Multi-Signal Requirement: A pattern is strictly formed only when at least TWO independent
   signals converge on the same entity or context (e.g. structural bridge + high degree + temporal burst).
   Single-metric flags never produce a pattern.
2. Neutral Investigative Language: Uses neutral phrasing such as "Pattern Flagged for Investigation".
   Never infers guilt, criminality, illicit intent, mastermind status, or universal risk scores.
3. Zero LLM Dependencies: All explanations are deterministic templates interpolated from observed metrics.
4. Strict Provenance Traceability: Every pattern preserves contributing signal IDs, relationship IDs,
   and evidence IDs back to raw source provenance.
5. Zero Timestamp Fabrication: Time windows reflect strictly observed timestamp boundaries.
"""

from dataclasses import dataclass
from datetime import datetime
import hashlib
from typing import Any, Dict, List, Optional, Set, Tuple

from neo4j import Driver

from app.schemas.analytics import (
    MultiSignalPattern,
    PatternType,
    StructuralSignal,
    StructuralSignalType,
    TemporalSignal,
    TemporalSignalType,
    TimeWindow,
)
from app.graph.config import Neo4jConfig
from app.graph.query import Neo4jGraphQuery
from app.analytics.structural import StructuralAnalyzer
from app.analytics.temporal import TemporalAnalyzer, parse_iso_datetime


def _deterministic_hash(val: str, length: int = 12) -> str:
    """Generates a deterministic hex hash prefix from an input string."""
    return hashlib.sha256(val.encode("utf-8")).hexdigest()[:length]


@dataclass(frozen=True)
class PatternDetectionConfig:
    """Configurable heuristic thresholds for multi-signal pattern detection.

    These thresholds are analytical heuristic filters designed to prioritize
    topological contexts for human review, not validated claims of criminality.
    """
    bridge_threshold: float = 0.0
    high_degree_threshold: int = 2
    min_burst_interactions: int = 2
    max_burst_span_seconds: Optional[float] = None


class PatternDetector:
    """Investigative multi-signal pattern detection engine."""

    def __init__(
        self,
        query: Optional[Neo4jGraphQuery] = None,
        driver: Optional[Driver] = None,
        config: Optional[Neo4jConfig] = None,
        detection_config: Optional[PatternDetectionConfig] = None,
    ):
        self.structural_analyzer = StructuralAnalyzer(query=query, driver=driver, config=config)
        self.temporal_analyzer = TemporalAnalyzer(query=query, driver=driver, config=config)
        self.config = detection_config or PatternDetectionConfig()

    def close(self) -> None:
        """Closes internal analyzer connections."""
        self.structural_analyzer.close()
        self.temporal_analyzer.close()

    def __enter__(self) -> "PatternDetector":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def evaluate_signals(
        self,
        structural_signals: List[StructuralSignal],
        temporal_signals: List[TemporalSignal],
        entities: Optional[List[Dict[str, Any]]] = None,
        relationships: Optional[List[Dict[str, Any]]] = None,
    ) -> List[MultiSignalPattern]:
        """Correlates precomputed structural and temporal signals into multi-signal patterns.

        Strictly enforces that every pattern requires at least TWO distinct, independent signals.
        """
        entity_name_map: Dict[str, str] = {}
        if entities:
            for e in entities:
                eid = e.get("entity_id")
                if eid:
                    entity_name_map[eid] = e.get("canonical_name", eid)

        # Index structural signals by entity ID and signal type
        bridge_signals_by_entity: Dict[str, StructuralSignal] = {}
        degree_signals_by_entity: Dict[str, StructuralSignal] = {}
        dense_comm_signals: List[StructuralSignal] = []

        for sig in structural_signals:
            if sig.signal_type == StructuralSignalType.BRIDGE_CANDIDATE:
                for eid in sig.entity_ids:
                    bridge_signals_by_entity[eid] = sig
            elif sig.signal_type == StructuralSignalType.HIGH_DEGREE_CENTRALITY:
                for eid in sig.entity_ids:
                    degree_signals_by_entity[eid] = sig
            elif sig.signal_type == StructuralSignalType.DENSE_COMMUNITY:
                dense_comm_signals.append(sig)

        # Index temporal signals by entity ID
        burst_signals_by_entity: Dict[str, List[TemporalSignal]] = {}
        for sig in temporal_signals:
            if sig.signal_type == TemporalSignalType.BURST_COMMUNICATION_WINDOW:
                for eid in sig.entity_ids:
                    if eid not in burst_signals_by_entity:
                        burst_signals_by_entity[eid] = []
                    burst_signals_by_entity[eid].append(sig)

        detected_patterns: List[MultiSignalPattern] = []
        seen_pattern_keys: Set[str] = set()

        # ---------------------------------------------------------------------
        # Rule 1: Intermediary Hub with Concentrated Activity (INTERMEDIARY_HUB_BURST)
        # Requires:
        # 1. Structural BRIDGE_CANDIDATE signal for entity E
        # 2. Structural HIGH_DEGREE_CENTRALITY signal for entity E
        # 3. Temporal BURST_COMMUNICATION_WINDOW signal involving entity E
        # ---------------------------------------------------------------------
        candidate_entities = sorted(list(set(bridge_signals_by_entity.keys())))

        for eid in candidate_entities:
            bridge_sig = bridge_signals_by_entity.get(eid)
            deg_sig = degree_signals_by_entity.get(eid)
            burst_sigs = burst_signals_by_entity.get(eid, [])

            # Strict three-signal convergence requirement:
            # 1. Structural BRIDGE_CANDIDATE
            # 2. Structural HIGH_DEGREE_CENTRALITY
            # 3. Temporal BURST_COMMUNICATION_WINDOW
            #
            # All three must converge on the same entity.
            if not (bridge_sig and deg_sig and burst_sigs):
                continue

            contributing_signals = [bridge_sig, deg_sig, *burst_sigs]

            # Must have at least one structural signal and at least one temporal burst signal
            has_structural = any(isinstance(s, StructuralSignal) for s in contributing_signals)
            has_temporal = any(isinstance(s, TemporalSignal) for s in contributing_signals)
            if not (has_structural and has_temporal):
                continue

            pattern_key = f"hub_burst:{eid}"
            if pattern_key in seen_pattern_keys:
                continue
            seen_pattern_keys.add(pattern_key)

            # Collect traceable identifiers
            contributing_ids = sorted(list({s.signal_id for s in contributing_signals}))
            contributing_types = sorted(list({s.signal_type.value for s in contributing_signals}))

            all_rel_ids: Set[str] = set()
            all_ev_ids: Set[str] = set()
            all_ent_ids: Set[str] = {eid}

            min_start: Optional[datetime] = None
            max_end: Optional[datetime] = None

            for s in contributing_signals:
                for r in s.relationship_ids:
                    all_rel_ids.add(r)
                for ev in s.evidence_ids:
                    all_ev_ids.add(ev)
                for ent in s.entity_ids:
                    all_ent_ids.add(ent)
                if s.time_window:
                    st = parse_iso_datetime(s.time_window.start_time)
                    et = parse_iso_datetime(s.time_window.end_time)
                    if st and (min_start is None or st < min_start):
                        min_start = st
                    if et and (max_end is None or et > max_end):
                        max_end = et

            window_obj = None
            if min_start is not None or max_end is not None:
                window_obj = TimeWindow(start_time=min_start, end_time=max_end)

            pat_id = f"urn:pattern:hub_burst:{_deterministic_hash(f'{eid}:{contributing_ids}')}"
            name = entity_name_map.get(eid, eid)

            bridge_val = bridge_sig.metric_value
            deg_val = int(deg_sig.metric_value)
            burst_rate = burst_sigs[0].metric_value

            explanation = (
                f"Pattern Flagged for Investigation: Entity '{name}' (ID: {eid}) exhibits a "
                f"multi-signal topological and temporal convergence: "
                f"(1) structural role as a BRIDGE_CANDIDATE with betweenness centrality of {bridge_val:.4f}, "
                f"(2) elevated connectivity with {deg_val} direct relationships, and "
                f"(3) participation in {len(burst_sigs)} BURST_COMMUNICATION_WINDOW event(s) "
                f"(peak rate: {burst_rate:.2f} interactions/hr). "
                f"Context analytically prioritized for human investigative assessment."
            )

            limitations = [
                "Pattern generated via deterministic heuristic rule linking independent structural and temporal signals.",
                "Thresholds are analytical prioritization filters, not verified indicators of illicit intent or wrongdoing.",
                "Subject to completeness of observed relationships within current graph slice; unrecorded offline interactions are omitted.",
            ]

            pattern = MultiSignalPattern(
                pattern_id=pat_id,
                pattern_type=PatternType.INTERMEDIARY_HUB_BURST,
                title=f"Pattern Flagged for Investigation: Intermediary Hub with Concentrated Activity ({name})",
                entity_ids=sorted(list(all_ent_ids)),
                contributing_signal_ids=contributing_ids,
                contributing_signal_types=contributing_types,
                relationship_ids=sorted(list(all_rel_ids)),
                evidence_ids=sorted(list(all_ev_ids)),
                time_window=window_obj,
                detection_method="heuristic_multi_signal_convergence:intermediary_hub_burst",
                explanation=explanation,
                limitations=limitations,
            )
            detected_patterns.append(pattern)

        # ---------------------------------------------------------------------
        # Rule 2: Dense Community with Internal Burst Activity (DENSE_COMMUNITY_BURST)
        # Requires:
        # 1. Structural DENSE_COMMUNITY signal for community member set M
        # 2. Temporal BURST_COMMUNICATION_WINDOW signal between members of M
        # ---------------------------------------------------------------------
        for comm_sig in dense_comm_signals:
            comm_members_set = set(comm_sig.entity_ids)

            # Find matching temporal burst signals where all involved entities belong to the community
            matching_bursts = [
                bs for bs in temporal_signals
                if bs.signal_type == TemporalSignalType.BURST_COMMUNICATION_WINDOW
                and set(bs.entity_ids).issubset(comm_members_set)
            ]

            if not matching_bursts:
                continue

            contributing = [comm_sig] + matching_bursts
            contributing_ids = sorted(list({s.signal_id for s in contributing}))
            contributing_types = sorted(list({s.signal_type.value for s in contributing}))

            all_rel_ids = set(comm_sig.relationship_ids)
            all_ev_ids = set(comm_sig.evidence_ids)
            all_ent_ids = set(comm_sig.entity_ids)

            min_start = None
            max_end = None

            for bs in matching_bursts:
                for r in bs.relationship_ids:
                    all_rel_ids.add(r)
                for ev in bs.evidence_ids:
                    all_ev_ids.add(ev)
                if bs.time_window:
                    st = parse_iso_datetime(bs.time_window.start_time)
                    et = parse_iso_datetime(bs.time_window.end_time)
                    if st and (min_start is None or st < min_start):
                        min_start = st
                    if et and (max_end is None or et > max_end):
                        max_end = et

            window_obj = None
            if min_start is not None or max_end is not None:
                window_obj = TimeWindow(start_time=min_start, end_time=max_end)

            min_eid = sorted(list(comm_members_set))[0]
            pat_id = f"urn:pattern:comm_burst:{_deterministic_hash(f'{min_eid}:{contributing_ids}')}"

            explanation = (
                f"Pattern Flagged for Investigation: Cohesive operational cluster comprising "
                f"{len(comm_members_set)} entities (density: {comm_sig.metric_value:.3f}) coincides with "
                f"{len(matching_bursts)} internal BURST_COMMUNICATION_WINDOW event(s). "
                f"Internal communications show elevated frequency within a compressed operational timeframe."
            )

            limitations = [
                "Pattern identified via deterministic rule joining dense community structure with internal temporal bursts.",
                "Heuristic classification intended for investigative prioritization, not evidence of criminal conspiracy.",
                "Missing communication logs or external links may alter observed density.",
            ]

            pattern = MultiSignalPattern(
                pattern_id=pat_id,
                pattern_type=PatternType.DENSE_COMMUNITY_BURST,
                title=f"Pattern Flagged for Investigation: Dense Cluster with Concentrated Activity (Size {len(comm_members_set)})",
                entity_ids=sorted(list(all_ent_ids)),
                contributing_signal_ids=contributing_ids,
                contributing_signal_types=contributing_types,
                relationship_ids=sorted(list(all_rel_ids)),
                evidence_ids=sorted(list(all_ev_ids)),
                time_window=window_obj,
                detection_method="heuristic_multi_signal_convergence:dense_community_burst",
                explanation=explanation,
                limitations=limitations,
            )
            detected_patterns.append(pattern)

        # Sort patterns deterministically by pattern_id
        return sorted(detected_patterns, key=lambda p: p.pattern_id)

    def detect_patterns(
        self,
        entity_id: Optional[str] = None,
        subgraph: Optional[Dict[str, Any]] = None,
        limit: int = 500,
    ) -> List[MultiSignalPattern]:
        """Runs end-to-end multi-signal pattern detection against live Neo4j or supplied subgraph.

        Executes:
        1. Betweenness centrality (BRIDGE_CANDIDATE signals)
        2. Degree metrics (HIGH_DEGREE_CENTRALITY signals)
        3. Community detection (DENSE_COMMUNITY signals)
        4. Interaction concentration (BURST_COMMUNICATION_WINDOW signals)
        5. Multi-signal pattern correlation and synthesis
        """
        # 1. Structural Analysis
        bc_res = self.structural_analyzer.compute_betweenness_centrality(
            subgraph=subgraph,
            bridge_threshold=self.config.bridge_threshold,
            limit=limit,
        )
        deg_res = self.structural_analyzer.compute_degree_metrics(
            entity_id=entity_id,
            subgraph=subgraph,
            high_degree_threshold=self.config.high_degree_threshold,
            limit=limit,
        )
        comm_res = self.structural_analyzer.detect_communities(
            subgraph=subgraph,
            limit=limit,
        )

        structural_signals: List[StructuralSignal] = []
        structural_signals.extend(bc_res["bridge_candidates"])
        structural_signals.extend(deg_res["signals"])
        structural_signals.extend(comm_res["signals"])

        # 2. Temporal Analysis
        temp_res = self.temporal_analyzer.analyze_interaction_concentration(
            entity_id=entity_id,
            subgraph=subgraph,
            min_interactions=self.config.min_burst_interactions,
            max_span_seconds=self.config.max_burst_span_seconds,
            limit=limit,
        )
        temporal_signals: List[TemporalSignal] = temp_res["signals"]

        # Resolve entities from subgraph or query layer
        entities, relationships = self.structural_analyzer._resolve_subgraph(
            entity_id=entity_id,
            subgraph=subgraph,
            limit=limit,
        )

        return self.evaluate_signals(
            structural_signals=structural_signals,
            temporal_signals=temporal_signals,
            entities=entities,
            relationships=relationships,
        )
