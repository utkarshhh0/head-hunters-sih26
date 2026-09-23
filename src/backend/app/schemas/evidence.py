"""Evidence and Provenance Traceability Schemas."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class EvidenceProvenance(BaseModel):
    """Immutable evidence provenance record linking pipeline artifacts back to raw source material."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(..., description="Unique URN for evidence e.g. urn:ev:001")
    source_record_id: str = Field(..., description="Foreign key reference to SourceRecord.source_id")
    source_type: str = Field(..., description="Type of raw source file e.g. CALL_DETAIL_RECORD, TOLL_LOG")
    document_name: str = Field(..., description="Document or feed name")
    raw_snippet: str = Field(..., description="Exact raw text snippet or row excerpt from source")
    offset_start: Optional[int] = Field(None, description="Starting text offset index")
    offset_end: Optional[int] = Field(None, description="Ending text offset index")
    extractor_name: str = Field(..., description="Name of extractor or rule that derived this evidence")
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Extraction timestamp")

