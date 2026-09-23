"""Generic Deterministic Normalization Engine.

This module provides field standardization functions for timestamps, phone numbers,
vehicle registrations, and canonical text strings, outputting NormalizedRecord objects.

Original raw source content is preserved byte-for-byte without modification.
"""

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.schemas.record import SourceRecord, NormalizedRecord


def normalize_phone_number(raw_phone: str) -> str:
    """Normalizes phone numbers to standard E.164 format (+91-XXXXXXXXXX)."""
    if not raw_phone:
        return ""
    digits = re.sub(r"\D", "", raw_phone)
    if digits.startswith("91") and len(digits) == 12:
        return f"+91-{digits[2:]}"
    elif len(digits) == 10:
        return f"+91-{digits}"
    return raw_phone.strip()


def normalize_vehicle_plate(raw_plate: str) -> str:
    """Normalizes Indian vehicle registration plates to standard format (e.g. DL-01-AB-1234)."""
    if not raw_plate:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw_plate).upper()
    match = re.match(r"^([A-Z]{2})(\d{2})([A-Z]{1,2})(\d{4})$", cleaned)
    if match:
        state, district, series, number = match.groups()
        return f"{state}-{district}-{series}-{number}"
    return cleaned


def normalize_timestamp(raw_dt: Any) -> Optional[datetime]:
    """Parses and normalizes timestamps into timezone-aware UTC datetime objects."""
    if isinstance(raw_dt, datetime):
        if raw_dt.tzinfo is None:
            return raw_dt.replace(tzinfo=timezone.utc)
        return raw_dt.astimezone(timezone.utc)
    if isinstance(raw_dt, str):
        try:
            # Handle ISO string formats
            dt = datetime.fromisoformat(raw_dt.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            pass
    return None


def normalize_record(
    source_record: SourceRecord,
    normalized_at: Optional[datetime] = None,
) -> NormalizedRecord:
    """Produces a NormalizedRecord with standardized canonical text and fields."""
    if source_record is None:
        raise ValueError("source_record cannot be None.")

    effective_timestamp = (
        normalized_at
        if normalized_at is not None
        else source_record.ingested_at
    )

    canonical_text = " ".join(source_record.raw_content.split()).upper()
    extracted_fields: Dict[str, Any] = {}

    # Standardize metadata / extracted fields if present in source metadata
    if "extracted_fields" in source_record.metadata:
        for k, v in source_record.metadata["extracted_fields"].items():
            if "phone" in k.lower() and isinstance(v, str):
                extracted_fields[k] = normalize_phone_number(v)
            elif "vehicle" in k.lower() or "reg" in k.lower() and isinstance(v, str):
                extracted_fields[k] = normalize_vehicle_plate(v)
            else:
                extracted_fields[k] = v

    timestamp_ctx = source_record.metadata.get("timestamp_context")
    normalized_timestamp = normalize_timestamp(timestamp_ctx)

    # Compute deterministic SHA-256 record_id
    hash_input = f"{source_record.source_id}:{canonical_text}".encode("utf-8")
    norm_hash = hashlib.sha256(hash_input).hexdigest()[:12]
    record_id = f"urn:norm:{norm_hash}"

    return NormalizedRecord(
        record_id=record_id,
        source_id=source_record.source_id,
        canonical_text=canonical_text,
        extracted_fields=extracted_fields,
        timestamp_context=normalized_timestamp,
        normalized_at=effective_timestamp,
    )
