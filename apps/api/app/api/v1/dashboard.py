from fastapi import APIRouter
from app.config import Config
from app.services.storage import supabase_service
from app.services.scheduler.daily_scheduler import daily_scheduler_service
from app.schemas.api import DashboardStatsResponse

router = APIRouter(tags=["Dashboard"])

@router.get("/dashboard/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats():
    """Statistiques globales et KPIs pour le Dashboard."""
    stats = {
        "priority_count": 0,
        "recommended_count": 0,
        "review_count": 0,
        "ignored_count": 0,
        "to_prepare_count": 0,
        "ready_count": 0,
        "applied_count": 0,
        "interview_count": 0,
    }
    recent_jobs = []
    recent_applications = []

    if supabase_service.client:
        try:
            jobs = supabase_service.get_jobs(limit=20)
            recent_jobs = jobs
            for job in jobs:
                score = job.get("match_score") or 0
                if score >= Config.MATCH_THRESHOLD_PRIORITY:
                    stats["priority_count"] += 1
                elif score >= Config.MATCH_THRESHOLD_RECOMMENDED:
                    stats["recommended_count"] += 1
                elif score >= Config.MATCH_THRESHOLD_REVIEW:
                    stats["review_count"] += 1
                elif job.get("status") == "IGNORED" or (score and score < Config.MATCH_THRESHOLD_REVIEW):
                    stats["ignored_count"] += 1

            applications = supabase_service.get_applications(limit=20)
            recent_applications = applications
            for app in applications:
                status = app.get("status")
                if status in ["QUALIFIED", "PREPARING"]:
                    stats["to_prepare_count"] += 1
                elif status in ["PREPARED", "READY"]:
                    stats["ready_count"] += 1
                elif status == "APPLIED":
                    stats["applied_count"] += 1
                elif status in ["INTERVIEW", "INTERVIEW_HR", "INTERVIEW_TECH"]:
                    stats["interview_count"] += 1
        except Exception:
            pass

    scheduler_status = None
    try:
        scheduler_status = daily_scheduler_service.get_status()
    except Exception:
        pass

    return {
        "stats": stats,
        "recent_jobs": recent_jobs,
        "recent_applications": recent_applications,
        "scheduler_status": scheduler_status,
    }
