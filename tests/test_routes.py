import pytest
from app import create_app
from app.config import Config

class TestConfig(Config):
    TESTING = True
    DEBUG = False
    SUPABASE_URL = ""
    SUPABASE_KEY = ""

@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.test_client() as client:
        yield client

def test_jobs_api_and_pages(client):
    # Test GET /api/jobs
    res = client.get("/api/jobs")
    assert res.status_code == 200
    assert "jobs" in res.get_json()

    # Test GET /jobs HTML page
    res_page = client.get("/jobs")
    assert res_page.status_code == 200
    assert b"Offres" in res_page.data

    # Test POST /api/jobs/import
    payload = {
        "source": "WTTJ",
        "source_job_id": "test-123",
        "title": "Product Owner",
        "company": "Company A",
        "url": "https://example.com/jobs/test-123?utm_campaign=tracker",
        "description": "Poste en CDI à Bordeaux, compétences Python et SQL requises."
    }
    res_import = client.post("/api/jobs/import", json=payload)
    assert res_import.status_code in [200, 201]
    data = res_import.get_json()
    assert data["status"] in ["CREATED", "SIMULATED", "DUPLICATE"]

def test_jobs_scrape_endpoint(client, monkeypatch):
    # Test sans URL
    res = client.post("/api/jobs/scrape", json={})
    assert res.status_code == 400

    # Test avec mock scraper
    mock_job_data = {
        "source": "WTTJ",
        "source_job_id": "scrape-123",
        "title": "Ingénieur Backend Cloud",
        "company": "Tech Corp",
        "location": "Paris",
        "contract_type": "CDI",
        "url": "https://example.com/jobs/scrape-123",
        "description": "Recherche dev backend python"
    }
    monkeypatch.setattr(
        "app.services.ingestion.scraper.job_scraper.scrape",
        lambda url: mock_job_data
    )
    res_scrape = client.post("/api/jobs/scrape", json={"url": "https://example.com/jobs/scrape-123", "auto_match": False})
    assert res_scrape.status_code in [200, 201]
    data = res_scrape.get_json()
    assert data["job"]["title"] == "Ingénieur Backend Cloud"

def test_applications_api_and_pages(client):
    # Test GET /api/applications
    res = client.get("/api/applications")
    assert res.status_code == 200
    assert "applications" in res.get_json()

    # Test GET /applications HTML page
    res_page = client.get("/applications")
    assert res_page.status_code == 200
    assert b"Candidatures" in res_page.data

    # Test GET download with invalid type
    res_down = client.get("/api/applications/non-existent-id/download/invalid")
    assert res_down.status_code in [404, 503]

def test_candidate_api_and_pages(client):
    # Test GET /candidate HTML page
    res_page = client.get("/candidate")
    assert res_page.status_code == 200
    assert b"Profil Ma" in res_page.data

    # Test POST /api/candidate
    candidate_data = {
        "name": "Jean Dupont",
        "personal": {
            "first_name": "Jean",
            "last_name": "Dupont",
            "email": "jean.dupont@example.com"
        },
        "preferences": {
            "target_titles": ["Product Manager"],
            "locations": ["Bordeaux", "Paris"],
            "remote": True
        }
    }
    res_post = client.post("/api/candidate", json=candidate_data)
    assert res_post.status_code == 200
    assert "profile" in res_post.get_json()

def test_upload_markdown_cv_empty(client):
    # Test avec contenu vide
    res = client.post("/api/candidate/upload-md", data={})
    assert res.status_code == 400
    assert "error" in res.get_json()

def test_upload_markdown_cv_with_mock(client, monkeypatch):
    from app.schemas.candidate import CandidateProfile, PersonalInfo, CandidatePreferences
    mock_profile = CandidateProfile(
        name="Jean Dupont",
        personal=PersonalInfo(first_name="Jean", last_name="Dupont", email="jean@example.com"),
        preferences=CandidatePreferences(target_titles=["Product Manager"])
    )
    # Mock transcriber
    monkeypatch.setattr(
        "app.services.ai.cv_transcriber.cv_transcriber_service.transcribe_markdown",
        lambda md: mock_profile
    )
    res = client.post("/api/candidate/upload-md", json={"markdown": "# Jean Dupont\nProduct Manager"})
    assert res.status_code == 200
    data = res.get_json()
    assert "profile" in data
    assert data["profile"]["name"] == "Jean Dupont"
