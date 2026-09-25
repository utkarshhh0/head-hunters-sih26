import { apiFetch } from './client';
import { HealthResponse, InvestigativeFinding, WorkspaceSummary } from './types';

/**
 * Health check endpoint: GET /health
 */
export async function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/health');
}

/**
 * Workspace summary endpoint: GET /api/v1/workspace/summary
 */
export async function getWorkspaceSummary(): Promise<WorkspaceSummary> {
  return apiFetch<WorkspaceSummary>('/api/v1/workspace/summary');
}

/**
 * Orchestrates pattern detection and finding synthesis: POST /api/v1/workspace/detect-findings
 */
export async function detectFindings(params?: {
  entityId?: string;
  limit?: number;
}): Promise<InvestigativeFinding[]> {
  const queryParams = new URLSearchParams();
  if (params?.entityId) {
    queryParams.append('entity_id', params.entityId);
  }
  if (params?.limit) {
    queryParams.append('limit', params.limit.toString());
  }

  const queryString = queryParams.toString();
  const endpoint = `/api/v1/workspace/detect-findings${queryString ? `?${queryString}` : ''}`;

  return apiFetch<InvestigativeFinding[]>(endpoint, {
    method: 'POST',
  });
}
