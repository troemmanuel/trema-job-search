"""Contrats HTTP de l'API v1 (requêtes & réponses).

Ces modèles alimentent le schéma OpenAPI exposé sur /openapi.json, qui sert ensuite à
générer les types TypeScript de `packages/api-client`. Les enregistrements issus de
Supabase (`JobRecord`, `ApplicationRecord`, ...) sont volontairement tolérants
(`extra="allow"`) : une colonne ajoutée en base ne doit jamais casser une réponse.
"""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.config import Config
from app.schemas.application import ApplicationAnswers, TailoredCV
from app.schemas.candidate import CandidatePreferences, CandidateProfile
from app.schemas.job import JobNormalizedData
from app.schemas.match import MatchDimensions, MatchResult

JobStatus = Literal["NEW", "QUALIFIED", "REVIEW", "PREPARING", "READY", "APPLIED", "IGNORED"]
ApplicationStatusValue = Literal[
    "QUALIFIED", "PREPARING", "PREPARED", "READY", "APPLIED", "INTERVIEW", "INTERVIEW_HR", "INTERVIEW_TECH", "OFFER", "REJECTED"
]
AnalyticsPeriod = Literal["all", "30d", "7d"]
DocumentType = Literal["CV", "COVER_LETTER"]


class LenientModel(BaseModel):
    """Base pour les enregistrements Supabase : conserve les colonnes inconnues."""
    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Génériques
# ---------------------------------------------------------------------------

class MessageResponse(BaseModel):
    message: str


class ServiceStatuses(BaseModel):
    supabase: Literal["connected", "unconfigured"]
    gemini: Literal["configured", "unconfigured"]
    notion: Literal["configured", "unconfigured"]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    services: ServiceStatuses


class RootInfoResponse(BaseModel):
    name: str
    version: str
    docs: str
    openapi: str


class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    total_pages: int
    has_prev: bool
    has_next: bool


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

class JobMatchAnalysis(LenientModel):
    """`MatchResult` persisté en base, tolérant : les anciennes analyses peuvent être partielles."""
    score: Optional[int] = None
    level: Optional[str] = None
    dimensions: Optional[MatchDimensions] = None
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)
    recommendation: Optional[str] = None
    company_type: Optional[str] = None
    company_domain: Optional[str] = None


class JobRecord(LenientModel):
    id: Optional[str] = Field(default=None, description="Absent uniquement pour une offre simulée (Supabase non configuré)")
    source: Optional[str] = None
    source_job_id: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    contract_type: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    published_at: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    normalized_data: Optional[JobNormalizedData] = None
    match_score: Optional[int] = None
    match_level: Optional[str] = None
    match_analysis: Optional[JobMatchAnalysis] = None
    status: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class JobListResponse(PaginationMeta):
    jobs: List[JobRecord]


class JobImportRequest(LenientModel):
    """Charge utile d'import manuel : mêmes champs que `JobImport`, tolérant aux extras des scrapers."""
    source: str
    source_job_id: Optional[str] = None
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    contract_type: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    published_at: Optional[str] = None
    url: str
    description: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    normalized_data: Optional[JobNormalizedData] = None


class JobImportResponse(BaseModel):
    status: Literal["CREATED", "DUPLICATE", "SIMULATED"]
    message: Optional[str] = None
    job: Optional[JobRecord] = None


class ScrapeRequest(BaseModel):
    url: Optional[str] = Field(default=None, description="Une URL, ou plusieurs séparées par virgule / retour à la ligne")
    urls: Optional[List[str]] = None
    auto_prepare: bool = True
    min_match_score: int = Config.MATCH_THRESHOLD_RECOMMENDED


class ScrapeItemResult(LenientModel):
    success: bool
    status: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    job: Optional[JobRecord] = None
    score: Optional[int] = None
    match: Optional[MatchResult] = None
    prepared: bool = False
    cv_url: Optional[str] = None
    letter_url: Optional[str] = None
    notion_page_id: Optional[str] = None
    notion_url: Optional[str] = None
    application_id: Optional[str] = None


class ScrapeBatchItemResult(ScrapeItemResult):
    url: str


class ScrapeBatchResponse(LenientModel):
    success: bool
    is_batch: Literal[True] = True
    error: Optional[str] = None
    total_requested: int
    total_unique: int
    processed_count: int
    qualified_count: int
    prepared_count: int
    notion_synced_count: int
    error_count: int
    results: List[ScrapeBatchItemResult]


class ScrapeStreamEvent(BaseModel):
    """Événement SSE émis par POST /jobs/scrape/stream (champ `data` de chaque message)."""
    type: Literal["start", "processing", "item_done", "item_error", "complete"]
    total: Optional[int] = None
    current: Optional[int] = None
    url: Optional[str] = None
    result: Optional[ScrapeItemResult] = None
    error: Optional[str] = None


class MatchJobResponse(MessageResponse):
    match: MatchResult


class CollectRequest(BaseModel):
    duration: str = "24h"
    query: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=20)
    auto_prepare: bool = True


class CollectedJobSummary(LenientModel):
    title: Optional[str] = None
    company: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[str] = None
    status: str
    match_score: Optional[int] = None
    notion_page_id: Optional[str] = None
    notion_url: Optional[str] = None


class CollectResponse(LenientModel):
    duration: str
    query: Optional[str] = None
    candidate_name: Optional[str] = None
    contract_filter: Optional[List[str]] = None
    total_found: int
    processed_count: int
    new_imported_count: int
    qualified_count: int
    prepared_count: int
    notion_synced_count: int
    jobs: List[CollectedJobSummary]


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

class ApplicationRecord(LenientModel):
    id: str
    job_id: str
    candidate_profile_id: Optional[str] = None
    status: str
    match_score: Optional[int] = None
    tailored_cv: Optional[TailoredCV] = None
    cover_letter: Optional[str] = None
    application_answers: Optional[ApplicationAnswers] = None
    notes: Optional[str] = None
    notion_page_id: Optional[str] = None
    prepared_at: Optional[str] = None
    applied_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class JobDetail(JobRecord):
    application: Optional[ApplicationRecord] = Field(default=None, description="Candidature déjà créée pour cette offre, le cas échéant")


class ApplicationDetail(ApplicationRecord):
    jobs: Optional[JobRecord] = Field(default=None, description="Offre associée (jointure Supabase)")


class ApplicationListResponse(PaginationMeta):
    applications: List[ApplicationRecord]


class ApplicationIdResponse(MessageResponse):
    application_id: str


class UpdateStatusRequest(BaseModel):
    status: ApplicationStatusValue


class UpdateStatusResponse(MessageResponse):
    status: ApplicationStatusValue


class NotionSyncResponse(MessageResponse):
    notion_page_id: str


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------

class CandidateProfileRecord(LenientModel):
    id: str
    name: Optional[str] = None
    profile: CandidateProfile
    preferences: CandidatePreferences = Field(default_factory=CandidatePreferences)
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UpdateCandidateProfileRequest(BaseModel):
    profile: CandidateProfile
    preferences: CandidatePreferences = Field(default_factory=CandidatePreferences)


class UpdateCandidateProfileResponse(MessageResponse):
    data: List[CandidateProfileRecord]


# ---------------------------------------------------------------------------
# Dashboard & Scheduler
# ---------------------------------------------------------------------------

class SchedulerReconcileSummary(BaseModel):
    matched_count: int = 0
    updated_supabase: int = 0
    updated_notion: int = 0


class SchedulerLastResult(LenientModel):
    """Bilan du dernier passage du planificateur ; `error` seul si le run a échoué."""
    error: Optional[str] = None
    total_found: int = 0
    processed_count: int = 0
    new_imported_count: int = 0
    qualified_count: int = 0
    prepared_count: int = 0
    notion_synced_count: int = 0
    notion_reconcile: Optional[SchedulerReconcileSummary] = None
    jobs: List[CollectedJobSummary] = Field(default_factory=list)


class SchedulerStatus(LenientModel):
    is_active: bool
    schedule_time: str
    next_run: Optional[str] = None
    last_run: Optional[str] = None
    last_result: Optional[SchedulerLastResult] = None
    is_running_job: bool = False


class DashboardCounters(BaseModel):
    priority_count: int
    recommended_count: int
    review_count: int
    ignored_count: int
    to_prepare_count: int
    ready_count: int
    applied_count: int
    interview_count: int


class DashboardStatsResponse(BaseModel):
    stats: DashboardCounters
    recent_jobs: List[JobRecord]
    recent_applications: List[ApplicationDetail]
    scheduler_status: Optional[SchedulerStatus] = None


class SchedulerTriggerResponse(MessageResponse):
    started: bool
    status: SchedulerStatus


class SchedulerUpdateRequest(BaseModel):
    time: str = Field(description="Heure d'exécution quotidienne au format HH:MM", pattern=r"^\d{1,2}:\d{2}$")
    enabled: bool = True


class SchedulerUpdateResponse(MessageResponse):
    status: SchedulerStatus


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

class FunnelCounts(BaseModel):
    detected: int
    qualified: int
    prepared: int
    applied: int
    interview: int
    offer: int
    rejected: int


class FunnelRates(BaseModel):
    qualification_rate: float
    preparation_rate: float
    application_rate: float
    interview_rate: float
    offer_rate: float
    global_conversion_rate: float


class Funnel(BaseModel):
    counts: FunnelCounts
    rates: FunnelRates


class AnalyticsKpis(LenientModel):
    total_jobs: int
    total_applications: int
    avg_match_score: float
    qualified_count: int
    applied_count: int
    interview_count: int
    offer_count: int
    global_conversion_rate: float
    recommendations: Dict[str, int]


class Timeline(BaseModel):
    labels: List[str]
    jobs_series: List[int]
    applications_series: List[int]


class AnalyticsStatsResponse(LenientModel):
    success: Literal[True] = True
    period: AnalyticsPeriod
    kpis: AnalyticsKpis
    funnel: Funnel
    tech_performance: List[Dict[str, Any]]
    geography: Dict[str, int]
    workplace: Dict[str, int]
    company_types: Dict[str, int]
    timeline: Timeline
    total_jobs: int
    total_applications: int
    router_stats: Optional[Dict[str, Any]] = None


class TaskDistribution(BaseModel):
    counts: Dict[str, int]
    total: int
    percentages: Dict[str, float]


class InterfacesAnalyticsResponse(LenientModel):
    success: Literal[True] = True
    timestamp: str
    kpis: Dict[str, Any]
    providers: List[Dict[str, Any]]
    task_distribution: TaskDistribution
    external_connectors: Dict[str, Dict[str, Any]]
    cache: Dict[str, Any]
    recent_runs: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class AIModel(BaseModel):
    id: str
    name: str
    description: str
    recommended: bool = False


class SettingsResponse(BaseModel):
    preferences: CandidatePreferences
    available_models: List[AIModel]
    router_overview: Optional[Dict[str, Any]] = None


class UpdateSettingsRequest(BaseModel):
    preferences: CandidatePreferences


class UpdateSettingsResponse(MessageResponse):
    preferences: CandidatePreferences


class BlacklistRequest(BaseModel):
    company: str = Field(min_length=1, description="Nom de l'entreprise à exclure")


class BlacklistResponse(MessageResponse):
    excluded_companies: List[str]
    retro_updated_jobs: int = Field(description="Offres existantes de cette entreprise passées en BLACKLISTED")


class NotionReconcileResponse(LenientModel):
    success: bool
    timestamp: str
    total_notion_pages: int = 0
    total_supabase_apps: int = 0
    matched_count: int = 0
    updated_supabase_count: int = 0
    updated_notion_count: int = 0
    created_notion_count: int = 0
    refreshed_documents_count: int = 0
    trashed_notion_pages: List[Dict[str, Any]] = Field(default_factory=list)
    details: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[Any] = Field(default_factory=list)
    error: Optional[str] = None
