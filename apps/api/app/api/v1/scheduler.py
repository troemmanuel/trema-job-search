from fastapi import APIRouter, HTTPException
from app.services.scheduler.daily_scheduler import daily_scheduler_service
from app.schemas.api import SchedulerStatus, SchedulerTriggerResponse, SchedulerUpdateRequest, SchedulerUpdateResponse

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])

@router.get("/status", response_model=SchedulerStatus)
def get_scheduler_status():
    """Récupère l'état courant du planificateur matinal."""
    return daily_scheduler_service.get_status()

@router.post("/trigger", response_model=SchedulerTriggerResponse)
def trigger_scheduler_job():
    """Déclenche manuellement et immédiatement le job de collecte et préparation."""
    started = daily_scheduler_service.trigger_now()
    return {
        "message": "Collecte lancée en arrière-plan" if started else "Une collecte est déjà en cours",
        "started": started,
        "status": daily_scheduler_service.get_status(),
    }

@router.post("/update", response_model=SchedulerUpdateResponse)
def update_scheduler_settings(payload: SchedulerUpdateRequest):
    """Met à jour l'heure et la configuration du planificateur."""
    parts = payload.time.split(":")
    try:
        h, m = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Format d'heure invalide (attendu HH:MM)")
    if not (0 <= h < 24 and 0 <= m < 60):
        raise HTTPException(status_code=400, detail="Heure hors plage (00:00 - 23:59)")

    status = daily_scheduler_service.update_config(schedule_time=payload.time, is_active=payload.enabled)
    return {"message": "Configuration du planificateur mise à jour", "status": status}
