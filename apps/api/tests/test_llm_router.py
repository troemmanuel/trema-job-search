import pytest
from unittest.mock import MagicMock, patch
from pydantic import BaseModel

from app.llm import (
    router,
    LLMRouter,
    LLMResult,
    LLMAllProvidersFailedError,
    LLMProviderError
)
from app.llm.providers.base import BaseLLMProvider

class JobScoreSchema(BaseModel):
    score: int
    recommendation: str

class DocContentSchema(BaseModel):
    summary: str
    skills: list[str]

@pytest.fixture(autouse=True)
def reset_router_stats():
    """Réinitialise les stats du routeur avant chaque test."""
    router.reset_stats()
    yield
    router.reset_stats()

def test_task_alias_normalization():
    """Vérifie la normalisation correcte des alias de tâches."""
    test_router = LLMRouter()
    assert test_router.get_canonical_task("job_scoring") == "job_scoring"
    assert test_router.get_canonical_task("matching") == "job_scoring"
    assert test_router.get_canonical_task("scorer") == "job_scoring"

    assert test_router.get_canonical_task("doc_content_generation") == "doc_content_generation"
    assert test_router.get_canonical_task("cv_content_generation") == "doc_content_generation"
    assert test_router.get_canonical_task("cv_tailoring") == "doc_content_generation"
    assert test_router.get_canonical_task("cover_letter") == "doc_content_generation"
    assert test_router.get_canonical_task("application_answers") == "doc_content_generation"

def test_primary_provider_success():
    """Scénario 1: Gemini réussit directement -> fallback_used=False."""
    mock_result = LLMResult(
        data=JobScoreSchema(score=88, recommendation="PRIORITY"),
        provider="gemini",
        model="gemini-2.5-flash",
        latency=0.32,
        tokens={"total_tokens": 150},
        fallback_used=False
    )

    with patch.object(router.providers["gemini"], "is_configured", return_value=True):
        with patch.object(router.providers["gemini"], "generate", return_value=mock_result) as mock_gemini:
            res = router.generate(
                task="job_scoring",
                prompt="Calculer le score de cette offre.",
                response_schema=JobScoreSchema
            )

            assert mock_gemini.called
            assert res.provider == "gemini"
            assert res.model == "gemini-2.5-flash"
            assert res.fallback_used is False
            assert res.data.score == 88
            assert res.data.recommendation == "PRIORITY"

            stats = router.get_stats()
            assert stats["gemini"]["success_count"] == 1
            assert stats["gemini"]["errors_count"] == 0

def test_fallback_on_429_gemini_to_groq():
    """Scénario 2: Gemini renvoie 429 -> bascule automatique vers Groq."""
    groq_result = LLMResult(
        data=JobScoreSchema(score=78, recommendation="RECOMMENDED"),
        provider="groq",
        model="llama-3.3-70b-versatile",
        latency=0.25,
        tokens={"total_tokens": 140},
        fallback_used=False
    )

    with patch.object(router.providers["gemini"], "is_configured", return_value=True):
        with patch.object(router.providers["groq"], "is_configured", return_value=True):
            with patch.object(router.providers["gemini"], "generate", side_effect=LLMProviderError("gemini", "Quota 429", status_code=429, is_rate_limit=True)):
                with patch.object(router.providers["groq"], "generate", return_value=groq_result) as mock_groq:
                    res = router.generate(
                        task="job_scoring",
                        prompt="Offre et profil",
                        response_schema=JobScoreSchema
                    )

                    assert mock_groq.called
                    assert res.provider == "groq"
                    assert res.model == "llama-3.3-70b-versatile"
                    assert res.fallback_used is True
                    assert res.data.score == 78

                    stats = router.get_stats()
                    assert stats["gemini"]["errors_count"] == 1
                    assert stats["groq"]["success_count"] == 1

def test_doc_content_generation_routes_to_mistral():
    """Scénario 3: Pour doc_content_generation, le fallback de gemini est mistral (et non groq)."""
    mistral_result = LLMResult(
        data=DocContentSchema(summary="Profil Lead Dev", skills=["Python", "FastAPI"]),
        provider="mistral",
        model="mistral-small-latest",
        latency=0.42,
        tokens={"total_tokens": 250},
        fallback_used=False
    )

    with patch.object(router.providers["gemini"], "is_configured", return_value=True):
        with patch.object(router.providers["mistral"], "is_configured", return_value=True):
            with patch.object(router.providers["gemini"], "generate", side_effect=LLMProviderError("gemini", "Rate limit", status_code=429)):
                with patch.object(router.providers["mistral"], "generate", return_value=mistral_result) as mock_mistral:
                    res = router.generate(
                        task="doc_content_generation",
                        prompt="Générer un CV adapté.",
                        response_schema=DocContentSchema
                    )

                    assert mock_mistral.called
                    assert res.provider == "mistral"
                    assert res.fallback_used is True
                    assert res.data.skills == ["Python", "FastAPI"]

def test_double_fallback_to_openrouter():
    """Scénario 4: Gemini + Groq échouent -> bascule vers OpenRouter."""
    openrouter_result = LLMResult(
        data={"score": 90, "recommendation": "PRIORITY"},
        provider="openrouter",
        model="meta-llama/llama-3.3-70b-instruct",
        latency=0.55,
        tokens={"total_tokens": 180},
        fallback_used=False
    )

    with patch.object(router.providers["gemini"], "is_configured", return_value=True):
        with patch.object(router.providers["groq"], "is_configured", return_value=True):
            with patch.object(router.providers["openrouter"], "is_configured", return_value=True):
                with patch.object(router.providers["gemini"], "generate", side_effect=LLMProviderError("gemini", "429")):
                    with patch.object(router.providers["groq"], "generate", side_effect=LLMProviderError("groq", "503")):
                        with patch.object(router.providers["openrouter"], "generate", return_value=openrouter_result):
                            res = router.generate(
                                task="job_scoring",
                                prompt="Calcul"
                            )
                            assert res.provider == "openrouter"
                            assert res.fallback_used is True
                            assert res.data["score"] == 90

def test_all_providers_failed_raises_exception():
    """Scénario 5: Tous les providers échouent -> LLMAllProvidersFailedError."""
    with patch.object(router.providers["gemini"], "is_configured", return_value=True):
        with patch.object(router.providers["groq"], "is_configured", return_value=True):
            with patch.object(router.providers["openrouter"], "is_configured", return_value=True):
                with patch.object(router.providers["gemini"], "generate", side_effect=LLMProviderError("gemini", "429")):
                    with patch.object(router.providers["groq"], "generate", side_effect=LLMProviderError("groq", "500")):
                        with patch.object(router.providers["openrouter"], "generate", side_effect=LLMProviderError("openrouter", "Timeout")):
                            with pytest.raises(LLMAllProvidersFailedError) as excinfo:
                                router.generate(task="job_scoring", prompt="test")

                            assert "Tous les providers configurés pour la tâche 'job_scoring' ont échoué" in str(excinfo.value)
                            assert "gemini" in excinfo.value.errors
                            assert "groq" in excinfo.value.errors
                            assert "openrouter" in excinfo.value.errors

def test_clean_json_extraction():
    """Scénario 6: Test du parseur JSON de BaseLLMProvider (markdown code blocks, trailing text)."""
    provider = router.providers["groq"]

    # 1. Avec bloc markdown ```json ... ```
    raw_md = "```json\n{\"score\": 82, \"recommendation\": \"RECOMMENDED\"}\n```"
    parsed = provider.parse_and_validate(raw_md, response_schema=JobScoreSchema)
    assert parsed.score == 82

    # 2. Avec texte avant et après
    raw_surrounded = "Voici l'analyse demandée :\n{\"score\": 95, \"recommendation\": \"PRIORITY\"}\nJ'espère que cela convient."
    parsed2 = provider.parse_and_validate(raw_surrounded, response_schema=JobScoreSchema)
    assert parsed2.score == 95

    # 3. JSON sans schéma Pydantic
    raw_dict = "{\"cle\": \"valeur\"}"
    parsed3 = provider.parse_and_validate(raw_dict, response_schema=None)
    assert parsed3 == {"cle": "valeur"}

def test_stats_counters_and_reset():
    """Scénario 7: Test du suivi des statistiques d'utilisation et de la réinitialisation."""
    assert router.stats["gemini"].requests_count == 0
    router._record_success("gemini", latency=0.5, tokens=100)
    router._record_error("groq", error_msg="Simulated Error")

    stats = router.get_stats()
    assert stats["gemini"]["requests_count"] == 1
    assert stats["gemini"]["success_count"] == 1
    assert stats["gemini"]["total_tokens"] == 100
    assert stats["groq"]["requests_count"] == 1
    assert stats["groq"]["errors_count"] == 1

    router.reset_stats()
    stats_after = router.get_stats()
    assert stats_after["gemini"]["requests_count"] == 0
    assert stats_after["groq"]["requests_count"] == 0
