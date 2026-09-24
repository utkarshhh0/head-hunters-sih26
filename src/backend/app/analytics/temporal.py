"""Deterministic Temporal Analysis Engine.

Provides Phase 4C temporal analytics against the Neo4j knowledge graph using actual
Phase-3 relationship temporal fields (first_seen, last_seen, interaction_count):
1. Activity within a supplied time window: isolates active relationships and entities
   without timestamp fabrication.
2. Interaction/activity concentration: identifies burst communication and high-frequency
   interaction windows, emitting BURST_COMMUNICATION_WINDOW signals.
3. Temporal relationship/activity summaries: computes activity lifespans, total interactions,
   and explicit dated vs. undated relationship accounting.

Strict Rules:
- Zero fabrication of timestamps or synthetic dates.
- Undated relationships are explicitly preserved and accounted for, never fabricated.
- Purely descriptive, explainable outputs retaining full evidence provenance.
"""

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional, Set, Tuple

from neo4j import Driver

from app.schemas.analytics import (
    AnalyticalMetric,
    TemporalSignal,
    TemporalSignalType,
    TemporalSummary,
    TimeWindow,
)
from app.graph.config import Neo4jConfig, get_driver
from app.graph.query import Neo4jGraphQuery


def _deterministic_hash(val: str, length: int = 12) -> str:
    """Generates a deterministic hex hash prefix from an input string."""
    return hashlib.sha256(val.encode("utf-8")).hexdigest()[:length]


def parse_iso_datetime(val: Any) -> Optional[datetime]:
    """Deterministically parses an ISO timestamp string or datetime object into a timezone-aware UTC datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None
    return None


class TemporalAnalyzer:
    """Investigative temporal analysis engine."""

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

    def __enter__(self) -> "TemporalAnalyzer":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _resolve_subgraph(
        self,
        entity_id: Optional[str] = None,
        subgraph: Optional[Dict[str, Any]] = None,
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
                hops=1,
                include_undated=True,
                limit=limit,
            )
            return trav.get("entities", []), trav.get("relationships", [])

        temp_sub = self.query.get_temporal_subgraph(
            include_undated=True,
            limit=limit,
        )
        entities = temp_sub.get("entities", [])
        relationships = temp_sub.get("relationships", [])
        return entities, relationships

    # -------------------------------------------------------------------------
    # 1. Activity Within a Supplied Time Window
    # -------------------------------------------------------------------------
    def analyze_window_activity(
        self,
        time_window: TimeWindow,
        entity_id: Optional[str] = None,
        subgraph: Optional[Dict[str, Any]] = None,
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Analyzes network activity strictly active within a supplied time window.

        Excludes undated relationships from dated window metrics while explicitly accounting
        for them in undated counts. Zero timestamp fabrication.
        """
        entities, relationships = self._resolve_subgraph(
            entity_id=entity_id,
            subgraph=subgraph,
            limit=limit,
        )

        w_start = parse_iso_datetime(time_window.start_time)
        w_end = parse_iso_datetime(time_window.end_time)

        active_relationships: List[Dict[str, Any]] = []
        undated_relationships: List[Dict[str, Any]] = []
        out_of_window_relationships: List[Dict[str, Any]] = []

        active_entity_ids: Set[str] = set()
        evidence_ids_set: Set[str] = set()
        total_interactions = 0

        earliest_seen: Optional[datetime] = None
        latest_seen: Optional[datetime] = None

        for rel in relationships:
            # Check target entity incident condition if entity_id specified
            if entity_id:
                if rel["source_entity_id"] != entity_id and rel["target_entity_id"] != entity_id:
                    continue

            fs_raw = rel.get("first_seen")
            ls_raw = rel.get("last_seen")

            # Preserve undated status without fabrication
            if fs_raw is None or ls_raw is None:
                undated_relationships.append(rel)
                continue

            fs = parse_iso_datetime(fs_raw)
            ls = parse_iso_datetime(ls_raw)

            if fs is None or ls is None:
                undated_relationships.append(rel)
                continue

            # Active in window test:
            # rel.last_seen >= window.start AND rel.first_seen <= window.end
            in_window = True
            if w_start is not None and ls < w_start:
                in_window = False
            if w_end is not None and fs > w_end:
                in_window = False

            if in_window:
                active_relationships.append(rel)
                src = rel["source_entity_id"]
                tgt = rel["target_entity_id"]
                active_entity_ids.add(src)
                active_entity_ids.add(tgt)

                count = int(rel.get("interaction_count", 1))
                total_interactions += count

                for ev in rel.get("evidence_ids", []):
                    evidence_ids_set.add(ev)

                if earliest_seen is None or fs < earliest_seen:
                    earliest_seen = fs
                if latest_seen is None or ls > latest_seen:
                    latest_seen = ls
            else:
                out_of_window_relationships.append(rel)

        sorted_entity_ids = sorted(list(active_entity_ids))
        sorted_rel_ids = sorted([r["relationship_id"] for r in active_relationships])
        sorted_ev_ids = sorted(list(evidence_ids_set))

        scope_desc = f"Entity '{entity_id}'" if entity_id else "Evaluated network"
        window_desc = (
            f"window [{w_start.isoformat() if w_start else 'OPEN'} to "
            f"{w_end.isoformat() if w_end else 'OPEN'}]"
        )
        explanation = (
            f"{scope_desc} activity in {window_desc}: {len(sorted_rel_ids)} active relationships "
            f"({total_interactions} total interactions) involving {len(sorted_entity_ids)} entities. "
            f"{len(undated_relationships)} undated relationship(s) excluded."
        )

        limitations = [
            "Metrics evaluate exclusively relationships with explicit timestamps.",
            f"{len(undated_relationships)} relationship(s) lacking timestamps were excluded from window metrics without fabrication.",
        ]

        metric = AnalyticalMetric(
            metric_name="window_activity",
            entity_ids=sorted_entity_ids,
            relationship_ids=sorted_rel_ids,
            evidence_ids=sorted_ev_ids,
            value={
                "active_entity_count": len(sorted_entity_ids),
                "active_relationship_count": len(sorted_rel_ids),
                "total_interactions": total_interactions,
                "undated_excluded_count": len(undated_relationships),
                "earliest_active_timestamp": earliest_seen.isoformat() if earliest_seen else None,
                "latest_active_timestamp": latest_seen.isoformat() if latest_seen else None,
            },
            method="temporal_window_filter",
            explanation=explanation,
            limitations=limitations,
            time_window=time_window,
        )

        return {
            "time_window": time_window,
            "active_entity_ids": sorted_entity_ids,
            "active_relationship_ids": sorted_rel_ids,
            "active_relationships": active_relationships,
            "total_interactions": total_interactions,
            "undated_relationships_excluded_count": len(undated_relationships),
            "evidence_ids": sorted_ev_ids,
            "metric": metric,
        }

    # -------------------------------------------------------------------------
    # 2. Interaction / Activity Concentration
    # -------------------------------------------------------------------------
    def analyze_interaction_concentration(
        self,
        entity_id: Optional[str] = None,
        subgraph: Optional[Dict[str, Any]] = None,
        min_interactions: int = 2,
        max_span_seconds: Optional[float] = None,
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Identifies burst communication and concentrated interaction periods.

        Emits BURST_COMMUNICATION_WINDOW signals for relationships demonstrating
        elevated interaction frequency over a compressed temporal span.
        """
        entities, relationships = self._resolve_subgraph(
            entity_id=entity_id,
            subgraph=subgraph,
            limit=limit,
        )

        signals: List[TemporalSignal] = []
        rel_evaluations: List[Dict[str, Any]] = []

        all_rel_ids: List[str] = []
        all_ev_ids_set: Set[str] = set()

        for rel in relationships:
            if entity_id:
                if rel["source_entity_id"] != entity_id and rel["target_entity_id"] != entity_id:
                    continue

            rel_id = rel["relationship_id"]
            all_rel_ids.append(rel_id)

            for ev in rel.get("evidence_ids", []):
                all_ev_ids_set.add(ev)

            fs = parse_iso_datetime(rel.get("first_seen"))
            ls = parse_iso_datetime(rel.get("last_seen"))
            count = int(rel.get("interaction_count", 1))

            # Skip undated relationships without fabrication
            if fs is None or ls is None:
                continue

            span_seconds = max((ls - fs).total_seconds(), 0.0)

            # Check burst qualification
            qualifies_count = count >= min_interactions
            qualifies_span = (max_span_seconds is None) or (span_seconds <= max_span_seconds)

            # Concentration rate: interactions per hour (with floor for instantaneous spans)
            effective_hours = max(span_seconds / 3600.0, 0.01)
            rate_per_hour = round(count / effective_hours, 2)

            eval_entry = {
                "relationship_id": rel_id,
                "interaction_count": count,
                "first_seen": fs.isoformat(),
                "last_seen": ls.isoformat(),
                "span_seconds": span_seconds,
                "rate_per_hour": rate_per_hour,
                "is_burst": qualifies_count and qualifies_span,
            }
            rel_evaluations.append(eval_entry)

            if qualifies_count and qualifies_span:
                sig_id = f"urn:sig:temp:burst:{_deterministic_hash(f'{rel_id}:{count}:{span_seconds}')}"
                ent_ids = sorted([rel["source_entity_id"], rel["target_entity_id"]])
                ev_ids = sorted(rel.get("evidence_ids", []))

                explanation = (
                    f"Burst communication window on relationship '{rel_id}': {count} interactions "
                    f"occurred within {span_seconds:.0f} seconds ({fs.isoformat()} to {ls.isoformat()}), "
                    f"yielding an interaction frequency of {rate_per_hour:.2f} interactions/hr."
                )

                limitations = [
                    "Concentration calculated strictly from pre-aggregated relationship timestamp bounds.",
                    "Missing or unrecorded intermediate calls cannot be interpolated.",
                ]

                sig = TemporalSignal(
                    signal_id=sig_id,
                    signal_type=TemporalSignalType.BURST_COMMUNICATION_WINDOW,
                    entity_ids=ent_ids,
                    relationship_ids=[rel_id],
                    evidence_ids=ev_ids,
                    metric_value=rate_per_hour,
                    method="temporal_span_concentration",
                    explanation=explanation,
                    limitations=limitations,
                    time_window=TimeWindow(start_time=fs, end_time=ls),
                )
                signals.append(sig)

        # Sort signals by rate_per_hour descending, signal_id ascending
        signals = sorted(signals, key=lambda s: (-s.metric_value, s.signal_id))

        metric = AnalyticalMetric(
            metric_name="activity_concentration",
            entity_ids=[entity_id] if entity_id else sorted(list({e["entity_id"] for e in entities})),
            relationship_ids=sorted(all_rel_ids),
            evidence_ids=sorted(list(all_ev_ids_set)),
            value={
                "evaluated_relationship_count": len(rel_evaluations),
                "burst_signal_count": len(signals),
                "max_interaction_rate": signals[0].metric_value if signals else 0.0,
            },
            method="temporal_span_concentration",
            explanation=(
                f"Evaluated interaction concentration across {len(rel_evaluations)} dated relationships. "
                f"Detected {len(signals)} burst communication window signal(s)."
            ),
            limitations=[
                "Calculated strictly on actual relationship first_seen and last_seen timestamps.",
                "Undated relationships were excluded from burst evaluations.",
            ],
        )

        return {
            "entity_id": entity_id,
            "evaluations": rel_evaluations,
            "signals": signals,
            "signal_count": len(signals),
            "metric": metric,
        }

    # -------------------------------------------------------------------------
    # 3. Temporal Relationship / Activity Summaries
    # -------------------------------------------------------------------------
    def summarize_temporal_activity(
        self,
        entity_id: Optional[str] = None,
        subgraph: Optional[Dict[str, Any]] = None,
        limit: int = 500,
    ) -> TemporalSummary:
        """Generates a comprehensive temporal activity summary for an entity or network slice.

        Calculates active lifespan, dated vs undated relationship distribution, and preserves
        evidence references without timestamp fabrication.
        """
        entities, relationships = self._resolve_subgraph(
            entity_id=entity_id,
            subgraph=subgraph,
            limit=limit,
        )

        # Filter incident relationships if entity_id specified
        if entity_id:
            rels_to_eval = [
                r for r in relationships
                if r["source_entity_id"] == entity_id or r["target_entity_id"] == entity_id
            ]
        else:
            rels_to_eval = relationships

        dated_rels: List[Dict[str, Any]] = []
        undated_rels: List[Dict[str, Any]] = []
        all_ev_ids_set: Set[str] = set()
        all_rel_ids_set: Set[str] = set()

        earliest_seen: Optional[datetime] = None
        latest_seen: Optional[datetime] = None
        total_interactions = 0

        for r in rels_to_eval:
            all_rel_ids_set.add(r["relationship_id"])
            for ev in r.get("evidence_ids", []):
                all_ev_ids_set.add(ev)

            count = int(r.get("interaction_count", 1))
            total_interactions += count

            fs = parse_iso_datetime(r.get("first_seen"))
            ls = parse_iso_datetime(r.get("last_seen"))

            if fs is not None and ls is not None:
                dated_rels.append(r)
                if earliest_seen is None or fs < earliest_seen:
                    earliest_seen = fs
                if latest_seen is None or ls > latest_seen:
                    latest_seen = ls
            else:
                undated_rels.append(r)

        dated_count = len(dated_rels)
        undated_count = len(undated_rels)

        active_span_seconds: Optional[float] = None
        if earliest_seen is not None and latest_seen is not None:
            active_span_seconds = max((latest_seen - earliest_seen).total_seconds(), 0.0)

        scope_desc = f"Entity '{entity_id}'" if entity_id else "Evaluated network"
        if dated_count > 0:
            span_hrs = round(active_span_seconds / 3600.0, 2) if active_span_seconds is not None else 0.0
            explanation = (
                f"{scope_desc} temporal activity summary: {total_interactions} total interactions "
                f"across {dated_count} dated relationships spanning {span_hrs} hours "
                f"({earliest_seen.isoformat()} to {latest_seen.isoformat()}). "
                f"{undated_count} undated relationship(s) observed."
            )
        else:
            explanation = (
                f"{scope_desc} temporal activity summary: {total_interactions} total interactions "
                f"across {undated_count} undated relationships. Zero recorded timestamps."
            )

        limitations = [
            "Summary is derived strictly from recorded relationship timestamps.",
        ]
        if undated_count > 0:
            limitations.append(
                f"{undated_count} undated relationship(s) excluded from duration calculations without fabrication."
            )

        return TemporalSummary(
            entity_id=entity_id,
            first_seen=earliest_seen,
            last_seen=latest_seen,
            active_span_seconds=active_span_seconds,
            total_interactions=total_interactions,
            dated_relationship_count=dated_count,
            undated_relationship_count=undated_count,
            relationship_ids=sorted(list(all_rel_ids_set)),
            evidence_ids=sorted(list(all_ev_ids_set)),
            explanation=explanation,
            limitations=limitations,
        )
