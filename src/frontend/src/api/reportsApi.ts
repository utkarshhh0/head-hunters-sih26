/**
 * Frontend API client helper for Investigative PDF Reports (Phase 6C).
 */

import { ApiRequestError } from './client';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

/**
 * Fetch analytical PDF report for a given finding:
 * GET /api/v1/reports/findings/{finding_id}/pdf
 *
 * Returns raw Blob for in-browser PDF.js rendering and downloading.
 */
export async function getFindingReportPdf(findingId: string): Promise<Blob> {
  const cleanId = (findingId || '').trim();
  if (!cleanId) {
    throw new ApiRequestError(400, 'Finding identifier must not be empty.');
  }

  const endpoint = `/api/v1/reports/findings/${encodeURIComponent(cleanId)}/pdf`;
  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      Accept: 'application/pdf',
    },
  });

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status} ${response.statusText}`;
    try {
      const errorData = await response.json();
      if (errorData && typeof errorData.detail === 'string') {
        errorMessage = errorData.detail;
      } else if (errorData && typeof errorData.detail === 'object') {
        errorMessage = JSON.stringify(errorData.detail);
      }
    } catch {
      // Non-JSON response fallback
    }
    throw new ApiRequestError(response.status, errorMessage);
  }

  return await response.blob();
}
