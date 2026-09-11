import pytest
from unittest.mock import MagicMock
from app import create_app
from app.config import Config
from app.services.analytics import AnalyticsService

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

def test_analytics_service_empty_data(monkeypatch):
    service = AnalyticsService()
    monkeypatch.setattr(service, "_fetch_raw_data", lambda: ([], []))

    res = service.get_analytics()
    assert res["total_jobs"] == 0
    assert res["total_applications"] == 0
    assert res["funnel"]["counts"]["detected"] == 0
    assert res["funnel"]["rates"]["qualification_rate"] == 0.0
    assert res["funnel"]["rates"]["interview_rate"] == 0.0
    assert res["kpis"]["avg_match_score"] == 0.0
    assert len(res["tech_performance"]) > 0

def test_analytics_service_funnel_calculations(monkeypatch):
    service = AnalyticsService()

    # 10 offres : 8 qualifiées (score >= 75), 2 en dessous
    mock_jobs = [
        {"id": f"job_{i}", "match_score": 85 if i < 8 else 60, "status": "QUALIFIED" if i < 8 else "REVIEW", "normalized_data": {"skills": ["Python"]}}
        for i in range(10)
    ]

    # 4 applications : 1 PREPARED, 1 APPLIED, 1 INTERVIEW_HR, 1 OFFER
    mock_apps = [
        {"id": "app_1", "job_id": "job_0", "status": "PREPARED"},
        {"id": "app_2", "job_id": "job_1", "status": "APPLIED"},
        {"id": "app_3", "job_id": "job_2", "status": "INTERVIEW_HR"},
        {"id": "app_4", "job_id": "job_3", "status": "OFFER"},
    ]

    monkeypatch.setattr(service, "_fetch_raw_data", lambda: (mock_jobs, mock_apps))

    res = service.get_analytics()
    counts = res["funnel"]["counts"]
    rates = res["funnel"]["rates"]

    assert counts["detected"] == 10
    assert counts["qualified"] == 8
    assert counts["prepared"] == 4
    assert counts["applied"] == 3  # APPLIED, INTERVIEW_HR, OFFER
    assert counts["interview"] == 2  # INTERVIEW_HR, OFFER
    assert counts["offer"] == 1

    # Taux
    assert rates["qualification_rate"] == 80.0  # 8 / 10
    assert rates["preparation_rate"] == 50.0   # 4 / 8
    assert rates["application_rate"] == 75.0   # 3 / 4
    assert rates["interview_rate"] == 66.7     # 2 / 3
    assert rates["offer_rate"] == 50.0         # 1 / 2
    assert rates["global_conversion_rate"] == 20.0  # 2 / 10

def test_analytics_service_tech_aggregation(monkeypatch):
    service = AnalyticsService()

    mock_jobs = [
        {"id": "j1", "match_score": 90, "title": "Dev Go Backend", "normalized_data": {"skills": ["Go", "Docker"]}},
        {"id": "j2", "match_score": 80, "title": "Lead Go Cloud", "normalized_data": {"skills": ["Golang", "Kubernetes"]}},
        {"id": "j3", "match_score": 70, "title": "Dev Python", "normalized_data": {"skills": ["Python", "FastAPI"]}},
    ]
    mock_apps = [
        {"id": "a1", "job_id": "j1", "status": "APPLIED"},
        {"id": "a2", "job_id": "j2", "status": "INTERVIEW_TECH"},
    ]

    monkeypatch.setattr(service, "_fetch_raw_data", lambda: (mock_jobs, mock_apps))

    res = service.get_analytics()
    techs = {t["tech"]: t for t in res["tech_performance"]}

    assert "Go / Golang" in techs
    assert techs["Go / Golang"]["job_count"] == 2
    assert techs["Go / Golang"]["avg_score"] == 85.0
    assert techs["Go / Golang"]["applied_count"] == 2
    assert techs["Go / Golang"]["interview_count"] == 1

    assert "Python / FastAPI" in techs
    assert techs["Python / FastAPI"]["job_count"] == 1
    assert techs["Python / FastAPI"]["avg_score"] == 70.0

def test_analytics_service_geography_and_workplace(monkeypatch):
    service = AnalyticsService()

    mock_jobs = [
        {"id": "j1", "location": "Paris (75001)", "description": "Télétravail partiel 2 jours/semaine", "normalized_data": {"remote": True}},
        {"id": "j2", "location": "Cesson-Sévigné, Rennes Métropole", "description": "Full remote possible 100% télétravail", "normalized_data": {"remote": True}},
        {"id": "j3", "location": "Nantes", "description": "Sur site au siège", "normalized_data": {"remote": False}},
    ]

    monkeypatch.setattr(service, "_fetch_raw_data", lambda: (mock_jobs, []))

    res = service.get_analytics()
    geo = res["geography"]
    wp = res["workplace"]

    assert geo["Paris & Île-de-France"] == 1
    assert geo["Rennes & Bretagne"] == 1
    assert geo["Nantes & Pays de la Loire"] == 1

    assert wp["Full Remote (100%)"] == 1
    assert wp["Hybride / Partiel"] == 1
    assert wp["Présentiel"] == 1

def test_api_analytics_stats_endpoint(client, monkeypatch):
    from app.services.analytics import analytics_service

    mock_analytics = {
        "period": "all",
        "total_jobs": 5,
        "total_applications": 2,
        "kpis": {"total_jobs": 5, "avg_match_score": 82.5},
        "funnel": {
            "counts": {"detected": 5, "qualified": 4, "prepared": 2, "applied": 2, "interview": 1, "offer": 0, "rejected": 0},
            "rates": {"qualification_rate": 80.0, "interview_rate": 50.0, "global_conversion_rate": 20.0}
        },
        "tech_performance": [],
        "geography": {},
        "workplace": {},
        "company_types": {},
        "timeline": {"labels": [], "jobs_series": [], "applications_series": []}
    }
    monkeypatch.setattr(analytics_service, "get_analytics", lambda period="all": mock_analytics)

    res = client.get("/api/analytics/stats")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["total_jobs"] == 5
    assert data["funnel"]["counts"]["qualified"] == 4

def test_analytics_html_view(client, monkeypatch):
    from app.services.analytics import analytics_service

    mock_analytics = {
        "period": "all",
        "total_jobs": 2,
        "total_applications": 1,
        "kpis": {"total_jobs": 2, "total_applications": 1, "avg_match_score": 85.0},
        "funnel": {
            "counts": {"detected": 2, "qualified": 2, "prepared": 1, "applied": 1, "interview": 0, "offer": 0, "rejected": 0},
            "rates": {"qualification_rate": 100.0, "preparation_rate": 50.0, "application_rate": 100.0, "interview_rate": 0.0, "offer_rate": 0.0, "global_conversion_rate": 0.0}
        },
        "tech_performance": [{"tech": "Go / Golang", "job_count": 1, "avg_score": 90.0, "applied_count": 1, "interview_count": 0}],
        "geography": {"Paris & Île-de-France": 1},
        "workplace": {"Hybride / Partiel": 1},
        "company_types": {"Grand groupe": 1},
        "timeline": {"labels": ["11/09"], "jobs_series": [1], "applications_series": [1]}
    }
    monkeypatch.setattr(analytics_service, "get_analytics", lambda period="all": mock_analytics)

    res = client.get("/analytics")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Entonnoir de Conversion" in html
    assert "Performance par Technologie" in html
    assert "Go / Golang" in html
