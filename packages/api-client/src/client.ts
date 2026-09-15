import createClient, { type Client, type ClientOptions } from 'openapi-fetch';

import { ApiError } from './errors';
import type { paths } from './generated/schema';

export type ApiClient = Client<paths>;

export const DEFAULT_API_URL = 'http://localhost:8000';

// Déclaration minimale pour lire `process.env` sans dépendre de @types/node (le package est isomorphe).
declare const process: { env?: Record<string, string | undefined> } | undefined;

/** Résout l'URL de l'API : argument explicite > `NEXT_PUBLIC_API_URL` > localhost. */
export function resolveApiUrl(baseUrl?: string): string {
  if (baseUrl) return baseUrl;
  const fromEnv = typeof process !== 'undefined' ? process?.env?.NEXT_PUBLIC_API_URL : undefined;
  return fromEnv || DEFAULT_API_URL;
}

/**
 * Client bas niveau `openapi-fetch`, typé par chemin et méthode.
 *
 * @example
 * const { data, error } = await client.GET('/api/v1/jobs', { params: { query: { page: 2 } } });
 */
export function createApiClient(options: ClientOptions = {}): ApiClient {
  return createClient<paths>({
    ...options,
    baseUrl: resolveApiUrl(options.baseUrl),
  });
}

/**
 * Déballe une réponse `openapi-fetch` : renvoie `data` ou lève une `ApiError`.
 * Pratique avec TanStack Query, qui attend une promesse qui rejette en cas d'échec.
 */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    const detail = (result.error as { detail?: unknown } | undefined)?.detail ?? result.error;
    throw new ApiError(result.response.status, detail, result.response.statusText);
  }
  return result.data as T;
}
