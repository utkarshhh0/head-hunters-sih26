"""Workspace Management and Analysis Trigger API Endpoints for Phase 5."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from app.schemas.finding import InvestigativeFinding
from app.schemas.workspace import WorkspaceSummary
from app.services.workspace_service import WorkspaceService
from app.api.deps import get_workspace_service

router = APIRouter(prefix="/workspace", tags=["Workspace"])


@router.get("/summary", response_model=WorkspaceSummary)
def get_workspace_summary(
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceSummary:
    """Retrieves aggregated metrics for the investigator workspace dashboard."""
    return service.get_workspace_summary()


@router.post("/detect-findings", response_model=List[InvestigativeFinding])
def detect_findings(
    entity_id: Optional[str] = Query(default=None, description="Optional entity ID filter for targeted analysis"),
    limit: int = Query(default=500, ge=1, le=1000, description="Max graph elements to analyze"),
    service: WorkspaceService = Depends(get_workspace_service),
) -> List[InvestigativeFinding]:
    """Orchestrates pattern detection and finding synthesis, registering findings in workspace.

    Pure orchestration: PatternDetector -> FindingSynthesizer -> WorkspaceService.
    No analytical logic is implemented in this endpoint handler.
    """
    return service.detect_and_register_findings(entity_id=entity_id, limit=limit)
