from fastapi import APIRouter, HTTPException
from app.services.storage import supabase_service
from app.schemas.api import CandidateProfileRecord, UpdateCandidateProfileRequest, UpdateCandidateProfileResponse

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

    profile_obj = payload.profile.model_dump()
    preferences_obj = payload.preferences.model_dump()

    active = supabase_service.get_active_candidate_profile()
    if active:
        res = supabase_service.client.table("candidate_profiles").update({
            "profile": profile_obj,
            "preferences": preferences_obj,
        }).eq("id", active["id"]).execute()
        return {"message": "Profil mis à jour", "data": res.data}
    else:
        res = supabase_service.client.table("candidate_profiles").insert({
            "name": payload.profile.name or "Candidat",
            "profile": profile_obj,
            "preferences": preferences_obj,
            "is_active": True,
        }).execute()
        return {"message": "Profil créé", "data": res.data}
