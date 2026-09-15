// Types générés depuis l'OpenAPI FastAPI (ne pas éditer `generated/` à la main : `pnpm generate:api-client`).
export type * from './generated/schema';

export { ApiError } from './errors';
export { createApiClient, resolveApiUrl, unwrap, DEFAULT_API_URL, type ApiClient } from './client';
export { readSseStream, streamScrapeJobs, type StreamOptions } from './sse';
export {
  api,
  createTremaApi,
  type TremaApi,
  type JobListQuery,
  type ApplicationListQuery,
  type ApplicationStatus,
  type AnalyticsPeriod,
  type DocumentType,
} from './api';
