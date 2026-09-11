import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

def compute_next_run(schedule_time_str: str) -> datetime:
    """Calcule la prochaine occurrence pour une heure HH:MM donnée (locale)."""
    now = datetime.now()
    try:
        parts = schedule_time_str.strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        hour, minute = 8, 0

    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target

class DailySchedulerService:
    """Planificateur automatique quotidien basé sur threading standard (zéro dépendance externe)."""

    def __init__(self, status_file: Optional[Path] = None):
        self.project_dir = Path(__file__).resolve().parents[3]
        self.status_file = status_file or (self.project_dir / "instance" / "scheduler_status.json")
        self._stop_event = threading.Event()
        self._reschedule_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._app = None
        self._lock = threading.Lock()
        
        # Charger ou initialiser l'état
        self.state: Dict[str, Any] = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Charge l'état depuis le fichier JSON persistant ou génère les valeurs par défaut."""
        default_time = os.getenv("CRON_SCHEDULE_TIME", "08:00")
        default_state = {
            "is_active": True,
            "schedule_time": default_time,
            "next_run": compute_next_run(default_time).isoformat(),
            "last_run": None,
            "last_result": None,
            "is_running_job": False
        }
        if self.status_file.exists():
            try:
                data = json.loads(self.status_file.read_text(encoding="utf-8"))
                default_state.update(data)
                # Recalculer le next_run si dans le passé
                next_dt = datetime.fromisoformat(default_state["next_run"]) if default_state.get("next_run") else None
                if not next_dt or next_dt <= datetime.now():
                    default_state["next_run"] = compute_next_run(default_state["schedule_time"]).isoformat()
            except Exception as e:
                logger.warning(f"Impossible de charger {self.status_file}: {e}")
        
        self._save_state(default_state)
        return default_state

    def _save_state(self, state: Dict[str, Any]) -> None:
        """Sauvegarde l'état dans le fichier JSON."""
        try:
            self.status_file.parent.mkdir(parents=True, exist_ok=True)
            self.status_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Erreur écriture fichier statut scheduler: {e}")

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self.state)

    def update_config(self, schedule_time: Optional[str] = None, is_active: Optional[bool] = None) -> Dict[str, Any]:
        """Met à jour l'heure programmée ou l'état actif/pause."""
        with self._lock:
            if schedule_time:
                # Validation format HH:MM
                try:
                    parts = schedule_time.strip().split(":")
                    h, m = int(parts[0]), int(parts[1])
                    if 0 <= h < 24 and 0 <= m < 60:
                        self.state["schedule_time"] = f"{h:02d}:{m:02d}"
                        self.state["next_run"] = compute_next_run(self.state["schedule_time"]).isoformat()
                except Exception as e:
                    logger.warning(f"Format heure invalide {schedule_time}: {e}")

            if is_active is not None:
                self.state["is_active"] = bool(is_active)
                if self.state["is_active"]:
                    self.state["next_run"] = compute_next_run(self.state["schedule_time"]).isoformat()

            self._save_state(self.state)
            self._reschedule_event.set()
            return dict(self.state)

    def start(self, app=None) -> None:
        """Démarre le thread d'arrière-plan du planificateur."""
        if app:
            self._app = app

        if self._thread and self._thread.is_alive():
            logger.info("Le DailySchedulerService est déjà en cours d'exécution.")
            return

        self._stop_event.clear()
        self._reschedule_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="DailyJobSchedulerThread")
        self._thread.start()
        logger.info(f"DailySchedulerService démarré. Prochaine exécution : {self.state.get('next_run')}")

    def stop(self) -> None:
        """Arrête le thread du planificateur."""
        self._stop_event.set()
        self._reschedule_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        logger.info("DailySchedulerService arrêté.")

    def trigger_now(self, app=None) -> bool:
        """Déclenche immédiatement une exécution de la collecte en arrière-plan."""
        active_app = app or self._app
        with self._lock:
            if self.state.get("is_running_job"):
                logger.warning("Une collecte est déjà en cours d'exécution.")
                return False
            self.state["is_running_job"] = True
            self._save_state(self.state)

        # Lancement dans un thread séparé pour ne pas bloquer
        run_thread = threading.Thread(
            target=self._execute_job_wrapper,
            args=(active_app,),
            daemon=True,
            name="ManualTriggerJobThread"
        )
        run_thread.start()
        return True

    def _execute_job_wrapper(self, app) -> None:
        """Exécute la collecte avec contexte applicatif Flask et met à jour le statut."""
        logger.info("Début de l'exécution automatique de la collecte quotidienne...")
        start_iso = datetime.now().isoformat()
        try:
            from app.services.ingestion.collector import job_collector_service
            if app:
                with app.app_context():
                    result = job_collector_service.run_collection(
                        duration="24h",
                        limit=10,
                        auto_prepare=True
                    )
            else:
                result = job_collector_service.run_collection(
                    duration="24h",
                    limit=10,
                    auto_prepare=True
                )

            # Réconciliation bidirectionnelle Notion ↔ Supabase
            reconcile_report = None
            try:
                from app.services.notion.sync import notion_sync_service
                reconcile_report = notion_sync_service.reconcile()
                logger.info(
                    f"Réconciliation Notion quotidienne effectuée: {reconcile_report.get('matched_count', 0)} appariées, "
                    f"{reconcile_report.get('updated_supabase_count', 0)} màj Supabase, {reconcile_report.get('updated_notion_count', 0)} màj Notion."
                )
            except Exception as ne:
                logger.warning(f"Échec de la réconciliation Notion quotidienne: {ne}")

            with self._lock:
                self.state["last_run"] = start_iso
                self.state["last_result"] = {
                    "total_found": result.get("total_found", 0),
                    "processed_count": result.get("processed_count", 0),
                    "new_imported_count": result.get("new_imported_count", 0),
                    "qualified_count": result.get("qualified_count", 0),
                    "prepared_count": result.get("prepared_count", 0),
                    "notion_synced_count": result.get("notion_synced_count", 0),
                    "notion_reconcile": {
                        "matched_count": reconcile_report.get("matched_count", 0) if reconcile_report else 0,
                        "updated_supabase": reconcile_report.get("updated_supabase_count", 0) if reconcile_report else 0,
                        "updated_notion": reconcile_report.get("updated_notion_count", 0) if reconcile_report else 0
                    } if reconcile_report else None,
                    "jobs": [
                        {
                            "title": j.get("title"),
                            "company": j.get("company"),
                            "match_score": j.get("match_score"),
                            "status": j.get("status"),
                            "notion_url": j.get("notion_url")
                        }
                        for j in result.get("jobs", [])
                    ]
                }
                self.state["is_running_job"] = False
                # Reprogrammer la prochaine exécution
                self.state["next_run"] = compute_next_run(self.state["schedule_time"]).isoformat()
                self._save_state(self.state)

            logger.info(f"Collecte quotidienne achevée avec succès : {result.get('prepared_count', 0)} candidatures préparées.")

        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de la collecte quotidienne: {e}")
            with self._lock:
                self.state["is_running_job"] = False
                self.state["last_run"] = start_iso
                self.state["last_result"] = {"error": str(e)}
                self._save_state(self.state)

    def _run_loop(self) -> None:
        """Boucle principale du planificateur qui attend jusqu'au prochain créneau."""
        while not self._stop_event.is_set():
            with self._lock:
                is_active = self.state.get("is_active", True)
                schedule_time = self.state.get("schedule_time", "08:00")

            if not is_active:
                # Si en pause, attendre une modification de configuration ou l'arrêt
                self._reschedule_event.wait(timeout=30.0)
                self._reschedule_event.clear()
                continue

            next_run_dt = compute_next_run(schedule_time)
            with self._lock:
                self.state["next_run"] = next_run_dt.isoformat()
                self._save_state(self.state)

            now = datetime.now()
            delay_seconds = max((next_run_dt - now).total_seconds(), 0)
            logger.info(f"DailySchedulerService en attente de {delay_seconds:.0f}s jusqu'à {next_run_dt.strftime('%Y-%m-%d %H:%M:%S')}")

            # Attendre jusqu'au réveil ou signal de reprogrammation
            interrupted = self._reschedule_event.wait(timeout=delay_seconds)
            if self._stop_event.is_set():
                break

            if interrupted:
                self._reschedule_event.clear()
                logger.info("Reprogrammation détectée, recalcul du prochain créneau.")
                continue

            # Heure atteinte : lancer le job automatique
            logger.info("Heure planifiée atteinte ! Lancement de la collecte automatique des dernières 24h...")
            self._execute_job_wrapper(self._app)

daily_scheduler_service = DailySchedulerService()
