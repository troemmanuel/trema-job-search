import json
from datetime import datetime
from pathlib import Path
import pytest
from app.services.scheduler.daily_scheduler import DailySchedulerService, compute_next_run

def test_compute_next_run():
    # Heure future ou passée
    next_run = compute_next_run("08:00")
    assert isinstance(next_run, datetime)
    assert next_run > datetime.now()
    assert next_run.hour == 8
    assert next_run.minute == 0

    next_run_23 = compute_next_run("23:59")
    assert next_run_23 > datetime.now()
    assert next_run_23.hour == 23
    assert next_run_23.minute == 59

def test_scheduler_state_save_and_load(tmp_path):
    status_file = tmp_path / "test_status.json"
    scheduler = DailySchedulerService(status_file=status_file)
    status = scheduler.get_status()

    assert status["is_active"] is True
    assert status["schedule_time"] in ["08:00", "8:00"]
    assert "next_run" in status

    # Mise à jour
    updated = scheduler.update_config(schedule_time="09:30", is_active=False)
    assert updated["schedule_time"] == "09:30"
    assert updated["is_active"] is False

    # Recharger dans une nouvelle instance
    scheduler_reloaded = DailySchedulerService(status_file=status_file)
    status_reloaded = scheduler_reloaded.get_status()
    assert status_reloaded["schedule_time"] == "09:30"
    assert status_reloaded["is_active"] is False

def test_scheduler_api_routes(client, monkeypatch):
    from app.services.scheduler.daily_scheduler import daily_scheduler_service

    # Ne pas écrire l'état réel du planificateur pendant les tests
    monkeypatch.setattr(daily_scheduler_service, "_save_state", lambda state: None)
    original_time = daily_scheduler_service.get_status()["schedule_time"]

    res = client.get("/api/v1/scheduler/status")
    assert res.status_code == 200
    data = res.json()
    assert "is_active" in data and "schedule_time" in data and "next_run" in data

    res_config = client.post("/api/v1/scheduler/update", json={"time": "07:45", "enabled": True})
    assert res_config.status_code == 200
    assert res_config.json()["status"]["schedule_time"] == "07:45"
    assert res_config.json()["status"]["is_active"] is True

    # Heure invalide : 400 (hors plage) ou 422 (format)
    assert client.post("/api/v1/scheduler/update", json={"time": "25:00"}).status_code == 400
    assert client.post("/api/v1/scheduler/update", json={"time": "bad"}).status_code == 422

    # Déclenchement manuel, sans exécuter la collecte
    monkeypatch.setattr(daily_scheduler_service, "trigger_now", lambda: True)
    res_run = client.post("/api/v1/scheduler/trigger")
    assert res_run.status_code == 200
    assert res_run.json()["started"] is True
    assert "lancée" in res_run.json()["message"]

    monkeypatch.setattr(daily_scheduler_service, "trigger_now", lambda: False)
    assert client.post("/api/v1/scheduler/trigger").json()["started"] is False

    daily_scheduler_service.update_config(schedule_time=original_time, is_active=True)
