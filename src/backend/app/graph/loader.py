"""Idempotent Neo4j Graph Loader for Phase-2 PipelineResult.

Persists:
1. SourceRecord nodes
2. Evidence nodes linked to SourceRecord via [:FROM_SOURCE]
3. Canonical Entity nodes with domain attributes
4. Pre-aggregated native relationships carrying:
   relationship_id, origin, confidence, first_seen, last_seen,
   interaction_count, evidence_ids, attributes_json
5. POSSIBLE_MATCH candidate pairs via [:EVALUATED_PAIR] (unmerged)

Guarantees:
- Idempotency: Repeated loads yield identical graph state with absolute synchronization.
- Strict provenance traversal: native edge -> evidence_ids -> (:Evidence)-[:FROM_SOURCE]->(:SourceRecord).
- No intermediate Relationship nodes, no HAS_EVIDENCE, no APOC, no LLM.
"""

import json
from typing import Any, Dict, List, Optional
from neo4j import Driver, Session

from app.schemas.record import SourceRecord
from app.schemas.entity import (
    Entity,
    EntityType,
    PersonEntity,
    PhoneEntity,
    VehicleEntity,
    LocationEntity,
    OrganizationEntity,
    AccountEntity,
)
from app.schemas.evidence import EvidenceProvenance
from app.schemas.relationship import (
    ResolutionCandidate,
    ResolutionStatus,
)
from app.pipeline import PipelineResult
from app.graph.config import Neo4jConfig, get_driver
from app.graph.pre_aggregation import (
    AggregatedRelationship,
    pre_aggregate_relationships,
    APPROVED_RELATIONSHIP_TYPES,
)

# Label mapping for Entity categories
ENTITY_TYPE_LABEL_MAP: Dict[str, str] = {
    EntityType.PERSON.value: "Person",
    EntityType.PHONE.value: "Phone",
    EntityType.VEHICLE.value: "Vehicle",
    EntityType.LOCATION.value: "Location",
    EntityType.ORGANIZATION.value: "Organization",
    EntityType.ACCOUNT.value: "Account",
}


class Neo4jGraphLoader:
    """Manages idempotent synchronization of PipelineResult into Neo4j."""

    def __init__(self, driver: Optional[Driver] = None, config: Optional[Neo4jConfig] = None):
        self.driver: Driver = driver or get_driver(config)
        self._owned_driver: bool = driver is None

    def close(self) -> None:
        """Closes the driver if internally owned."""
        if self._owned_driver and self.driver:
            self.driver.close()

    def __enter__(self) -> "Neo4jGraphLoader":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def init_schema(self, session: Optional[Session] = None) -> None:
        """Ensures unique constraints on primary identifiers."""
        constraints = [
            (
                "source_record_id_unique",
                "CREATE CONSTRAINT source_record_id_unique IF NOT EXISTS "
                "FOR (s:SourceRecord) REQUIRE s.source_id IS UNIQUE",
            ),
            (
                "evidence_id_unique",
                "CREATE CONSTRAINT evidence_id_unique IF NOT EXISTS "
                "FOR (e:Evidence) REQUIRE e.evidence_id IS UNIQUE",
            ),
            (
                "entity_id_unique",
                "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
                "FOR (n:Entity) REQUIRE n.entity_id IS UNIQUE",
            ),
        ]

        def _apply(s: Session):
            for _, query in constraints:
                s.run(query)

        if session:
            _apply(session)
        else:
            with self.driver.session() as s:
                _apply(s)

    def persist_source_records(self, session: Session, source_records: List[SourceRecord]) -> int:
        """Idempotently merges SourceRecord nodes."""
        cypher = """
        MERGE (s:SourceRecord {source_id: $source_id})
        SET s.source_type = $source_type,
            s.document_name = $document_name,
            s.raw_content = $raw_content,
            s.ingested_at = $ingested_at,
            s.metadata_json = $metadata_json
        """
        count = 0
        for src in source_records:
            session.run(
                cypher,
                {
                    "source_id": src.source_id,
                    "source_type": src.source_type,
                    "document_name": src.document_name,
                    "raw_content": src.raw_content,
                    "ingested_at": src.ingested_at.isoformat() if src.ingested_at else None,
                    "metadata_json": json.dumps(src.metadata, sort_keys=True),
                },
            )
            count += 1
        return count

    def persist_evidence_items(self, session: Session, evidence_items: List[EvidenceProvenance]) -> int:
        """Idempotently merges Evidence nodes and links them via [:FROM_SOURCE] to SourceRecord."""
        cypher = """
        MERGE (ev:Evidence {evidence_id: $evidence_id})
        SET ev.source_record_id = $source_record_id,
            ev.source_type = $source_type,
            ev.document_name = $document_name,
            ev.raw_snippet = $raw_snippet,
            ev.offset_start = $offset_start,
            ev.offset_end = $offset_end,
            ev.extractor_name = $extractor_name,
            ev.extracted_at = $extracted_at
        WITH ev
        MATCH (s:SourceRecord {source_id: $source_record_id})
        MERGE (ev)-[:FROM_SOURCE]->(s)
        """
        count = 0
        for ev in evidence_items:
            session.run(
                cypher,
                {
                    "evidence_id": ev.evidence_id,
                    "source_record_id": ev.source_record_id,
                    "source_type": ev.source_type,
                    "document_name": ev.document_name,
                    "raw_snippet": ev.raw_snippet,
                    "offset_start": ev.offset_start,
                    "offset_end": ev.offset_end,
                    "extractor_name": ev.extractor_name,
                    "extracted_at": ev.extracted_at.isoformat() if ev.extracted_at else None,
                },
            )
            count += 1
        return count

    def persist_entities(self, session: Session, entities: List[Entity]) -> int:
        """Idempotently merges canonical Entity nodes with domain properties."""
        count = 0
        for entity in entities:
            etype_str = entity.entity_type.value if hasattr(entity.entity_type, "value") else str(entity.entity_type)
            category_label = ENTITY_TYPE_LABEL_MAP.get(etype_str)

            props: Dict[str, Any] = {
                "entity_id": entity.entity_id,
                "entity_type": etype_str,
                "canonical_name": entity.canonical_name,
                "aliases": entity.aliases,
                "source_record_ids": entity.source_record_ids,
                "created_at": entity.created_at.isoformat() if entity.created_at else None,
                "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
                "attributes_json": json.dumps(entity.attributes, sort_keys=True),
            }

            # Map subtype-specific fields
            if isinstance(entity, PersonEntity):
                props.update({
                    "full_name": entity.full_name,
                    "dob": entity.dob,
                    "gender": entity.gender,
                    "national_id": entity.national_id,
                })
            elif isinstance(entity, PhoneEntity):
                props.update({
                    "phone_number": entity.phone_number,
                    "carrier": entity.carrier,
                    "imei": entity.imei,
                    "imsi": entity.imsi,
                })
            elif isinstance(entity, VehicleEntity):
                props.update({
                    "registration_number": entity.registration_number,
                    "make": entity.make,
                    "model": entity.model,
                    "color": entity.color,
                    "vin": entity.vin,
                })
            elif isinstance(entity, LocationEntity):
                props.update({
                    "address": entity.address,
                    "city": entity.city,
                    "state": entity.state,
                    "latitude": entity.latitude,
                    "longitude": entity.longitude,
                    "location_type": entity.location_type,
                })
            elif isinstance(entity, OrganizationEntity):
                props.update({
                    "org_name": entity.org_name,
                    "registration_id": entity.registration_id,
                    "org_type": entity.org_type,
                })
            elif isinstance(entity, AccountEntity):
                props.update({
                    "account_number": entity.account_number,
                    "bank_name": entity.bank_name,
                    "ifsc_code": entity.ifsc_code,
                    "account_type": entity.account_type,
                })

            if category_label:
                cypher = f"MERGE (n:Entity {{entity_id: $entity_id}}) SET n:{category_label}, n += $props"
            else:
                cypher = "MERGE (n:Entity {entity_id: $entity_id}) SET n += $props"

            session.run(cypher, {"entity_id": entity.entity_id, "props": props})
            count += 1
        return count

    def persist_aggregated_relationships(
        self, session: Session, aggregates: List[AggregatedRelationship]
    ) -> int:
        """Idempotently merges native Neo4j relationships carrying approved aggregate properties."""
        count = 0
        for agg in aggregates:
            rel_type = agg.relationship_type
            if rel_type not in APPROVED_RELATIONSHIP_TYPES:
                raise ValueError(
                    f"Unsupported relationship type: {rel_type!r}. "
                    f"Approved: {sorted(APPROVED_RELATIONSHIP_TYPES)}"
                )

            # Query safely parameterized with static-whitelisted relationship type
            cypher = f"""
            MATCH (source:Entity {{entity_id: $source_id}}), (target:Entity {{entity_id: $target_id}})
            MERGE (source)-[r:{rel_type} {{relationship_id: $relationship_id}}]->(target)
            SET r.origin = $origin,
                r.confidence = $confidence,
                r.first_seen = $first_seen,
                r.last_seen = $last_seen,
                r.interaction_count = $interaction_count,
                r.evidence_ids = $evidence_ids,
                r.attributes_json = $attributes_json
            """

            session.run(
                cypher,
                {
                    "source_id": agg.source_entity_id,
                    "target_id": agg.target_entity_id,
                    "relationship_id": agg.relationship_id,
                    "origin": agg.origin,
                    "confidence": agg.confidence,
                    "first_seen": agg.first_seen.isoformat() if agg.first_seen else None,
                    "last_seen": agg.last_seen.isoformat() if agg.last_seen else None,
                    "interaction_count": agg.interaction_count,
                    "evidence_ids": agg.evidence_ids,
                    "attributes_json": agg.attributes_json,
                },
            )
            count += 1
        return count

    def persist_possible_match_candidates(
        self, session: Session, candidates: List[ResolutionCandidate]
    ) -> int:
        """Persists unresolved POSSIBLE_MATCH candidate pairs as [:EVALUATED_PAIR] without merging."""
        cypher = """
        MATCH (a:Entity {entity_id: $entity_id_a}), (b:Entity {entity_id: $entity_id_b})
        MERGE (a)-[r:EVALUATED_PAIR {candidate_id: $candidate_id}]->(b)
        SET r.status = 'POSSIBLE_MATCH',
            r.similarity_score = $similarity_score,
            r.confidence = $confidence,
            r.heuristic_name = $heuristic_name,
            r.justification = $justification
        """
        count = 0
        for cand in candidates:
            if cand.status == ResolutionStatus.POSSIBLE_MATCH:
                session.run(
                    cypher,
                    {
                        "candidate_id": cand.candidate_id,
                        "entity_id_a": cand.entity_id_a,
                        "entity_id_b": cand.entity_id_b,
                        "similarity_score": cand.similarity_score,
                        "confidence": cand.confidence,
                        "heuristic_name": cand.heuristic_name,
                        "justification": cand.justification,
                    },
                )
                count += 1
        return count

    def load_pipeline_result(self, pipeline_result: PipelineResult) -> Dict[str, int]:
        """Loads and synchronizes an entire PipelineResult idempotently into Neo4j."""
        if pipeline_result is None:
            raise ValueError("PipelineResult cannot be None.")

        # Pre-aggregate relationships in Python before touching the database
        aggregates = pre_aggregate_relationships(pipeline_result.relationships)

        with self.driver.session() as session:
            self.init_schema(session)

            # 1. Source Records
            src_count = self.persist_source_records(session, pipeline_result.source_records)

            # 2. Evidence Items (linked via [:FROM_SOURCE] to SourceRecord)
            ev_count = self.persist_evidence_items(session, pipeline_result.evidence_items)

            # 3. Canonical Entities
            ent_count = self.persist_entities(session, pipeline_result.extracted_entities)

            # 4. Native Pre-Aggregated Relationships
            rel_count = self.persist_aggregated_relationships(session, aggregates)

            # 5. POSSIBLE_MATCH candidate pairs as EVALUATED_PAIR
            pair_count = self.persist_possible_match_candidates(
                session, pipeline_result.resolution_candidates
            )

        return {
            "source_records": src_count,
            "evidence_items": ev_count,
            "entities": ent_count,
            "relationships": rel_count,
            "evaluated_pairs": pair_count,
        }


def load_pipeline_result(
    pipeline_result: PipelineResult,
    driver: Optional[Driver] = None,
    config: Optional[Neo4jConfig] = None,
) -> Dict[str, int]:
    """Convenience functional interface for loading a PipelineResult into Neo4j."""
    with Neo4jGraphLoader(driver=driver, config=config) as loader:
        return loader.load_pipeline_result(pipeline_result)
