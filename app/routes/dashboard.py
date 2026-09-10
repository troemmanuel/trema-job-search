from flask import Blueprint, jsonify, render_template, current_app
from app.services.storage import supabase_service
from app.services.ai.gemini import gemini_service
from app.services.notion.client import notion_service

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/health", methods=["GET"])
def health_check():
    """Endpoint de santé pour monitoring et tests de disponibilité."""
    return jsonify({
        "status": "ok",
        "version": "1.0.0",
        "services": {
            "supabase": "connected" if supabase_service.is_configured() else "unconfigured",
            "gemini": "configured" if gemini_service.is_configured() else "unconfigured",
            "notion": "configured" if notion_service.is_configured() else "unconfigured"
        }
    }), 200

@dashboard_bp.route("/", methods=["GET"])
def index():
    """Page d'accueil du Dashboard Flask."""
    # Statistiques d'offres et de candidatures
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
                if score >= current_app.config["MATCH_THRESHOLD_PRIORITY"]:
                    stats["priority_count"] += 1
                elif score >= current_app.config["MATCH_THRESHOLD_RECOMMENDED"]:
                    stats["recommended_count"] += 1
                elif score >= current_app.config["MATCH_THRESHOLD_REVIEW"]:
                    stats["review_count"] += 1
                elif job.get("status") == "IGNORED" or (score and score < current_app.config["MATCH_THRESHOLD_REVIEW"]):
                    stats["ignored_count"] += 1

            applications = supabase_service.get_applications(limit=20)
            recent_applications = applications
            for app in applications:
                status = app.get("status")
                if status in ["QUALIFIED", "PREPARING"]:
                    stats["to_prepare_count"] += 1
                elif status == "READY":
                    stats["ready_count"] += 1
                elif status == "APPLIED":
                    stats["applied_count"] += 1
                elif status == "INTERVIEW":
                    stats["interview_count"] += 1
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la récupération des stats Supabase: {e}")

    return render_template("dashboard.html", stats=stats, recent_jobs=recent_jobs, recent_applications=recent_applications)
