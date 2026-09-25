"""Entities and Graph Exploration API Endpoints for Phase 5."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.workspace import EntityNeighborhoodResponse
from app.services.workspace_service import WorkspaceService
from app.api.deps import get_workspace_service

router = APIRouter(prefix="/entities", tags=["Entities"])


@router.get("", response_model=List[Dict[str, Any]])
def search_entities(
    query: Optional[str] = None,
    entity_type: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500, description="Max entities to return"),
    service: WorkspaceService = Depends(get_workspace_service),
) -> List[Dict[str, Any]]:
    """Searches canonical entities by substring, alias, identifier, or entity type."""
    try:
        return service.search_entities(query=query, entity_type=entity_type, limit=limit)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{entity_id}", response_model=Dict[str, Any])
def get_entity_details(
    entity_id: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> Dict[str, Any]:
    """Retrieves full properties and degree connectivity metrics for an entity."""
    try:
        data = service.get_entity_details(entity_id)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity not found: {entity_id}",
            )
        return data
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{entity_id}/neighborhood", response_model=EntityNeighborhoodResponse)
def get_entity_neighborhood(
    entity_id: str,
    depth: int = Query(default=1, ge=1, le=2, description="Neighborhood depth (strictly 1 or 2)"),
    limit: int = Query(default=50, ge=1, le=200, description="Max relationships to return"),
    service: WorkspaceService = Depends(get_workspace_service),
) -> EntityNeighborhoodResponse:
    """Retrieves a bounded 1-hop or 2-hop network graph slice around an entity.

    Traversal depth is strictly bounded to 1 or 2 hops. Depth > 2 is rejected.
    """
    try:
        return service.get_entity_neighborhood(entity_id=entity_id, depth=depth, limit=limit)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
