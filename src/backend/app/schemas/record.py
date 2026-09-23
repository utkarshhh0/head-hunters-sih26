"""Source and Normalized Record Schemas for Ingestion Pipeline."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class SourceRecord(BaseModel):
    """Represents an ingested raw source document or data feed entry."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., description="Unique URN identifier for the source record e.g. urn:source:cdr:001")
    source_type: str = Field(..., description="Type of source feed e.g. CALL_DETAIL_RECORD, VEHICLE_TOLL_LOG, FIR_REPORT")
    document_name: str = Field(..., description="Title or filename of original raw record")
    raw_content: str = Field(..., description="Original unedited text or row values")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Header, origin, or file metadata")
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Ingestion timestamp")


class NormalizedRecord(BaseModel):
    """Represents a standardized, parsed version of a source record."""

    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(..., description="Unique URN identifier for normalized record e.g. urn:norm:001")
    source_id: str = Field(..., description="Foreign key reference to SourceRecord.source_id")
    canonical_text: str = Field(..., description="Standardized canonical text representation")
    extracted_fields: Dict[str, Any] = Field(default_factory=dict, description="Normalized field key-value pairs")
    timestamp_context: Optional[datetime] = Field(None, description="Primary event timestamp extracted from source")
    normalized_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Normalization timestamp")

