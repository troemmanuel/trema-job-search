"""Routeur LLM multi-fournisseurs : vue d'ensemble, test de provider, cache et statistiques."""
from unittest.mock import patch

from app.llm.schemas.router import LLMResult


def test_settings_exposes_router_overview(client):
    """GET /settings embarque l'état complet du routeur (providers, cascade de repli, cache)."""
    res = client.get("/api/v1/settings")
    assert res.status_code == 200
    overview = res.json()["router_overview"]
    assert overview is not None
    provider_names = [p["name"] for p in overview["providers"]]
    for name in ("gemini", "groq", "mistral", "openrouter"):
        assert name in provider_names
    assert "job_scoring" in overview["routing_config"]
    assert "hit_ratio_percent" in overview["cache"]


def test_router_test_provider(client):
    """POST /settings/router/test teste un provider avec son modèle par défaut."""
    with patch("app.llm.providers.groq.GroqProvider.generate") as mock_gen, patch(
        "app.llm.providers.groq.GroqProvider.is_configured", return_value=True
    ):
        mock_gen.return_value = LLMResult(data={"status": "OK"}, provider="groq", model="openai/gpt-oss-120b", latency=0.15, tokens=5)
        res = client.post("/api/v1/settings/router/test", json={"provider": "groq"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["provider"] == "groq"
    assert data["model"] == "openai/gpt-oss-120b"


def test_router_test_unknown_provider(client):
    data = client.post("/api/v1/settings/router/test", json={"provider": "inconnu"}).json()
    assert data["success"] is False
    assert "inconnu" in data["error"]


def test_router_cache_clear(client):
    res = client.post("/api/v1/settings/router/cache/clear")
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert "vidé" in res.json()["message"]


def test_router_stats_reset(client):
    res = client.post("/api/v1/settings/router/stats/reset")
    assert res.status_code == 200
    assert res.json()["success"] is True
