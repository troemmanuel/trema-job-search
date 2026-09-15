"""Isolation des tests : aucun test ne doit toucher la base Supabase réelle, Gemini ou le disque du candidat.

Les singletons `supabase_service` / `gemini_service` lisent le `.env` à l'import, indépendamment de la
config passée à `create_app` : sans ce garde-fou, `pytest` écrasait le profil maître en production.
Un test qui a réellement besoin d'une connexion live doit être marqué `@pytest.mark.live`.
"""
import pytest


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
