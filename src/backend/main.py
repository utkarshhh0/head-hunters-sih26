"""FastAPI Application Entrypoint for Phase 5 Investigator Backend.

Exposes controlled, parameterized, and validated REST API endpoints for:
- System health
- Investigator workspace summary and analysis orchestration
- Finding discovery, lifecycle status transitions, and end-to-end provenance
- Bounded entity exploration (neighborhood limited to depth 1 or 2)

Prohibits arbitrary Cypher execution, unbounded graph traversals, and universal risk scoring.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import v1_router
from app.api.deps import get_workspace_service, set_workspace_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and clean resource shutdown."""
    yield
    # Clean shutdown of workspace services and Neo4j connections
    service = get_workspace_service()
    if service:
        service.close()
    set_workspace_service(None)


app = FastAPI(
    title="SIH26189 — Investigator Backend",
    description="AI-Powered Criminal Network Analysis System — Phase 5 Investigator Backend",
    version="0.5.0",
    lifespan=lifespan,
)

# CORS middleware for local development with Phase 6 UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router
app.include_router(v1_router)


@app.get("/health", tags=["Health"])
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "investigator-backend"}
