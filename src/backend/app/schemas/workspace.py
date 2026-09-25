"""Investigator Workspace Domain and API Contracts for Phase 5.

Provides typed schemas for:
- FindingStatusUpdate: request contract for updating finding status and investigator notes
- FindingProvenanceBundle: typed end-to-end provenance bundle tracing Finding -> Pattern -> Signals -> Entities/Relationships -> Evidence -> SourceRecord
- WorkspaceSummary: aggregate overview metrics for investigator dashboard
- EntityNeighborhoodResponse: bounded 1-hop or 2-hop graph exploration slice
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.finding import FindingStatus, InvestigativeFinding
from app.schemas.analytics import MultiSignalPattern


class FindingStatusUpdate(BaseModel):
    """Request payload for updating the lifecycle status or notes of an investigative finding."""

    model_config = ConfigDict(extra="forbid")

    status: FindingStatus = Field(..., description="Target lifecycle status")
    notes: Optional[str] = Field(None, description="Optional investigator assessment notes")


class FindingProvenanceBundle(BaseModel):
    """Typed end-to-end provenance bundle for an investigative finding.

    Full forward and backward linkability:
    Finding -> Pattern / Signals -> Entities / Relationships -> Evidence -> SourceRecord
    """

    model_config = ConfigDict(extra="forbid")

    finding: InvestigativeFinding = Field(..., description="Target investigative finding")
    pattern: Optional[MultiSignalPattern] = Field(None, description="Associated multi-signal pattern if applicable")
    signals: List[Dict[str, Any]] = Field(default_factory=list, description="Associated structural and temporal signals")
    entities: List[Dict[str, Any]] = Field(default_factory=list, description="Resolved entities involved in the finding")
    relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Relationships involved in the finding")
    evidence: List[Dict[str, Any]] = Field(default_factory=list, description="Evidence provenance records")
    source_records: List[Dict[str, Any]] = Field(default_factory=list, description="Underlying raw source records")


class WorkspaceSummary(BaseModel):
    """Aggregated investigative dashboard metrics for the workspace."""

    model_config = ConfigDict(extra="forbid")

    total_findings: int = Field(..., description="Total number of findings in workspace")
    findings_by_status: Dict[str, int] = Field(default_factory=dict, description="Count of findings keyed by FindingStatus")
    findings_by_pattern_type: Dict[str, int] = Field(default_factory=dict, description="Count of findings keyed by pattern type")
    total_entities_monitored: int = Field(..., description="Total unique entities referenced across findings")
    total_signals_detected: int = Field(..., description="Total signals referenced across findings")


class EntityNeighborhoodResponse(BaseModel):
    """Bounded 1-hop or 2-hop graph neighborhood for entity exploration."""

    model_config = ConfigDict(extra="forbid")

    center_entity_id: str = Field(..., description="Focus entity ID")
    depth: int = Field(..., description="Traversal depth (1 or 2)")
    entities: List[Dict[str, Any]] = Field(default_factory=list, description="Discovered neighborhood entities")
    relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Discovered neighborhood relationships")
    total_nodes: int = Field(..., description="Total node count")
    total_edges: int = Field(..., description="Total edge count")
