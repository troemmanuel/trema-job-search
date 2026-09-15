import time
import pytest
from unittest.mock import patch, MagicMock
from pydantic import BaseModel

from app.llm import router, LLMRouter, LLMResult
from app.llm.cache import LLMCache, llm_cache
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobNormalizedData
from app.schemas.application import TailoredCV, CoverLetter
from app.schemas.dossier import ApplicationDossier
from app.services.ai.dossier_generator import dossier_generator_service

class SimpleTestSchema(BaseModel):
    message: str

@pytest.fixture(autouse=True)
def clean_cache():
    """Vide le cache LLM avant et après chaque test."""
    llm_cache.clear()
    router.reset_stats()
    yield
    llm_cache.clear()
    router.reset_stats()

def test_cache_set_and_get():
    """Vérifie l'insertion et la récupération d'un résultat dans le cache SHA-256."""
    cache = LLMCache()
    result = LLMResult(
        data={"ok": True},
        provider="groq",
        model="llama-3.3-70b-versatile",
        latency=0.35,
        tokens=120,
        fallback_used=False
    )
    key = cache.compute_key(task="job_scoring", prompt="test prompt")
    cache.set(key, result)

    cached = cache.get(key)
    assert cached is not None
    assert cached.data == {"ok": True}
    assert cached.latency == 0.0  # Latence nulle depuis le cache
    assert cached.provider == "groq"
    assert cache.hits == 1
    assert cache.misses == 0

def test_cache_miss():
    """Vérifie le comportement en cas de clé absente."""
    cache = LLMCache()
    assert cache.get("non_existent_key") is None
    assert cache.misses == 1

def test_cache_expiration():
    """Vérifie l'expiration d'une entrée selon son TTL."""
    cache = LLMCache(default_ttl_seconds=1)
    result = LLMResult(
        data={"ok": True},
        provider="gemini",
        model="gemini-2.5-flash",
        latency=0.2,
        tokens=50
    )
    key = "expiring_key"
    cache.set(key, result, ttl_seconds=1)
    assert cache.get(key) is not None

    time.sleep(1.05)
    assert cache.get(key) is None

def test_router_transparent_cache():
    """Vérifie que router.generate ne rappelle pas le provider sur une requête identique."""
    mock_res = LLMResult(
        data={"calculated": 42},
        provider="groq",
        model="llama-3.3-70b-versatile",
        latency=0.45,
        tokens=80
    )

    with patch.object(router.providers["gemini"], "is_configured", return_value=False):
        with patch.object(router.providers["groq"], "is_configured", return_value=True):
            with patch.object(router.providers["groq"], "generate", return_value=mock_res) as mock_groq:
                # 1. Premier appel : sollicite le provider
                res1 = router.generate(task="job_scoring", prompt="Prompt test cache")
                assert mock_groq.call_count == 1
                assert res1.data == {"calculated": 42}
                assert res1.latency == 0.45

                # 2. Second appel identique : servi immédiatement par le cache
                res2 = router.generate(task="job_scoring", prompt="Prompt test cache")
                assert mock_groq.call_count == 1  # Pas d'appel supplémentaire !
                assert res2.data == {"calculated": 42}
                assert res2.latency == 0.0

                # 3. Troisième appel avec force_refresh=True : bypass du cache
                res3 = router.generate(task="job_scoring", prompt="Prompt test cache", force_refresh=True)
                assert mock_groq.call_count == 2  # Nouveau calcul forcé

def test_router_stats_include_cache():
    """Vérifie que router.get_stats inclut les compteurs du cache applicatif."""
    stats = router.get_stats()
    assert "cache" in stats
    assert "hits" in stats["cache"]
    assert "misses" in stats["cache"]
    assert "hit_ratio_percent" in stats["cache"]

def test_dossier_generator_bundle():
    """Vérifie la génération groupée de CV + Lettre en un seul appel IA."""
    profile = CandidateProfile(
        name="Jean Dupont",
        personal={"first_name": "Jean", "last_name": "Dupont", "email": "jean@dupont.com"},
        title="Ingénieur Backend Python",
        skills={"technical": ["Python", "PostgreSQL", "Docker"]},
        experiences=[],
        projects=[]
    )
    job_data = JobNormalizedData(
        title="Développeur Senior Python",
        company="TechCorp",
        skills=["Python", "FastAPI"],
        language="fr"
    )

    mock_cv = TailoredCV(
        job_id="job-123",
        title="Ingénieur Backend Python",
        summary="Spécialiste Python orienté performance.",
        selected_experiences=[],
        skills=["Python", "PostgreSQL"]
    )
    mock_letter = CoverLetter(
        type="cover_letter",
        content="Madame, Monsieur,\nJe vous adresse ma candidature au poste de Développeur Senior.",
        personalization_points=["Expertise Python", "Architecture FastAPI"]
    )

    bundle = ApplicationDossier(
        tailored_cv=mock_cv,
        cover_letter=mock_letter
    )

    mock_llm_result = LLMResult(
        data=bundle,
        provider="gemini",
        model="gemini-2.5-flash",
        latency=0.6,
        tokens=350,
        fallback_used=False
    )

    with patch.object(router, "generate", return_value=mock_llm_result) as mock_router_gen:
        cv, letter = dossier_generator_service.generate(
            job_id="job-123",
            profile=profile,
            job_data=job_data
        )

        assert mock_router_gen.call_count == 1
        call_kwargs = mock_router_gen.call_args[1]
        assert call_kwargs["task"] == "doc_content_generation"
        assert call_kwargs["response_schema"] == ApplicationDossier

        assert cv is not None
        assert letter is not None
        assert cv.title == "Ingénieur Backend Python"
        assert "TechCorp" in letter.content or "candidature" in letter.content

def test_dossier_generator_fallback_on_error():
    """Vérifie que dossier_generator bascule sur les générateurs individuels si la génération groupée échoue."""
    profile = CandidateProfile(
        name="Test",
        personal={"first_name": "T", "last_name": "E", "email": "t@e.com"},
        title="Dev",
        skills={"technical": ["Python"]}
    )
    job_data = JobNormalizedData(title="Dev", company="Corp", language="fr")

    mock_cv = TailoredCV(
        job_id="job-999",
        summary="Accroche CV individuelle",
        selected_experiences=[],
        skills=["Python"]
    )
    mock_letter = CoverLetter(
        content="Lettre individuelle",
        personalization_points=[]
    )

    # Simuler échec de la génération groupée
    with patch.object(router, "generate", side_effect=Exception("Erreur de schéma")):
        with patch("app.services.ai.dossier_generator.cv_generator_service.generate", return_value=mock_cv) as mock_cv_gen:
            with patch("app.services.ai.dossier_generator.letter_generator_service.generate", return_value=mock_letter) as mock_letter_gen:
                cv, letter = dossier_generator_service.generate(
                    job_id="job-999",
                    profile=profile,
                    job_data=job_data
                )

                assert mock_cv_gen.called
                assert mock_letter_gen.called
                assert cv.summary == "Accroche CV individuelle"
                assert letter.content == "Lettre individuelle"
