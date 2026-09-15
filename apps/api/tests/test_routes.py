"""Routes v1 : offres, candidatures et profil candidat (avec base en mémoire pour les écritures)."""
import uuid

JOB_ID = "11111111-1111-1111-1111-111111111111"
APP_ID = "22222222-2222-2222-2222-222222222222"


def _job(**overrides):
    job = {"id": JOB_ID, "source": "WTTJ", "title": "Product Owner", "company": "Company A", "url": "https://example.com/jobs/1", "status": "QUALIFIED", "match_score": 82}
    job.update(overrides)
    return job


# ---------------------------------------------------------------------------
# Offres
# ---------------------------------------------------------------------------

def test_jobs_list_and_import_without_supabase(client):
    res = client.get("/api/v1/jobs")
    assert res.status_code == 200
    assert res.json()["jobs"] == [] and res.json()["total"] == 0

    payload = {
        "source": "WTTJ",
        "source_job_id": "test-123",
        "title": "Product Owner",
        "company": "Company A",
        "url": "https://example.com/jobs/test-123?utm_campaign=tracker",
        "description": "Poste en CDI à Bordeaux, compétences Python et SQL requises.",
    }
    res_import = client.post("/api/v1/jobs/import", json=payload)
    assert res_import.status_code == 200
    data = res_import.json()
    assert data["status"] == "SIMULATED"  # pas de base : l'offre est normalisée mais non persistée
    assert data["job"]["title"] == "Product Owner"
    assert data["job"]["normalized_data"]["contract_type"] == "CDI"

    # Corps invalide : 422 (source/title/url requis)
    assert client.post("/api/v1/jobs/import", json={"title": "Sans source"}).status_code == 422


def test_job_detail_with_linked_application(client, fake_db):
    fake_db["jobs"].append(_job())
    fake_db["applications"].append({"id": APP_ID, "job_id": JOB_ID, "status": "PREPARED"})

    res = client.get(f"/api/v1/jobs/{JOB_ID}")
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Product Owner"
    assert data["application"]["id"] == APP_ID
    assert data["application"]["status"] == "PREPARED"

    assert client.get(f"/api/v1/jobs/{uuid.uuid4()}").status_code == 404
    assert client.get("/api/v1/jobs/pas-un-uuid").status_code == 422


def test_job_match_requires_profile_and_ai(client, fake_db, monkeypatch):
    from app.services.ai.matcher import matcher_service
    from app.schemas.match import MatchDimensions, MatchResult

    fake_db["jobs"].append(_job(normalized_data={"title": "Product Owner", "skills": ["Python"]}))
    dims = MatchDimensions(title_match=90, skills_match=80, experience_match=85, seniority_match=80, location_match=70, salary_match=60)
    monkeypatch.setattr(
        matcher_service, "match", lambda profile, job: MatchResult(score=84, level="HIGH", dimensions=dims, recommendation="APPLY", matched_skills=["Python"])
    )
    res = client.post(f"/api/v1/jobs/{JOB_ID}/match")
    assert res.status_code == 200
    assert res.json()["match"]["score"] == 84
    assert fake_db["jobs"][0]["status"] == "QUALIFIED"
    assert fake_db["jobs"][0]["match_score"] == 84

    # Échec du LLM : 500 explicite
    monkeypatch.setattr(matcher_service, "match", lambda profile, job: None)
    assert client.post(f"/api/v1/jobs/{JOB_ID}/match").status_code == 500


# ---------------------------------------------------------------------------
# Candidatures
# ---------------------------------------------------------------------------

def test_applications_list_without_supabase(client):
    res = client.get("/api/v1/applications")
    assert res.status_code == 200
    assert res.json()["applications"] == []


def test_create_application_from_job_is_idempotent(client, fake_db):
    fake_db["jobs"].append(_job())

    res = client.post(f"/api/v1/applications/create-from-job/{JOB_ID}")
    assert res.status_code == 200
    assert res.json()["message"] == "Candidature créée"
    created_id = res.json()["application_id"]
    assert fake_db["applications"][0]["status"] == "QUALIFIED"
    assert fake_db["applications"][0]["match_score"] == 82

    res_again = client.post(f"/api/v1/applications/create-from-job/{JOB_ID}")
    assert res_again.json()["message"] == "Candidature existante"
    assert res_again.json()["application_id"] == created_id
    assert len(fake_db["applications"]) == 1


def test_application_detail_and_documents(client, fake_db):
    fake_db["jobs"].append(_job())
    fake_db["applications"].append({"id": APP_ID, "job_id": JOB_ID, "status": "QUALIFIED", "tailored_cv": None, "cover_letter": None})

    res = client.get(f"/api/v1/applications/{APP_ID}")
    assert res.status_code == 200
    assert res.json()["jobs"]["company"] == "Company A"

    # Documents non générés : 404 explicites ; type inconnu : 422
    assert client.get(f"/api/v1/applications/{APP_ID}/documents/CV").status_code == 404
    assert client.get(f"/api/v1/applications/{APP_ID}/documents/COVER_LETTER").status_code == 404
    assert client.get(f"/api/v1/applications/{APP_ID}/documents/invalid").status_code == 422
    assert client.get(f"/api/v1/applications/{uuid.uuid4()}/documents/CV").status_code == 404


def test_application_pdf_generation(client, fake_db):
    """La lettre est rendue en PDF (ReportLab) à partir du profil et du texte généré."""
    fake_db["jobs"].append(_job())
    fake_db["applications"].append({"id": APP_ID, "job_id": JOB_ID, "status": "PREPARED", "cover_letter": "Madame, Monsieur,\n\nJe candidate.\n\nCordialement", "prepared_at": "2026-09-15T10:00:00+00:00"})

    res = client.get(f"/api/v1/applications/{APP_ID}/documents/COVER_LETTER")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"].startswith("inline;")
    assert res.content.startswith(b"%PDF")

    res_dl = client.get(f"/api/v1/applications/{APP_ID}/documents/COVER_LETTER?download=true")
    assert res_dl.headers["content-disposition"].startswith("attachment;")


# ---------------------------------------------------------------------------
# Profil candidat
# ---------------------------------------------------------------------------

def test_candidate_profile_roundtrip(client, fake_db):
    res = client.get("/api/v1/candidate/profile")
    assert res.status_code == 200
    assert res.json()["profile"]["name"] == "John Doe"
    assert res.json()["version"] == 1

    profile = res.json()["profile"]
    profile["title"] = "Lead Backend"
    profile["experiences"] = [{"id": "exp_001", "company": "Acme", "role": "Dev", "start_date": "2024-01", "achievements": ["Livré X"], "skills": ["Python"]}]
    res_put = client.put("/api/v1/candidate/profile", json={"profile": profile})
    assert res_put.status_code == 200
    saved = fake_db["candidate_profiles"][0]
    assert saved["profile"]["title"] == "Lead Backend"
    assert saved["profile"]["experiences"][0]["company"] == "Acme"
    # Les préférences ne sont pas touchées quand elles ne sont pas envoyées
    assert saved["preferences"]["excluded_companies"] == ["Thales"]

    # Profil invalide (personal requis) : 422
    assert client.put("/api/v1/candidate/profile", json={"profile": {"name": "X"}}).status_code == 422


def test_candidate_profile_without_supabase(client):
    assert client.get("/api/v1/candidate/profile").status_code == 503


def test_transcribe_markdown_cv(client, fake_db, monkeypatch):
    from app.schemas.candidate import CandidatePreferences, CandidateProfile, PersonalInfo

    mock_profile = CandidateProfile(
        name="Jean Dupont",
        personal=PersonalInfo(first_name="Jean", last_name="Dupont", email="jean@example.com"),
        preferences=CandidatePreferences(target_titles=["Product Manager"]),
    )
    monkeypatch.setattr("app.services.ai.cv_transcriber.cv_transcriber_service.transcribe_markdown", lambda md: mock_profile)

    assert client.post("/api/v1/candidate/transcribe", json={"markdown": ""}).status_code == 422

    res = client.post("/api/v1/candidate/transcribe", json={"markdown": "# Jean Dupont\nProduct Manager"})
    assert res.status_code == 200
    data = res.json()
    assert data["profile"]["name"] == "Jean Dupont"
    assert data["profile"]["version"] == 2
    # Les préférences existantes sont conservées, pas celles du CV transcrit
    assert data["profile"]["preferences"]["excluded_companies"] == ["Thales"]

    monkeypatch.setattr("app.services.ai.cv_transcriber.cv_transcriber_service.transcribe_markdown", lambda md: None)
    assert client.post("/api/v1/candidate/transcribe", json={"markdown": "# Vide"}).status_code == 502
