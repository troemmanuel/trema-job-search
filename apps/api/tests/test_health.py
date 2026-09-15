from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobImport


def test_health_endpoint(client):
    """Vérifie que /health et /api/v1/health répondent 200 avec status: ok et l'état des services."""
    for path in ("/health", "/api/v1/health"):
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert data["services"]["supabase"] == "unconfigured"  # isolé par conftest


def test_root_info(client):
    """La racine expose les liens vers la documentation et le schéma OpenAPI."""
    data = client.get("/").json()
    assert data["docs"] == "/docs"
    assert data["openapi"] == "/openapi.json"


def test_dashboard_stats_without_supabase(client):
    """Sans base configurée, le dashboard renvoie des compteurs à zéro et des listes vides (pas d'erreur)."""
    response = client.get("/api/v1/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["stats"]["priority_count"] == 0
    assert data["recent_jobs"] == []
    assert data["recent_applications"] == []
    assert "scheduler_status" in data

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
