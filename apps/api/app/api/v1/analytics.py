from fastapi import APIRouter, Query
from app.services.analytics import analytics_service, interfaces_analytics_service
from app.schemas.api import AnalyticsPeriod, AnalyticsStatsResponse, InterfacesAnalyticsResponse

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/stats", response_model=AnalyticsStatsResponse)
def get_analytics_stats(period: AnalyticsPeriod = Query("all")):
    """API JSON des métriques d'entonnoir et de conversion."""
    data = analytics_service.get_analytics(period=period)
    router_stats = None
    try:
        from app.llm import router as llm_router
        router_stats = llm_router.get_stats()
    except Exception:
        pass

    return {
        "success": True,
        **data,
        "router_stats": router_stats,
    }

@router.get("/interfaces", response_model=InterfacesAnalyticsResponse)
def get_analytics_interfaces():
    """API JSON des métriques d'observabilité des interfaces et APIs (LLM, Cache, Connecteurs)."""
    interfaces_data = interfaces_analytics_service.get_interfaces_analytics()
    return {
        "success": True,
        **interfaces_data,
    }
