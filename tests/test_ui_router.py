import pytest
import os
import json
from unittest.mock import patch, MagicMock
from app import create_app
from app.config import Config
from app.llm.schemas.router import LLMResult

class TestConfig(Config):
    TESTING = True
    ENABLE_SCHEDULER = False
    SUPABASE_URL = "https://mock.supabase.co"
    SUPABASE_KEY = "mock-key"
    GEMINI_API_KEY = "mock-gemini-key"

@pytest.fixture
def client():
    app = create_app(TestConfig)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_api_settings_router(client):
    """Vérifie l'API de vue d'ensemble du LLM Router."""
    res = client.get("/api/settings/router")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "providers" in data
    assert "routing_config" in data
    assert "cache" in data

    provider_names = [p["name"] for p in data["providers"]]
    assert "gemini" in provider_names
    assert "groq" in provider_names
    assert "mistral" in provider_names
    assert "openrouter" in provider_names

def test_api_settings_router_test_provider(client):
    """Vérifie le test individuel d'un provider via l'API."""
    with patch("app.llm.providers.groq.GroqProvider.generate") as mock_gen:
        mock_gen.return_value = LLMResult(
            data={"status": "OK"},
            provider="groq",
            model="llama-3.3-70b-versatile",
            latency=0.15,
            tokens=5
        )
        with patch("app.llm.providers.groq.GroqProvider.is_configured", return_value=True):
            res = client.post("/api/settings/router/test", json={"provider": "groq"})
            assert res.status_code == 200
            data = res.get_json()
            assert data["success"] is True
            assert data["provider"] == "groq"
            assert data["model"] == "llama-3.3-70b-versatile"

def test_api_settings_router_cache_clear(client):
    """Vérifie l'API de vidage du cache LLM."""
    res = client.post("/api/settings/router/cache/clear")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "vidé" in data["message"]

def test_api_settings_router_stats_reset(client):
    """Vérifie la réinitialisation des statistiques du routeur."""
    res = client.post("/api/settings/router/stats/reset")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

def test_settings_page_with_router_overview(client):
    """Vérifie que la page /settings charge les nouveaux composants du routeur."""
    res = client.get("/settings")
    assert res.status_code == 200
    assert b"LLM Router" in res.data
    assert b"Failover Automatique 429" in res.data
    assert b"Cache d'Idempotence SHA-256" in res.data
    assert b"testRouterProvider" in res.data

def test_analytics_page_with_observability(client):
    """Vérifie que la page /analytics charge la section Observabilité LLM Router."""
    res = client.get("/analytics")
    assert res.status_code == 200
    assert b"Observabilit" in res.data
    assert b"LLM Router" in res.data
