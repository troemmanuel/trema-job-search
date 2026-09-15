import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException
from app.services.storage import supabase_service
from app.schemas.candidate import CandidatePreferences
from app.schemas.api import NotionReconcileResponse, SettingsResponse, UpdateSettingsRequest, UpdateSettingsResponse

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
    from app.services.notion.sync_service import notion_sync_service
    try:
        result = notion_sync_service.reconcile()
        return result
    except Exception as e:
        logger.error(f"Erreur sync bidirectionnelle Notion: {e}")
        raise HTTPException(status_code=500, detail=str(e))
