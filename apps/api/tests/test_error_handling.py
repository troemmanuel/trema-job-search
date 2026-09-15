"""Les erreurs non gérées doivent rester exploitables par le frontend : JSON `detail` + en-têtes CORS."""
import os

os.environ.setdefault("ENABLE_SCHEDULER", "0")

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

ORIGIN = "http://localhost:3000"


def test_unhandled_exception_returns_json_500_with_cors(monkeypatch):
    from app.api.v1 import scheduler as scheduler_module

    def boom():
        raise RuntimeError("panne simulée")

    monkeypatch.setattr(scheduler_module.daily_scheduler_service, "get_status", boom)

    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/api/v1/scheduler/status", headers={"Origin": ORIGIN})

    assert res.status_code == 500
    assert "panne simulée" in res.json()["detail"]
    assert res.headers.get("access-control-allow-origin") == ORIGIN


def test_malformed_uuid_is_a_validation_error():
    client = TestClient(app)
    res = client.get("/api/v1/jobs/pas-un-uuid", headers={"Origin": ORIGIN})
    assert res.status_code == 422
    assert res.headers.get("access-control-allow-origin") == ORIGIN
