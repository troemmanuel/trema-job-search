import pytest
from unittest.mock import MagicMock
from app import create_app
from app.config import Config
from app.services.storage.supabase_service import SupabaseService

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

def test_get_jobs_paginated_unit(monkeypatch):
    service = SupabaseService()
    # Mock client and chained PostgREST calls
    mock_client = MagicMock()
    monkeypatch.setattr(SupabaseService, "client", property(lambda self: mock_client))

    # Create dummy jobs
    mock_jobs = [
        {"id": f"job-{i}", "title": f"Dev {i}", "company": "Corp", "status": "QUALIFIED", "created_at": f"2026-09-0{i}T10:00:00"}
        for i in range(1, 6)
    ]

    mock_query = MagicMock()
    mock_client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.gte.return_value = mock_query
    mock_query.or_.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.range.return_value = mock_query

    mock_res = MagicMock()
    mock_res.data = mock_jobs
    mock_res.count = 25
    mock_query.execute.return_value = mock_res

    res = service.get_jobs_paginated(
        page=2,
        per_page=5,
        status="QUALIFIED",
        contract_type="CDI",
        min_score=75,
        search="python",
        order_by="created_at",
        desc=True
    )

    assert res["page"] == 2
    assert res["per_page"] == 5
    assert res["total"] == 25
    assert res["total_pages"] == 5
    assert res["has_prev"] is True
    assert res["has_next"] is True
    assert res["prev_page"] == 1
    assert res["next_page"] == 3
    assert len(res["items"]) == 5

    # Verify query chains
    mock_client.table.assert_called_with("jobs")
    mock_query.select.assert_called_with("*", count="exact")
    mock_query.eq.assert_any_call("status", "QUALIFIED")
    mock_query.eq.assert_any_call("contract_type", "CDI")
    mock_query.gte.assert_called_with("match_score", 75)
    mock_query.order.assert_called_with("created_at", desc=True)
    mock_query.range.assert_called_with(5, 9)

def test_get_applications_paginated_unit(monkeypatch):
    service = SupabaseService()
    mock_client = MagicMock()
    monkeypatch.setattr(SupabaseService, "client", property(lambda self: mock_client))

    mock_apps = [
        {
            "id": f"app-{i}",
            "status": "PREPARED",
            "match_score": 85,
            "created_at": f"2026-09-0{i}T10:00:00",
            "jobs": {"title": f"Engineer {i}", "company": "Tech"}
        }
        for i in range(1, 4)
    ]

    mock_query = MagicMock()
    mock_client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.gte.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.range.return_value = mock_query

    mock_res = MagicMock()
    mock_res.data = mock_apps
    mock_res.count = 12
    mock_query.execute.return_value = mock_res

    res = service.get_applications_paginated(
        page=1,
        per_page=3,
        status="PREPARED",
        min_score=80,
        order_by="created_at",
        desc=True
    )

    assert res["page"] == 1
    assert res["per_page"] == 3
    assert res["total"] == 12
    assert res["total_pages"] == 4
    assert res["has_prev"] is False
    assert res["has_next"] is True
    assert res["next_page"] == 2
    assert len(res["items"]) == 3

    mock_client.table.assert_called_with("applications")
    mock_query.select.assert_called_with("*, jobs(*)", count="exact")
    mock_query.order.assert_called_with("created_at", desc=True)

def test_jobs_routes_pagination_and_filters(client, monkeypatch):
    mock_paginated = {
        "items": [
            {"id": "j1", "title": "Lead Python", "company": "Acme", "location": "Paris", "contract_type": "CDI", "match_score": 88, "status": "QUALIFIED"}
        ],
        "total": 21,
        "page": 2,
        "per_page": 10,
        "total_pages": 3,
        "has_prev": True,
        "has_next": True,
        "prev_page": 1,
        "next_page": 3
    }

    monkeypatch.setattr(
        "app.services.storage.supabase_service.get_jobs_paginated",
        lambda **kwargs: mock_paginated
    )

    # 1. API endpoint /api/jobs
    res = client.get("/api/jobs?page=2&per_page=10&status=QUALIFIED&q=python&min_score=80")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["page"] == 2
    assert json_data["total"] == 21
    assert json_data["total_pages"] == 3
    assert json_data["has_prev"] is True
    assert json_data["has_next"] is True
    assert len(json_data["jobs"]) == 1
    assert json_data["jobs"][0]["title"] == "Lead Python"

    # 2. HTML page /jobs
    res_html = client.get("/jobs?page=2&q=python&status=QUALIFIED&contract_type=CDI&min_score=80")
    assert res_html.status_code == 200
    html_text = res_html.data.decode("utf-8")
    # Vérifier que le formulaire contient les valeurs de filtre
    assert 'value="python"' in html_text
    assert 'selected' in html_text
    # Vérifier que la table et le composant pagination sont bien rendus
    assert "Lead Python" in html_text
    assert "Affichage de" in html_text
    assert "sur <strong>21</strong> résultats" in html_text
    assert "pagination-btn" in html_text
    # Vérifier la présence des liens vers page 1 et page 3 avec conservation des filtres
    assert "page=1" in html_text
    assert "page=3" in html_text
    assert "q=python" in html_text

def test_applications_routes_pagination_and_filters(client, monkeypatch):
    mock_paginated = {
        "items": [
            {
                "id": "app-42",
                "status": "PREPARED",
                "match_score": 92,
                "prepared_at": "2026-09-11 12:00",
                "jobs": {"title": "Staff Engineer", "company": "MetaTech"}
            }
        ],
        "total": 15,
        "page": 1,
        "per_page": 10,
        "total_pages": 2,
        "has_prev": False,
        "has_next": True,
        "prev_page": None,
        "next_page": 2
    }

    monkeypatch.setattr(
        "app.services.storage.supabase_service.get_applications_paginated",
        lambda **kwargs: mock_paginated
    )

    # 1. API endpoint /api/applications
    res = client.get("/api/applications?page=1&per_page=10&status=PREPARED&min_score=80")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["page"] == 1
    assert json_data["total"] == 15
    assert json_data["total_pages"] == 2
    assert len(json_data["applications"]) == 1
    assert json_data["applications"][0]["id"] == "app-42"

    # 2. HTML page /applications
    res_html = client.get("/applications?page=1&status=PREPARED&min_score=80")
    assert res_html.status_code == 200
    html_text = res_html.data.decode("utf-8")
    assert "Staff Engineer" in html_text
    assert "MetaTech" in html_text
    assert "Affichage de" in html_text
    assert "sur <strong>15</strong> résultats" in html_text
    assert "page=2" in html_text
