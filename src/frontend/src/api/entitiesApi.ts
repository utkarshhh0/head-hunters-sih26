import { apiFetch } from './client';
import { EntityDetails, EntityNeighborhoodResponse, EntityRecord } from './types';

export interface SearchEntitiesParams {
  query?: string;
  entity_type?: string;
  limit?: number;
}

/**
 * Search canonical entities: GET /api/v1/entities
 */
export async function searchEntities(
  params?: SearchEntitiesParams
): Promise<EntityRecord[]> {
  const queryParams = new URLSearchParams();
  if (params?.query && params.query.trim()) {
    queryParams.append('query', params.query.trim());
  }
  if (params?.entity_type && params.entity_type.trim()) {
    queryParams.append('entity_type', params.entity_type.trim().toUpperCase());
  }
  if (params?.limit) {
    queryParams.append('limit', params.limit.toString());
  }

  const query = queryParams.toString();
  const endpoint = `/api/v1/entities${query ? `?${query}` : ''}`;
  return apiFetch<EntityRecord[]>(endpoint);
}

/**
 * Get detailed entity properties and degree connectivity: GET /api/v1/entities/{entity_id}
 */
export async function getEntityDetails(
  entityId: string
): Promise<EntityDetails> {
  return apiFetch<EntityDetails>(
    `/api/v1/entities/${encodeURIComponent(entityId)}`
  );
}

/**
 * Get bounded 1-hop or 2-hop network neighborhood: GET /api/v1/entities/{entity_id}/neighborhood
 * Traversal depth is strictly 1 or 2 hops.
 */
export async function getEntityNeighborhood(
  entityId: string,
  depth: 1 | 2 = 1,
  limit: number = 50
): Promise<EntityNeighborhoodResponse> {
  const queryParams = new URLSearchParams({
    depth: depth.toString(),
    limit: limit.toString(),
  });
  return apiFetch<EntityNeighborhoodResponse>(
    `/api/v1/entities/${encodeURIComponent(entityId)}/neighborhood?${queryParams.toString()}`
  );
}
