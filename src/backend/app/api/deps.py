"""API Dependencies for Phase 5 Investigator Backend."""

from typing import Optional
from app.services.workspace_service import WorkspaceService

_workspace_service_instance: Optional[WorkspaceService] = None


def get_workspace_service() -> WorkspaceService:
    """Returns the singleton or configured WorkspaceService instance."""
    global _workspace_service_instance
    if _workspace_service_instance is None:
        _workspace_service_instance = WorkspaceService()
    return _workspace_service_instance


def set_workspace_service(service: Optional[WorkspaceService]) -> None:
    """Sets or resets the WorkspaceService instance (for testing/lifespan)."""
    global _workspace_service_instance
    _workspace_service_instance = service
