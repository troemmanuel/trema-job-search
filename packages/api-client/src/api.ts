import { type ApiClient, createApiClient, resolveApiUrl, unwrap } from './client';
import type {
  AnalyticsStatsResponse,
  ApplicationDetail,
  ApplicationIdResponse,
  ApplicationListResponse,
  BlacklistRequest,
  BlacklistResponse,
  CandidateProfileRecord,
  CollectRequest,
  CollectResponse,
  DashboardStatsResponse,
  HealthResponse,
  InterfacesAnalyticsResponse,
  JobImportRequest,
  JobDetail,
  JobImportResponse,
  JobListResponse,
  MatchJobResponse,
  NotionReconcileResponse,
  NotionSyncResponse,
  ProviderTestRequest,
  ProviderTestResponse,
  SuccessMessageResponse,
  SchedulerStatus,
  SchedulerTriggerResponse,
  SchedulerUpdateRequest,
  SchedulerUpdateResponse,
  ScrapeBatchResponse,
  ScrapeItemResult,
  ScrapeRequest,
  SettingsResponse,
  TranscribeCvRequest,
  TranscribeCvResponse,
  UpdateCandidateProfileRequest,
  UpdateCandidateProfileResponse,
  UpdateSettingsRequest,
  UpdateSettingsResponse,
  UpdateStatusRequest,
  UpdateStatusResponse,
  paths,
} from './generated/schema';
import { type StreamOptions, streamScrapeJobs } from './sse';

type Query<P extends keyof paths, M extends keyof paths[P]> = paths[P][M] extends {
  parameters: { query?: infer Q };
}
  ? Q
  : never;

export type JobListQuery = NonNullable<Query<'/api/v1/jobs', 'get'>>;
export type ApplicationListQuery = NonNullable<Query<'/api/v1/applications', 'get'>>;
export type ApplicationStatus = UpdateStatusRequest['status'];
export type AnalyticsPeriod = NonNullable<NonNullable<Query<'/api/v1/analytics/stats', 'get'>>['period']>;
export type DocumentType = paths['/api/v1/applications/{app_id}/documents/{doc_type}']['get']['parameters']['path']['doc_type'];

/**
 * Façade haut niveau : une méthode par opération, qui renvoie directement le `data` typé
 * ou lève une `ApiError`. Les types proviennent exclusivement du schéma OpenAPI généré.
 */
export function createTremaApi(options: { baseUrl?: string; fetch?: typeof fetch } = {}) {
  const client: ApiClient = createApiClient(options);
  const baseUrl = resolveApiUrl(options.baseUrl);

  return {
    /** Client `openapi-fetch` sous-jacent pour les cas non couverts par la façade. */
    client,
    baseUrl,

    system: {
      health: (): Promise<HealthResponse> => client.GET('/health').then(unwrap),
    },

    dashboard: {
      stats: (): Promise<DashboardStatsResponse> => client.GET('/api/v1/dashboard/stats').then(unwrap),
    },

    jobs: {
      list: (query: JobListQuery = {}): Promise<JobListResponse> =>
        client.GET('/api/v1/jobs', { params: { query } }).then(unwrap),
      get: (jobId: string): Promise<JobDetail> =>
        client.GET('/api/v1/jobs/{job_id}', { params: { path: { job_id: jobId } } }).then(unwrap),
      import: (body: JobImportRequest): Promise<JobImportResponse> =>
        client.POST('/api/v1/jobs/import', { body }).then(unwrap),
      scrape: (body: ScrapeRequest): Promise<ScrapeItemResult | ScrapeBatchResponse> =>
        client.POST('/api/v1/jobs/scrape', { body }).then(unwrap),
      scrapeStream: (body: ScrapeRequest, streamOptions: Omit<StreamOptions, 'baseUrl'> = {}) =>
        streamScrapeJobs(body, { ...streamOptions, baseUrl }),
      match: (jobId: string): Promise<MatchJobResponse> =>
        client.POST('/api/v1/jobs/{job_id}/match', { params: { path: { job_id: jobId } } }).then(unwrap),
      collect: (body: CollectRequest): Promise<CollectResponse> =>
        client.POST('/api/v1/jobs/collect', { body }).then(unwrap),
    },

    applications: {
      list: (query: ApplicationListQuery = {}): Promise<ApplicationListResponse> =>
        client.GET('/api/v1/applications', { params: { query } }).then(unwrap),
      get: (appId: string): Promise<ApplicationDetail> =>
        client.GET('/api/v1/applications/{app_id}', { params: { path: { app_id: appId } } }).then(unwrap),
      createFromJob: (jobId: string): Promise<ApplicationIdResponse> =>
        client
          .POST('/api/v1/applications/create-from-job/{job_id}', { params: { path: { job_id: jobId } } })
          .then(unwrap),
      prepare: (appId: string): Promise<ApplicationIdResponse> =>
        client.POST('/api/v1/applications/{app_id}/prepare', { params: { path: { app_id: appId } } }).then(unwrap),
      updateStatus: (appId: string, body: UpdateStatusRequest): Promise<UpdateStatusResponse> =>
        client
          .PATCH('/api/v1/applications/{app_id}/status', { params: { path: { app_id: appId } }, body })
          .then(unwrap),
      syncNotion: (appId: string): Promise<NotionSyncResponse> =>
        client
          .POST('/api/v1/applications/{app_id}/sync-notion', { params: { path: { app_id: appId } } })
          .then(unwrap),
      /** URL directe du PDF (CV ou lettre) : inline pour un `<iframe>`, `download: true` pour forcer l'enregistrement. */
      documentUrl: (appId: string, docType: DocumentType, options: { download?: boolean } = {}): string =>
        `${baseUrl}/api/v1/applications/${encodeURIComponent(appId)}/documents/${docType}${options.download ? '?download=true' : ''}`,
      /** Télécharge le PDF en mémoire (ex. pour un visualiseur PDF in-app). */
      document: (appId: string, docType: DocumentType): Promise<Blob> =>
        client
          .GET('/api/v1/applications/{app_id}/documents/{doc_type}', {
            params: { path: { app_id: appId, doc_type: docType } },
            parseAs: 'blob',
          })
          .then(unwrap),
    },

    candidate: {
      profile: (): Promise<CandidateProfileRecord> => client.GET('/api/v1/candidate/profile').then(unwrap),
      updateProfile: (body: UpdateCandidateProfileRequest): Promise<UpdateCandidateProfileResponse> =>
        client.PUT('/api/v1/candidate/profile', { body }).then(unwrap),
      /** Transcription IA d'un CV Markdown : remplace le profil actif (les préférences sont conservées). */
      transcribe: (body: TranscribeCvRequest): Promise<TranscribeCvResponse> =>
        client.POST('/api/v1/candidate/transcribe', { body }).then(unwrap),
    },

    scheduler: {
      status: (): Promise<SchedulerStatus> => client.GET('/api/v1/scheduler/status').then(unwrap),
      trigger: (): Promise<SchedulerTriggerResponse> => client.POST('/api/v1/scheduler/trigger').then(unwrap),
      update: (body: SchedulerUpdateRequest): Promise<SchedulerUpdateResponse> =>
        client.POST('/api/v1/scheduler/update', { body }).then(unwrap),
    },

    analytics: {
      stats: (period: AnalyticsPeriod = 'all'): Promise<AnalyticsStatsResponse> =>
        client.GET('/api/v1/analytics/stats', { params: { query: { period } } }).then(unwrap),
      interfaces: (): Promise<InterfacesAnalyticsResponse> =>
        client.GET('/api/v1/analytics/interfaces').then(unwrap),
    },

    settings: {
      get: (): Promise<SettingsResponse> => client.GET('/api/v1/settings').then(unwrap),
      update: (body: UpdateSettingsRequest): Promise<UpdateSettingsResponse> =>
        client.PUT('/api/v1/settings', { body }).then(unwrap),
      syncNotion: (): Promise<NotionReconcileResponse> => client.POST('/api/v1/settings/sync-notion').then(unwrap),
      addToBlacklist: (body: BlacklistRequest): Promise<BlacklistResponse> =>
        client.POST('/api/v1/settings/blacklist', { body }).then(unwrap),
      removeFromBlacklist: (body: BlacklistRequest): Promise<BlacklistResponse> =>
        client.DELETE('/api/v1/settings/blacklist', { body }).then(unwrap),
      testProvider: (body: ProviderTestRequest): Promise<ProviderTestResponse> =>
        client.POST('/api/v1/settings/router/test', { body }).then(unwrap),
      clearLlmCache: (): Promise<SuccessMessageResponse> => client.POST('/api/v1/settings/router/cache/clear').then(unwrap),
      resetRouterStats: (): Promise<SuccessMessageResponse> => client.POST('/api/v1/settings/router/stats/reset').then(unwrap),
    },
  };
}

export type TremaApi = ReturnType<typeof createTremaApi>;

/** Instance par défaut, configurée via `NEXT_PUBLIC_API_URL`. */
export const api: TremaApi = createTremaApi();
