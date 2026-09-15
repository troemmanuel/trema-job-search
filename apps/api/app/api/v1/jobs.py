import json
import logging
from typing import Optional, List, Union
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.config import Config
from app.services.storage import supabase_service
from app.services.ingestion.importer import job_importer
from app.services.ai.matcher import matcher_service
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobNormalizedData
from app.schemas.api import (
    CollectRequest,
    CollectResponse,
    JobImportRequest,
    JobImportResponse,
    JobListResponse,
    JobRecord,
    MatchJobResponse,
    ScrapeBatchResponse,
    ScrapeItemResult,
    ScrapeRequest,
    ScrapeStreamEvent,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["Jobs"])

def _extract_urls(payload: ScrapeRequest) -> List[str]:
    if payload.urls:
        return [u.strip() for u in payload.urls if u.strip()]
    if payload.url:
        return [part.strip() for part in payload.url.replace(",", "\n").splitlines() if part.strip()]
    return []

@router.get("", response_model=JobListResponse)
def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    contract_type: Optional[str] = None,
    min_score: Optional[int] = None,
    search: Optional[str] = Query(None, alias="q"),
):
    """Liste les offres enregistrées avec pagination et filtres."""
    paginated = supabase_service.get_jobs_paginated(
        page=page,
        per_page=per_page,
        status=status,
        contract_type=contract_type,
        min_score=min_score,
        search=search,
        order_by="created_at",
        desc=True,
    )
    return {
        "jobs": paginated["items"],
        "total": paginated["total"],
        "page": paginated["page"],
        "per_page": paginated["per_page"],
        "total_pages": paginated["total_pages"],
        "has_prev": paginated["has_prev"],
        "has_next": paginated["has_next"],
    }

@router.get("/{job_id}", response_model=JobRecord)
def get_job(job_id: str):
    """Détail complet d'une offre."""
    if not supabase_service.client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")
    res = supabase_service.client.table("jobs").select("*").eq("id", job_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    return res.data[0]

@router.post("/import", response_model=JobImportResponse)
def import_job(payload: JobImportRequest):
    """Importe une nouvelle offre et la persiste après déduplication."""
    try:
        result = job_importer.import_job(payload.model_dump(exclude_none=True))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur import offre : {e}")
        raise HTTPException(status_code=500, detail="Erreur interne lors de l'import")

@router.post("/scrape", response_model=Union[ScrapeItemResult, ScrapeBatchResponse])
def scrape_job(payload: ScrapeRequest):
    """Scrape une ou plusieurs offres depuis leurs URLs (LinkedIn, WTTJ, etc.).

    Une seule URL renvoie un `ScrapeItemResult`, un lot renvoie un `ScrapeBatchResponse` (`is_batch: true`).
    """
    urls_list = _extract_urls(payload)
    if not urls_list:
        raise HTTPException(status_code=400, detail="Au moins une URL d'offre est requise")

    from app.services.ingestion.collector import job_collector_service

    try:
        if len(urls_list) == 1:
            result = job_collector_service.import_and_process_url(
                url=urls_list[0],
                auto_prepare=payload.auto_prepare,
                min_match_score=payload.min_match_score,
            )
            if not result.get("success", False):
                raise HTTPException(status_code=400, detail=result.get("error", "Erreur lors de l'import"))
            return result
        else:
            result = job_collector_service.import_and_process_urls(
                urls=urls_list,
                auto_prepare=payload.auto_prepare,
                min_match_score=payload.min_match_score,
            )
            if not result.get("success", False) and result.get("total_unique", 0) == 0:
                raise HTTPException(status_code=400, detail=result.get("error", "Erreur lors de l'import du lot"))
            return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur scraping offres : {e}")
        raise HTTPException(status_code=500, detail=f"Impossible de récupérer les offres: {str(e)}")

@router.post(
    "/scrape/stream",
    responses={200: {"content": {"text/event-stream": {"schema": {"$ref": "#/components/schemas/ScrapeStreamEvent"}}}, "description": "Flux SSE : chaque `data:` est un ScrapeStreamEvent JSON"}},
)
def scrape_job_stream(payload: ScrapeRequest):
    """Scrape un lot d'offres avec streaming SSE pour afficher l'avancement en direct.

    Chaque message `data:` est un `ScrapeStreamEvent` sérialisé en JSON.
    """
    urls_list = _extract_urls(payload)
    if not urls_list:
        raise HTTPException(status_code=400, detail="Au moins une URL est requise")

    from app.services.ingestion.collector import job_collector_service

    def sse_event_stream():
        total = len(urls_list)
        yield f"data: {json.dumps({'type': 'start', 'total': total})}\n\n"

        for idx, url in enumerate(urls_list, start=1):
            yield f"data: {json.dumps({'type': 'processing', 'current': idx, 'total': total, 'url': url})}\n\n"
            try:
                res = job_collector_service.import_and_process_url(
                    url=url,
                    auto_prepare=payload.auto_prepare,
                    min_match_score=payload.min_match_score,
                )
                yield f"data: {json.dumps({'type': 'item_done', 'current': idx, 'total': total, 'result': res})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'item_error', 'current': idx, 'total': total, 'url': url, 'error': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'complete'})}\n\n"

    return StreamingResponse(sse_event_stream(), media_type="text/event-stream")

@router.post("/{job_id}/match", response_model=MatchJobResponse)
def match_job(job_id: str):
    """Calcule le score de matching IA pour l'offre spécifiée."""
    if not supabase_service.client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")

    res_job = supabase_service.client.table("jobs").select("*").eq("id", job_id).execute()
    if not res_job.data:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    job = res_job.data[0]

    profile_data = supabase_service.get_active_candidate_profile()
    if not profile_data:
        raise HTTPException(status_code=400, detail="Aucun profil candidat actif trouvé")

    candidate_profile = CandidateProfile.model_validate(profile_data["profile"])
    candidate_profile.preferences = candidate_profile.preferences.model_validate(profile_data.get("preferences", {}))
    job_normalized = JobNormalizedData.model_validate(job.get("normalized_data", {}))

    match_result = matcher_service.match(candidate_profile, job_normalized)
    if not match_result:
        raise HTTPException(status_code=500, detail="Échec du calcul de matching Gemini")

    update_data = {
        "match_score": match_result.score,
        "match_level": match_result.level,
        "match_analysis": match_result.model_dump(),
        "status": "QUALIFIED" if match_result.score >= Config.MATCH_THRESHOLD_RECOMMENDED else "REVIEW",
    }
    supabase_service.client.table("jobs").update(update_data).eq("id", job_id).execute()

    return {"message": "Matching effectué", "match": match_result.model_dump()}

@router.post("/collect", response_model=CollectResponse)
def collect_jobs(payload: CollectRequest):
    """Lance la collecte automatique et scraping batch d'offres récentes."""
    try:
        from app.services.ingestion.collector import job_collector_service
        summary = job_collector_service.run_collection(
            duration=payload.duration,
            query=payload.query,
            limit=payload.limit,
            auto_prepare=payload.auto_prepare,
        )
        return summary
    except Exception as e:
        logger.error(f"Erreur lors de la collecte d'offres: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la collecte: {str(e)}")
