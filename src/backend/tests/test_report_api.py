"""Integration Tests for Reports API Endpoints (Phase 6C-A Backend).

Verifies:
1. GET /api/v1/reports/findings/{finding_id}/pdf returns 200 with application/pdf.
2. Content-Disposition header contains safe filename derived from finding ID.
3. PDF content is valid binary bytes (starting with %PDF-).
4. Missing finding returns 404.
5. Empty / invalid finding ID returns 404.
6. No arbitrary filesystem path exposure in response headers or body.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from main import app
from app.api.deps import set_workspace_service
from app.schemas.finding import FindingStatus, InvestigativeFinding
from app.schemas.analytics import MultiSignalPattern, PatternType, TimeWindow
from app.schemas.workspace import FindingProvenanceBundle


@pytest.fixture
def mock_provenance_bundle() -> FindingProvenanceBundle:
    """Creates a sample FindingProvenanceBundle for API testing."""
    t_start = datetime(2026, 3, 10, 8, 30, 0, tzinfo=timezone.utc)
    t_end = datetime(2026, 3, 10, 11, 45, 0, tzinfo=timezone.utc)

    finding = InvestigativeFinding(
        finding_id="urn:finding:hub_burst:001",
        title="Pattern Flagged for Investigation: Intermediary Hub (Vikram Malhotra)",
        summary="Entity Vikram Malhotra exhibits topological bridge characteristics and communication burst.",
        entity_ids=["urn:entity:person:001", "urn:entity:person:002"],
        relationship_ids=["urn:rel:comm:101"],
        signal_ids=["urn:sig:bridge:001", "urn:sig:burst:001"],
        evidence_ids=["urn:ev:call:901"],
        confidence=1.0,
        caveats=["Analytical observation in controlled demonstration environment."],
        created_at=t_end,
        status=FindingStatus.OPEN,
        pattern_id="urn:pattern:hub_burst:001",
        pattern_type="INTERMEDIARY_HUB_BURST",
        time_window=TimeWindow(start_time=t_start, end_time=t_end),
        investigator_notes="Triage in progress.",
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
        explanation="Multi-signal convergence observed.",
        limitations=["Controlled environment."],
    )

    return FindingProvenanceBundle(
        finding=finding,
        pattern=pattern,
        signals=[
            {
                "signal_id": "urn:sig:bridge:001",
                "signal_type": "BRIDGE_CANDIDATE",
                "metric_value": 0.8421,
                "rule_description": "High betweenness centrality observed",
                "entity_ids": ["urn:entity:person:001"],
                "relationship_ids": ["urn:rel:comm:101"],
            },
            {
                "signal_id": "urn:sig:burst:001",
                "signal_type": "BURST_COMMUNICATION_WINDOW",
                "metric_value": 14.0,
                "rule_description": "Concentrated communication window observed",
                "entity_ids": ["urn:entity:person:001", "urn:entity:person:002"],
                "relationship_ids": ["urn:rel:comm:101"],
            },
        ],
        entities=[
            {
                "entity_id": "urn:entity:person:001",
                "canonical_name": "Vikram Malhotra",
                "entity_type": "PERSON",
            },
            {
                "entity_id": "urn:entity:person:002",
                "canonical_name": "Rajesh Kumar",
                "entity_type": "PERSON",
            },
        ],
        relationships=[
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
        ],
        evidence=[
            {
                "evidence_id": "urn:ev:call:901",
                "extraction_type": "CALL_LOG_RECORD",
                "extracted_value": "Call duration 420s",
                "confidence": 1.0,
                "source_id": "urn:source:cdr:001",
            }
        ],
        source_records=[
            {
                "source_id": "urn:source:cdr:001",
                "source_type": "CALL_DATA_RECORD",
                "document_name": "CDR_20260310_BATCH_A.csv",
                "ingested_at": datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc),
                "raw_content": "+919876543210,+919876543211,420s",
            }
        ],
    )


@pytest.fixture
def client_with_workspace_service(mock_provenance_bundle: FindingProvenanceBundle):
    """Sets up a TestClient with a controlled WorkspaceService mock without live Neo4j."""
    mock_service = MagicMock()

    def get_bundle(finding_id: str):
        clean_id = finding_id.strip()
        if clean_id == "urn:finding:hub_burst:001":
            return mock_provenance_bundle
        raise KeyError(f"Finding not found: {clean_id}")

    mock_service.get_finding_provenance_bundle.side_effect = get_bundle
    set_workspace_service(mock_service)

    with TestClient(app) as client:
        yield client

    set_workspace_service(None)


def test_get_finding_pdf_success(client_with_workspace_service: TestClient):
    """Verifies that GET /api/v1/reports/findings/{finding_id}/pdf returns 200 with valid PDF."""
    finding_id = "urn:finding:hub_burst:001"
    response = client_with_workspace_service.get(f"/api/v1/reports/findings/{finding_id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "Content-Disposition" in response.headers
    assert "finding_report_urn_finding_hub_burst_001.pdf" in response.headers["Content-Disposition"]
    assert response.content.startswith(b"%PDF-")
    assert len(response.content) > 500


def test_get_finding_pdf_missing_returns_404(client_with_workspace_service: TestClient):
    """Verifies that requesting a PDF for a non-existent finding returns 404."""
    response = client_with_workspace_service.get("/api/v1/reports/findings/urn:finding:nonexistent:999/pdf")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_finding_pdf_empty_returns_404(client_with_workspace_service: TestClient):
    """Verifies that an empty or whitespace finding_id returns 404."""
    response = client_with_workspace_service.get("/api/v1/reports/findings/%20%20/pdf")

    assert response.status_code == 404


def test_no_filesystem_exposure(client_with_workspace_service: TestClient):
    """Verifies that internal server filesystem paths are never leaked in response headers."""
    finding_id = "urn:finding:hub_burst:001"
    response = client_with_workspace_service.get(f"/api/v1/reports/findings/{finding_id}/pdf")

    assert response.status_code == 200
    for header_name, header_value in response.headers.items():
        assert "D:\\" not in header_value
        assert "C:\\" not in header_value
        assert "/home/" not in header_value
