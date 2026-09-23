"""Generic Executable Data Pipeline Package."""

from typing import List
from pydantic import BaseModel, ConfigDict

from app.schemas.record import SourceRecord, NormalizedRecord
from app.schemas.entity import Entity
from app.schemas.evidence import EvidenceProvenance
from app.schemas.relationship import ResolutionCandidate, ResolutionDecision, Relationship
from app.pipeline.ingestion import ingest_raw_source
from app.pipeline.normalization import normalize_record
from app.pipeline.extraction import extract_entities_and_relationships
from app.pipeline.resolution import resolve_entities_and_link_relationships


class PipelineResult(BaseModel):
    """Container holding outputs of an executed pipeline run."""

    model_config = ConfigDict(extra="forbid")

    source_records: List[SourceRecord]
    normalized_records: List[NormalizedRecord]
    extracted_entities: List[Entity]
    evidence_items: List[EvidenceProvenance]
    resolution_candidates: List[ResolutionCandidate]
    resolution_decisions: List[ResolutionDecision]
    relationships: List[Relationship]


__all__ = [
    "ingest_raw_source",
    "normalize_record",
    "extract_entities_and_relationships",
    "resolve_entities_and_link_relationships",
    "PipelineResult",
]
