import abc
import json
import logging
import re
import time
from typing import Any, Dict, Optional, Type, Union
from pydantic import BaseModel, ValidationError

from app.llm.schemas.router import LLMResult, LLMProviderError

logger = logging.getLogger(__name__)

class BaseLLMProvider(abc.ABC):
    """Classe de base abstraite pour tous les fournisseurs LLM."""

    name: str = "base"

    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None):
        self.api_key = api_key or ""
        self.default_model = default_model or ""

    def is_configured(self) -> bool:
        """Indique si la clé API du provider est présente."""
        return bool(self.api_key and self.api_key.strip())

    @abc.abstractmethod
    def generate(
        self,
        prompt: str,
        response_schema: Optional[Type[BaseModel]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        model: Optional[str] = None
    ) -> LLMResult:
        """Génère une complétion structurée ou textuelle."""
        pass

    def clean_json_text(self, text: str) -> str:
        """Extrait et nettoie le JSON d'une réponse textuelle de LLM."""
        if not text:
            return "{}"

        text = text.strip()

        # Bloc markdown ```json ... ``` ou ``` ... ```
        code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if code_block_match:
            text = code_block_match.group(1).strip()

        # Si le texte commence et finit par { } ou [ ]
        if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
            return text

        # Recherche de la première accolade ouvrante et de la dernière fermante
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return text[first_brace:last_brace + 1].strip()

        first_bracket = text.find("[")
        last_bracket = text.rfind("]")
        if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
            return text[first_bracket:last_bracket + 1].strip()

        return text

    def parse_and_validate(
        self,
        raw_text: str,
        response_schema: Optional[Type[BaseModel]] = None
    ) -> Any:
        """Parse le JSON brut et valide éventuellement contre un schéma Pydantic."""
        cleaned_json = self.clean_json_text(raw_text)

        if response_schema is not None:
            try:
                # Tentative directe de validation JSON
                return response_schema.model_validate_json(cleaned_json)
            except (ValidationError, ValueError) as err1:
                # Tentative en chargeant avec json.loads d'abord
                try:
                    loaded_dict = json.loads(cleaned_json)
                    return response_schema.model_validate(loaded_dict)
                except Exception as err2:
                    logger.error(f"[{self.name}] Échec validation schéma {response_schema.__name__}: {err2}. Réponse brute: {raw_text[:200]}")
                    raise LLMProviderError(
                        provider=self.name,
                        message=f"Erreur validation Pydantic ({response_schema.__name__}): {err2}",
                        status_code=422
                    )

        # Pas de schéma imposé : tente json.loads, sinon retourne le texte
        try:
            return json.loads(cleaned_json)
        except Exception:
            return raw_text

    def execute_with_retry(
        self,
        call_fn,
        max_retries: int = 2,
        base_delay: float = 0.5
    ) -> Any:
        """Exécute une fonction d'appel API avec retry et backoff exponentiel pour les erreurs transitoires."""
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                return call_fn()
            except Exception as e:
                last_error = e
                err_str = str(e).lower()

                # Détection de 429 (rate limit / quota épuisé)
                is_429 = "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str or "rate limit" in err_str
                # Détection d'erreurs réseau ou indisponibilité serveur 5xx
                is_transient = is_429 or any(code in err_str for code in ["500", "502", "503", "504", "timeout", "unavailable", "connection"])

                if not is_transient or attempt >= max_retries:
                    # Plus de retry, propager l'erreur
                    status_code = 429 if is_429 else 500
                    raise LLMProviderError(
                        provider=self.name,
                        message=str(last_error),
                        status_code=status_code,
                        is_rate_limit=is_429
                    )

                # Backoff exponentiel avant nouvel essai
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(f"[{self.name}] Tentative {attempt}/{max_retries} échouée ({err_str[:80]}). Attente de {delay:.1f}s...")
                time.sleep(delay)

        raise LLMProviderError(provider=self.name, message=str(last_error))
