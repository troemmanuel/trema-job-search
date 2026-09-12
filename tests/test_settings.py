import pytest
from unittest.mock import patch, MagicMock
from app import create_app
from app.services.ingestion.filters import is_company_blacklisted, matches_excluded_keyword, is_esn_company
from app.services.ai.gemini import gemini_service
from app.services.ingestion.collector import job_collector_service
from app.services.storage.supabase_service import supabase_service

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_settings_html_view(client):
    """Vérifie que la page HTML /settings s'affiche avec statut 200."""
    res = client.get("/settings")
    assert res.status_code == 200
    assert "Paramètres & Configuration IA".encode("utf-8") in res.data
    assert "Modèle principal".encode("utf-8") in res.data
    assert "Blacklist".encode("utf-8") in res.data
    assert "Planificateur Quotidien".encode("utf-8") in res.data

def test_get_settings_api(client):
    """Vérifie la récupération des paramètres via l'API GET /api/settings."""
    res = client.get("/api/settings")
    assert res.status_code == 200
    data = res.get_json()
    assert "preferences" in data
    assert "available_models" in data
    assert "ai_model" in data["preferences"]
    assert "excluded_companies" in data["preferences"]
    assert "match_threshold_recommended" in data["preferences"]

def test_put_settings_api(client):
    """Vérifie la mise à jour des paramètres via PUT /api/settings."""
    payload = {
        "preferences": {
            "ai_model": "gemini-2.5-pro",
            "ai_temperature": 0.3,
            "ai_custom_instructions": "Focus Cloud & Kubernetes",
            "excluded_companies": ["BadCompany"],
            "excluded_keywords": ["Stage"],
            "filter_esn": True,
            "match_threshold_recommended": 80
        }
    }
    res = client.put("/api/settings", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["preferences"]["ai_model"] == "gemini-2.5-pro"
    assert data["preferences"]["ai_temperature"] == 0.3
    assert data["preferences"]["excluded_companies"] == ["BadCompany"]
    assert data["preferences"]["filter_esn"] is True

def test_blacklist_add_and_remove(client):
    """Vérifie l'ajout puis la suppression d'une entreprise via l'API de blacklist."""
    # 1. Ajout
    res_add = client.post("/api/settings/blacklist", json={"company": "TestCorp"})
    assert res_add.status_code == 200
    data_add = res_add.get_json()
    assert "TestCorp" in data_add["excluded_companies"]

    # 2. Suppression
    res_del = client.delete("/api/settings/blacklist", json={"company": "TestCorp"})
    assert res_del.status_code == 200
    data_del = res_del.get_json()
    assert "TestCorp" not in data_del["excluded_companies"]

def test_blacklist_add_validation(client):
    """Vérifie que l'ajout sans nom d'entreprise renvoie une erreur 400."""
    res = client.post("/api/settings/blacklist", json={"company": ""})
    assert res.status_code == 400

def test_filters_company_blacklisted():
    """Vérifie les correspondances exactes et tolérantes de la blacklist."""
    excluded = ["Capgemini", "Societe Generale", "Alten"]
    assert is_company_blacklisted("Capgemini", excluded) is True
    assert is_company_blacklisted("capgemini", excluded) is True
    assert is_company_blacklisted("Capgemini France", excluded) is True
    assert is_company_blacklisted("Societe Generale", excluded) is True
    assert is_company_blacklisted("Doctolib", excluded) is False
    assert is_company_blacklisted(None, excluded) is False
    assert is_company_blacklisted("Google", []) is False

def test_filters_excluded_keywords():
    """Vérifie la détection de mots-clés négatifs dans les titres."""
    keywords = ["stage", "alternance", "wordpress", "php"]
    assert matches_excluded_keyword("Développeur Python (Stage)", keywords) == "stage"
    assert matches_excluded_keyword("Ingénieur Backend alternance", keywords) == "alternance"
    assert matches_excluded_keyword("Développeur WordPress", keywords) == "wordpress"
    assert matches_excluded_keyword("Ingénieur Logiciel Java", keywords) is None
    # Ne doit pas matcher de faux positifs de sous-chaînes partielles
    assert matches_excluded_keyword("Stagecraft Engineer", keywords) is None

def test_filters_is_esn():
    """Vérifie la détection d'entreprises ESN."""
    assert is_esn_company("Capgemini") is True
    assert is_esn_company("Sopra Steria") is True
    assert is_esn_company("Doctolib") is False

def test_test_ai_endpoint(client):
    """Vérifie l'endpoint POST /api/settings/test-ai."""
    with patch.object(gemini_service, "test_connection", return_value={"success": True, "model": "gemini-3.5-flash", "response_time_ms": 120, "output": "OK"}):
        res = client.post("/api/settings/test-ai", json={"model": "gemini-3.5-flash"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["output"] == "OK"

def test_collector_filters_blacklisted_and_keywords():
    """Vérifie que run_collection ignore les offres blacklistées ou contenant des mots-clés exclus."""
    fake_hits = [
        {"url": "https://wttj.com/job1", "title": "Dev Python", "company": "BannedCorp", "published_at": "2026-09-12T10:00:00Z"},
        {"url": "https://wttj.com/job2", "title": "Stage Développeur Java", "company": "GoodCorp", "published_at": "2026-09-12T10:00:00Z"},
    ]

    mock_profile = {
        "name": "John Doe",
        "profile": {
            "name": "John Doe",
            "personal": {"first_name": "John", "last_name": "Doe", "email": "john.doe@example.com"}
        },
        "preferences": {
            "excluded_companies": ["BannedCorp"],
            "excluded_keywords": ["Stage"]
        }
    }

    with patch.object(supabase_service, "get_active_candidate_profile", return_value=mock_profile):
        with patch.object(job_collector_service, "search_wttj_recent_jobs", return_value=fake_hits):
            summary = job_collector_service.run_collection(duration="24h", limit=5)
            assert summary["processed_count"] == 2
            # Aucune offre ne doit avoir été importée car les 2 sont filtrées
            assert summary["new_imported_count"] == 0
            statuses = [j["status"] for j in summary["jobs"]]
            assert "BLACKLISTED" in statuses
            assert "FILTERED_KEYWORD" in statuses

def test_import_and_process_url_blacklisted():
    """Vérifie que l'import d'une offre d'une entreprise blacklistée s'arrête immédiatement."""
    mock_profile = {
        "id": "cand-123",
        "name": "John Doe",
        "profile": {
            "name": "John Doe",
            "personal": {"first_name": "John", "last_name": "Doe", "email": "john.doe@example.com"}
        },
        "preferences": {
            "excluded_companies": ["BlacklistedEnterprise"]
        }
    }

    scraped_job = {
        "title": "Ingénieur Backend",
        "company": "BlacklistedEnterprise",
        "url": "https://linkedin.com/jobs/view/123",
        "description": "Super job",
        "source": "LINKEDIN"
    }

    with patch.object(supabase_service, "get_active_candidate_profile", return_value=mock_profile):
        with patch("app.services.ingestion.scraper.job_scraper.scrape", return_value=scraped_job):
            with patch("app.services.ingestion.importer.job_importer.import_job", return_value={"status": "CREATED", "job": scraped_job}):
                result = job_collector_service.import_and_process_url("https://linkedin.com/jobs/view/123")
                assert result["success"] is True
                assert result["status"] == "BLACKLISTED"
                assert "liste noire" in result["message"]

def test_dynamic_ai_model_and_temperature_resolution():
    """Vérifie que GeminiService résout dynamiquement le modèle et la température configurés."""
    mock_profile = {
        "preferences": {
            "ai_model": "gemini-2.5-pro",
            "ai_temperature": 0.45
        }
    }
    with patch.object(supabase_service, "get_active_candidate_profile", return_value=mock_profile):
        assert gemini_service.get_configured_model() == "gemini-2.5-pro"
        assert gemini_service.get_configured_temperature() == 0.45

    # Fallback si pas de profil
    with patch.object(supabase_service, "get_active_candidate_profile", return_value=None):
        assert gemini_service.get_configured_model() == gemini_service.config.GEMINI_MODEL
        assert gemini_service.get_configured_temperature() == 0.2

