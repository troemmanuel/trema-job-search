from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel

from app.config import Config
from app.llm.cache import llm_cache
from app.llm.providers.base import BaseLLMProvider
from app.llm.providers.gemini import GeminiProvider
from app.llm.providers.groq import GroqProvider
from app.llm.providers.mistral import MistralProvider
from app.llm.providers.openrouter import OpenRouterProvider
from app.llm.schemas.router import (
    LLMResult,
    ProviderStats,
    LLMAllProvidersFailedError,
    LLMProviderError
)

logger = logging.getLogger(__name__)

DEFAULT_ROUTING_CONFIG: Dict[str, List[str]] = {
    "job_scoring": ["gemini", "groq", "openrouter"],
    "doc_content_generation": ["gemini", "mistral", "groq", "openrouter"],
}

TASK_ALIASES: Dict[str, str] = {
    "job_scoring": "job_scoring",
    "matching": "job_scoring",
    "scorer": "job_scoring",
    "scrape_fallback": "job_scoring",
    "doc_content_generation": "doc_content_generation",
    "cv_content_generation": "doc_content_generation",
    "cv_generation": "doc_content_generation",
    "cv_tailoring": "doc_content_generation",
    "cover_letter": "doc_content_generation",
    "letter_generation": "doc_content_generation",
    "application_answers": "doc_content_generation",
    "answers_generation": "doc_content_generation",
    "cv_markdown_transcription": "doc_content_generation",
    "letter": "doc_content_generation",
    "cv": "doc_content_generation",
}

class LLMRouter:
    """Routeur intelligent de requêtes LLM multi-fournisseurs avec bascule automatique (failover)."""

    def __init__(self, config: Optional[Config] = None, routing_config: Optional[Dict[str, List[str]]] = None):
        self.config = config or Config()
        self.routing_config = routing_config or DEFAULT_ROUTING_CONFIG

        # Initialisation des adaptateurs fournisseurs
        self.providers: Dict[str, BaseLLMProvider] = {
            "gemini": GeminiProvider(
                api_key=self.config.GEMINI_API_KEY,
                default_model=self.config.GEMINI_MODEL
            ),
            "groq": GroqProvider(
                api_key=self.config.GROQ_API_KEY,
                default_model=self.config.GROQ_MODEL
            ),
            "mistral": MistralProvider(
                api_key=self.config.MISTRAL_API_KEY,
                default_model=self.config.MISTRAL_MODEL
            ),
            "openrouter": OpenRouterProvider(
                api_key=self.config.OPENROUTER_API_KEY,
                default_model=self.config.OPENROUTER_MODEL
            ),
        }

        # Statistiques d'utilisation en mémoire par fournisseur
        self.stats: Dict[str, ProviderStats] = {
            name: ProviderStats(provider=name) for name in self.providers
        }

    def get_canonical_task(self, task: str) -> str:
        """Normalise le nom de la tâche selon les alias et mots-clés supportés."""
        task_normalized = task.lower().strip()
        if any(kw in task_normalized for kw in ["letter", "lettre", "cv", "answer", "question", "doc", "dossier", "transcri"]):
            return "doc_content_generation"
        if any(kw in task_normalized for kw in ["score", "scoring", "match", "scrape", "extract", "filtr"]):
            return "job_scoring"
        return TASK_ALIASES.get(task_normalized, "doc_content_generation")

    def get_configured_providers(self) -> List[str]:
        """Retourne la liste des fournisseurs dont la clé API est renseignée."""
        return [name for name, p in self.providers.items() if p.is_configured()]

    def get_stats(self) -> Dict[str, Any]:
        """Retourne un instantané des compteurs d'utilisation de chaque provider et du cache."""
        provider_data = {name: stat.model_dump() for name, stat in self.stats.items()}
        provider_data["cache"] = llm_cache.get_stats()
        return provider_data

    def reset_stats(self):
        """Réinitialise l'ensemble des métriques d'utilisation et le cache."""
        for name in self.providers:
            self.stats[name] = ProviderStats(provider=name)
        llm_cache.clear()

    def _record_success(self, provider_name: str, latency: float, tokens: Any):
        stat = self.stats[provider_name]
        stat.requests_count += 1
        stat.success_count += 1
        stat.total_latency_seconds += latency
        stat.last_used_at = datetime.now(timezone.utc).isoformat()

        if isinstance(tokens, dict):
            stat.total_tokens += tokens.get("total_tokens", 0)
        elif isinstance(tokens, int):
            stat.total_tokens += tokens

    def _record_error(self, provider_name: str, error_msg: str):
        stat = self.stats[provider_name]
        stat.requests_count += 1
        stat.errors_count += 1
        stat.last_error = error_msg
        stat.last_used_at = datetime.now(timezone.utc).isoformat()

    def generate(
        self,
        task: str,
        prompt: str,
        response_schema: Optional[Type[BaseModel]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        override_model: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> LLMResult:
        """Point d'entrée unique pour la génération LLM avec failover automatique et cache d'idempotence.

        Args:
            task: Nom de la tâche ('job_scoring', 'doc_content_generation', etc.)
            prompt: Prompt utilisateur
            response_schema: Schéma Pydantic optionnel pour valider la sortie
            system_instruction: Instruction système optionnelle
            temperature: Température de génération (0.0 - 1.0)
            override_model: Modèle spécifique optionnel à forcer
            preferred_provider: Provider optionnel à tenter en priorité absolue
            use_cache: Si True, vérifie et sauvegarde dans le cache applicatif SHA-256
            force_refresh: Si True, ignore le cache existant et force un nouvel appel

        Returns:
            LLMResult: Résultat contenant data, provider, model, latency, tokens, fallback_used.

        Raises:
            LLMAllProvidersFailedError: Si tous les fournisseurs ont échoué.
        """
        canonical_task = self.get_canonical_task(task)

        # 1. Vérification du cache SHA-256
        cache_key = None
        if use_cache:
            cache_key = llm_cache.compute_key(
                task=canonical_task,
                prompt=prompt,
                response_schema=response_schema,
                system_instruction=system_instruction,
                model=override_model
            )
            if not force_refresh:
                cached_res = llm_cache.get(cache_key)
                if cached_res is not None:
                    logger.info(f"[LLM Router] ⚡ Cache HIT ({cache_key[:8]}) pour tâche='{canonical_task}' → réponse instantanée (0.0s, 0 token)")
                    return cached_res

        candidate_names = list(self.routing_config.get(canonical_task, ["gemini", "groq", "openrouter"]))

        if preferred_provider and preferred_provider in self.providers:
            if preferred_provider in candidate_names:
                candidate_names.remove(preferred_provider)
            candidate_names.insert(0, preferred_provider)

        logger.info(f"[LLM Router] 🎯 Tâche: '{canonical_task}' | Chaîne de fallback: {candidate_names}")

        primary_provider_name = candidate_names[0] if candidate_names else None
        errors: Dict[str, str] = {}

        for idx, provider_name in enumerate(candidate_names):
            provider = self.providers.get(provider_name)
            if not provider:
                continue

            if not provider.is_configured():
                logger.info(f"[LLM Router] ⏭️ Provider '{provider_name}' non configuré (clé absente), passage au suivant.")
                errors[provider_name] = "Clé API non configurée"
                continue

            fallback_flag = (provider_name != primary_provider_name)
            try:
                # N'appliquer override_model que s'il est compatible avec le provider ciblé
                provider_model = None
                if override_model:
                    ov = override_model.lower()
                    if provider.name == "gemini" and "gemini" in ov:
                        provider_model = override_model
                    elif provider.name == "groq" and any(k in ov for k in ["llama", "gpt-oss", "qwen", "allam", "groq"]):
                        provider_model = override_model
                    elif provider.name == "mistral" and "mistral" in ov:
                        provider_model = override_model
                    elif provider.name == "openrouter":
                        provider_model = override_model

                effective_model = provider_model or provider.default_model
                logger.info(f"[LLM Router] ⏳ [{idx+1}/{len(candidate_names)}] Appel provider='{provider_name}' (modèle='{effective_model}', fallback={fallback_flag})...")
                result = provider.generate(
                    prompt=prompt,
                    response_schema=response_schema,
                    system_instruction=system_instruction,
                    temperature=temperature,
                    model=provider_model
                )

                # Si le résultat a été produit par un fallback
                result.fallback_used = fallback_flag

                self._record_success(provider_name, result.latency, result.tokens)

                # Sauvegarde dans le cache si actif
                if use_cache and cache_key:
                    llm_cache.set(cache_key, result)

                logger.info(
                    f"[LLM Router] ✅ Succès provider='{provider_name}' modèle='{result.model}' "
                    f"en {result.latency}s (fallback={fallback_flag})"
                )
                return result

            except Exception as e:
                err_msg = str(e)
                self._record_error(provider_name, err_msg)
                errors[provider_name] = err_msg
                logger.warning(
                    f"[LLM Router] ⚠️ Échec du provider '{provider_name}' ({effective_model if 'effective_model' in locals() else 'default'}): {err_msg[:120]}. "
                    f"Bascule automatique vers le fallback suivant..."
                )

        # Tous les providers ont échoué
        logger.error(f"[LLM Router] ❌ Tous les providers pour la tâche '{task}' ({canonical_task}) ont échoué: {errors}")
        raise LLMAllProvidersFailedError(task=task, errors=errors)

router = LLMRouter()
