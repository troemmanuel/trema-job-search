import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from app import create_app
from app.config import Config
from app.services.notion.client import (
    SUPABASE_TO_NOTION_STATUS,
    NOTION_TO_SUPABASE_STATUS,
    NotionService,
)
from app.services.notion.sync import (
    NotionSyncService,
    parse_iso_datetime,
)
from app.services.storage.supabase_service import SupabaseService

class TestConfig(Config):
    TESTING = True
    DEBUG = False
    SUPABASE_URL = ""
    SUPABASE_KEY = ""
    NOTION_TOKEN = "fake-token"
    NOTION_DATABASE_ID = "fake-db-id"

@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.test_client() as client:
        yield client

def test_parse_iso_datetime():
    dt1 = parse_iso_datetime("2026-09-11T12:00:00Z")
    assert dt1 is not None
    assert dt1.tzinfo == timezone.utc

    dt2 = parse_iso_datetime("2026-09-11T14:30:00+02:00")
    assert dt2 is not None

    assert parse_iso_datetime(None) is None
    assert parse_iso_datetime("") is None
    assert parse_iso_datetime("invalid-date") is None

def test_bidirectional_status_mappings():
    # Notion -> Supabase
    assert NOTION_TO_SUPABASE_STATUS["Candidature prête - en attente de validation"] == "PREPARED"
    assert NOTION_TO_SUPABASE_STATUS["Candidature envoyée"] == "APPLIED"
    assert NOTION_TO_SUPABASE_STATUS["Entretien RH confirmé"] == "INTERVIEW_HR"
    assert NOTION_TO_SUPABASE_STATUS["Offre reçue/Acceptée"] == "OFFER"
    assert NOTION_TO_SUPABASE_STATUS["Refusée"] == "REJECTED"

    # Supabase -> Notion
    assert SUPABASE_TO_NOTION_STATUS["PREPARED"] == "Candidature prête - en attente de validation"
    assert SUPABASE_TO_NOTION_STATUS["APPLIED"] == "Candidature envoyée"
    assert SUPABASE_TO_NOTION_STATUS["INTERVIEW_HR"] == "Entretien RH confirmé"
    assert SUPABASE_TO_NOTION_STATUS["OFFER"] == "Offre reçue/Acceptée"
    assert SUPABASE_TO_NOTION_STATUS["REJECTED"] == "Refusée"

def test_parse_notion_page():
    sync_service = NotionSyncService()
    raw_page = {
        "id": "page-uuid-123",
        "last_edited_time": "2026-09-11T15:00:00.000Z",
        "properties": {
            "Entreprise": {"title": [{"plain_text": "Doctolib"}]},
            "Poste": {"rich_text": [{"plain_text": "Senior Backend Engineer"}]},
            "Statut": {"type": "select", "select": {"name": "Candidature envoyée"}},
            "Date de candidature": {"date": {"start": "2026-09-11"}},
            "Date de refus": {"date": None},
            "Motif de refus": {"type": "rich_text", "rich_text": []},
            "Lien de l'offre": {"url": "https://doctolib.jobs/123"},
            "N suivi": {"number": 166}
        }
    }

    parsed = sync_service._parse_notion_page(raw_page)
    assert parsed["id"] == "page-uuid-123"
    assert parsed["company"] == "Doctolib"
    assert parsed["job_title"] == "Senior Backend Engineer"
    assert parsed["status"] == "Candidature envoyée"
    assert parsed["applied_date"] == "2026-09-11"
    assert parsed["n_suivi"] == 166

def test_reconcile_notion_newer(monkeypatch):
    sync_service = NotionSyncService()

    # 1. Mock Notion pages (Statut: Candidature envoyée, last_edited: 14h00)
    mock_notion_pages = [
        {
            "id": "notion-p1",
            "last_edited_time": "2026-09-11T14:00:00.000Z",
            "company": "PayFit",
            "job_title": "Backend Go",
            "status": "Candidature envoyée",
            "applied_date": "2026-09-11",
            "refusal_date": None,
            "refusal_reason": None,
            "job_url": "https://payfit.jobs/1",
            "n_suivi": 167
        }
    ]
    monkeypatch.setattr(sync_service, "fetch_all_notion_pages", lambda: mock_notion_pages)

    # 2. Mock Supabase apps (Statut: PREPARED, updated_at: 10h00)
    mock_supabase_apps = [
        {
            "id": "app-uuid-1",
            "notion_page_id": "notion-p1",
            "status": "PREPARED",
            "updated_at": "2026-09-11T10:00:00+00:00",
            "created_at": "2026-09-11T09:00:00+00:00",
            "applied_at": None,
            "jobs": {"company": "PayFit", "title": "Backend Go"}
        }
    ]
    from app.services.storage.supabase_service import supabase_service
    monkeypatch.setattr(supabase_service, "get_all_applications_for_sync", lambda: mock_supabase_apps)

    updated_records = []
    monkeypatch.setattr(
        supabase_service,
        "update_application",
        lambda app_id, data: updated_records.append((app_id, data)) or True
    )

    # 3. Exécuter réconciliation
    report = sync_service.reconcile()

    assert report["success"] is True
    assert report["matched_count"] == 1
    assert report["updated_supabase_count"] == 1
    assert report["updated_notion_count"] == 0
    assert len(updated_records) == 1
    assert updated_records[0][0] == "app-uuid-1"
    assert updated_records[0][1]["status"] == "APPLIED"
    assert updated_records[0][1]["applied_at"] == "2026-09-11"

def test_reconcile_supabase_newer(monkeypatch):
    sync_service = NotionSyncService()

    # 1. Mock Notion pages (Statut: Candidature prête, last_edited: 10h00)
    mock_notion_pages = [
        {
            "id": "notion-p2",
            "last_edited_time": "2026-09-11T10:00:00.000Z",
            "company": "Qonto",
            "job_title": "Cloud Architect",
            "status": "Candidature prête - en attente de validation",
            "applied_date": None,
            "refusal_date": None,
            "refusal_reason": None,
            "job_url": "https://qonto.jobs/2",
            "n_suivi": 168
        }
    ]
    monkeypatch.setattr(sync_service, "fetch_all_notion_pages", lambda: mock_notion_pages)

    # 2. Mock Supabase apps (Statut: APPLIED, updated_at: 16h00)
    mock_supabase_apps = [
        {
            "id": "app-uuid-2",
            "notion_page_id": "notion-p2",
            "status": "APPLIED",
            "updated_at": "2026-09-11T16:00:00+00:00",
            "created_at": "2026-09-11T09:00:00+00:00",
            "applied_at": "2026-09-11T15:55:00+00:00",
            "jobs": {"company": "Qonto", "title": "Cloud Architect"}
        }
    ]
    from app.services.storage.supabase_service import supabase_service
    from app.services.notion.client import notion_service

    monkeypatch.setattr(supabase_service, "get_all_applications_for_sync", lambda: mock_supabase_apps)

    notion_updates = []
    monkeypatch.setattr(
        notion_service,
        "update_page_status",
        lambda page_id, status_name, applied_date=None: notion_updates.append((page_id, status_name, applied_date)) or True
    )

    # 3. Exécuter réconciliation
    report = sync_service.reconcile()

    assert report["success"] is True
    assert report["matched_count"] == 1
    assert report["updated_supabase_count"] == 0
    assert report["updated_notion_count"] == 1
    assert len(notion_updates) == 1
    assert notion_updates[0][0] == "notion-p2"
    assert notion_updates[0][1] == "Candidature envoyée"
    assert notion_updates[0][2] == "2026-09-11"

def test_reconcile_secondary_matching_by_company_and_title(monkeypatch):
    sync_service = NotionSyncService()

    # Notion page sans notion_page_id dans Supabase au départ
    mock_notion_pages = [
        {
            "id": "new-notion-page-id",
            "last_edited_time": "2026-09-11T12:00:00.000Z",
            "company": "Infomil",
            "job_title": "Ingénieur développement (H/F)",
            "status": "Candidature prête - en attente de validation",
            "applied_date": None,
            "refusal_date": None,
            "refusal_reason": None,
            "job_url": None,
            "n_suivi": 169
        }
    ]
    monkeypatch.setattr(sync_service, "fetch_all_notion_pages", lambda: mock_notion_pages)

    # Supabase application avec notion_page_id manquant
    mock_supabase_apps = [
        {
            "id": "app-uuid-unlinked",
            "notion_page_id": None,
            "status": "PREPARED",
            "updated_at": "2026-09-11T12:00:00+00:00",
            "created_at": "2026-09-11T11:00:00+00:00",
            "applied_at": None,
            "jobs": {"company": "Infomil", "title": "Ingénieur développement (H/F)"}
        }
    ]
    from app.services.storage.supabase_service import supabase_service
    monkeypatch.setattr(supabase_service, "get_all_applications_for_sync", lambda: mock_supabase_apps)

    updates = []
    monkeypatch.setattr(
        supabase_service,
        "update_application",
        lambda app_id, data: updates.append((app_id, data)) or True
    )

    report = sync_service.reconcile()
    assert report["matched_count"] == 1
    # Doit avoir lié la page Notion
    assert any(u[0] == "app-uuid-unlinked" and u[1].get("notion_page_id") == "new-notion-page-id" for u in updates)

def test_api_notion_reconcile_route(client, monkeypatch):
    mock_report = {
        "success": True,
        "total_notion_pages": 5,
        "total_supabase_apps": 4,
        "matched_count": 4,
        "updated_supabase_count": 1,
        "updated_notion_count": 1,
        "details": []
    }
    from app.services.notion.sync import notion_sync_service
    monkeypatch.setattr(notion_sync_service, "reconcile", lambda: mock_report)

    res = client.post("/api/notion/reconcile")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["total_notion_pages"] == 5
    assert data["updated_supabase_count"] == 1

def test_api_mark_as_applied_propagates_to_notion(client, monkeypatch):
    from app.services.storage.supabase_service import supabase_service
    from app.services.notion.client import notion_service

    mock_client = MagicMock()
    monkeypatch.setattr(SupabaseService, "client", property(lambda self: mock_client))

    # Mock select notion_page_id
    mock_query = MagicMock()
    mock_client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_res = MagicMock()
    mock_res.data = [{"notion_page_id": "page-notion-xyz"}]
    mock_query.execute.return_value = mock_res

    notion_updates = []
    monkeypatch.setattr(
        notion_service,
        "update_page_status",
        lambda page_id, status_name, applied_date=None: notion_updates.append((page_id, status_name, applied_date)) or True
    )

    res = client.post("/api/applications/test-app-id/applied")
    assert res.status_code == 200
    assert len(notion_updates) == 1
    assert notion_updates[0][0] == "page-notion-xyz"
    assert notion_updates[0][1] == "Candidature envoyée"
    assert notion_updates[0][2] is not None


def test_classify_company_known_companies():
    from app.services.ingestion.company_classifier import classify_company

    c_type, c_domain = classify_company("Infomil")
    assert "Grand groupe" in c_type or "Filiale IT" in c_type
    assert "Grande distribution" in c_domain

    c_type, c_domain = classify_company("Doctolib")
    assert "MedTech" in c_type or "Scale-up" in c_type
    assert "Santé" in c_domain

    c_type, c_domain = classify_company("Thales")
    assert "Grand groupe" in c_type
    assert "Défense" in c_domain

    c_type, c_domain = classify_company("Groupe SII")
    assert "ESN" in c_type
    assert "Conseil" in c_domain


def test_classify_company_wttj_and_heuristics():
    from app.services.ingestion.company_classifier import classify_company

    # Test via raw WTTJ data
    raw_wttj = {
        "organization": {
            "industry": "Fintech & Néobanques",
            "sectors": [{"name": "Fintech"}, {"name": "Banque"}],
            "nb_employees": 300,
            "description": "Nous révolutionnons les services bancaires."
        }
    }
    c_type, c_domain = classify_company("Unknown Fintech Co", raw_data=raw_wttj)
    assert c_type == "ETI"
    assert "Fintech" in c_domain or "Banque" in c_domain

    # Test via keyword heuristics in description
    c_type, c_domain = classify_company(
        company="SecOps Startup",
        title="Ingénieur Sécurité",
        description="Société de conseil spécialisée dans la cybersécurité, IAM et détection des vulnérabilités."
    )
    assert "ESN" in c_type or "Conseil" in c_type
    assert "Cybersécurité" in c_domain


def test_reconcile_enriches_missing_type_and_domain(monkeypatch):
    from app.services.notion.sync import NotionSyncService
    from app.services.storage.supabase_service import supabase_service
    from app.services.notion.client import notion_service

    sync_service = NotionSyncService()

    mock_notion_pages = [
        {
            "id": "notion-enrich-1",
            "last_edited_time": "2026-09-11T14:00:00.000Z",
            "company": "Infomil",
            "job_title": "Développeur Python",
            "status": "Candidature prête - en attente de validation",
            "company_type": None,  # Absent dans Notion
            "domain": "Ingénierie Logicielle / Backend & Cloud",  # Placeholder à enrichir
            "applied_date": None,
            "refusal_date": None,
            "refusal_reason": None,
            "job_url": "https://infomil.jobs/1",
            "n_suivi": 170
        }
    ]
    monkeypatch.setattr(sync_service, "fetch_all_notion_pages", lambda: mock_notion_pages)

    mock_supabase_apps = [
        {
            "id": "app-enrich-1",
            "notion_page_id": "notion-enrich-1",
            "status": "PREPARED",
            "updated_at": "2026-09-11T14:00:00+00:00",
            "created_at": "2026-09-11T12:00:00+00:00",
            "applied_at": None,
            "jobs": {
                "company": "Infomil",
                "title": "Développeur Python",
                "description": "Filiale informatique de E.Leclerc",
                "match_analysis": {},
                "normalized_data": {}
            }
        }
    ]
    monkeypatch.setattr(supabase_service, "get_all_applications_for_sync", lambda: mock_supabase_apps)

    enriched_props = []
    monkeypatch.setattr(
        notion_service,
        "update_page_properties",
        lambda page_id, props: enriched_props.append((page_id, props)) or True
    )

    report = sync_service.reconcile()

    assert report["success"] is True
    assert report["matched_count"] == 1
    assert len(enriched_props) == 1
    page_id, props = enriched_props[0]
    assert page_id == "notion-enrich-1"
    assert "Type" in props
    assert "Domaine" in props
    assert "Infomil" in props["Type"]["rich_text"][0]["text"]["content"] or "Grand groupe" in props["Type"]["rich_text"][0]["text"]["content"]
    assert "Grande distribution" in props["Domaine"]["rich_text"][0]["text"]["content"]


def test_notion_create_application_page_payload(monkeypatch):
    from app.services.notion.client import NotionService

    service = NotionService()
    mock_client = MagicMock()
    service._client = mock_client
    service.config.NOTION_DATABASE_ID = "test-db-id"
    service.config.NOTION_TOKEN = "fake-token"

    # Mock get_next_suivi_number
    monkeypatch.setattr(service, "get_next_suivi_number", lambda: 171)

    mock_client.pages.create.return_value = {"id": "new-notion-page-created"}

    page_id = service.sync_application(
        application_id="app-123",
        company="Euro Protection Surveillance",
        job_title="Lead Developer",
        job_url="https://eps.fr/jobs/1",
        score=85,
        status="PREPARED",
        location="Strasbourg",
        contract_type="CDI",
        domain="Télésurveillance & Sécurité des biens / Banque",
        company_type="Grand groupe (Bancassurance / Sécurité)",
        cv_url="https://example.com/cv.pdf"
    )

    assert page_id == "new-notion-page-created"
    assert mock_client.pages.create.called
    call_args = mock_client.pages.create.call_args[1]
    properties = call_args["properties"]

    assert properties["Entreprise"]["title"][0]["text"]["content"] == "Euro Protection Surveillance"
    assert properties["Type"]["rich_text"][0]["text"]["content"] == "Grand groupe (Bancassurance / Sécurité)"
    assert properties["Domaine"]["rich_text"][0]["text"]["content"] == "Télésurveillance & Sécurité des biens / Banque"
    assert properties["N suivi"]["number"] == 171

