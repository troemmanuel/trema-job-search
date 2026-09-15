"""Test de contrat : le schéma OpenAPI doit rester exploitable pour générer le SDK TypeScript.

Toute route JSON de l'API v1 doit déclarer un `response_model` (sinon `openapi-typescript`
génère `unknown` et le typage bout en bout est perdu).
"""
import os

import pytest

os.environ.setdefault("ENABLE_SCHEDULER", "0")

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

# Routes qui ne renvoient volontairement pas de JSON typé (fichiers binaires, SSE)
NON_JSON_ROUTES = {
    ("get", "/api/v1/applications/{app_id}/documents/{doc_type}"),
    ("post", "/api/v1/jobs/scrape/stream"),
}


@pytest.fixture(scope="module")
def spec():
    client = TestClient(app)
    res = client.get("/openapi.json")
    assert res.status_code == 200
    return res.json()


def test_every_json_route_has_typed_response(spec):
    untyped = []
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            if (method, path) in NON_JSON_ROUTES:
                continue
            schema = (
                operation.get("responses", {})
                .get("200", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema")
            )
            if not schema:
                untyped.append(f"{method.upper()} {path}")
    assert not untyped, f"Routes sans response_model : {untyped}"


def test_every_body_route_has_typed_request(spec):
    untyped = []
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            body = operation.get("requestBody")
            if not body:
                continue
            schema = body.get("content", {}).get("application/json", {}).get("schema", {})
            if "$ref" not in schema:
                untyped.append(f"{method.upper()} {path}")
    assert not untyped, f"Routes avec un corps non typé (dict) : {untyped}"


def test_sse_event_schema_is_exposed(spec):
    schemas = spec["components"]["schemas"]
    assert "ScrapeStreamEvent" in schemas
    stream_op = spec["paths"]["/api/v1/jobs/scrape/stream"]["post"]
    sse_schema = stream_op["responses"]["200"]["content"]["text/event-stream"]["schema"]
    assert sse_schema == {"$ref": "#/components/schemas/ScrapeStreamEvent"}
    assert set(schemas["ScrapeStreamEvent"]["properties"]["type"]["enum"]) == {
        "start", "processing", "item_done", "item_error", "complete",
    }


def test_pdf_route_declares_binary_content(spec):
    op = spec["paths"]["/api/v1/applications/{app_id}/documents/{doc_type}"]["get"]
    assert "application/pdf" in op["responses"]["200"]["content"]
    doc_type_param = next(p for p in op["parameters"] if p["name"] == "doc_type")
    assert doc_type_param["schema"]["enum"] == ["CV", "COVER_LETTER"]


def test_exported_spec_matches_committed_file():
    """`packages/api-client/openapi.json` doit être régénéré après tout changement d'API."""
    import json
    from pathlib import Path

    committed = Path(__file__).resolve().parents[3] / "packages" / "api-client" / "openapi.json"
    if not committed.exists():
        pytest.skip("openapi.json non encore exporté")
    assert json.loads(committed.read_text(encoding="utf-8")) == app.openapi(), (
        "Le schéma OpenAPI a changé : lancez `pnpm generate:api-client`"
    )
