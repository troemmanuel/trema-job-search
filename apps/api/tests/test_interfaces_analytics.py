from app.config import Config
from app.services.analytics.interfaces_analytics import InterfacesAnalyticsService


class TestConfig(Config):
    SUPABASE_URL = ""
    SUPABASE_KEY = ""

def test_interfaces_analytics_service_empty(monkeypatch):
    service = InterfacesAnalyticsService(TestConfig())
    monkeypatch.setattr(service, "_fetch_db_telemetry", lambda: {
        "ai_runs": [],
        "applications": [],
        "documents": [],
        "jobs": []
    })
    monkeypatch.setattr(service, "_fetch_router_stats", lambda: {
        "gemini": {"requests_count": 0, "success_count": 0, "errors_count": 0, "total_latency_seconds": 0.0, "total_tokens": 0},
        "groq": {"requests_count": 0, "success_count": 0, "errors_count": 0, "total_latency_seconds": 0.0, "total_tokens": 0},
        "mistral": {"requests_count": 0, "success_count": 0, "errors_count": 0, "total_latency_seconds": 0.0, "total_tokens": 0},
        "openrouter": {"requests_count": 0, "success_count": 0, "errors_count": 0, "total_latency_seconds": 0.0, "total_tokens": 0},
        "cache": {"hits": 0, "misses": 0, "hit_ratio_percent": 0.0, "size": 0, "total_saved_seconds": 0.0},
        "failover_count": 0,
        "recent_runs": []
    })

    res = service.get_interfaces_analytics()
    assert "kpis" in res
    assert "providers" in res
    assert len(res["providers"]) == 4
    assert "task_distribution" in res
    assert "external_connectors" in res
    assert "recent_runs" in res
    assert res["kpis"]["total_calls"] == 0
    assert res["kpis"]["failover_count"] == 0
    assert res["kpis"]["cache_hit_rate"] == 0.0

def test_interfaces_analytics_service_with_telemetry(monkeypatch):
    service = InterfacesAnalyticsService(TestConfig())

    mock_db_data = {
        "ai_runs": [
            {
                "id": "run-1",
                "operation": "job_scoring",
                "model": "gemini-3.6-flash",
                "status": "SUCCESS",
                "input_data": {"provider": "gemini", "latency": 1.8, "tokens": 950, "fallback_used": False},
                "created_at": "2026-09-14T22:00:00Z"
            },
            {
                "id": "run-2",
                "operation": "doc_content_generation",
                "model": "openai/gpt-oss-120b",
                "status": "SUCCESS",
                "input_data": {"provider": "groq", "latency": 0.55, "tokens": 1400, "fallback_used": True},
                "created_at": "2026-09-14T22:05:00Z"
            }
        ],
        "applications": [
            {"id": "app-1", "notion_page_id": "notion-123", "status": "APPLIED"},
            {"id": "app-2", "notion_page_id": None, "status": "PREPARED"},
        ],
        "documents": [
            {"id": "doc-1", "type": "CV", "storage_path": "resumes/cv_1.pdf"},
            {"id": "doc-2", "type": "COVER_LETTER", "storage_path": "letters/lettre_1.pdf"}
        ],
        "jobs": [
            {"id": "job-1", "status": "IGNORED", "match_score": None},
            {"id": "job-2", "status": "QUALIFIED", "match_score": 85},
            {"id": "job-3", "status": "IGNORED", "match_score": None},
            {"id": "job-4", "status": "QUALIFIED", "match_score": 78}
        ]
    }

    mock_router_stats = {
        "gemini": {"requests_count": 1, "success_count": 1, "errors_count": 0, "total_latency_seconds": 1.8, "total_tokens": 950, "last_used_at": "2026-09-14T22:00:00Z"},
        "groq": {"requests_count": 1, "success_count": 1, "errors_count": 0, "total_latency_seconds": 0.55, "total_tokens": 1400, "last_used_at": "2026-09-14T22:05:00Z"},
        "mistral": {"requests_count": 0, "success_count": 0, "errors_count": 0, "total_latency_seconds": 0.0, "total_tokens": 0, "last_used_at": None},
        "openrouter": {"requests_count": 0, "success_count": 0, "errors_count": 0, "total_latency_seconds": 0.0, "total_tokens": 0, "last_used_at": None},
        "cache": {"hits": 4, "misses": 2, "hit_ratio_percent": 66.7, "size": 6, "total_saved_seconds": 7.5},
        "failover_count": 1,
        "recent_runs": [
            {
                "id": "cache-abc12345",
                "timestamp": "2026-09-14T22:10:00Z",
                "operation": "job_scoring",
                "provider": "cache",
                "model": "SHA-256 Memory",
                "status": "CACHE_HIT",
                "latency": 0.0,
                "tokens": 0,
                "fallback_used": False,
                "error": None
            }
        ]
    }

    monkeypatch.setattr(service, "_fetch_db_telemetry", lambda: mock_db_data)
    monkeypatch.setattr(service, "_fetch_router_stats", lambda: mock_router_stats)

    res = service.get_interfaces_analytics()

    # KPIs globaux
    assert res["kpis"]["total_calls"] >= 2
    assert res["kpis"]["failover_count"] == 1
    assert res["kpis"]["cache_hit_rate"] == 66.7
    assert res["kpis"]["cache_hits"] == 4
    assert res["kpis"]["heuristic_shield_count"] == 2

    # Providers
    providers_map = {p["id"]: p for p in res["providers"]}
    assert "gemini" in providers_map
    assert "groq" in providers_map
    assert providers_map["gemini"]["requests_count"] == 1
    assert providers_map["groq"]["requests_count"] == 1

    # Connecteurs externes
    assert res["external_connectors"]["notion"]["synced_count"] == 1
    assert res["external_connectors"]["notion"]["total_applications"] == 2
    assert res["external_connectors"]["notion"]["sync_rate_percent"] == 50.0

    assert res["external_connectors"]["supabase_storage"]["total_documents"] == 2
    assert res["external_connectors"]["supabase_storage"]["cv_count"] == 1
    assert res["external_connectors"]["supabase_storage"]["letter_count"] == 1

    assert res["external_connectors"]["scraper_shield"]["heuristic_filtered"] == 2
    assert res["external_connectors"]["scraper_shield"]["quota_saved_percent"] == 50.0

    # Exécutions récentes
    assert len(res["recent_runs"]) >= 3
    statuses = [r["status"] for r in res["recent_runs"]]
    assert "CACHE_HIT" in statuses
    assert "FALLBACK" in statuses

def test_api_analytics_interfaces_endpoint(client, monkeypatch):
    from app.services.analytics import interfaces_analytics_service

    mock_data = {
        "timestamp": "2026-09-14T22:30:00Z",
        "kpis": {
            "total_calls": 12,
            "global_success_rate": 91.7,
            "avg_latency_ms": 780,
            "total_tokens": 15400,
            "cache_hit_rate": 40.0,
            "cache_hits": 8,
            "cache_saved_seconds": 12.4,
            "failover_count": 2,
            "heuristic_shield_count": 15,
            "notion_sync_count": 6
        },
        "providers": [
            {"id": "gemini", "name": "Google Gemini", "status": "OPÉRATIONNEL", "requests_count": 8, "success_count": 7, "errors_count": 1, "success_rate": 87.5, "avg_latency_ms": 1850, "total_tokens": 8000, "default_model": "gemini-3.6-flash", "is_configured": True, "icon": "✨", "color": "#3b82f6", "description": "Test Gemini", "last_used_at": None, "last_error": None, "benchmark_latency_ms": 1950},
            {"id": "groq", "name": "Groq Cloud (LPU)", "status": "OPÉRATIONNEL", "requests_count": 4, "success_count": 4, "errors_count": 0, "success_rate": 100.0, "avg_latency_ms": 580, "total_tokens": 7400, "default_model": "openai/gpt-oss-120b", "is_configured": True, "icon": "⚡", "color": "#f59e0b", "description": "Test Groq", "last_used_at": None, "last_error": None, "benchmark_latency_ms": 580},
        ],
        "task_distribution": {"counts": {"job_scoring": 8, "doc_content_generation": 4, "other": 0}, "total": 12, "percentages": {"job_scoring": 66.7, "doc_content_generation": 33.3, "other": 0.0}},
        "external_connectors": {
            "notion": {"configured": True, "synced_count": 6, "total_applications": 8, "sync_rate_percent": 75.0, "status": "Opérationnel"},
            "supabase_storage": {"connected": True, "total_documents": 8, "cv_count": 4, "letter_count": 4, "answers_count": 0, "buckets": ["resumes", "letters"]},
            "scraper_shield": {"total_jobs": 30, "heuristic_filtered": 15, "llm_scored": 15, "quota_saved_percent": 50.0, "estimated_tokens_saved": 18000}
        },
        "cache": {"hits": 8, "misses": 12, "hit_ratio_percent": 40.0, "size": 20, "total_saved_seconds": 12.4},
        "recent_runs": [
            {"id": "run-001", "timestamp": "14/09 22:25:10", "operation": "JOB_SCORING", "provider": "gemini", "model": "gemini-3.6-flash", "status": "SUCCESS", "latency_ms": 1820, "tokens": 950, "fallback_used": False, "error_message": None}
        ]
    }

    monkeypatch.setattr(interfaces_analytics_service, "get_interfaces_analytics", lambda: mock_data)

    res = client.get("/api/v1/analytics/interfaces")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["kpis"]["total_calls"] == 12
    assert data["kpis"]["failover_count"] == 2
    assert len(data["providers"]) == 2
    assert data["external_connectors"]["notion"]["synced_count"] == 6
    assert data["task_distribution"]["total"] == 12


def test_api_analytics_interfaces_endpoint_without_telemetry(client):
    """Sans base : structure complète, compteurs à zéro."""
    res = client.get("/api/v1/analytics/interfaces")
    assert res.status_code == 200
    data = res.json()
    assert data["task_distribution"]["total"] >= 0
    assert "scraper_shield" in data["external_connectors"]
    assert isinstance(data["recent_runs"], list)
