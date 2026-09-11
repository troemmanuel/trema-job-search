import logging
from flask import Blueprint, jsonify, request, current_app
from app.services.scheduler.daily_scheduler import daily_scheduler_service

logger = logging.getLogger(__name__)

scheduler_bp = Blueprint("scheduler", __name__)

@scheduler_bp.route("/api/scheduler/status", methods=["GET"])
def get_scheduler_status():
    """Renvoie le statut et les paramètres du planificateur automatique."""
    try:
        status = daily_scheduler_service.get_status()
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"Erreur récupération statut scheduler: {e}")
        return jsonify({"error": str(e)}), 500

@scheduler_bp.route("/api/scheduler/config", methods=["POST"])
def update_scheduler_config():
    """Met à jour l'heure de programmation ou active/désactive le planificateur."""
    payload = request.get_json() or {}
    schedule_time = payload.get("schedule_time")
    is_active = payload.get("is_active")

    if schedule_time is None and is_active is None:
        return jsonify({"error": "Paramètres 'schedule_time' ou 'is_active' attendus"}), 400

    try:
        updated = daily_scheduler_service.update_config(
            schedule_time=schedule_time,
            is_active=is_active
        )
        return jsonify({
            "message": "Configuration du planificateur mise à jour",
            "scheduler": updated
        }), 200
    except Exception as e:
        logger.error(f"Erreur mise à jour config scheduler: {e}")
        return jsonify({"error": str(e)}), 500

@scheduler_bp.route("/api/scheduler/run-now", methods=["POST"])
def trigger_scheduler_now():
    """Déclenche immédiatement une exécution de la collecte automatique en arrière-plan."""
    try:
        started = daily_scheduler_service.trigger_now(app=current_app._get_current_object())
        if started:
            return jsonify({
                "message": "Collecte quotidienne lancée avec succès en arrière-plan",
                "is_running_job": True
            }), 202
        else:
            return jsonify({
                "message": "Une collecte est déjà en cours d'exécution",
                "is_running_job": True
            }), 409
    except Exception as e:
        logger.error(f"Erreur déclenchement manuel scheduler: {e}")
        return jsonify({"error": str(e)}), 500
