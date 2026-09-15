import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Response

from app.services.storage import supabase_service
from app.services.ai.cv_generator import cv_generator_service
from app.services.ai.letter_generator import letter_generator_service
from app.services.ai.answer_generator import answer_generator_service
from app.services.ai.dossier_generator import dossier_generator_service
from app.services.documents.renderer import document_renderer
from app.services.documents.pdf import pdf_generator
from app.services.notion.client import notion_service
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobNormalizedData
from app.schemas.api import (
    ApplicationDetail,
    ApplicationIdResponse,
    ApplicationListResponse,
    DocumentType,
    NotionSyncResponse,
    UpdateStatusRequest,
    UpdateStatusResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/applications", tags=["Applications"])

@router.get("", response_model=ApplicationListResponse)
def list_applications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    min_score: Optional[int] = None,
    search: Optional[str] = Query(None, alias="q"),
):
    """Liste les candidatures existantes avec pagination et filtres."""
    paginated = supabase_service.get_applications_paginated(
        page=page,
        per_page=per_page,
        status=status,
        min_score=min_score,
        search=search,
        order_by="created_at",
        desc=True,
    )
    return {
        "applications": paginated["items"],
        "total": paginated["total"],
        "page": paginated["page"],
        "per_page": paginated["per_page"],
        "total_pages": paginated["total_pages"],
        "has_prev": paginated["has_prev"],
        "has_next": paginated["has_next"],
    }

@router.get("/{app_id}", response_model=ApplicationDetail)
def get_application(app_id: str):
    """Détail complet d'une candidature avec son offre associée."""
    if not supabase_service.client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")
    res = supabase_service.client.table("applications").select("*, jobs(*)").eq("id", app_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    return res.data[0]

@router.post("/create-from-job/{job_id}", response_model=ApplicationIdResponse)
def create_application_from_job(job_id: str):
    """Crée une candidature à partir d'une offre d'emploi."""
    if not supabase_service.client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")

    profile_data = supabase_service.get_active_candidate_profile()
    if not profile_data:
        raise HTTPException(status_code=400, detail="Aucun profil candidat actif trouvé")

    existing = supabase_service.client.table("applications").select("*").eq("job_id", job_id).execute()
    if existing.data:
        return {"message": "Candidature existante", "application_id": existing.data[0]["id"]}

    res_job = supabase_service.client.table("jobs").select("*").eq("id", job_id).execute()
    match_score = res_job.data[0].get("match_score") if res_job.data else None

    new_app = {
        "job_id": job_id,
        "candidate_profile_id": profile_data["id"],
        "status": "QUALIFIED",
        "match_score": match_score,
    }
    res_create = supabase_service.client.table("applications").insert(new_app).execute()
    return {"message": "Candidature créée", "application_id": res_create.data[0]["id"]}

@router.post("/{app_id}/prepare", response_model=ApplicationIdResponse)
def prepare_application(app_id: str):
    """Génère le CV personnalisé, la lettre et les réponses, puis synchronise Notion."""
    if not supabase_service.client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")

    res_app = supabase_service.client.table("applications").select("*, jobs(*)").eq("id", app_id).execute()
    if not res_app.data:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    application = res_app.data[0]
    job = application.get("jobs", {})

    supabase_service.client.table("applications").update({"status": "PREPARING"}).eq("id", app_id).execute()

    try:
        profile_data = supabase_service.get_active_candidate_profile()
        candidate_profile = CandidateProfile.model_validate(profile_data["profile"])
        candidate_profile.preferences = candidate_profile.preferences.model_validate(profile_data.get("preferences", {}))
        job_normalized = JobNormalizedData.model_validate(job.get("normalized_data", {}))

        dossier = dossier_generator_service.generate_dossier(
            job_id=job["id"],
            profile=candidate_profile,
            job=job_normalized,
            application_id=app_id,
        )

        update_fields = {
            "tailored_cv": dossier.cv.model_dump(),
            "cover_letter": dossier.letter.content,
            "application_answers": dossier.answers.model_dump(),
            "status": "READY",
            "prepared_at": datetime.now(timezone.utc).isoformat(),
        }

        # Notion sync
        try:
            notion_page_id = notion_service.create_or_update_job_page(
                job=job,
                application=update_fields,
                candidate=profile_data,
            )
            if notion_page_id:
                update_fields["notion_page_id"] = notion_page_id
        except Exception as ne:
            logger.warning(f"Erreur sync Notion : {ne}")

        supabase_service.client.table("applications").update(update_fields).eq("id", app_id).execute()
        return {"message": "Dossier préparé avec succès", "application_id": app_id}

    except Exception as e:
        logger.error(f"Erreur préparation candidature : {e}")
        supabase_service.client.table("applications").update({"status": "QUALIFIED"}).eq("id", app_id).execute()
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{app_id}/status", response_model=UpdateStatusResponse)
def update_application_status(app_id: str, payload: UpdateStatusRequest):
    """Met à jour le statut d'une candidature."""
    if not supabase_service.client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")

    update_data = {"status": payload.status}
    if payload.status == "APPLIED":
        update_data["applied_at"] = datetime.now(timezone.utc).isoformat()

    supabase_service.client.table("applications").update(update_data).eq("id", app_id).execute()
    return {"message": "Statut mis à jour", "status": payload.status}

@router.get(
    "/{app_id}/documents/{doc_type}",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "Document PDF généré (ReportLab)"}},
)
def get_application_document(app_id: str, doc_type: DocumentType):
    """Télécharge ou prévisualise un document PDF (CV ou COVER_LETTER)."""
    if not supabase_service.client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")

    res_app = supabase_service.client.table("applications").select("*, jobs(*)").eq("id", app_id).execute()
    if not res_app.data:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    application = res_app.data[0]
    job = application.get("jobs", {})

    company = (job.get("company") or "Entreprise").replace(" ", "_")
    if doc_type == "CV":
        tailored_cv = application.get("tailored_cv")
        if not tailored_cv:
            raise HTTPException(status_code=404, detail="CV non généré pour cette offre")
        profile_data = supabase_service.get_active_candidate_profile()
        candidate_profile = CandidateProfile.model_validate(profile_data["profile"])
        pdf_bytes = pdf_generator.generate_cv_pdf(tailored_cv, candidate_profile, company=company)
        filename = f"CV_Emmanuel_Tro_{company}.pdf"
    else:
        letter_content = application.get("cover_letter")
        if not letter_content:
            raise HTTPException(status_code=404, detail="Lettre de motivation non générée")
        profile_data = supabase_service.get_active_candidate_profile()
        candidate_profile = CandidateProfile.model_validate(profile_data["profile"])
        pdf_bytes = pdf_generator.generate_letter_pdf(letter_content, candidate_profile, company=company, job_title=job.get("title", ""))
        filename = f"Lettre_Motivation_Emmanuel_Tro_{company}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )

@router.post("/{app_id}/sync-notion", response_model=NotionSyncResponse)
def sync_application_notion(app_id: str):
    """Synchronise manuellement une candidature vers Notion."""
    if not supabase_service.client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")

    res_app = supabase_service.client.table("applications").select("*, jobs(*)").eq("id", app_id).execute()
    if not res_app.data:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    application = res_app.data[0]
    job = application.get("jobs", {})
    profile_data = supabase_service.get_active_candidate_profile()

    page_id = notion_service.create_or_update_job_page(
        job=job,
        application=application,
        candidate=profile_data,
    )
    if page_id:
        supabase_service.client.table("applications").update({"notion_page_id": page_id}).eq("id", app_id).execute()
        return {"message": "Synchronisation Notion réussie", "notion_page_id": page_id}
    raise HTTPException(status_code=500, detail="Échec de la synchronisation Notion")
