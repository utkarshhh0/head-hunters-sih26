"""Analytical Domain Contracts for Phase 4 Graph Intelligence.

Provides structured models for:
- TimeWindow: temporal boundary filter with strict validation
- AnalyticalMetric: quantitative or structured graph/temporal result
- StructuralSignal: network topology signal (e.g., HIGH_DEGREE_CENTRALITY, BRIDGE_CANDIDATE)
- TemporalSignal: temporal activity signal (e.g., BURST_COMMUNICATION_WINDOW, INTERACTION_CONCENTRATION)
- CommunityResult: deterministic community detection partition
- TemporalSummary: descriptive temporal activity summary

All models preserve evidence references, entity IDs, relationship IDs, method explanations,
and analytical limitations without fabricating data or risk scores.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.finding import SignalType, AnalyticalSignal


class TimeWindow(BaseModel):
    """Temporal boundary filter for analytical queries."""

    model_config = ConfigDict(extra="forbid")

    start_time: Optional[datetime] = Field(None, description="Window start timestamp (inclusive)")
    end_time: Optional[datetime] = Field(None, description="Window end timestamp (inclusive)")

    @model_validator(mode="after")
    def validate_window(self) -> "TimeWindow":
        """Ensures start_time is not chronologically after end_time."""
        if self.start_time is not None and self.end_time is not None:
            if self.start_time > self.end_time:
                raise ValueError("start_time cannot be after end_time.")
        return self


class StructuralSignalType(str, Enum):
    """Classifications of structural network signals."""

    HIGH_DEGREE_CENTRALITY = "HIGH_DEGREE_CENTRALITY"
    BRIDGE_CANDIDATE = "BRIDGE_CANDIDATE"
    DENSE_COMMUNITY = "DENSE_COMMUNITY"
    ISOLATED_CLUSTER = "ISOLATED_CLUSTER"


class TemporalSignalType(str, Enum):
    """Classifications of temporal activity signals."""

    BURST_COMMUNICATION_WINDOW = "BURST_COMMUNICATION_WINDOW"
    INTERACTION_CONCENTRATION = "INTERACTION_CONCENTRATION"
    HIGH_FREQUENCY_ACTIVITY = "HIGH_FREQUENCY_ACTIVITY"
    PERSISTENT_INTERACTION = "PERSISTENT_INTERACTION"


class AnalyticalMetric(BaseModel):
    """Deterministic calculated graph or temporal metric result."""

    model_config = ConfigDict(extra="forbid")

    metric_name: str = Field(..., description="Descriptive identifier of the metric")
    entity_ids: List[str] = Field(default_factory=list, description="Associated entity URNs")
    relationship_ids: List[str] = Field(default_factory=list, description="Associated relationship URNs")
    evidence_ids: List[str] = Field(default_factory=list, description="Associated evidence URNs for traceability")
    value: Any = Field(..., description="Calculated metric value (scalar, distribution, or structured dict)")
    method: str = Field(..., description="Exact algorithm or calculation method used")
    explanation: str = Field(..., description="Deterministic explainable summary of the metric")
    limitations: List[str] = Field(default_factory=list, description="Analytical limitations and boundary conditions")
    time_window: Optional[TimeWindow] = Field(None, description="Optional temporal window under which metric was evaluated")


class StructuralSignal(BaseModel):
    """Structural/network topology signal flag."""

    model_config = ConfigDict(extra="forbid")

    signal_id: str = Field(..., description="Unique URN for signal e.g. urn:sig:struct:001")
    signal_type: StructuralSignalType = Field(..., description="Type of structural signal")
    entity_ids: List[str] = Field(default_factory=list, description="Entities involved in signal")
    relationship_ids: List[str] = Field(default_factory=list, description="Relationships involved in signal")
    evidence_ids: List[str] = Field(default_factory=list, description="Evidence provenance references")
    metric_value: float = Field(..., description="Underlying quantitative metric score")
    method: str = Field(..., description="Algorithm or rule used to derive signal")
    explanation: str = Field(..., description="Deterministic explainable rationale for signal")
    limitations: List[str] = Field(default_factory=list, description="Limitations of the structural signal")
    time_window: Optional[TimeWindow] = Field(None, description="Temporal window if signal was time-bounded")

    def to_phase1_signal(self) -> AnalyticalSignal:
        """Converts to Phase-1 AnalyticalSignal for backward compatibility.

        NOTE: Mappings such as:
        - DENSE_COMMUNITY → HIGH_DEGREE_CENTRALITY
        - ISOLATED_CLUSTER → HIGH_DEGREE_CENTRALITY
        are LOSSY BACKWARD-COMPATIBILITY mappings because Phase-1 SignalType
        does not represent all Phase-4 signal types.
        """
        st_map = {
            StructuralSignalType.HIGH_DEGREE_CENTRALITY: SignalType.HIGH_DEGREE_CENTRALITY,
            StructuralSignalType.BRIDGE_CANDIDATE: SignalType.BRIDGE_ACTOR,
            StructuralSignalType.DENSE_COMMUNITY: SignalType.HIGH_DEGREE_CENTRALITY,
            StructuralSignalType.ISOLATED_CLUSTER: SignalType.HIGH_DEGREE_CENTRALITY,
        }
        mapped_type = st_map.get(self.signal_type, SignalType.HIGH_DEGREE_CENTRALITY)
        return AnalyticalSignal(
            signal_id=self.signal_id,
            signal_type=mapped_type,
            entity_ids=self.entity_ids,
            relationship_ids=self.relationship_ids,
            metric_value=self.metric_value,
            rule_description=self.explanation,
        )


class TemporalSignal(BaseModel):
    """Temporal activity signal flag."""

    model_config = ConfigDict(extra="forbid")

    signal_id: str = Field(..., description="Unique URN for signal e.g. urn:sig:temp:001")
    signal_type: TemporalSignalType = Field(..., description="Type of temporal signal")
    entity_ids: List[str] = Field(default_factory=list, description="Entities involved in signal")
    relationship_ids: List[str] = Field(default_factory=list, description="Relationships involved in signal")
    evidence_ids: List[str] = Field(default_factory=list, description="Evidence provenance references")
    metric_value: float = Field(..., description="Calculated temporal metric or concentration ratio")
    method: str = Field(..., description="Method used to detect temporal pattern")
    explanation: str = Field(..., description="Deterministic explainable rationale for signal")
    limitations: List[str] = Field(default_factory=list, description="Limitations of the temporal signal")
    time_window: Optional[TimeWindow] = Field(None, description="Time window evaluated")

    def to_phase1_signal(self) -> AnalyticalSignal:
        """Converts to Phase-1 AnalyticalSignal for backward compatibility.

        NOTE: Mappings such as:
        - INTERACTION_CONCENTRATION → BURST_COMMUNICATION_WINDOW
        - HIGH_FREQUENCY_ACTIVITY → BURST_COMMUNICATION_WINDOW
        - PERSISTENT_INTERACTION → BURST_COMMUNICATION_WINDOW
        are LOSSY BACKWARD-COMPATIBILITY mappings because Phase-1 SignalType
        does not represent all Phase-4 signal types.
        """
        st_map = {
            TemporalSignalType.BURST_COMMUNICATION_WINDOW: SignalType.BURST_COMMUNICATION_WINDOW,
            TemporalSignalType.INTERACTION_CONCENTRATION: SignalType.BURST_COMMUNICATION_WINDOW,
            TemporalSignalType.HIGH_FREQUENCY_ACTIVITY: SignalType.BURST_COMMUNICATION_WINDOW,
            TemporalSignalType.PERSISTENT_INTERACTION: SignalType.BURST_COMMUNICATION_WINDOW,
        }
        mapped_type = st_map.get(self.signal_type, SignalType.BURST_COMMUNICATION_WINDOW)
        return AnalyticalSignal(
            signal_id=self.signal_id,
            signal_type=mapped_type,
            entity_ids=self.entity_ids,
            relationship_ids=self.relationship_ids,
            metric_value=self.metric_value,
            rule_description=self.explanation,
        )


class CommunityResult(BaseModel):
    """Result of deterministic community detection partitioning."""

    model_config = ConfigDict(extra="forbid")

    community_id: str = Field(..., description="Deterministic community URN e.g. urn:comm:0")
    entity_ids: List[str] = Field(default_factory=list, description="Member entity URNs (sorted)")
    internal_relationship_ids: List[str] = Field(default_factory=list, description="Edges between members")
    external_relationship_ids: List[str] = Field(default_factory=list, description="Edges connecting outside")
    evidence_ids: List[str] = Field(default_factory=list, description="Evidence provenance references")
    density: float = Field(..., description="Graph density of internal connections")
    member_count: int = Field(..., description="Number of entities in community")
    explanation: str = Field(..., description="Descriptive explanation of the community")
    limitations: List[str] = Field(default_factory=list, description="Algorithm limitations")


class TemporalSummary(BaseModel):
    """Comprehensive temporal activity summary for an entity or network slice."""

    model_config = ConfigDict(extra="forbid")

    entity_id: Optional[str] = Field(None, description="Entity URN if summary is entity-specific")
    first_seen: Optional[datetime] = Field(None, description="Earliest observed actual timestamp")
    last_seen: Optional[datetime] = Field(None, description="Latest observed actual timestamp")
    active_span_seconds: Optional[float] = Field(None, description="Total seconds between first and last seen")
    total_interactions: int = Field(..., description="Sum of interaction_count across evaluated edges")
    dated_relationship_count: int = Field(..., description="Number of edges with actual timestamps")
    undated_relationship_count: int = Field(..., description="Number of edges missing timestamps")
    relationship_ids: List[str] = Field(default_factory=list, description="Evaluated relationship IDs")
    evidence_ids: List[str] = Field(default_factory=list, description="Traceable evidence IDs")
    explanation: str = Field(..., description="Descriptive explanation of temporal activity")
    limitations: List[str] = Field(default_factory=list, description="Explicit caveats regarding missing dates")


class PatternType(str, Enum):
    """Classifications of multi-signal investigative patterns."""

    INTERMEDIARY_HUB_BURST = "INTERMEDIARY_HUB_BURST"
    DENSE_COMMUNITY_BURST = "DENSE_COMMUNITY_BURST"


class MultiSignalPattern(BaseModel):
    """Deterministic multi-signal investigative pattern combining independent structural and temporal signals."""

    model_config = ConfigDict(extra="forbid")

    pattern_id: str = Field(..., description="Unique deterministic URN for pattern e.g. urn:pattern:hub_burst:001")
    pattern_type: PatternType = Field(..., description="Classification category of the multi-signal pattern")
    title: str = Field(..., description="Neutral descriptive title e.g. Pattern Flagged for Investigation: Intermediary Hub with Concentrated Activity")
    entity_ids: List[str] = Field(default_factory=list, description="Referenced entity IDs involved in pattern")
    contributing_signal_ids: List[str] = Field(default_factory=list, description="IDs of the contributing independent signals (minimum 2)")
    contributing_signal_types: List[str] = Field(default_factory=list, description="Types of the contributing signals")
    relationship_ids: List[str] = Field(default_factory=list, description="Underlying relationship IDs involved across contributing signals")
    evidence_ids: List[str] = Field(default_factory=list, description="Underlying evidence provenance references")
    time_window: Optional[TimeWindow] = Field(None, description="Temporal window bounding the activity where applicable")
    detection_method: str = Field(..., description="Deterministic heuristic rule or method used")
    explanation: str = Field(..., description="Template-driven explainable narrative constructed deterministically from observed signals")
    limitations: List[str] = Field(default_factory=list, description="Explicit analytical caveats, boundary conditions, and heuristic disclosures")

    @model_validator(mode="after")
    def validate_multi_signal_requirement(self) -> "MultiSignalPattern":
        """Ensures that pattern strictly combines multiple contributing signals."""
        if len(self.contributing_signal_ids) < 2:
            raise ValueError(
                f"MultiSignalPattern requires at least 2 contributing signals, got {len(self.contributing_signal_ids)}."
            )
        return self
