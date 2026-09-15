"""Isolation des tests : aucun test ne doit toucher la base Supabase réelle, Gemini ou le disque du candidat.

Les singletons `supabase_service` / `gemini_service` lisent le `.env` à l'import : sans ce garde-fou,
`pytest` écrasait le profil maître en production. Un test qui a réellement besoin d'une connexion live
doit être marqué `@pytest.mark.live`.

Le planificateur d'arrière-plan est désactivé pour toute la session de tests.
"""
import os

import pytest

os.environ["ENABLE_SCHEDULER"] = "0"


def pytest_configure(config):
    config.addinivalue_line("markers", "live: autorise l'accès aux services externes (Supabase, Gemini)")


@pytest.fixture(autouse=True)
def isolate_external_services(request, monkeypatch):
    if request.node.get_closest_marker("live"):
        yield
        return

    from app.services.ai.gemini import GeminiService
    from app.services.documents.renderer import DocumentRenderer
    from app.services.storage.supabase_service import SupabaseService

    monkeypatch.setattr(SupabaseService, "client", property(lambda self: None))
    monkeypatch.setattr(SupabaseService, "is_configured", lambda self: False)
    monkeypatch.setattr(GeminiService, "client", property(lambda self: None))
    monkeypatch.setattr(DocumentRenderer, "_save_local_backup", classmethod(lambda cls, *a, **k: None))
    yield


@pytest.fixture
def client():
    """Client HTTP FastAPI (les exceptions non gérées deviennent des 500 JSON, comme en production)."""
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Faux client Supabase en mémoire : permet de tester les routes d'écriture
# (profil, paramètres, statuts, PDF) sans base réelle.
# ---------------------------------------------------------------------------
import uuid
from datetime import datetime, timezone


class _Result:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class _FakeQuery:
    def __init__(self, store, table):
        self._store = store
        self._table = table
        self._op = "select"
        self._select = "*"
        self._payload = None
        self._filters = []
        self._limit = None
        self._range = None
        self._order = None

    # --- constructeurs d'opération ---
    def select(self, columns="*", count=None):
        self._op, self._select = "select", columns
        return self

    def insert(self, payload):
        self._op, self._payload = "insert", payload
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def delete(self):
        self._op = "delete"
        return self

    # --- filtres / modificateurs (chaînables) ---
    def eq(self, key, value):
        self._filters.append(lambda r: str(r.get(key)) == str(value))
        return self

    def gte(self, key, value):
        self._filters.append(lambda r: r.get(key) is not None and r.get(key) >= value)
        return self

    def order(self, key, desc=False):
        self._order = (key, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def _matching(self):
        rows = [r for r in self._store[self._table] if all(f(r) for f in self._filters)]
        if self._order:
            key, desc = self._order
            rows.sort(key=lambda r: str(r.get(key) or ""), reverse=desc)
        return rows

    def _with_join(self, row):
        if self._table == "applications" and "jobs(" in self._select:
            job = next((j for j in self._store["jobs"] if j.get("id") == row.get("job_id")), None)
            return {**row, "jobs": job}
        return row

    def execute(self):
        rows = self._matching()
        if self._op == "select":
            total = len(rows)
            if self._range:
                rows = rows[self._range[0] : self._range[1] + 1]
            if self._limit is not None:
                rows = rows[: self._limit]
            return _Result([self._with_join(r) for r in rows], count=total)
        if self._op == "insert":
            payloads = self._payload if isinstance(self._payload, list) else [self._payload]
            created = []
            for p in payloads:
                row = {"id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat(), **p}
                self._store[self._table].append(row)
                created.append(row)
            return _Result(created)
        if self._op == "update":
            for r in rows:
                r.update(self._payload)
            return _Result(rows)
        if self._op == "delete":
            self._store[self._table] = [r for r in self._store[self._table] if r not in rows]
            return _Result(rows)
        raise NotImplementedError(self._op)


class FakeSupabaseClient:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        self.store.setdefault(name, [])
        return _FakeQuery(self.store, name)


def make_profile_record(**overrides):
    record = {
        "id": str(uuid.uuid4()),
        "name": "John Doe",
        "profile": {
            "name": "John Doe",
            "personal": {"first_name": "John", "last_name": "Doe", "email": "john.doe@example.com"},
            "title": "Développeur Backend",
            "experiences": [],
            "projects": [],
        },
        "preferences": {"target_titles": ["Développeur Python"], "excluded_companies": ["Thales"]},
        "version": 1,
        "is_active": True,
    }
    record.update(overrides)
    return record


@pytest.fixture
def fake_db(monkeypatch):
    """Base en mémoire avec un profil actif ; renvoie le `store` (dict de tables) pour y ajouter des lignes."""
    from app.services.storage.supabase_service import SupabaseService

    store = {"candidate_profiles": [make_profile_record()], "jobs": [], "applications": []}
    fake_client = FakeSupabaseClient(store)
    monkeypatch.setattr(SupabaseService, "client", property(lambda self: fake_client))
    monkeypatch.setattr(SupabaseService, "is_configured", lambda self: True)
    return store
