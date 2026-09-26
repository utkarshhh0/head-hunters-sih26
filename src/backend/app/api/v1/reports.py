"""Reports API Endpoints for Phase 6C-A Backend."""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_workspace_service
from app.services.report_service import ReportService
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/findings/{finding_id}/pdf", response_class=Response)
def get_finding_report_pdf(
    finding_id: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> Response:
    """Generates and returns an investigative analytical PDF report for a finding.

    - Resolves the typed FindingProvenanceBundle.
    - Deterministically renders Jinja2 template and compiles via WeasyPrint.
    - Returns application/pdf with Content-Disposition derived from finding ID.
    - Raises 404 if the finding is not registered in the workspace.
    """
    clean_id = finding_id.strip() if finding_id else ""
    if not clean_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding identifier must not be empty.",
        )

    try:
        provenance = service.get_finding_provenance_bundle(clean_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding not found: {clean_id}",
        )

    report_service = ReportService()
    try:
        pdf_bytes = report_service.generate_pdf(provenance)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF report generation failed: {str(e)}",
        )

    # Sanitize finding ID for Content-Disposition filename
    safe_filename_part = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in clean_id)
    filename = f"finding_report_{safe_filename_part}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Type": "application/pdf",
        },
    )
