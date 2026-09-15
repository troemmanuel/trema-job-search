import pytest
from bs4 import BeautifulSoup
from app.services.ingestion.scraper import clean_url, JobScraper
from app.services.ingestion.collector import JobCollectorService

def test_clean_url():
    # Test suppression des paramètres de tracking
    dirty_wttj = "https://www.welcometothejungle.com/fr/companies/corp/jobs/dev?utm_source=newsletter&utm_medium=email&trackingId=abc#section"
    assert clean_url(dirty_wttj) == "https://www.welcometothejungle.com/fr/companies/corp/jobs/dev"

    # Test normalisation d'URL LinkedIn
    dirty_linkedin = "https://www.linkedin.com/jobs/view/4165261775/?eBP=CwEAAAGWd&refId=kP9&trackingId=xyz"
    assert clean_url(dirty_linkedin) == "https://www.linkedin.com/jobs/view/4165261775/"

    # Test URL propre reste inchangée
    clean_url_test = "https://jobs.lever.co/company/job-id-123"
    assert clean_url(clean_url_test) == "https://jobs.lever.co/company/job-id-123"

def test_extract_from_meta_tags():
    scraper = JobScraper()
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta property="og:title" content="Développeur Go & Kubernetes - PayFit" />
        <meta property="og:description" content="PayFit recrute un développeur Go senior pour son équipe Core Banking." />
        <meta name="author" content="PayFit" />
    </head>
    <body>
        <main>
            <p>Rejoignez notre équipe en CDI à Paris ou Full Remote.</p>
        </main>
    </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    data = scraper.extract_from_meta_tags(soup, "https://payfit.jobs/dev-go")

    assert data is not None
    assert "Développeur Go & Kubernetes" in data["title"]
    assert "PayFit" in (data["company"] or "")
    assert "PayFit recrute" in data["description"]
    assert data["source"] == "PAYFIT"

def test_import_and_process_url_orchestration(monkeypatch):
    collector = JobCollectorService()

    # Mock job_scraper.scrape
    mock_scraped = {
        "title": "Ingénieur Backend Go / Python",
        "company": "Qonto",
        "location": "Paris, France",
        "contract_type": "CDI",
        "description": "Développement d'APIs financières en Go et Python. PostgreSQL, Docker, AWS.",
        "url": "https://www.linkedin.com/jobs/view/123456/",
        "source": "LINKEDIN"
    }
    monkeypatch.setattr("app.services.ingestion.scraper.job_scraper.scrape", lambda url: mock_scraped)

    # Mock supabase_service
    from app.services.storage import supabase_service
    mock_profile = {
        "id": "profile_active_1",
        "profile": {
            "name": "John Doe",
            "personal": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "location": "Rennes, France"
            },
            "summary": "Ingénieur Logiciel Backend",
            "experiences": [],
            "skills": {
                "technical": ["Go", "Python", "Docker", "PostgreSQL", "AWS"],
                "tools": ["Git", "CI/CD"]
            }
        },
        "preferences": {
            "target_titles": ["Ingénieur Backend", "Développeur Go"],
            "contract_types": ["CDI"]
        }
    }
    monkeypatch.setattr(supabase_service, "get_active_candidate_profile", lambda: mock_profile)
    monkeypatch.setattr(type(supabase_service), "client", property(lambda self: None))  # Mode sans DB live pour test unitaire

    # Mock matcher_service
    from app.services.ai.matcher import matcher_service
    from app.schemas.match import MatchResult, MatchDimensions
    mock_match = MatchResult(
        score=88,
        level="HIGH",
        recommendation="APPLY",
        dimensions=MatchDimensions(
            title_match=90,
            skills_match=85,
            experience_match=80,
            seniority_match=90,
            location_match=95,
            salary_match=85
        ),
        matched_skills=["Go", "Python", "AWS"],
        missing_skills=[],
        strengths=["Maîtrise de Go et Python", "Expérience AWS"],
        concerns=[]
    )
    monkeypatch.setattr(matcher_service, "match", lambda profile, job: mock_match)

    # Mock generators
    from app.services.ai.cv_generator import cv_generator_service
    from app.services.ai.letter_generator import letter_generator_service
    from app.services.ai.answer_generator import answer_generator_service
    from app.schemas.application import TailoredCV, CoverLetter, ApplicationAnswers

    mock_cv = TailoredCV(
        job_id="test_job",
        summary="Ingénieur Go & Python ciblé",
        skills=["Go", "Python", "AWS"],
        selected_experiences=[]
    )
    monkeypatch.setattr(cv_generator_service, "generate", lambda **kwargs: mock_cv)
    monkeypatch.setattr(letter_generator_service, "generate", lambda **kwargs: CoverLetter(content="Bonjour, je postule avec enthousiasme..."))
    monkeypatch.setattr(answer_generator_service, "generate", lambda **kwargs: ApplicationAnswers(questions=[]))

    # Mock document_renderer
    from app.services.documents.renderer import document_renderer
    monkeypatch.setattr(document_renderer, "render_and_save_cv", lambda *args, **kwargs: "https://mock-storage/cv.pdf")
    monkeypatch.setattr(document_renderer, "render_and_save_letter", lambda *args, **kwargs: "https://mock-storage/letter.pdf")

    # Mock notion_service
    from app.services.notion.client import notion_service
    monkeypatch.setattr(notion_service, "sync_application", lambda **kwargs: "page_notion_123")

    # Exécution
    res = collector.import_and_process_url("https://www.linkedin.com/jobs/view/123456/", auto_prepare=True, min_match_score=75)

    assert res["success"] is True
    assert res["status"] == "PREPARED"
    assert res["score"] == 88
    assert res["prepared"] is True
    assert res["cv_url"] == "https://mock-storage/cv.pdf"
    assert res["letter_url"] == "https://mock-storage/letter.pdf"
    assert res["notion_page_id"] == "page_notion_123"
    assert "https://app.notion.com/p/page_notion_123" in res["notion_url"]

def test_api_jobs_scrape_endpoint(client, monkeypatch):
    # Sans URL : 400
    res_empty = client.post("/api/v1/jobs/scrape", json={})
    assert res_empty.status_code == 400
    assert "requise" in res_empty.json()["detail"]

    from app.services.ingestion.collector import job_collector_service

    monkeypatch.setattr(
        job_collector_service,
        "import_and_process_url",
        lambda url, auto_prepare, min_match_score: {
            "success": True,
            "status": "PREPARED",
            "job": {"title": "Tech Lead Java", "company": "Airbus"},
            "score": 92,
            "prepared": True,
            "notion_url": "https://app.notion.com/p/test123",
        },
    )
    res_valid = client.post(
        "/api/v1/jobs/scrape",
        json={"url": "https://www.welcometothejungle.com/fr/companies/airbus/jobs/lead-java", "auto_prepare": True, "min_match_score": 75},
    )
    assert res_valid.status_code == 200
    data = res_valid.json()
    assert data["success"] is True
    assert data["score"] == 92
    assert data["status"] == "PREPARED"
    assert data["notion_url"] == "https://app.notion.com/p/test123"

    # Échec d'extraction : 400 avec le message du collecteur
    monkeypatch.setattr(job_collector_service, "import_and_process_url", lambda **kw: {"success": False, "error": "Page introuvable"})
    res_fail = client.post("/api/v1/jobs/scrape", json={"url": "https://example.com/404"})
    assert res_fail.status_code == 400
    assert res_fail.json()["detail"] == "Page introuvable"


def test_import_and_process_urls_batch(monkeypatch):
    collector = JobCollectorService()

    # Simuler import_and_process_url pour deux URLs (l'une réussit, l'autre échoue)
    def mock_import_single(url, auto_prepare, min_match_score):
        if "fail" in url:
            return {
                "success": False,
                "error": "Page 404 introuvable",
                "status": "ERROR"
            }
        return {
            "success": True,
            "status": "PREPARED",
            "job": {"title": "Dev Backend", "company": "Stripe", "url": url},
            "score": 85,
            "prepared": True,
            "notion_page_id": "notion_page_stripe",
            "notion_url": "https://app.notion.com/p/notion_page_stripe",
            "cv_url": "https://mock/cv.pdf"
        }

    monkeypatch.setattr(collector, "import_and_process_url", mock_import_single)

    urls = [
        "https://www.welcometothejungle.com/fr/companies/stripe/jobs/dev",
        "https://www.welcometothejungle.com/fr/companies/fail/jobs/old",
        "https://www.welcometothejungle.com/fr/companies/stripe/jobs/dev"  # Doublon volontaire dans le lot
    ]

    summary = collector.import_and_process_urls(urls, auto_prepare=True, min_match_score=75)

    assert summary["success"] is True
    assert summary["is_batch"] is True
    assert summary["total_requested"] == 3
    assert summary["total_unique"] == 2
    assert summary["processed_count"] == 2
    assert summary["qualified_count"] == 1
    assert summary["prepared_count"] == 1
    assert summary["notion_synced_count"] == 1
    assert summary["error_count"] == 1
    assert len(summary["results"]) == 2

def _fake_batch(urls, auto_prepare, min_match_score):
    return {
        "success": True,
        "is_batch": True,
        "total_requested": len(urls),
        "total_unique": len(urls),
        "processed_count": len(urls),
        "qualified_count": len(urls),
        "prepared_count": len(urls),
        "notion_synced_count": len(urls),
        "error_count": 0,
        "results": [{"url": u, "success": True, "status": "PREPARED", "score": 90, "prepared": True} for u in urls],
    }


def test_api_jobs_scrape_batch_endpoint(client, monkeypatch):
    from app.services.ingestion.collector import job_collector_service

    monkeypatch.setattr(job_collector_service, "import_and_process_urls", _fake_batch)

    # 1. Payload `urls: [...]`
    res_batch = client.post(
        "/api/v1/jobs/scrape",
        json={"urls": ["https://www.welcometothejungle.com/fr/companies/a/jobs/1", "https://www.linkedin.com/jobs/view/2/"], "auto_prepare": True},
    )
    assert res_batch.status_code == 200
    data_batch = res_batch.json()
    assert data_batch["is_batch"] is True
    assert data_batch["processed_count"] == 2
    assert len(data_batch["results"]) == 2

    # 2. Payload multi-lignes dans `url`
    res_multiline = client.post(
        "/api/v1/jobs/scrape",
        json={"url": "https://www.welcometothejungle.com/fr/companies/a/jobs/1\nhttps://www.linkedin.com/jobs/view/2/", "auto_prepare": True},
    )
    assert res_multiline.status_code == 200
    assert res_multiline.json()["is_batch"] is True
    assert res_multiline.json()["processed_count"] == 2


def test_api_jobs_scrape_stream_endpoint(client, monkeypatch):
    """Le flux SSE émet start → processing/item_done par URL → complete, chaque `data:` étant un JSON."""
    import json

    from app.services.ingestion.collector import job_collector_service

    def fake_single(url, auto_prepare, min_match_score):
        if "fail" in url:
            raise RuntimeError("Scraper KO")
        return {"success": True, "status": "QUALIFIED", "job": {"title": "Offre", "url": url}, "score": 80, "prepared": False}

    monkeypatch.setattr(job_collector_service, "import_and_process_url", fake_single)

    res = client.post("/api/v1/jobs/scrape/stream", json={"urls": ["https://a.example/1", "https://b.example/fail"]})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")

    events = [json.loads(line[len("data: "):]) for line in res.text.split("\n") if line.startswith("data: ")]
    types = [e["type"] for e in events]
    assert types == ["start", "processing", "item_done", "processing", "item_error", "complete"]
    assert events[0]["total"] == 2
    assert events[2]["result"]["job"]["title"] == "Offre"
    assert "Scraper KO" in events[4]["error"]


def test_wttj_api_extraction_builds_headers(monkeypatch):
    """Régression : l'appel API WTTJ référençait une constante USER_AGENT supprimée (NameError silencieux → fallback vide)."""
    import httpx
    from app.services.ingestion.scraper import JobScraper

    captured = {}

    class FakeResponse:
        status_code = 200
        def json(self):
            return {"job": {"name": "Dev Backend", "organization": {"name": "ACME"}, "slug": "dev-backend",
                            "office": {"city": "Paris"}, "contract_type": "full_time", "description": "<p>Python</p>"}}

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url, headers=None):
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    result = JobScraper.extract_from_wttj_api("https://www.welcometothejungle.com/fr/companies/acme/jobs/dev-backend")
    assert "Mozilla" in captured["headers"]["User-Agent"]
    assert result and result["company"] == "ACME" and result["title"] == "Dev Backend"


def test_gemini_fallback_rejects_empty_extraction(monkeypatch):
    """Une page anti-bot ne doit pas produire une offre squelette (« Offre d'emploi », sans entreprise)."""
    import pytest
    from bs4 import BeautifulSoup
    from app.schemas.job import JobNormalizedData
    from app.services.ingestion.scraper import JobScraper, gemini_service

    monkeypatch.setattr(gemini_service, "generate_structured",
                        lambda **k: JobNormalizedData(title="Offre d'emploi", company=None, location=None))
    with pytest.raises(ValueError, match="anti-bot"):
        JobScraper.extract_with_gemini_fallback(BeautifulSoup("<html><body>Access denied</body></html>", "html.parser"),
                                                "https://example.com/job")


def test_collector_enriches_incomplete_existing_job(monkeypatch):
    """Un doublon d'URL dont l'enregistrement est vide est remplacé par le scraping complet."""
    from app.services.ingestion.collector import JobCollectorService
    from app.services.storage import supabase_service

    updated = {}

    class FakeTable:
        def update(self, payload): updated.update(payload); return self
        def eq(self, *a): return self
        def execute(self):
            class R: data = [{"id": "job_1", **updated}]
            return R()

    class FakeClient:
        def table(self, name): return FakeTable()

    monkeypatch.setattr(type(supabase_service), "client", property(lambda self: FakeClient()))
    existing = {"id": "job_1", "title": "Offre d'emploi", "company": None, "url": "https://x.io/j/1"}
    scraped = {"title": "Dev Backend", "company": "ACME", "location": "Paris", "description": "Python", "url": "https://x.io/j/1"}
    job = JobCollectorService._enrich_incomplete_job(existing, scraped)
    assert job["title"] == "Dev Backend" and job["company"] == "ACME"
    assert updated["normalized_data"]["title"] == "Dev Backend"

    # Un enregistrement déjà complet n'est pas touché
    updated.clear()
    full = {"id": "job_2", "title": "Lead Dev", "company": "Beta"}
    assert JobCollectorService._enrich_incomplete_job(full, scraped) is full and not updated


def test_collector_skips_matching_and_reuses_existing_score(monkeypatch):
    """Vérifie qu'un doublon déjà évalué ne rappelle pas le service Gemini de matching."""
    from app.services.ingestion.collector import JobCollectorService
    from app.services.ingestion.scraper import job_scraper
    from app.services.ingestion.importer import job_importer
    from app.services.ai.matcher import matcher_service
    from app.services.storage import supabase_service

    collector = JobCollectorService()

    # Mock scraping & import retournant un doublon déjà scoré
    scraped = {
        "title": "Ingénieur Backend Python",
        "company": "FastTech",
        "location": "Paris",
        "url": "https://example.com/job-duplicate",
        "description": "Python, FastAPI"
    }
    monkeypatch.setattr(job_scraper, "scrape", lambda url: scraped)
    monkeypatch.setattr(job_importer, "import_job", lambda p: {
        "status": "DUPLICATE",
        "job": {
            "id": "job_duplicate_1",
            "title": "Ingénieur Backend Python",
            "company": "FastTech",
            "match_score": 85,
            "match_level": "RECOMMENDED",
            "match_analysis": {"score": 85, "level": "RECOMMENDED", "strengths": ["Python"]},
            "url": "https://example.com/job-duplicate"
        }
    })

    # Mock profil candidat
    mock_profile = {
        "id": "cand_1",
        "profile": {
            "name": "Test Candidate",
            "personal": {
                "first_name": "Test",
                "last_name": "Candidate",
                "email": "test@example.com",
                "location": "Paris"
            },
            "summary": "Backend engineer",
            "experiences": [],
            "skills": {"technical": ["Python"]}
        },
        "preferences": {"match_threshold_recommended": 75, "auto_prepare_documents": False}
    }
    monkeypatch.setattr(supabase_service, "get_active_candidate_profile", lambda: mock_profile)
    monkeypatch.setattr(type(supabase_service), "client", property(lambda self: None))

    # Vérifier que matcher_service.match n'est PAS appelé
    matcher_called = []
    monkeypatch.setattr(matcher_service, "match", lambda p, j: matcher_called.append(True))

    res = collector.import_and_process_url("https://example.com/job-duplicate", auto_prepare=False)

    assert res["success"] is True
    assert res["score"] == 85
    assert len(matcher_called) == 0, "matcher_service.match ne doit pas être appelé pour un doublon déjà scoré"


def test_collector_run_collection_skips_scraping_for_duplicates(monkeypatch):
    """Vérifie que run_collection ignore le scraping pour les offres déjà présentes en base."""
    from app.services.ingestion.collector import JobCollectorService
    from app.services.ingestion.scraper import job_scraper
    from app.services.ingestion.deduplicator import deduplicator
    from app.services.storage import supabase_service

    collector = JobCollectorService()

    fake_hits = [
        {"url": "https://wttj.com/already-imported", "title": "Dev Python", "company": "GoodCorp", "published_at": "2026-09-12T10:00:00Z", "source": "WTTJ", "source_job_id": "job_1"}
    ]
    monkeypatch.setattr(collector, "search_wttj_recent_jobs", lambda **k: fake_hits)

    # Profil candidat
    mock_profile = {
        "id": "cand_1",
        "profile": {
            "name": "Test Candidate",
            "personal": {"first_name": "Test", "last_name": "Candidate", "email": "test@example.com", "location": "Paris"},
            "summary": "Backend",
            "experiences": [],
            "skills": {"technical": ["Python"]}
        },
        "preferences": {
            "target_titles": ["Dev Python"],
            "contract_types": ["CDI"],
            "match_threshold_recommended": 75,
            "auto_prepare_documents": False
        }
    }
    monkeypatch.setattr(supabase_service, "get_active_candidate_profile", lambda: mock_profile)
    monkeypatch.setattr(type(supabase_service), "client", property(lambda self: None))

    # Simuler que l'offre est un doublon
    monkeypatch.setattr(deduplicator, "is_duplicate", lambda source, source_job_id, url: True)

    # Vérifier que scrape n'est JAMAIS appelé
    scrape_called = []
    monkeypatch.setattr(job_scraper, "scrape", lambda url: scrape_called.append(url))

    summary = collector.run_collection(duration="24h", limit=5)

    assert summary["processed_count"] == 1
    assert summary["new_imported_count"] == 0
    assert summary["jobs"][0]["status"] == "DUPLICATE_OR_EXISTING"
    assert len(scrape_called) == 0, "job_scraper.scrape ne doit pas être appelé pour une offre déjà existante"


def test_import_and_process_url_heuristic_rejection_skips_gemini(monkeypatch):
    """Vérifie qu'une offre incompatible (Stage pour souhait CDI) est rejetée déterministement sans appel Gemini."""
    from app.services.ingestion.collector import JobCollectorService
    from app.services.ingestion.scraper import job_scraper
    from app.services.ingestion.importer import job_importer
    from app.services.ai.matcher import matcher_service
    from app.services.storage import supabase_service

    collector = JobCollectorService()

    scraped = {
        "title": "Stage Développeur Python",
        "company": "StartupAI",
        "contract_type": "Stage",
        "location": "Paris",
        "url": "https://example.com/stage-python",
        "description": "Stage de fin d'études en Python."
    }
    monkeypatch.setattr(job_scraper, "scrape", lambda url: scraped)
    monkeypatch.setattr(job_importer, "import_job", lambda p: {"status": "CREATED", "job": scraped})

    mock_profile = {
        "id": "cand_1",
        "profile": {
            "name": "Test Candidate",
            "personal": {"first_name": "Test", "last_name": "Candidate", "email": "t@c.com", "location": "Paris"},
            "summary": "Backend engineer",
            "experiences": [],
            "skills": {"technical": ["Python"]}
        },
        "preferences": {
            "target_titles": ["Développeur Python"],
            "contract_types": ["CDI"],
            "match_threshold_recommended": 75,
            "auto_prepare_documents": False
        }
    }
    monkeypatch.setattr(supabase_service, "get_active_candidate_profile", lambda: mock_profile)
    monkeypatch.setattr(type(supabase_service), "client", property(lambda self: None))

    matcher_called = []
    monkeypatch.setattr(matcher_service, "match", lambda p, j: matcher_called.append(True))

    res = collector.import_and_process_url("https://example.com/stage-python")

    assert res["success"] is True
    assert res["status"] == "REVIEW"  # ou REJECTED selon le statut de fallback
    assert res["score"] == 20
    assert len(matcher_called) == 0, "matcher_service.match ne doit pas être appelé pour une offre rejetée par pré-filtre"
