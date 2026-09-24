"""Neo4j Connection and Driver Configuration.

Provides runtime configuration and driver management for interacting with Neo4j.
Credentials are read from environment variables and never hardcoded in source.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from neo4j import GraphDatabase, Driver


@dataclass(frozen=True)
class Neo4jConfig:
    """Runtime configuration for Neo4j connection."""

    uri: str = field(
        default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687")
    )
    username: str = field(
        default_factory=lambda: os.getenv("NEO4J_USER", "neo4j")
    )
    password: str = field(
        default_factory=lambda: os.getenv("NEO4J_PASSWORD", "")
    )
    database: Optional[str] = field(
        default_factory=lambda: os.getenv("NEO4J_DATABASE") or None
    )

    def __repr__(self) -> str:
        # Mask password in string representation for security
        return (
            f"Neo4jConfig("
            f"uri={self.uri!r}, "
            f"username={self.username!r}, "
            f"database={self.database!r}, "
            f"password='***')"
        )


def get_driver(config: Optional[Neo4jConfig] = None) -> Driver:
    """Creates and returns a new Neo4j driver instance from configuration."""
    cfg = config or Neo4jConfig()

    if not cfg.password:
        raise ValueError("NEO4J_PASSWORD must be provided.")

    return GraphDatabase.driver(
        cfg.uri,
        auth=(cfg.username, cfg.password),
    )


def verify_connection(
    driver: Optional[Driver] = None,
    config: Optional[Neo4jConfig] = None,
) -> bool:
    """Verifies that the Neo4j instance is reachable and accepts connections."""
    close_after = False

    if driver is None:
        driver = get_driver(config)
        close_after = True

    try:
        driver.verify_connectivity()
        return True
    finally:
        if close_after:
            driver.close()