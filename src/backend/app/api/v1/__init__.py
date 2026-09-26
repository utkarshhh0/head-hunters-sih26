"""API v1 Router Aggregator."""

from fastapi import APIRouter

from app.api.v1.findings import router as findings_router
from app.api.v1.entities import router as entities_router
from app.api.v1.workspace import router as workspace_router
from app.api.v1.reports import router as reports_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(findings_router)
v1_router.include_router(entities_router)
v1_router.include_router(workspace_router)
v1_router.include_router(reports_router)

__all__ = ["v1_router"]
