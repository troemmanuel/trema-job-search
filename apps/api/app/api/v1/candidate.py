import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from app.services.storage import supabase_service
from app.schemas.api import (
    CandidateProfileRecord,
    TranscribeCvRequest,
    TranscribeCvResponse,
    UpdateCandidateProfileRequest,
    UpdateCandidateProfileResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidate", tags=["Candidate"])

@router.get("/profile", response_model=CandidateProfileRecord)
def get_candidate_profile():
    """Récupère le profil candidat maître actif."""
    if not supabase_service.client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")
    profile = supabase_service.get_active_candidate_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="Aucun profil candidat actif")
    return profile

@router.put("/profile", response_model=UpdateCandidateProfileResponse)
def update_candidate_profile(payload: UpdateCandidateProfileRequest):
    """Met à jour le profil candidat maître actif (validation Pydantic automatique, 422 si invalide)."""
    if not supabase_service.client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")

    # Les préférences vivent dans /settings : le formulaire profil ne les envoie pas, on conserve les actuelles.
    profile_obj = payload.profile.model_dump(exclude={"preferences"})
    active = supabase_service.get_active_candidate_profile()

    if active:
        update_data = {
            "name": payload.profile.name or active.get("name") or "Candidat",
            "profile": profile_obj,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if payload.preferences is not None:
            update_data["preferences"] = payload.preferences.model_dump()
        res = supabase_service.client.table("candidate_profiles").update(update_data).eq("id", active["id"]).execute()
        return {"message": "Profil mis à jour", "data": res.data}

    res = supabase_service.client.table("candidate_profiles").insert({
        "name": payload.profile.name or "Candidat",
        "profile": profile_obj,
        "preferences": (payload.preferences or payload.profile.preferences).model_dump(),
        "is_active": True,
    }).execute()
    return {"message": "Profil créé", "data": res.data}


@router.post("/transcribe", response_model=TranscribeCvResponse)
def transcribe_markdown_cv(payload: TranscribeCvRequest):
    """Transcrit un CV Markdown en profil structuré via l'IA, puis remplace le profil actif (version incrémentée)."""
    if not supabase_service.client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")
    from app.services.ai.cv_transcriber import cv_transcriber_service

    try:
        profile_obj = cv_transcriber_service.transcribe_markdown(payload.markdown)
    except Exception as e:
        logger.error(f"Erreur transcription CV Markdown: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur de transcription : {e}")
    if not profile_obj:
        raise HTTPException(status_code=502, detail="La transcription par l'IA a échoué")

    current = supabase_service.get_active_candidate_profile()
    record = {
        "name": profile_obj.name,
        "profile": profile_obj.model_dump(exclude={"preferences"}),
        # Un nouveau CV ne doit pas effacer les critères de recherche configurés.
        "preferences": (current or {}).get("preferences") or profile_obj.preferences.model_dump(),
        "version": (current.get("version", 1) + 1) if current else 1,
        "is_active": True,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if current:
        res = supabase_service.client.table("candidate_profiles").update(record).eq("id", current["id"]).execute()
    else:
        res = supabase_service.client.table("candidate_profiles").insert(record).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Enregistrement du profil transcrit échoué")
    return {"message": "CV transcrit et profil mis à jour", "profile": res.data[0]}
