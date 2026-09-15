from fastapi import APIRouter
from app.services.storage import supabase_service
from app.services.ai.gemini import gemini_service
from app.services.notion.client import notion_service
from app.schemas.api import HealthResponse

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthResponse)
def health_check():
    """Endpoint de santé pour monitoring et tests de disponibilité."""
    return {
        "status": "ok",
        "version": "2.0.0",
        "services": {
            "supabase": "connected" if supabase_service.is_configured() else "unconfigured",
            "gemini": "configured" if gemini_service.is_configured() else "unconfigured",
            "notion": "configured" if notion_service.is_configured() else "unconfigured",
        }
    }
