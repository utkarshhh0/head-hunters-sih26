/**
 * Centralized API client for communicating with the FastAPI backend.
 */

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export class ApiRequestError extends Error {
  public status: number;
  public detail: string;

  constructor(status: number, detail: string) {
    super(`API Error ${status}: ${detail}`);
    this.name = 'ApiRequestError';
    this.status = status;
    this.detail = detail;
  }
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const defaultHeaders: Record<string, string> = {
    'Accept': 'application/json',
  };

  if (options.body && typeof options.body === 'string') {
    defaultHeaders['Content-Type'] = 'application/json';
  }

  const mergedOptions: RequestInit = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  try {
    const response = await fetch(url, mergedOptions);

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
        // Fallback to generic status text if response is not JSON
      }
      throw new ApiRequestError(response.status, errorMessage);
    }

    // For 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return await response.json();
  } catch (err: unknown) {
    if (err instanceof ApiRequestError) {
      throw err;
    }
    const message = err instanceof Error ? err.message : 'Unknown network error';
    throw new ApiRequestError(0, `Network communication failure: ${message}`);
  }
}
