"""Findings API Endpoints for Phase 5 Investigator Backend."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.finding import FindingStatus, InvestigativeFinding
from app.schemas.workspace import FindingProvenanceBundle, FindingStatusUpdate
from app.services.workspace_service import WorkspaceService
from app.api.deps import get_workspace_service

router = APIRouter(prefix="/findings", tags=["Findings"])


@router.get("", response_model=List[InvestigativeFinding])
def list_findings(
    status: Optional[FindingStatus] = None,
    entity_id: Optional[str] = None,
    pattern_type: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500, description="Max findings to return"),
    service: WorkspaceService = Depends(get_workspace_service),
) -> List[InvestigativeFinding]:
    """Retrieves filtered list of investigative findings."""
    return service.list_findings(
        status=status,
        entity_id=entity_id,
        pattern_type=pattern_type,
        limit=limit,
    )


@router.get("/{finding_id}", response_model=InvestigativeFinding)
def get_finding(
    finding_id: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> InvestigativeFinding:
    """Retrieves a single investigative finding by its finding ID."""
    finding = service.get_finding(finding_id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding not found: {finding_id}",
        )
    return finding


@router.patch("/{finding_id}/status", response_model=InvestigativeFinding)
def update_finding_status(
    finding_id: str,
    payload: FindingStatusUpdate,
    service: WorkspaceService = Depends(get_workspace_service),
) -> InvestigativeFinding:
    """Updates the status and optional investigator notes for a finding."""
    try:
        return service.update_finding_status(
            finding_id=finding_id,
            status=payload.status,
            notes=payload.notes,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding not found: {finding_id}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{finding_id}/provenance", response_model=FindingProvenanceBundle)
def get_finding_provenance(
    finding_id: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> FindingProvenanceBundle:
    """Retrieves the complete typed provenance bundle for an investigative finding."""
    try:
        return service.get_finding_provenance_bundle(finding_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding not found: {finding_id}",
        )
