import { apiFetch } from './client';
import {
  FindingProvenanceBundle,
  FindingStatus,
  FindingStatusUpdate,
  InvestigativeFinding,
} from './types';

export interface ListFindingsParams {
  status?: FindingStatus;
  entity_id?: string;
  pattern_type?: string;
  limit?: number;
}

/**
 * List findings endpoint: GET /api/v1/findings
 */
export async function listFindings(
  params?: ListFindingsParams
): Promise<InvestigativeFinding[]> {
  const queryParams = new URLSearchParams();
  if (params?.status) {
    queryParams.append('status', params.status);
  }
  if (params?.entity_id) {
    queryParams.append('entity_id', params.entity_id);
  }
  if (params?.pattern_type) {
    queryParams.append('pattern_type', params.pattern_type);
  }
  if (params?.limit) {
    queryParams.append('limit', params.limit.toString());
  }

  const query = queryParams.toString();
  const endpoint = `/api/v1/findings${query ? `?${query}` : ''}`;
  return apiFetch<InvestigativeFinding[]>(endpoint);
}

/**
 * Get single finding by ID: GET /api/v1/findings/{finding_id}
 */
export async function getFinding(findingId: string): Promise<InvestigativeFinding> {
  return apiFetch<InvestigativeFinding>(`/api/v1/findings/${encodeURIComponent(findingId)}`);
}

/**
 * Update finding lifecycle status and investigator notes: PATCH /api/v1/findings/{finding_id}/status
 */
export async function updateFindingStatus(
  findingId: string,
  payload: FindingStatusUpdate
): Promise<InvestigativeFinding> {
  return apiFetch<InvestigativeFinding>(
    `/api/v1/findings/${encodeURIComponent(findingId)}/status`,
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }
  );
}

/**
 * Get end-to-end finding provenance bundle: GET /api/v1/findings/{finding_id}/provenance
 */
export async function getFindingProvenance(
  findingId: string
): Promise<FindingProvenanceBundle> {
  return apiFetch<FindingProvenanceBundle>(
    `/api/v1/findings/${encodeURIComponent(findingId)}/provenance`
  );
}
