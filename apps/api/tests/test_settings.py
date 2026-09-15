"""Paramètres : préférences, liste noire et filtres de pré-tri."""
from unittest.mock import patch

from app.services.ai.gemini import gemini_service
from app.services.ingestion.collector import job_collector_service
from app.services.ingestion.filters import is_company_blacklisted, is_esn_company, matches_excluded_keyword
from app.services.storage.supabase_service import supabase_service


def test_get_settings_api(client, fake_db):
    res = client.get("/api/v1/settings")
    assert res.status_code == 200
    data = res.json()
    assert data["preferences"]["target_titles"] == ["Développeur Python"]
    assert data["preferences"]["excluded_companies"] == ["Thales"]
    assert "match_threshold_recommended" in data["preferences"]
    assert any(m["recommended"] for m in data["available_models"])


def test_get_settings_without_profile_returns_defaults(client):
    """Sans base : préférences par défaut, jamais d'erreur."""
    res = client.get("/api/v1/settings")
    assert res.status_code == 200
    assert res.json()["preferences"]["match_threshold_recommended"] == 75


def test_put_settings_api(client, fake_db):
    payload = {
        "preferences": {
            "ai_model": "gemini-2.5-pro",
            "ai_temperature": 0.3,
            "ai_custom_instructions": "Focus Cloud & Kubernetes",
            "excluded_companies": ["BadCompany"],
            "excluded_keywords": ["Stage"],
            "filter_esn": True,
            "match_threshold_recommended": 80,
        }
    }
    res = client.put("/api/v1/settings", json=payload)
    assert res.status_code == 200
    prefs = res.json()["preferences"]
    assert prefs["ai_model"] == "gemini-2.5-pro"
    assert prefs["ai_temperature"] == 0.3
    assert prefs["excluded_companies"] == ["BadCompany"]
    assert prefs["filter_esn"] is True
    # Persisté dans le profil actif
    assert fake_db["candidate_profiles"][0]["preferences"]["match_threshold_recommended"] == 80


def test_put_settings_without_profile(client):
    res = client.put("/api/v1/settings", json={"preferences": {"ai_temperature": 0.3}})
    assert res.status_code == 404


def test_blacklist_add_and_remove(client, fake_db):
    fake_db["jobs"].append({"id": "11111111-1111-1111-1111-111111111111", "company": "TestCorp France", "status": "QUALIFIED"})

    res_add = client.post("/api/v1/settings/blacklist", json={"company": "TestCorp"})
    assert res_add.status_code == 200
    data_add = res_add.json()
    assert "TestCorp" in data_add["excluded_companies"]
    assert "Thales" in data_add["excluded_companies"]
    assert data_add["retro_updated_jobs"] == 1
    assert fake_db["jobs"][0]["status"] == "BLACKLISTED"

    # Idempotent (insensible à la casse)
    assert client.post("/api/v1/settings/blacklist", json={"company": "testcorp"}).json()["excluded_companies"].count("TestCorp") == 1

    res_del = client.request("DELETE", "/api/v1/settings/blacklist", json={"company": "testcorp"})
    assert res_del.status_code == 200
    assert "TestCorp" not in res_del.json()["excluded_companies"]


def test_blacklist_add_validation(client, fake_db):
    assert client.post("/api/v1/settings/blacklist", json={"company": ""}).status_code == 422


def test_filters_company_blacklisted():
    excluded = ["Capgemini", "Societe Generale", "Alten"]
    assert is_company_blacklisted("Capgemini", excluded) is True
    assert is_company_blacklisted("capgemini", excluded) is True
    assert is_company_blacklisted("Capgemini France", excluded) is True
    assert is_company_blacklisted("Societe Generale", excluded) is True
    assert is_company_blacklisted("Doctolib", excluded) is False
    assert is_company_blacklisted(None, excluded) is False
    assert is_company_blacklisted("Google", []) is False


def test_filters_excluded_keywords():
    keywords = ["stage", "alternance", "wordpress", "php"]
    assert matches_excluded_keyword("Développeur Python (Stage)", keywords) == "stage"
    assert matches_excluded_keyword("Ingénieur Backend alternance", keywords) == "alternance"
    assert matches_excluded_keyword("Développeur WordPress", keywords) == "wordpress"
    assert matches_excluded_keyword("Ingénieur Logiciel Java", keywords) is None
    assert matches_excluded_keyword("Stagecraft Engineer", keywords) is None


def test_filters_is_esn():
    assert is_esn_company("Capgemini") is True
    assert is_esn_company("Sopra Steria") is True
    assert is_esn_company("Doctolib") is False


def test_collector_filters_blacklisted_and_keywords():
    fake_hits = [
        {"url": "https://wttj.com/job1", "title": "Dev Python", "company": "BannedCorp", "published_at": "2026-09-12T10:00:00Z"},
        {"url": "https://wttj.com/job2", "title": "Stage Développeur Java", "company": "GoodCorp", "published_at": "2026-09-12T10:00:00Z"},
    ]
    mock_profile = {
        "name": "John Doe",
        "profile": {"name": "John Doe", "personal": {"first_name": "John", "last_name": "Doe", "email": "john.doe@example.com"}},
        "preferences": {"excluded_companies": ["BannedCorp"], "excluded_keywords": ["Stage"]},
    }
    with patch.object(supabase_service, "get_active_candidate_profile", return_value=mock_profile), patch.object(
        job_collector_service, "search_wttj_recent_jobs", return_value=fake_hits
    ):
        summary = job_collector_service.run_collection(duration="24h", limit=5)
    assert summary["processed_count"] == 2
    assert summary["new_imported_count"] == 0
    statuses = [j["status"] for j in summary["jobs"]]
    assert "BLACKLISTED" in statuses
    assert "FILTERED_KEYWORD" in statuses


def test_import_and_process_url_blacklisted():
    mock_profile = {
        "id": "cand-123",
        "name": "John Doe",
        "profile": {"name": "John Doe", "personal": {"first_name": "John", "last_name": "Doe", "email": "john.doe@example.com"}},
        "preferences": {"excluded_companies": ["BlacklistedEnterprise"]},
    }
    scraped_job = {"title": "Ingénieur Backend", "company": "BlacklistedEnterprise", "url": "https://linkedin.com/jobs/view/123", "description": "Super job", "source": "LINKEDIN"}
    with patch.object(supabase_service, "get_active_candidate_profile", return_value=mock_profile), patch(
        "app.services.ingestion.scraper.job_scraper.scrape", return_value=scraped_job
    ), patch("app.services.ingestion.importer.job_importer.import_job", return_value={"status": "CREATED", "job": scraped_job}):
        result = job_collector_service.import_and_process_url("https://linkedin.com/jobs/view/123")
    assert result["success"] is True
    assert result["status"] == "BLACKLISTED"
    assert "liste noire" in result["message"]


def test_dynamic_ai_model_and_temperature_resolution():
    mock_profile = {"preferences": {"ai_model": "gemini-2.5-pro", "ai_temperature": 0.45}}
    with patch.object(supabase_service, "get_active_candidate_profile", return_value=mock_profile):
        assert gemini_service.get_configured_model() == "gemini-2.5-pro"
        assert gemini_service.get_configured_temperature() == 0.45
    with patch.object(supabase_service, "get_active_candidate_profile", return_value=None):
        assert gemini_service.get_configured_model() == gemini_service.config.GEMINI_MODEL
        assert gemini_service.get_configured_temperature() == 0.2
