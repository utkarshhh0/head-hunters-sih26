"""Analytical Signal and Investigative Finding Schemas."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SignalType(str, Enum):
    """Types of analytical signals detected in graph or temporal data."""

    HIGH_DEGREE_CENTRALITY = "HIGH_DEGREE_CENTRALITY"
    BURST_COMMUNICATION_WINDOW = "BURST_COMMUNICATION_WINDOW"
    BRIDGE_ACTOR = "BRIDGE_ACTOR"
    SHARED_FINANCIAL_ACCOUNT = "SHARED_FINANCIAL_ACCOUNT"
    CO_LOCATION_RECURRENCE = "CO_LOCATION_RECURRENCE"


class AnalyticalSignal(BaseModel):
    """Rule-based analytical signal flag."""

    model_config = ConfigDict(extra="forbid")

    signal_id: str = Field(..., description="Unique URN for analytical signal e.g. urn:signal:001")
    signal_type: SignalType = Field(..., description="Classification type of signal")
    entity_ids: List[str] = Field(default_factory=list, description="Entities involved in signal")
    relationship_ids: List[str] = Field(default_factory=list, description="Relationships involved in signal")
    metric_value: float = Field(..., description="Calculated metric or rule score")
    rule_description: str = Field(..., description="Deterministic description of rule trigger")


class FindingStatus(str, Enum):
    """Lifecycle status of an investigative finding."""

    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


# Deferred import of TimeWindow to avoid circular dependency with app.schemas.analytics
from app.schemas.analytics import TimeWindow


class InvestigativeFinding(BaseModel):
    """High-level explainable investigative finding combining analytical signals and evidence."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(..., description="Unique URN for finding e.g. urn:finding:001")
    title: str = Field(..., description="Deterministic title for finding")
    summary: str = Field(..., description="Template-driven explainable summary (no LLM dependence)")
    entity_ids: List[str] = Field(default_factory=list, description="Referenced entity IDs")
    relationship_ids: List[str] = Field(default_factory=list, description="Referenced relationship IDs")
    signal_ids: List[str] = Field(default_factory=list, description="Referenced analytical signal IDs")
    evidence_ids: List[str] = Field(default_factory=list, description="Referenced evidence provenance IDs")
    confidence: float = Field(default=1.0, description="Analytical confidence score (0.0 to 1.0)")
    caveats: List[str] = Field(default_factory=list, description="Explicit synthetic/analytical caveats")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    status: FindingStatus = Field(default=FindingStatus.OPEN, description="Investigative lifecycle status")
    pattern_id: Optional[str] = Field(None, description="Optional multi-signal pattern ID reference")
    pattern_type: Optional[str] = Field(None, description="Optional pattern type classification")
    time_window: Optional[TimeWindow] = Field(None, description="Observed time window if temporally bounded")
    investigator_notes: Optional[str] = Field(None, description="Optional investigator assessment notes")

    @field_validator("confidence")
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        """Ensure confidence is within valid [0.0, 1.0] bound."""
        if not (0.0 <= v <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0 inclusive.")
        return v
