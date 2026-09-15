from unittest.mock import MagicMock

from app.services.storage.supabase_service import SupabaseService

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
    captured = {}

    def fake_paginated(**kwargs):
        captured.update(kwargs)
        return {
            "items": [{"id": "11111111-1111-1111-1111-111111111111", "title": "Lead Python", "company": "Acme", "location": "Paris", "contract_type": "CDI", "match_score": 88, "status": "QUALIFIED"}],
            "total": 21, "page": 2, "per_page": 10, "total_pages": 3, "has_prev": True, "has_next": True, "prev_page": 1, "next_page": 3,
        }

    monkeypatch.setattr("app.services.storage.supabase_service.get_jobs_paginated", fake_paginated)

    res = client.get("/api/v1/jobs?page=2&per_page=10&status=QUALIFIED&q=python&min_score=80&contract_type=CDI")
    assert res.status_code == 200
    data = res.json()
    assert data["page"] == 2 and data["total"] == 21 and data["total_pages"] == 3
    assert data["has_prev"] is True and data["has_next"] is True
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["title"] == "Lead Python"
    # Les filtres de la query string sont bien transmis au service (`q` → `search`)
    assert captured["page"] == 2 and captured["per_page"] == 10
    assert captured["status"] == "QUALIFIED" and captured["contract_type"] == "CDI"
    assert captured["min_score"] == 80 and captured["search"] == "python"


def test_jobs_routes_pagination_bounds(client):
    assert client.get("/api/v1/jobs?page=0").status_code == 422
    assert client.get("/api/v1/jobs?per_page=500").status_code == 422


def test_applications_routes_pagination_and_filters(client, monkeypatch):
    captured = {}

    def fake_paginated(**kwargs):
        captured.update(kwargs)
        return {
            "items": [{"id": "22222222-2222-2222-2222-222222222222", "job_id": "11111111-1111-1111-1111-111111111111", "status": "PREPARED", "match_score": 92,
                       "prepared_at": "2026-09-11T12:00:00+00:00", "jobs": {"id": "11111111-1111-1111-1111-111111111111", "title": "Staff Engineer", "company": "MetaTech"}}],
            "total": 15, "page": 1, "per_page": 10, "total_pages": 2, "has_prev": False, "has_next": True, "prev_page": None, "next_page": 2,
        }

    monkeypatch.setattr("app.services.storage.supabase_service.get_applications_paginated", fake_paginated)

    res = client.get("/api/v1/applications?page=1&per_page=10&status=PREPARED&min_score=80&q=staff")
    assert res.status_code == 200
    data = res.json()
    assert data["page"] == 1 and data["total"] == 15 and data["total_pages"] == 2
    assert len(data["applications"]) == 1
    assert data["applications"][0]["id"] == "22222222-2222-2222-2222-222222222222"
    # L'offre jointe est typée et conservée
    assert data["applications"][0]["jobs"]["title"] == "Staff Engineer"
    assert captured["status"] == "PREPARED" and captured["min_score"] == 80 and captured["search"] == "staff"
