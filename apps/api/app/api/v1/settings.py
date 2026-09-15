import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException
from app.services.storage import supabase_service
from app.schemas.candidate import CandidatePreferences
from app.schemas.api import (
    BlacklistRequest,
    BlacklistResponse,
    NotionReconcileResponse,
    ProviderTestRequest,
    ProviderTestResponse,
    SettingsResponse,
    SuccessMessageResponse,
    UpdateSettingsRequest,
    UpdateSettingsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["Settings"])

AVAILABLE_AI_MODELS = [
    {
        "id": "gemini-2.5-flash",
        "name": "Gemini 2.5 Flash",
        "description": "Modèle rapide et équilibré par défaut, idéal pour le tri, matching et rédaction",
        "recommended": True,
    },
    {
        "id": "gemini-2.0-flash",
        "name": "Gemini 2.0 Flash",
        "description": "Très rapide avec excellente compréhension structurée",
        "recommended": False,
    },
    {
        "id": "gemini-2.5-flash-lite",
        "name": "Gemini 2.5 Flash Lite",
        "description": "Ultra léger, rapide et très économe en quota",
        "recommended": False,
    },
    {
        "id": "gemini-2.5-pro",
        "name": "Gemini 2.5 Pro",
        "description": "Raisonnement avancé, excellent pour les lettres de motivation ciblées",
        "recommended": False,
    },
]

def _get_active_preferences() -> Dict[str, Any]:
    profile = supabase_service.get_active_candidate_profile() if supabase_service.client else None
    raw_prefs = (profile.get("preferences") or {}) if profile else {}
    validated = CandidatePreferences.model_validate(raw_prefs)
    return validated.model_dump()

@router.get("", response_model=SettingsResponse)
def get_settings():
    """Récupère les préférences et paramètres actuels."""
    preferences = _get_active_preferences()
    router_overview = None
    try:
        from app.llm import router as llm_router
        router_overview = llm_router.get_router_overview()
    except Exception:
        pass

    return {
        "preferences": preferences,
        "available_models": AVAILABLE_AI_MODELS,
        "router_overview": router_overview,
    }

@router.put("", response_model=UpdateSettingsResponse)
def update_settings(payload: UpdateSettingsRequest):
    """Met à jour les paramètres dans le profil candidat actif."""
    try:
        validated_prefs = payload.preferences

        profile = supabase_service.get_active_candidate_profile() if supabase_service.client else None
        if profile and supabase_service.client:
            profile_id = profile.get("id")
            update_data = {
                "preferences": validated_prefs.model_dump(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            supabase_service.client.table("candidate_profiles").update(update_data).eq("id", profile_id).execute()
            return {"message": "Paramètres mis à jour avec succès", "preferences": validated_prefs.model_dump()}
        else:
            raise HTTPException(status_code=404, detail="Profil candidat introuvable")
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Erreur mise à jour settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync-notion", response_model=NotionReconcileResponse)
def trigger_notion_bidirectional_sync():
    """Déclenche la synchronisation bidirectionnelle Notion ↔ Supabase."""
    from app.services.notion.sync import notion_sync_service
    try:
        result = notion_sync_service.reconcile()
        return result
    except Exception as e:
        logger.error(f"Erreur sync bidirectionnelle Notion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/blacklist", response_model=BlacklistResponse)
def add_to_blacklist(payload: BlacklistRequest):
    """Ajoute une entreprise à la liste noire et passe ses offres existantes en BLACKLISTED."""
    if not supabase_service.client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")
    company = payload.company.strip()
    profile = supabase_service.get_active_candidate_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil candidat introuvable")

    current_prefs = dict(profile.get("preferences") or {})
    excluded = list(current_prefs.get("excluded_companies") or [])
    if not any(c.lower() == company.lower() for c in excluded):
        excluded.append(company)
        current_prefs["excluded_companies"] = excluded
        supabase_service.client.table("candidate_profiles").update({
            "preferences": current_prefs,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", profile["id"]).execute()

    # Rétro-mise à jour des offres existantes de cette entreprise (correspondance souple, comme l'ancienne route Flask)
    updated_jobs_count = 0
    try:
        res = supabase_service.client.table("jobs").select("id, company").execute()
        needle = company.lower()
        for j in res.data or []:
            j_comp = (j.get("company") or "").strip().lower()
            if not j_comp:
                continue
            if needle == j_comp or (len(company) >= 3 and (needle in j_comp or j_comp in needle)):
                supabase_service.client.table("jobs").update({"status": "BLACKLISTED"}).eq("id", j["id"]).execute()
                updated_jobs_count += 1
    except Exception as je:
        logger.warning(f"Erreur mise à jour offres existantes pour blacklist: {je}")

    return {
        "message": f"« {company} » a été ajoutée à la liste noire.",
        "excluded_companies": excluded,
        "retro_updated_jobs": updated_jobs_count,
    }


@router.delete("/blacklist", response_model=BlacklistResponse)
def remove_from_blacklist(payload: BlacklistRequest):
    """Retire une entreprise de la liste noire (les offres déjà marquées BLACKLISTED ne sont pas modifiées)."""
    if not supabase_service.client:
        raise HTTPException(status_code=503, detail="Supabase non configuré")
    company = payload.company.strip()
    profile = supabase_service.get_active_candidate_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil candidat introuvable")

    current_prefs = dict(profile.get("preferences") or {})
    excluded = [c for c in (current_prefs.get("excluded_companies") or []) if c.lower() != company.lower()]
    current_prefs["excluded_companies"] = excluded
    supabase_service.client.table("candidate_profiles").update({
        "preferences": current_prefs,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", profile["id"]).execute()
    return {"message": f"« {company} » a été retirée de la liste noire.", "excluded_companies": excluded}


@router.post("/router/test", response_model=ProviderTestResponse)
def test_router_provider(payload: ProviderTestRequest):
    """Teste la connectivité d'un provider LLM (Gemini, Groq, Mistral, OpenRouter) avec un modèle optionnel."""
    from app.llm import router as llm_router
    try:
        return llm_router.test_provider(payload.provider.lower(), model=payload.model)
    except Exception as e:
        logger.error(f"Erreur test provider '{payload.provider}': {e}")
        return {"success": False, "provider": payload.provider, "error": str(e)}


@router.post("/router/cache/clear", response_model=SuccessMessageResponse)
def clear_router_cache():
    """Vide le cache d'idempotence SHA-256 des appels LLM."""
    from app.llm.cache import llm_cache
    llm_cache.clear()
    return {"message": "Cache LLM vidé."}


@router.post("/router/stats/reset", response_model=SuccessMessageResponse)
def reset_router_stats():
    """Réinitialise les compteurs d'utilisation des providers LLM."""
    from app.llm import router as llm_router
    llm_router.reset_stats()
    return {"message": "Statistiques du routeur réinitialisées."}
