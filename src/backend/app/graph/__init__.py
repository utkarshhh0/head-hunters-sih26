"""Graph Foundation Package for Neo4j Persistence and Pre-Aggregation."""

from app.graph.config import Neo4jConfig, get_driver, verify_connection
from app.graph.pre_aggregation import (
    AggregatedRelationship,
    pre_aggregate_relationships,
    APPROVED_RELATIONSHIP_TYPES,
)
from app.graph.loader import Neo4jGraphLoader, load_pipeline_result
from app.graph.query import Neo4jGraphQuery

__all__ = [
    "Neo4jConfig",
    "get_driver",
    "verify_connection",
    "AggregatedRelationship",
    "pre_aggregate_relationships",
    "APPROVED_RELATIONSHIP_TYPES",
    "Neo4jGraphLoader",
    "load_pipeline_result",
    "Neo4jGraphQuery",
]

