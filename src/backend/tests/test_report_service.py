"""Unit Tests for ReportService (Phase 6C-A Backend).

Verifies:
1. Report view data uses real provenance values (finding, pattern, signals, entities, relationships, evidence, source records).
2. HTML rendering contains actual finding title, ID, evidence, entity names.
3. PDF generation returns valid PDF bytes (starting with %PDF-).
4. Zero fabricated evidence, timestamps, or entities.
5. Deterministic report content apart from explicit generated timestamp.
6. Proper omission of investigator notes when absent.
7. Language compliance (no claims of guilt, criminality, conspiracy, mastermind, etc.).
"""

from datetime import datetime, timezone
from typing import Any, Dict
import pytest

from app.schemas.finding import FindingStatus, InvestigativeFinding
from app.schemas.analytics import MultiSignalPattern, PatternType, TimeWindow
from app.schemas.workspace import FindingProvenanceBundle
from app.services.report_service import ReportService


@pytest.fixture
def sample_provenance_bundle() -> FindingProvenanceBundle:
    """Creates a realistic, complete FindingProvenanceBundle fixture."""
    t_start = datetime(2026, 3, 10, 8, 30, 0, tzinfo=timezone.utc)
    t_end = datetime(2026, 3, 10, 11, 45, 0, tzinfo=timezone.utc)

    finding = InvestigativeFinding(
        finding_id="urn:finding:hub_burst:001",
        title="Pattern Flagged for Investigation: Intermediary Hub with Concentrated Activity (Vikram Malhotra)",
        summary="Entity Vikram Malhotra exhibits topological bridge characteristics and concentrated communication burst.",
        entity_ids=["urn:entity:person:001", "urn:entity:person:002"],
        relationship_ids=["urn:rel:comm:101"],
        signal_ids=["urn:sig:bridge:001", "urn:sig:burst:001"],
        evidence_ids=["urn:ev:call:901"],
        confidence=1.0,
        caveats=["Observed pattern derived from synthetic communication logs under controlled conditions."],
        created_at=t_end,
        status=FindingStatus.OPEN,
        pattern_id="urn:pattern:hub_burst:001",
        pattern_type="INTERMEDIARY_HUB_BURST",
        time_window=TimeWindow(start_time=t_start, end_time=t_end),
        investigator_notes="Preliminary triage completed. Recommend entity verification.",
    )

    pattern = MultiSignalPattern(
        pattern_id="urn:pattern:hub_burst:001",
        pattern_type=PatternType.INTERMEDIARY_HUB_BURST,
        title="Pattern Flagged for Investigation: Intermediary Hub with Concentrated Activity",
        entity_ids=["urn:entity:person:001", "urn:entity:person:002"],
        contributing_signal_ids=["urn:sig:bridge:001", "urn:sig:burst:001"],
        contributing_signal_types=["BRIDGE_CANDIDATE", "BURST_COMMUNICATION_WINDOW"],
        relationship_ids=["urn:rel:comm:101"],
        evidence_ids=["urn:ev:call:901"],
        time_window=TimeWindow(start_time=t_start, end_time=t_end),
        detection_method="heuristic_multi_signal_convergence:hub_burst",
        explanation="Entity connects disjoint network components during anomalous temporal density window.",
        limitations=["Subject to boundary conditions of synthetic monitoring window."],
    )

    signals: list[Dict[str, Any]] = [
        {
            "signal_id": "urn:sig:bridge:001",
            "signal_type": "BRIDGE_CANDIDATE",
            "metric_value": 0.8421,
            "rule_description": "Betweenness centrality exceeds 95th percentile with bridging topology",
            "entity_ids": ["urn:entity:person:001"],
            "relationship_ids": ["urn:rel:comm:101"],
        },
        {
            "signal_id": "urn:sig:burst:001",
            "signal_type": "BURST_COMMUNICATION_WINDOW",
            "metric_value": 14.0,
            "rule_description": "14 interactions within 3-hour sliding temporal window",
            "entity_ids": ["urn:entity:person:001", "urn:entity:person:002"],
            "relationship_ids": ["urn:rel:comm:101"],
        },
    ]

    entities: list[Dict[str, Any]] = [
        {
            "entity_id": "urn:entity:person:001",
            "canonical_name": "Vikram Malhotra",
            "entity_type": "PERSON",
            "degree": 12,
            "phone_number": "+919876543210",
        },
        {
            "entity_id": "urn:entity:person:002",
            "canonical_name": "Rajesh Kumar",
            "entity_type": "PERSON",
            "degree": 5,
            "phone_number": "+919876543211",
        },
    ]

    relationships: list[Dict[str, Any]] = [
        {
            "relationship_id": "urn:rel:comm:101",
            "source_entity_id": "urn:entity:person:001",
            "target_entity_id": "urn:entity:person:002",
            "relationship_type": "COMMUNICATION",
            "interaction_count": 14,
            "first_seen": datetime(2026, 3, 10, 8, 35, 0, tzinfo=timezone.utc),
            "last_seen": datetime(2026, 3, 10, 11, 40, 0, tzinfo=timezone.utc),
            "evidence_ids": ["urn:ev:call:901"],
        }
    ]

    evidence: list[Dict[str, Any]] = [
        {
            "evidence_id": "urn:ev:call:901",
            "extraction_type": "CALL_LOG_RECORD",
            "extracted_value": "Call duration 420s between +919876543210 and +919876543211",
            "confidence": 1.0,
            "source_id": "urn:source:cdr:001",
        }
    ]

    source_records: list[Dict[str, Any]] = [
        {
            "source_id": "urn:source:cdr:001",
            "source_type": "CALL_DATA_RECORD",
            "document_name": "CDR_20260310_BATCH_A.csv",
            "ingested_at": datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc),
            "raw_content": "+919876543210,+919876543211,2026-03-10T08:35:00Z,420,TOWER_4B",
        }
    ]

    return FindingProvenanceBundle(
        finding=finding,
        pattern=pattern,
        signals=signals,
        entities=entities,
        relationships=relationships,
        evidence=evidence,
        source_records=source_records,
    )


def test_report_view_data_uses_real_provenance_values(sample_provenance_bundle: FindingProvenanceBundle):
    """Verifies that report view data extracts and presents exact provenance values."""
    service = ReportService()
    fixed_time = datetime(2026, 9, 25, 12, 0, 0, tzinfo=timezone.utc)
    data = service.build_report_data(sample_provenance_bundle, generated_at=fixed_time)

    # 1. Header
    assert data["header"]["finding_id"] == "urn:finding:hub_burst:001"
    assert data["header"]["status"] == "OPEN"
    assert data["header"]["pattern_type"] == "INTERMEDIARY_HUB_BURST"
    assert "2026-09-25" in data["header"]["generated_at"]
    assert "DEMONSTRATION NOTICE" in data["header"]["synthetic_notice"].upper()

    # 2. Executive Summary
    assert data["summary"]["title"] == sample_provenance_bundle.finding.title
    assert data["summary"]["summary"] == sample_provenance_bundle.finding.summary
    assert "2026-03-10T08:30:00+00:00 to 2026-03-10T11:45:00+00:00" in data["summary"]["time_window_text"]
    assert len(data["summary"]["caveats"]) == 1

    # 3. Entities
    assert len(data["entities"]) == 2
    assert data["entities"][0]["entity_id"] == "urn:entity:person:001"
    assert data["entities"][0]["canonical_name"] == "Vikram Malhotra"
    assert data["entities"][1]["canonical_name"] == "Rajesh Kumar"

    # 4. Relationships
    assert len(data["relationships"]) == 1
    assert data["relationships"][0]["relationship_id"] == "urn:rel:comm:101"
    assert data["relationships"][0]["interaction_count"] == 14

    # 5. Signals
    assert len(data["signals"]) == 2
    assert data["signals"][0]["signal_id"] == "urn:sig:bridge:001"
    assert data["signals"][0]["metric_value"] == pytest.approx(0.8421)

    # 6. Supporting Evidence & Source Records
    assert len(data["evidence_items"]) == 1
    ev_item = data["evidence_items"][0]
    assert ev_item["evidence_id"] == "urn:ev:call:901"
    assert ev_item["source_record"] is not None
    assert ev_item["source_record"]["source_id"] == "urn:source:cdr:001"
    assert ev_item["source_record"]["document_name"] == "CDR_20260310_BATCH_A.csv"

    # 7. Investigator Notes
    assert data["investigator_notes"] == "Preliminary triage completed. Recommend entity verification."


def test_no_fabricated_evidence_timestamps_entities(sample_provenance_bundle: FindingProvenanceBundle):
    """Verifies that no entities, evidence, or timestamps are fabricated."""
    service = ReportService()

    # Bundle with NO temporal window and NO relationship timestamps
    undated_finding = sample_provenance_bundle.finding.model_copy(update={"time_window": None})
    undated_rels = [
        {
            "relationship_id": "urn:rel:comm:101",
            "source_entity_id": "urn:entity:person:001",
            "target_entity_id": "urn:entity:person:002",
            "relationship_type": "COMMUNICATION",
            "interaction_count": None,
            "first_seen": None,
            "last_seen": None,
            "evidence_ids": [],
        }
    ]
    undated_bundle = FindingProvenanceBundle(
        finding=undated_finding,
        pattern=None,
        signals=[],
        entities=sample_provenance_bundle.entities,
        relationships=undated_rels,
        evidence=[],
        source_records=[],
    )

    data = service.build_report_data(undated_bundle)
    assert data["summary"]["time_window_text"] == "Not temporally bounded"
    assert len(data["timeline_events"]) == 0  # Zero fabricated timestamps!
    assert len(data["evidence_items"]) == 0  # Zero fabricated evidence!
    assert len(data["entities"]) == 2  # Exactly matches provenance entities!


def test_deterministic_report_content(sample_provenance_bundle: FindingProvenanceBundle):
    """Verifies that report view data and HTML rendering are 100% deterministic given a timestamp."""
    service = ReportService()
    fixed_time = datetime(2026, 9, 25, 14, 30, 0, tzinfo=timezone.utc)

    data_1 = service.build_report_data(sample_provenance_bundle, generated_at=fixed_time)
    data_2 = service.build_report_data(sample_provenance_bundle, generated_at=fixed_time)
    assert data_1 == data_2

    html_1 = service.render_html(sample_provenance_bundle, generated_at=fixed_time)
    html_2 = service.render_html(sample_provenance_bundle, generated_at=fixed_time)
    assert html_1 == html_2
    assert len(html_1) > 0


def test_html_rendering_contains_actual_values(sample_provenance_bundle: FindingProvenanceBundle):
    """Verifies that the rendered HTML contains key provenance details."""
    service = ReportService()
    fixed_time = datetime(2026, 9, 25, 12, 0, 0, tzinfo=timezone.utc)
    html = service.render_html(sample_provenance_bundle, generated_at=fixed_time)

    # Required headers and titles
    assert "Investigative Analytical Report" in html
    assert "urn:finding:hub_burst:001" in html
    assert "Vikram Malhotra" in html
    assert "Rajesh Kumar" in html
    assert "urn:rel:comm:101" in html
    assert "urn:sig:bridge:001" in html
    assert "0.8421" in html
    assert "urn:ev:call:901" in html
    assert "CDR_20260310_BATCH_A.csv" in html
    assert "Preliminary triage completed. Recommend entity verification." in html
    assert "DEMONSTRATION NOTICE" in html.upper()


def test_investigator_notes_omitted_when_absent(sample_provenance_bundle: FindingProvenanceBundle):
    """Verifies that investigator notes section is cleanly omitted when notes are None."""
    service = ReportService()
    bundle_no_notes = sample_provenance_bundle.model_copy(
        update={
            "finding": sample_provenance_bundle.finding.model_copy(update={"investigator_notes": None})
        }
    )
    html = service.render_html(bundle_no_notes)
    assert "8. Investigator Notes" not in html


def test_pdf_generation_returns_valid_pdf_bytes(sample_provenance_bundle: FindingProvenanceBundle):
    """Verifies that WeasyPrint generates valid PDF bytes starting with %PDF-."""
    service = ReportService()
    fixed_time = datetime(2026, 9, 25, 12, 0, 0, tzinfo=timezone.utc)
    pdf_bytes = service.generate_pdf(sample_provenance_bundle, generated_at=fixed_time)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-")


def test_neutral_language_compliance(sample_provenance_bundle: FindingProvenanceBundle):
    """Verifies that prohibited biased/legal-conclusion terms never appear in report output."""
    service = ReportService()
    html = service.render_html(sample_provenance_bundle).lower()

    prohibited_terms = [
        "guilt",
        "criminality",
        "conspiracy",
        "mastermind",
        "illicit network",
        "legal admissibility",
        "court readiness",
    ]
    for term in prohibited_terms:
        assert term not in html, f"Prohibited term '{term}' found in report HTML!"
