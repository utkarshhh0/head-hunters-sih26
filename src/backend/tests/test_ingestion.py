"""Unit Tests for Generic Ingestion and Normalization Engine."""

from datetime import datetime, timezone
import pytest

from app.pipeline.ingestion import ingest_raw_source
from app.pipeline.normalization import normalize_record, normalize_phone_number, normalize_vehicle_plate

# Operation Hawkeye raw synthetic test payloads (declared strictly inside test code)
HAWKEYE_CDR_RAW = "CALL,2026-08-10T01:15:00Z,+91-9900000101,+91-9900000102,480s,TOWER_DELHI_NORTH"
HAWKEYE_TOLL_RAW = '{"timestamp":"2026-08-10T02:30:00Z","reg":"DL-01-AB-1234","toll_id":"TOLL_NH48_KM42","owner":"Aarav Sharma"}'
HAWKEYE_FIR_RAW = "FIR #882/2026: Suspect alias 'V. Singh' sighted driving black sedan reg DL-01-AB-1234 near illegal warehouse."
HAWKEYE_BANK_RAW = "TXN,2026-08-10T04:00:00Z,ACC-112233,ACC-998877,450000.00,INR,REMARKS:APEX_SUPPLY"
HAWKEYE_HOTEL_RAW = '{"checkin":"2026-08-10T06:00:00Z","guest":"Vikram Singh","phone":"+91-9900000101","national_id":"IND-98765432","vehicle":"DL-01-AB-1234"}'


def test_ingest_all_five_raw_source_formats():
    """Test generic ingestion across all 5 synthetic raw formats."""
    fixed_dt = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)

    # 1. CDR CSV
    cdr_source = ingest_raw_source(
        raw_content=HAWKEYE_CDR_RAW,
        source_type="CALL_DETAIL_RECORD",
        document_name="cdr.csv",
        ingested_at=fixed_dt,
    )
    assert cdr_source.raw_content == HAWKEYE_CDR_RAW
    assert cdr_source.source_type == "CALL_DETAIL_RECORD"
    assert cdr_source.source_id.startswith("urn:source:call_detail_record:")

    # 2. Toll JSON
    toll_source = ingest_raw_source(
        raw_content=HAWKEYE_TOLL_RAW,
        source_type="VEHICLE_TOLL_LOG",
        document_name="toll.json",
        ingested_at=fixed_dt,
    )
    assert toll_source.raw_content == HAWKEYE_TOLL_RAW

    # 3. FIR Text
    fir_source = ingest_raw_source(
        raw_content=HAWKEYE_FIR_RAW,
        source_type="FIR_REPORT",
        document_name="fir.txt",
        ingested_at=fixed_dt,
    )
    assert fir_source.raw_content == HAWKEYE_FIR_RAW

    # 4. Bank CSV
    bank_source = ingest_raw_source(
        raw_content=HAWKEYE_BANK_RAW,
        source_type="BANK_TRANSACTION",
        document_name="bank.csv",
        ingested_at=fixed_dt,
    )
    assert bank_source.raw_content == HAWKEYE_BANK_RAW

    # 5. Hotel JSON
    hotel_source = ingest_raw_source(
        raw_content=HAWKEYE_HOTEL_RAW,
        source_type="HOTEL_CHECKIN",
        document_name="hotel.json",
        ingested_at=fixed_dt,
    )
    assert hotel_source.raw_content == HAWKEYE_HOTEL_RAW


def test_ingestion_raw_content_preservation_and_metadata():
    """Test that raw_content is preserved byte-for-byte and metadata is attached."""
    fixed_dt = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    source = ingest_raw_source(
        raw_content=HAWKEYE_FIR_RAW,
        source_type="FIR_REPORT",
        document_name="fir.txt",
        metadata={"custom_meta": "test_val"},
        ingested_at=fixed_dt,
    )
    assert source.raw_content == HAWKEYE_FIR_RAW
    assert source.metadata.get("is_synthetic") is True
    assert source.metadata.get("custom_meta") == "test_val"
    assert source.ingested_at == fixed_dt


def test_normalization_rules_and_preservation():
    """Test E.164 phone, vehicle plate, and date normalization while raw_content remains unchanged."""
    fixed_dt = datetime(2026, 8, 10, 1, 0, 0, tzinfo=timezone.utc)
    source = ingest_raw_source(
        raw_content=HAWKEYE_CDR_RAW,
        source_type="CALL_DETAIL_RECORD",
        document_name="cdr.csv",
        ingested_at=fixed_dt,
    )
    norm = normalize_record(source, normalized_at=fixed_dt)

    assert norm.source_id == source.source_id
    assert source.raw_content == HAWKEYE_CDR_RAW  # Unchanged
    assert norm.canonical_text == "CALL,2026-08-10T01:15:00Z,+91-9900000101,+91-9900000102,480S,TOWER_DELHI_NORTH"

    # Test phone normalization helper
    assert normalize_phone_number("9900000101") == "+91-9900000101"
    assert normalize_phone_number("+91-9900000101") == "+91-9900000101"

    # Test vehicle plate normalization helper
    assert normalize_vehicle_plate("dl 01 ab 1234") == "DL-01-AB-1234"
    assert normalize_vehicle_plate("DL01AB1234") == "DL-01-AB-1234"
