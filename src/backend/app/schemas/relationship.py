"""Relationship and Entity Resolution Schemas."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResolutionStatus(str, Enum):
    """Entity resolution match classification states."""

    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    NO_MATCH = "NO_MATCH"


class ResolutionCandidate(BaseModel):
    """Candidate pair evaluated during entity resolution."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(..., description="Unique URN for candidate pair e.g. urn:res:cand:001")
    entity_id_a: str = Field(..., description="First entity URN")
    entity_id_b: str = Field(..., description="Second entity URN")
    similarity_score: float = Field(..., description="Heuristic similarity score (0.0 to 1.0)")
    heuristic_name: str = Field(..., description="Name of heuristic algorithm used")
    status: ResolutionStatus = Field(..., description="Match status classification")
    confidence: float = Field(..., description="Resolution confidence score (0.0 to 1.0)")
    justification: str = Field(..., description="Human-readable match justification")
    analyst_override: Optional[bool] = Field(None, description="Manual analyst review override flag")

    @field_validator("similarity_score", "confidence")
    @classmethod
    def validate_score_range(cls, v: float) -> float:
        """Ensure scores are within valid [0.0, 1.0] bound."""
        if not (0.0 <= v <= 1.0):
            raise ValueError("Score must be between 0.0 and 1.0 inclusive.")
        return v


class ResolutionDecision(BaseModel):
    """Final decision record for an entity resolution candidate."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(..., description="Unique URN for resolution decision e.g. urn:res:dec:001")
    candidate_id: str = Field(..., description="Reference to ResolutionCandidate.candidate_id")
    status: ResolutionStatus = Field(..., description="Final resolution status")
    merged_entity_id: Optional[str] = Field(None, description="Resulting merged entity URN if status is HIGH_CONFIDENCE")
    reasoning: str = Field(..., description="Reasoning for decision")
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Decision timestamp")



class RelationshipType(str, Enum):
    """Types of graph relationships between entities."""

    COMMUNICATED_WITH = "COMMUNICATED_WITH"
    TRANSACTED_WITH = "TRANSACTED_WITH"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    MEMBER_OF = "MEMBER_OF"
    LOCATED_AT = "LOCATED_AT"
    OWNED_BY = "OWNED_BY"
    CO_OCCURRED_WITH = "CO_OCCURRED_WITH"


class RelationshipOrigin(str, Enum):
    """Origin of relationship discovery."""

    EXTRACTED = "EXTRACTED"
    ANALYTICALLY_INFERRED = "ANALYTICALLY_INFERRED"


class Relationship(BaseModel):
    """Graph relationship edge between two entities."""

    model_config = ConfigDict(extra="forbid")

    relationship_id: str = Field(..., description="Unique URN for relationship e.g. urn:rel:001")
    source_entity_id: str = Field(..., description="Source entity URN")
    target_entity_id: str = Field(..., description="Target entity URN")
    relationship_type: RelationshipType = Field(..., description="Type of edge")
    origin: RelationshipOrigin = Field(..., description="Extracted vs Analytically Inferred")
    confidence: float = Field(..., description="Relationship confidence score (0.0 to 1.0)")
    timestamp_context: Optional[datetime] = Field(None, description="Event or discovery timestamp")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Edge properties e.g. duration, amount")
    evidence_ids: List[str] = Field(default_factory=list, description="Evidence provenance references")

    @field_validator("confidence")
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        """Ensure confidence is within valid [0.0, 1.0] bound."""
        if not (0.0 <= v <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0 inclusive.")
        return v
