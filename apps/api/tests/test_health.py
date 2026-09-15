import pytest
from app import create_app
from app.config import Config
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobImport

class TestConfig(Config):
    TESTING = True
    DEBUG = False

@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.test_client() as client:
        yield client

def test_health_endpoint(client):
    """Vérifie que l'endpoint /health répond avec 200 et status: ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "services" in data

def test_dashboard_index(client):
    """Vérifie que le dashboard d'accueil se charge correctement en HTML avec la carte du planificateur."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Tableau de bord".encode("utf-8") in response.data
    assert "Planificateur Quotidien (Cron 24h)".encode("utf-8") in response.data
    assert "schedulerCard".encode("utf-8") in response.data

def test_candidate_schema_validation():
    """Valide la désérialisation d'un profil candidat maître via Pydantic."""
    raw_profile = {
        "name": "Jean Dupont",
        "personal": {
            "first_name": "Jean",
            "last_name": "Dupont",
            "email": "jean@example.com",
            "location": "Bordeaux"
        },
        "summary": "Product Manager expérimenté",
        "experiences": [
            {
                "id": "exp_001",
                "company": "Tech Corp",
                "role": "Product Manager",
                "start_date": "2022-01",
                "skills": ["Python", "SQL"]
            }
        ],
        "preferences": {
            "target_titles": ["Product Manager"],
            "locations": ["Bordeaux"],
            "remote": True
        }
    }
    profile = CandidateProfile.model_validate(raw_profile)
    assert profile.name == "Jean Dupont"
    assert profile.personal.email == "jean@example.com"
    assert len(profile.experiences) == 1
    assert profile.preferences.remote is True

def test_job_import_schema():
    """Valide l'import d'une offre d'emploi via Pydantic."""
    raw_job = {
        "source": "WTTJ",
        "source_job_id": "job-12345",
        "title": "Lead Product Manager",
        "company": "Startup X",
        "location": "Bordeaux",
        "url": "https://example.com/jobs/12345",
        "description": "Nous recherchons un PM avec compétences Python et SQL."
    }
    job = JobImport.model_validate(raw_job)
    assert job.source == "WTTJ"
    assert job.title == "Lead Product Manager"
