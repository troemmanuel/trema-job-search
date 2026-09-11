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
            "name": "Emmanuel TRO",
            "personal": {
                "first_name": "Emmanuel",
                "last_name": "TRO",
                "email": "emmanuel@example.com",
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

def test_api_jobs_scrape_endpoint(monkeypatch):
    from app import create_app
    from app.config import Config

    class TestConfig(Config):
        TESTING = True
        DEBUG = False
        SUPABASE_URL = ""
        SUPABASE_KEY = ""

    flask_app = create_app(TestConfig)
    with flask_app.test_client() as test_client:
        # Test sans URL
        res_empty = test_client.post("/api/jobs/scrape", json={})
        assert res_empty.status_code == 400
        assert "requise" in res_empty.get_json()["error"]

        # Test avec URL valide mockée
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
                "notion_url": "https://app.notion.com/p/test123"
            }
        )

        res_valid = test_client.post("/api/jobs/scrape", json={
            "url": "https://www.welcometothejungle.com/fr/companies/airbus/jobs/lead-java",
            "auto_prepare": True,
            "min_match_score": 75
        })

        assert res_valid.status_code == 200
        data = res_valid.get_json()
        assert data["success"] is True
        assert data["score"] == 92
        assert data["status"] == "PREPARED"
        assert data["notion_url"] == "https://app.notion.com/p/test123"

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

def test_api_jobs_scrape_batch_endpoint(monkeypatch):
    from app import create_app
    from app.config import Config

    class TestConfig(Config):
        TESTING = True
        DEBUG = False
        SUPABASE_URL = ""
        SUPABASE_KEY = ""

    flask_app = create_app(TestConfig)
    with flask_app.test_client() as test_client:
        from app.services.ingestion.collector import job_collector_service

        monkeypatch.setattr(
            job_collector_service,
            "import_and_process_urls",
            lambda urls, auto_prepare, min_match_score: {
                "success": True,
                "is_batch": True,
                "total_requested": len(urls),
                "total_unique": len(urls),
                "processed_count": len(urls),
                "qualified_count": len(urls),
                "prepared_count": len(urls),
                "notion_synced_count": len(urls),
                "error_count": 0,
                "results": [
                    {"url": u, "success": True, "status": "PREPARED", "score": 90, "prepared": True}
                    for u in urls
                ]
            }
        )

        # 1. Test avec payload `urls: [...]`
        res_batch = test_client.post("/api/jobs/scrape", json={
            "urls": [
                "https://www.welcometothejungle.com/fr/companies/a/jobs/1",
                "https://www.linkedin.com/jobs/view/2/"
            ],
            "auto_prepare": True
        })

        assert res_batch.status_code == 200
        data_batch = res_batch.get_json()
        assert data_batch["is_batch"] is True
        assert data_batch["processed_count"] == 2
        assert len(data_batch["results"]) == 2

        # 2. Test avec payload multi-lignes dans `url: "url1\nurl2"`
        res_multiline = test_client.post("/api/jobs/scrape", json={
            "url": "https://www.welcometothejungle.com/fr/companies/a/jobs/1\nhttps://www.linkedin.com/jobs/view/2/",
            "auto_prepare": True
        })

        assert res_multiline.status_code == 200
        data_multiline = res_multiline.get_json()
        assert data_multiline["is_batch"] is True
        assert data_multiline["processed_count"] == 2

