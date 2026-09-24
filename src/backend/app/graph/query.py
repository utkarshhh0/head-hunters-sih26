"""Bounded and Explicit Neo4j Graph Query Layer for Phase 3B.

Provides investigative read queries against the persistent Neo4j knowledge graph:
1. Entity lookup/search with filtering
2. Entity details
3. Direct relationships with directional, type, confidence, and temporal filtering
4. Bounded 1-hop and 2-hop network traversal (unbounded traversal prohibited)
5. Temporal filtering across graph slices
6. Strict provenance tracing: Relationship/Entity -> Evidence -> FROM_SOURCE -> SourceRecord
7. Unresolved POSSIBLE_MATCH candidate inspection via [:EVALUATED_PAIR]

Rules & Constraints:
- Zero fabrication of timestamps or evidence.
- Approved relationship types only: COMMUNICATED_WITH, OWNED_BY, ASSOCIATED_WITH, TRANSACTED_WITH.
- Traversal depth strictly bounded to 1 or 2 hops.
- Strict LIMIT bounds on all queries.
- Deterministic ordering of query results.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Set
from neo4j import Driver, Session

from app.schemas.entity import EntityType
from app.schemas.relationship import RelationshipType
from app.graph.config import Neo4jConfig, get_driver
from app.graph.pre_aggregation import APPROVED_RELATIONSHIP_TYPES

# Valid entity types set for query validation
VALID_ENTITY_TYPES: Set[str] = {e.value for e in EntityType}


def _normalize_timestamp(ts: Optional[datetime | str]) -> Optional[str]:
    """Converts a datetime or ISO string into a canonical ISO string for comparison."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts.isoformat()
    if isinstance(ts, str):
        s = ts.strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(s)
            return parsed.isoformat()
        except Exception:
            return s
    return str(ts)


def _format_entity(node: Any) -> Dict[str, Any]:
    """Formats a Neo4j Entity node into a clean domain dictionary."""
    if hasattr(node, "items"):
        props = dict(node)
    elif isinstance(node, dict):
        props = dict(node)
    else:
        try:
            props = dict(node)
        except Exception:
            props = {}

    attrs_raw = props.pop("attributes_json", None)
    if isinstance(attrs_raw, str):
        try:
            props["attributes"] = json.loads(attrs_raw)
        except Exception:
            props["attributes"] = {}
    elif isinstance(attrs_raw, dict):
        props["attributes"] = attrs_raw
    else:
        props["attributes"] = {}

    if hasattr(node, "labels"):
        props["labels"] = sorted(list(node.labels))
    return props


def _format_relationship(
    rel: Any,
    source_id: Optional[str] = None,
    target_id: Optional[str] = None,
    rel_type: Optional[str] = None,
    source_name: Optional[str] = None,
    target_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Formats a Neo4j Relationship into a clean domain dictionary with aggregate properties."""
    if hasattr(rel, "items"):
        props = dict(rel)
    elif isinstance(rel, dict):
        props = dict(rel)
    elif isinstance(rel, (tuple, list)) and len(rel) == 3:
        props = {}
    else:
        try:
            props = dict(rel)
        except Exception:
            props = {}

    attrs_raw = props.pop("attributes_json", None)
    if isinstance(attrs_raw, str):
        try:
            props["attributes"] = json.loads(attrs_raw)
        except Exception:
            props["attributes"] = {}
    elif isinstance(attrs_raw, dict):
        props["attributes"] = attrs_raw
    else:
        props["attributes"] = {}

    props["relationship_type"] = rel_type or (rel.type if hasattr(rel, "type") else None)
    props.setdefault("first_seen", None)
    props.setdefault("last_seen", None)
    props.setdefault("evidence_ids", [])
    props.setdefault("interaction_count", 1)
    props.setdefault("confidence", 1.0)
    props.setdefault("origin", "EXTRACTED")

    if source_id is not None:
        props["source_entity_id"] = source_id
    if target_id is not None:
        props["target_entity_id"] = target_id
    if source_name is not None:
        props["source_name"] = source_name
    if target_name is not None:
        props["target_name"] = target_name
    return props



def _format_evidence(node: Any) -> Dict[str, Any]:
    """Formats a Neo4j Evidence node into a domain dictionary."""
    if hasattr(node, "items"):
        return dict(node)
    elif isinstance(node, dict):
        return dict(node)
    return {}


def _format_source_record(node: Any) -> Dict[str, Any]:
    """Formats a Neo4j SourceRecord node, parsing metadata_json if present."""
    if hasattr(node, "items"):
        props = dict(node)
    elif isinstance(node, dict):
        props = dict(node)
    else:
        props = {}

    meta_raw = props.pop("metadata_json", None)
    if isinstance(meta_raw, str):
        try:
            props["metadata"] = json.loads(meta_raw)
        except Exception:
            props["metadata"] = {}
    elif isinstance(meta_raw, dict):
        props["metadata"] = meta_raw
    else:
        props["metadata"] = {}
    return props


class Neo4jGraphQuery:
    """Investigative query interface providing bounded, safe read operations against Neo4j."""

    def __init__(self, driver: Optional[Driver] = None, config: Optional[Neo4jConfig] = None):
        self.driver: Driver = driver or get_driver(config)
        self._owned_driver: bool = driver is None

    def close(self) -> None:
        """Closes the driver connection if internally owned."""
        if self._owned_driver and self.driver:
            self.driver.close()

    def __enter__(self) -> "Neo4jGraphQuery":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # -------------------------------------------------------------------------
    # 1. Entity Lookup / Search
    # -------------------------------------------------------------------------
    def search_entities(
        self,
        query: Optional[str] = None,
        entity_type: Optional[str | EntityType] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Searches canonical entities by substring, alias, identifier, or entity type."""
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500.")

        type_str: Optional[str] = None
        if entity_type is not None:
            type_str = entity_type.value if hasattr(entity_type, "value") else str(entity_type)
            if type_str not in VALID_ENTITY_TYPES:
                raise ValueError(
                    f"Invalid entity_type: {type_str!r}. Valid types: {sorted(VALID_ENTITY_TYPES)}"
                )

        cypher = """
        MATCH (n:Entity)
        WHERE ($entity_type IS NULL OR n.entity_type = $entity_type)
          AND (
            $query IS NULL
            OR toLower(n.canonical_name) CONTAINS toLower($query)
            OR any(alias IN n.aliases WHERE toLower(alias) CONTAINS toLower($query))
            OR toLower(n.entity_id) CONTAINS toLower($query)
            OR (n.full_name IS NOT NULL AND toLower(n.full_name) CONTAINS toLower($query))
            OR (n.phone_number IS NOT NULL AND toLower(n.phone_number) CONTAINS toLower($query))
            OR (n.registration_number IS NOT NULL AND toLower(n.registration_number) CONTAINS toLower($query))
            OR (n.address IS NOT NULL AND toLower(n.address) CONTAINS toLower($query))
            OR (n.org_name IS NOT NULL AND toLower(n.org_name) CONTAINS toLower($query))
            OR (n.account_number IS NOT NULL AND toLower(n.account_number) CONTAINS toLower($query))
          )
        RETURN n
        ORDER BY n.canonical_name ASC, n.entity_id ASC
        LIMIT $limit
        """

        clean_query = query.strip() if query and query.strip() else None

        with self.driver.session() as session:
            records = list(
                session.run(
                    cypher,
                    {
                        "query": clean_query,
                        "entity_type": type_str,
                        "limit": limit,
                    },
                )
            )

        return [_format_entity(r["n"]) for r in records]

    # -------------------------------------------------------------------------
    # 2. Entity Details
    # -------------------------------------------------------------------------
    def get_entity_details(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves complete properties and connectivity metrics for a specific entity."""
        if not entity_id or not entity_id.strip():
            raise ValueError("entity_id must be a non-empty string.")

        cypher = """
        MATCH (n:Entity {entity_id: $entity_id})
        OPTIONAL MATCH (n)-[r:COMMUNICATED_WITH|OWNED_BY|ASSOCIATED_WITH|TRANSACTED_WITH]-(neighbor:Entity)
        OPTIONAL MATCH (n)-[p:EVALUATED_PAIR]-(other:Entity)
        RETURN n,
               count(DISTINCT r) AS direct_relationship_count,
               count(DISTINCT p) AS possible_match_count
        """

        with self.driver.session() as session:
            record = session.run(cypher, {"entity_id": entity_id.strip()}).single()

        if not record or record["n"] is None:
            return None

        entity_data = _format_entity(record["n"])
        entity_data["direct_relationship_count"] = record["direct_relationship_count"]
        entity_data["possible_match_count"] = record["possible_match_count"]
        return entity_data

    # -------------------------------------------------------------------------
    # 3. Direct Relationships & Temporal Filtering
    # -------------------------------------------------------------------------
    def get_direct_relationships(
        self,
        entity_id: str,
        direction: str = "BOTH",
        relationship_types: Optional[List[str]] = None,
        min_confidence: Optional[float] = None,
        start_time: Optional[datetime | str] = None,
        end_time: Optional[datetime | str] = None,
        include_undated: bool = True,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieves direct native relationships connected to an entity with strict filtering."""
        if not entity_id or not entity_id.strip():
            raise ValueError("entity_id must be a non-empty string.")
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500.")

        dir_clean = direction.upper().strip()
        if dir_clean not in ("BOTH", "OUTGOING", "INCOMING"):
            raise ValueError("direction must be 'BOTH', 'OUTGOING', or 'INCOMING'.")

        if min_confidence is not None and not (0.0 <= min_confidence <= 1.0):
            raise ValueError("min_confidence must be between 0.0 and 1.0.")

        # Validate relationship types against authorized whitelist
        types_to_use: List[str]
        if relationship_types:
            for rt in relationship_types:
                t_str = rt.value if hasattr(rt, "value") else str(rt)
                if t_str not in APPROVED_RELATIONSHIP_TYPES:
                    raise ValueError(
                        f"Unsupported relationship type: {t_str!r}. "
                        f"Approved: {sorted(APPROVED_RELATIONSHIP_TYPES)}"
                    )
            types_to_use = sorted(
                list({rt.value if hasattr(rt, "value") else str(rt) for rt in relationship_types})
            )
        else:
            types_to_use = sorted(list(APPROVED_RELATIONSHIP_TYPES))

        st_iso = _normalize_timestamp(start_time)
        et_iso = _normalize_timestamp(end_time)

        rel_type_pattern = "|".join(types_to_use)

        where_clauses: List[str] = []
        params: Dict[str, Any] = {
            "entity_id": entity_id.strip(),
            "min_confidence": min_confidence,
            "start_time": st_iso,
            "end_time": et_iso,
            "limit": limit,
        }

        # Build Cypher based on direction
        if dir_clean == "OUTGOING":
            match_pattern = (
                f"MATCH (source:Entity {{entity_id: $entity_id}})-[r:{rel_type_pattern}]->(target:Entity)"
            )
        elif dir_clean == "INCOMING":
            match_pattern = (
                f"MATCH (source:Entity)-[r:{rel_type_pattern}]->(target:Entity {{entity_id: $entity_id}})"
            )
        else:  # BOTH
            match_pattern = (
                f"MATCH (source:Entity)-[r:{rel_type_pattern}]->(target:Entity) "
                f"WHERE (source.entity_id = $entity_id OR target.entity_id = $entity_id)"
            )

        if min_confidence is not None:
            where_clauses.append("r.confidence >= $min_confidence")

        # Temporal filtering logic: preserve distinction between missing and actual timestamps
        has_temporal_filter = st_iso is not None or et_iso is not None
        if has_temporal_filter:
            if not include_undated:
                where_clauses.append("r.first_seen IS NOT NULL AND r.last_seen IS NOT NULL")
                if st_iso is not None:
                    where_clauses.append("r.last_seen >= $start_time")
                if et_iso is not None:
                    where_clauses.append("r.first_seen <= $end_time")
            else:
                date_conditions: List[str] = []
                if st_iso is not None:
                    date_conditions.append("r.last_seen >= $start_time")
                if et_iso is not None:
                    date_conditions.append("r.first_seen <= $end_time")
                if date_conditions:
                    inner = " AND ".join(date_conditions)
                    where_clauses.append(f"(r.first_seen IS NULL OR ({inner}))")

        # Assemble full Cypher query
        where_str = ""
        if where_clauses:
            prefix = " AND " if dir_clean == "BOTH" else " WHERE "
            where_str = prefix + " AND ".join(where_clauses)

        cypher = f"""
        {match_pattern}
        {where_str}
        RETURN r,
               type(r) AS rel_type,
               source.entity_id AS source_entity_id,
               target.entity_id AS target_entity_id,
               source.canonical_name AS source_name,
               target.canonical_name AS target_name
        ORDER BY r.relationship_id ASC
        LIMIT $limit
        """

        with self.driver.session() as session:
            records = list(session.run(cypher, params))

        results: List[Dict[str, Any]] = []
        for rec in records:
            formatted = _format_relationship(
                rel=rec["r"],
                source_id=rec["source_entity_id"],
                target_id=rec["target_entity_id"],
                rel_type=rec["rel_type"],
                source_name=rec["source_name"],
                target_name=rec["target_name"],
            )
            results.append(formatted)

        return results

    # -------------------------------------------------------------------------
    # 4. Bounded 1-Hop and 2-Hop Network Traversal
    # -------------------------------------------------------------------------
    def traverse_network(
        self,
        start_entity_id: str,
        hops: int = 1,
        direction: str = "BOTH",
        relationship_types: Optional[List[str]] = None,
        min_confidence: Optional[float] = None,
        start_time: Optional[datetime | str] = None,
        end_time: Optional[datetime | str] = None,
        include_undated: bool = True,
        include_possible_matches: bool = False,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Bounded 1-hop and 2-hop graph traversal. Unbounded traversal is strictly prohibited."""
        if not start_entity_id or not start_entity_id.strip():
            raise ValueError("start_entity_id must be a non-empty string.")
        if hops not in (1, 2):
            raise ValueError(
                "hops must be 1 or 2. Arbitrary or unbounded graph traversal is strictly prohibited."
            )
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500.")

        clean_id = start_entity_id.strip()

        # Step 1: Fetch root entity
        with self.driver.session() as session:
            root_rec = session.run(
                "MATCH (n:Entity {entity_id: $id}) RETURN n",
                {"id": clean_id},
            ).single()

        if not root_rec or root_rec["n"] is None:
            return {
                "start_entity_id": clean_id,
                "hops": hops,
                "entities": [],
                "relationships": [],
                "evaluated_pairs": [],
                "metrics": {
                    "entity_count": 0,
                    "relationship_count": 0,
                    "evaluated_pair_count": 0,
                },
            }

        entities_by_id: Dict[str, Dict[str, Any]] = {
            clean_id: _format_entity(root_rec["n"])
        }
        relationships_by_id: Dict[str, Dict[str, Any]] = {}

        # Step 2: 1-Hop relationships
        hop1_rels = self.get_direct_relationships(
            entity_id=clean_id,
            direction=direction,
            relationship_types=relationship_types,
            min_confidence=min_confidence,
            start_time=start_time,
            end_time=end_time,
            include_undated=include_undated,
            limit=limit,
        )

        hop1_neighbor_ids: Set[str] = set()
        for rel in hop1_rels:
            relationships_by_id[rel["relationship_id"]] = rel
            if rel["source_entity_id"] != clean_id:
                hop1_neighbor_ids.add(rel["source_entity_id"])
            if rel["target_entity_id"] != clean_id:
                hop1_neighbor_ids.add(rel["target_entity_id"])

        # Step 3: 2-Hop expansion if requested and quota remains
        if hops == 2 and hop1_neighbor_ids:
            remaining_limit = limit - len(relationships_by_id)
            for neighbor_id in sorted(list(hop1_neighbor_ids)):
                if remaining_limit <= 0:
                    break
                hop2_rels = self.get_direct_relationships(
                    entity_id=neighbor_id,
                    direction=direction,
                    relationship_types=relationship_types,
                    min_confidence=min_confidence,
                    start_time=start_time,
                    end_time=end_time,
                    include_undated=include_undated,
                    limit=remaining_limit,
                )
                for rel in hop2_rels:
                    rel_id = rel["relationship_id"]
                    if rel_id not in relationships_by_id:
                        relationships_by_id[rel_id] = rel
                        remaining_limit -= 1
                        if remaining_limit <= 0:
                            break

        # Step 4: Batch-fetch all discovered entity nodes
        all_referenced_ids: Set[str] = {clean_id}
        for rel in relationships_by_id.values():
            all_referenced_ids.add(rel["source_entity_id"])
            all_referenced_ids.add(rel["target_entity_id"])

        missing_entity_ids = sorted(list(all_referenced_ids - set(entities_by_id.keys())))
        if missing_entity_ids:
            with self.driver.session() as session:
                rec_nodes = list(
                    session.run(
                        "MATCH (n:Entity) WHERE n.entity_id IN $ids RETURN n",
                        {"ids": missing_entity_ids},
                    )
                )
                for rec in rec_nodes:
                    ent = _format_entity(rec["n"])
                    entities_by_id[ent["entity_id"]] = ent

        # Step 5: Optionally inspect [:EVALUATED_PAIR] candidate links among discovered nodes
        evaluated_pairs: List[Dict[str, Any]] = []
        if include_possible_matches and len(entities_by_id) > 1:
            all_ids_list = sorted(list(entities_by_id.keys()))
            pair_cypher = """
            MATCH (a:Entity)-[p:EVALUATED_PAIR]->(b:Entity)
            WHERE a.entity_id IN $all_ids AND b.entity_id IN $all_ids
            RETURN p,
                   a.entity_id AS entity_id_a, a.canonical_name AS name_a, a.entity_type AS type_a,
                   b.entity_id AS entity_id_b, b.canonical_name AS name_b, b.entity_type AS type_b
            ORDER BY p.similarity_score DESC, p.candidate_id ASC
            """
            with self.driver.session() as session:
                pair_records = list(session.run(pair_cypher, {"all_ids": all_ids_list}))

            for prec in pair_records:
                p_props = dict(prec["p"])
                p_props["entity_id_a"] = prec["entity_id_a"]
                p_props["name_a"] = prec["name_a"]
                p_props["type_a"] = prec["type_a"]
                p_props["entity_id_b"] = prec["entity_id_b"]
                p_props["name_b"] = prec["name_b"]
                p_props["type_b"] = prec["type_b"]
                evaluated_pairs.append(p_props)

        # Assemble deterministic output
        sorted_entities = [entities_by_id[eid] for eid in sorted(entities_by_id.keys())]
        sorted_relationships = [
            relationships_by_id[rid] for rid in sorted(relationships_by_id.keys())
        ]
        sorted_evaluated_pairs = sorted(evaluated_pairs, key=lambda x: x["candidate_id"])

        return {
            "start_entity_id": clean_id,
            "hops": hops,
            "entities": sorted_entities,
            "relationships": sorted_relationships,
            "evaluated_pairs": sorted_evaluated_pairs,
            "metrics": {
                "entity_count": len(sorted_entities),
                "relationship_count": len(sorted_relationships),
                "evaluated_pair_count": len(sorted_evaluated_pairs),
            },
        }

    # -------------------------------------------------------------------------
    # 5. Global Temporal Subgraph Query
    # -------------------------------------------------------------------------
    def get_temporal_subgraph(
        self,
        start_time: Optional[datetime | str] = None,
        end_time: Optional[datetime | str] = None,
        include_undated: bool = False,
        relationship_types: Optional[List[str]] = None,
        min_confidence: Optional[float] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Queries relationships and active entities within a specified time slice across the entire graph."""
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500.")

        if min_confidence is not None and not (0.0 <= min_confidence <= 1.0):
            raise ValueError("min_confidence must be between 0.0 and 1.0.")

        # Validate types
        types_to_use: List[str]
        if relationship_types:
            for rt in relationship_types:
                t_str = rt.value if hasattr(rt, "value") else str(rt)
                if t_str not in APPROVED_RELATIONSHIP_TYPES:
                    raise ValueError(f"Unsupported relationship type: {t_str!r}.")
            types_to_use = sorted(
                list({rt.value if hasattr(rt, "value") else str(rt) for rt in relationship_types})
            )
        else:
            types_to_use = sorted(list(APPROVED_RELATIONSHIP_TYPES))

        st_iso = _normalize_timestamp(start_time)
        et_iso = _normalize_timestamp(end_time)
        rel_type_pattern = "|".join(types_to_use)

        where_clauses: List[str] = []
        params: Dict[str, Any] = {
            "min_confidence": min_confidence,
            "start_time": st_iso,
            "end_time": et_iso,
            "limit": limit,
        }

        if min_confidence is not None:
            where_clauses.append("r.confidence >= $min_confidence")

        has_temporal = st_iso is not None or et_iso is not None
        if has_temporal:
            if not include_undated:
                where_clauses.append("r.first_seen IS NOT NULL AND r.last_seen IS NOT NULL")
                if st_iso is not None:
                    where_clauses.append("r.last_seen >= $start_time")
                if et_iso is not None:
                    where_clauses.append("r.first_seen <= $end_time")
            else:
                date_conditions: List[str] = []
                if st_iso is not None:
                    date_conditions.append("r.last_seen >= $start_time")
                if et_iso is not None:
                    date_conditions.append("r.first_seen <= $end_time")
                if date_conditions:
                    inner = " AND ".join(date_conditions)
                    where_clauses.append(f"(r.first_seen IS NULL OR ({inner}))")

        where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        cypher = f"""
        MATCH (source:Entity)-[r:{rel_type_pattern}]->(target:Entity)
        {where_str}
        RETURN r,
               type(r) AS rel_type,
               source.entity_id AS source_entity_id,
               target.entity_id AS target_entity_id,
               source.canonical_name AS source_name,
               target.canonical_name AS target_name,
               source,
               target
        ORDER BY coalesce(r.first_seen, '') ASC, r.relationship_id ASC
        LIMIT $limit
        """

        with self.driver.session() as session:
            records = list(session.run(cypher, params))

        entities_by_id: Dict[str, Dict[str, Any]] = {}
        relationships: List[Dict[str, Any]] = []

        for rec in records:
            rel_formatted = _format_relationship(
                rel=rec["r"],
                source_id=rec["source_entity_id"],
                target_id=rec["target_entity_id"],
                rel_type=rec["rel_type"],
                source_name=rec["source_name"],
                target_name=rec["target_name"],
            )
            relationships.append(rel_formatted)

            s_id = rec["source_entity_id"]
            if s_id not in entities_by_id:
                entities_by_id[s_id] = _format_entity(rec["source"])
            t_id = rec["target_entity_id"]
            if t_id not in entities_by_id:
                entities_by_id[t_id] = _format_entity(rec["target"])

        sorted_entities = [entities_by_id[k] for k in sorted(entities_by_id.keys())]

        return {
            "entities": sorted_entities,
            "relationships": relationships,
            "metrics": {
                "entity_count": len(sorted_entities),
                "relationship_count": len(relationships),
            },
        }

    # -------------------------------------------------------------------------
    # 6. Evidence & Source Provenance Retrieval
    # -------------------------------------------------------------------------
    def get_relationship_evidence(self, relationship_id: str) -> List[Dict[str, Any]]:
        """Strict provenance tracing: relationship evidence_ids -> Evidence -> [:FROM_SOURCE] -> SourceRecord."""
        if not relationship_id or not relationship_id.strip():
            raise ValueError("relationship_id must be a non-empty string.")

        cypher = """
        MATCH (source:Entity)-[r {relationship_id: $rel_id}]->(target:Entity)
        UNWIND r.evidence_ids AS ev_id
        MATCH (ev:Evidence {evidence_id: ev_id})-[:FROM_SOURCE]->(s:SourceRecord)
        RETURN r.relationship_id AS relationship_id,
               type(r) AS relationship_type,
               source.entity_id AS source_entity_id,
               target.entity_id AS target_entity_id,
               ev,
               s
        ORDER BY ev.evidence_id ASC
        """

        with self.driver.session() as session:
            records = list(session.run(cypher, {"rel_id": relationship_id.strip()}))

        results: List[Dict[str, Any]] = []
        for rec in records:
            results.append(
                {
                    "relationship_id": rec["relationship_id"],
                    "relationship_type": rec["relationship_type"],
                    "source_entity_id": rec["source_entity_id"],
                    "target_entity_id": rec["target_entity_id"],
                    "evidence": _format_evidence(rec["ev"]),
                    "source_record": _format_source_record(rec["s"]),
                }
            )
        return results

    def get_entity_evidence(self, entity_id: str,  limit: int = 100,) -> Dict[str, Any]:
        """Retrieves complete provenance backing an entity, including direct source records and relationship evidence."""
        if not entity_id or not entity_id.strip():
            raise ValueError("entity_id must be a non-empty string.")

        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500.")

        clean_id = entity_id.strip()

        # 1. Direct SourceRecords and Evidence linked from entity.source_record_ids
        direct_cypher = """
        MATCH (e:Entity {entity_id: $id})
        UNWIND e.source_record_ids AS src_id
        MATCH (s:SourceRecord {source_id: src_id})
        OPTIONAL MATCH (ev:Evidence)-[:FROM_SOURCE]->(s)
        RETURN s, collect(ev) AS ev_nodes
        ORDER BY s.source_id ASC
        """

        # 2. Evidence from incident native relationships
        rel_ev_cypher = """
        MATCH (e:Entity {entity_id: $id})-[r:COMMUNICATED_WITH|OWNED_BY|ASSOCIATED_WITH|TRANSACTED_WITH]-()
        UNWIND r.evidence_ids AS ev_id
        MATCH (ev:Evidence {evidence_id: ev_id})-[:FROM_SOURCE]->(s:SourceRecord)
        RETURN DISTINCT r.relationship_id AS relationship_id,
               type(r) AS relationship_type,
               ev,
               s
        ORDER BY ev.evidence_id ASC
        """

        with self.driver.session() as session:
            direct_recs = list(session.run(direct_cypher, {"id": clean_id}))
            rel_ev_recs = list(session.run(rel_ev_cypher, {"id": clean_id}))

        source_records_by_id: Dict[str, Dict[str, Any]] = {}
        direct_evidence_by_id: Dict[str, Dict[str, Any]] = {}

        for d in direct_recs:
            s_dict = _format_source_record(d["s"])
            source_records_by_id[s_dict["source_id"]] = s_dict
            for ev_node in d["ev_nodes"]:
                if ev_node:
                    ev_dict = _format_evidence(ev_node)
                    direct_evidence_by_id[ev_dict["evidence_id"]] = ev_dict

        rel_evidence: List[Dict[str, Any]] = []
        for r in rel_ev_recs:
            ev_dict = _format_evidence(r["ev"])
            s_dict = _format_source_record(r["s"])
            rel_evidence.append(
                {
                    "relationship_id": r["relationship_id"],
                    "relationship_type": r["relationship_type"],
                    "evidence": ev_dict,
                    "source_record": s_dict,
                }
            )

        return {
            "entity_id": clean_id,
            "source_records": [source_records_by_id[k] for k in sorted(source_records_by_id.keys())],
            "direct_evidence": [direct_evidence_by_id[k] for k in sorted(direct_evidence_by_id.keys())],
            "relationship_evidence": rel_evidence,
        }

    def get_evidence_by_id(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """Direct lookup of an Evidence node and its originating SourceRecord."""
        if not evidence_id or not evidence_id.strip():
            raise ValueError("evidence_id must be a non-empty string.")

        cypher = """
        MATCH (ev:Evidence {evidence_id: $ev_id})-[:FROM_SOURCE]->(s:SourceRecord)
        RETURN ev, s
        """

        with self.driver.session() as session:
            rec = session.run(cypher, {"ev_id": evidence_id.strip()}).single()

        if not rec or rec["ev"] is None:
            return None

        return {
            "evidence": _format_evidence(rec["ev"]),
            "source_record": _format_source_record(rec["s"]),
        }

    # -------------------------------------------------------------------------
    # 7. Possible-Match Inspection
    # -------------------------------------------------------------------------
    def get_possible_matches(
        self,
        min_similarity: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Inspects unresolved candidate pairs connected via [:EVALUATED_PAIR] across the graph."""
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500.")
        if min_similarity is not None and not (0.0 <= min_similarity <= 1.0):
            raise ValueError("min_similarity must be between 0.0 and 1.0.")

        cypher = """
        MATCH (a:Entity)-[r:EVALUATED_PAIR]->(b:Entity)
        WHERE ($min_sim IS NULL OR r.similarity_score >= $min_sim)
        RETURN r,
               a.entity_id AS entity_id_a, a.canonical_name AS name_a, a.entity_type AS type_a,
               b.entity_id AS entity_id_b, b.canonical_name AS name_b, b.entity_type AS type_b
        ORDER BY r.similarity_score DESC, r.candidate_id ASC
        LIMIT $limit
        """

        with self.driver.session() as session:
            records = list(session.run(cypher, {"min_sim": min_similarity, "limit": limit}))

        results: List[Dict[str, Any]] = []
        for rec in records:
            r_props = dict(rec["r"])
            r_props.update(
                {
                    "entity_id_a": rec["entity_id_a"],
                    "name_a": rec["name_a"],
                    "type_a": rec["type_a"],
                    "entity_id_b": rec["entity_id_b"],
                    "name_b": rec["name_b"],
                    "type_b": rec["type_b"],
                }
            )
            results.append(r_props)
        return results

    def get_entity_possible_matches(self, entity_id: str, limit: int = 50,) -> List[Dict[str, Any]]:
        """Inspects unresolved candidate pairs involving a specific entity."""
        if not entity_id or not entity_id.strip():
            raise ValueError("entity_id must be a non-empty string.")

        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500.")

        cypher = """
        MATCH (a:Entity)-[r:EVALUATED_PAIR]->(b:Entity)
        WHERE a.entity_id = $id OR b.entity_id = $id
        RETURN r,
               a.entity_id AS entity_id_a, a.canonical_name AS name_a, a.entity_type AS type_a,
               b.entity_id AS entity_id_b, b.canonical_name AS name_b, b.entity_type AS type_b
        ORDER BY r.similarity_score DESC, r.candidate_id ASC
        """

        with self.driver.session() as session:
            records = list(session.run(cypher, {"id": entity_id.strip()}))

        results: List[Dict[str, Any]] = []
        for rec in records:
            r_props = dict(rec["r"])
            r_props.update(
                {
                    "entity_id_a": rec["entity_id_a"],
                    "name_a": rec["name_a"],
                    "type_a": rec["type_a"],
                    "entity_id_b": rec["entity_id_b"],
                    "name_b": rec["name_b"],
                    "type_b": rec["type_b"],
                }
            )
            results.append(r_props)
        return results
