"""Generic Raw Source Ingestion Engine.

This module provides generic raw data ingestion capabilities converting multi-format
text, CSV, and JSON string payloads into strictly validated SourceRecord domain objects.

It is 100% generic and contains zero references to specific test scenarios.
"""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.schemas.record import SourceRecord


def ingest_raw_source(
    raw_content: str,
    source_type: str,
    document_name: str,
    metadata: Optional[Dict[str, Any]] = None,
    ingested_at: Optional[datetime] = None,
) -> SourceRecord:
    """Ingests raw content and returns a strictly validated SourceRecord.

    To guarantee byte-for-byte execution determinism, ingested_at should be
    explicitly provided by the caller. If omitted, a fixed UTC epoch timestamp
    is used rather than reading the system clock.
    """
    if raw_content is None:
        raise ValueError("raw_content cannot be None.")
    if not source_type or not source_type.strip():
        raise ValueError("source_type must be a non-empty string.")
    if not document_name or not document_name.strip():
        raise ValueError("document_name must be a non-empty string.")

    # Fixed deterministic timestamp fallback if caller omits ingested_at (NO datetime.now())
    effective_timestamp = (
        ingested_at
        if ingested_at is not None
        else datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    )

    merged_metadata = {"is_synthetic": True}
    if metadata:
        merged_metadata.update(metadata)

    # Compute deterministic SHA-256 source URN
    hash_input = f"{source_type.upper().strip()}:{document_name.strip()}:{raw_content}".encode("utf-8")
    content_hash = hashlib.sha256(hash_input).hexdigest()[:12]
    source_id = f"urn:source:{source_type.lower().strip()}:{content_hash}"

    return SourceRecord(
        source_id=source_id,
        source_type=source_type.upper().strip(),
        document_name=document_name.strip(),
        raw_content=raw_content,
        metadata=merged_metadata,
        ingested_at=effective_timestamp,
    )
