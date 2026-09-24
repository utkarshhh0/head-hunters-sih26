"""Deterministic Relationship Pre-Aggregation Engine.

Aggregates multiple Phase-2 Relationship observations sharing the same logical
relationship_id into a single canonical aggregated relationship representation.

Strict Rules:
1. Approved relationship types: COMMUNICATED_WITH, OWNED_BY, ASSOCIATED_WITH, TRANSACTED_WITH.
   Unsupported types (e.g. MEMBER_OF, LOCATED_AT, CO_OCCURRED_WITH) raise ValueError.
2. interaction_count equals exact number of contributing observations.
3. Zero timestamp fabrication: first_seen and last_seen use min/max of actual timestamps.
   If none exist, both remain None.
4. Confidence equals maximum contributing confidence.
5. Origin strictly remains EXTRACTED.
6. evidence_ids are deduplicated deterministically.
7. Numeric attributes (e.g. call duration, amount) aggregate sum/min/max.
8. Nonnumeric attributes are deterministically preserved.
"""

import json
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.relationship import Relationship, RelationshipType, RelationshipOrigin

# Strictly authorized Phase-2 relationship types for Phase 3 persistence
APPROVED_RELATIONSHIP_TYPES: Set[str] = {
    RelationshipType.COMMUNICATED_WITH.value,
    RelationshipType.OWNED_BY.value,
    RelationshipType.ASSOCIATED_WITH.value,
    RelationshipType.TRANSACTED_WITH.value,
}


class AggregatedRelationship(BaseModel):
    """Aggregate state of multiple relationship observations sharing one logical relationship_id."""

    model_config = ConfigDict(extra="forbid")

    relationship_id: str = Field(..., description="Unique URN for logical relationship")
    source_entity_id: str = Field(..., description="Canonical source entity URN")
    target_entity_id: str = Field(..., description="Canonical target entity URN")
    relationship_type: str = Field(..., description="Authorized relationship type")
    origin: str = Field(default=RelationshipOrigin.EXTRACTED.value, description="Relationship origin")
    confidence: float = Field(..., description="Maximum confidence across observations")
    first_seen: Optional[datetime] = Field(None, description="Earliest observed actual timestamp")
    last_seen: Optional[datetime] = Field(None, description="Latest observed actual timestamp")
    interaction_count: int = Field(..., description="Total count of contributing observations")
    evidence_ids: List[str] = Field(default_factory=list, description="Deduplicated evidence IDs")
    attributes_json: str = Field(default="{}", description="JSON string of aggregated domain attributes")


def _aggregate_attributes(attributes_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Deterministically aggregates numeric and categorical attributes across observations."""
    if not attributes_list:
        return {}

    # Group all values by attribute key
    grouped_values: Dict[str, List[Any]] = defaultdict(list)
    for attrs in attributes_list:
        if not attrs:
            continue
        for k, v in attrs.items():
            if v is not None:
                grouped_values[k].append(v)

    aggregated: Dict[str, Any] = {}
    for key in sorted(grouped_values.keys()):
        values = grouped_values[key]
        if not values:
            continue

        # Check if all values are numeric (int or float, not bool)
        is_numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values)

        if is_numeric:
            total = sum(values)
            min_val = min(values)
            max_val = max(values)
            # Preserve integers if all values are ints
            if all(isinstance(v, int) for v in values):
                aggregated[key] = {
                    "sum": int(total),
                    "min": int(min_val),
                    "max": int(max_val),
                    "count": len(values),
                }
            else:
                aggregated[key] = {
                    "sum": round(float(total), 4),
                    "min": round(float(min_val), 4),
                    "max": round(float(max_val), 4),
                    "count": len(values),
                }
        else:
            # Deterministic categorical preservation
            unique_values: List[str] = []
            for v in values:
                str_v = str(v)
                if str_v not in unique_values:
                    unique_values.append(str_v)
            unique_values.sort()

            if len(unique_values) == 1:
                aggregated[key] = unique_values[0]
            else:
                aggregated[key] = unique_values

    return aggregated


def pre_aggregate_relationships(relationships: List[Relationship]) -> List[AggregatedRelationship]:
    """Groups relationships by logical relationship_id and calculates deterministic aggregate states."""
    if relationships is None:
        raise ValueError("Relationships list cannot be None.")

    grouped: Dict[str, List[Relationship]] = defaultdict(list)
    for rel in relationships:
        # Validate relationship type against approved Phase-2 types
        type_str = rel.relationship_type.value if hasattr(rel.relationship_type, "value") else str(rel.relationship_type)
        if type_str not in APPROVED_RELATIONSHIP_TYPES:
            raise ValueError(
                f"Unsupported relationship type: {type_str!r}. "
                f"Phase 3 accepts only: {sorted(APPROVED_RELATIONSHIP_TYPES)}"
            )

        grouped[rel.relationship_id].append(rel)

    aggregates: List[AggregatedRelationship] = []

    # Iterate deterministically by sorted relationship_id
    for rel_id in sorted(grouped.keys()):
        obs_list = grouped[rel_id]
        first_obs = obs_list[0]

        canonical_source = first_obs.source_entity_id
        canonical_target = first_obs.target_entity_id
        rel_type_str = first_obs.relationship_type.value if hasattr(first_obs.relationship_type, "value") else str(first_obs.relationship_type)

        # Verify endpoint and type consistency across all observations sharing relationship_id
        for obs in obs_list:
            obs_type_str = obs.relationship_type.value if hasattr(obs.relationship_type, "value") else str(obs.relationship_type)
            if obs.source_entity_id != canonical_source or obs.target_entity_id != canonical_target or obs_type_str != rel_type_str:
                raise ValueError(
                    f"Inconsistent endpoints or type for relationship_id {rel_id!r}: "
                    f"({canonical_source} -> {canonical_target}, {rel_type_str}) vs "
                    f"({obs.source_entity_id} -> {obs.target_entity_id}, {obs_type_str})"
                )

        # 1. interaction_count: exact count of contributing observations
        interaction_count = len(obs_list)

        # 2. Zero-fabrication timestamps: extract actual non-None timestamp_context
        actual_timestamps: List[datetime] = [
            obs.timestamp_context for obs in obs_list if obs.timestamp_context is not None
        ]
        first_seen = min(actual_timestamps) if actual_timestamps else None
        last_seen = max(actual_timestamps) if actual_timestamps else None

        # 3. Maximum confidence
        max_confidence = max(obs.confidence for obs in obs_list)

        # 4. Deduplicated evidence IDs
        dedup_evidence: List[str] = []
        for obs in obs_list:
            for ev_id in obs.evidence_ids:
                if ev_id not in dedup_evidence:
                    dedup_evidence.append(ev_id)
        dedup_evidence.sort()

        # 5. Attributes aggregation
        all_attrs = [obs.attributes for obs in obs_list]
        agg_attrs = _aggregate_attributes(all_attrs)
        attrs_json = json.dumps(agg_attrs, sort_keys=True)

        agg = AggregatedRelationship(
            relationship_id=rel_id,
            source_entity_id=canonical_source,
            target_entity_id=canonical_target,
            relationship_type=rel_type_str,
            origin=RelationshipOrigin.EXTRACTED.value,
            confidence=max_confidence,
            first_seen=first_seen,
            last_seen=last_seen,
            interaction_count=interaction_count,
            evidence_ids=dedup_evidence,
            attributes_json=attrs_json,
        )
        aggregates.append(agg)

    return aggregates
