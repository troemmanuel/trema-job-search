import json
from datetime import datetime
from pathlib import Path
import pytest
from app import create_app
from app.services.scheduler.daily_scheduler import DailySchedulerService, compute_next_run

@pytest.fixture
def test_client(tmp_path):
    app = create_app()
    app.config["TESTING"] = True
    app.config["ENABLE_SCHEDULER"] = False
    return app.test_client()

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

def test_scheduler_api_routes(test_client, monkeypatch, tmp_path):
    # Test GET /api/scheduler/status
    res = test_client.get("/api/scheduler/status")
    assert res.status_code == 200
    data = res.get_json()
    assert "is_active" in data
    assert "schedule_time" in data
    assert "next_run" in data

    # Test POST /api/scheduler/config
    res_config = test_client.post("/api/scheduler/config", json={"schedule_time": "07:45", "is_active": True})
    assert res_config.status_code == 200
    data_config = res_config.get_json()
    assert data_config["scheduler"]["schedule_time"] == "07:45"
    assert data_config["scheduler"]["is_active"] is True

    # Test POST /api/scheduler/run-now (mocking trigger_now to avoid heavy execution in test)
    from app.services.scheduler.daily_scheduler import daily_scheduler_service
    monkeypatch.setattr(daily_scheduler_service, "trigger_now", lambda app=None: True)

    res_run = test_client.post("/api/scheduler/run-now")
    assert res_run.status_code == 202
    assert "Collecte quotidienne lancée" in res_run.get_json()["message"]
