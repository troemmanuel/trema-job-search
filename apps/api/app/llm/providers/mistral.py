import json
import logging
import time
from typing import Any, Dict, Optional, Type
import httpx
from pydantic import BaseModel

from app.llm.providers.base import BaseLLMProvider
from app.llm.schemas.router import LLMResult, LLMProviderError

logger = logging.getLogger(__name__)

class MistralProvider(BaseLLMProvider):
    """Fournisseur pour Mistral AI via httpx (compatible OpenAI Chat Completions)."""

    name: str = "mistral"
    API_URL: str = "https://api.mistral.ai/v1/chat/completions"
    DEFAULT_MODEL: str = "ministral-8b-latest"
    CANDIDATE_MODELS: list = [
        "ministral-8b-latest",
        "ministral-14b-latest",
        "codestral-latest",
        "mistral-small-latest"
    ]

    MODEL_ALIASES: dict = {
        "mistral-small-latest": "ministral-8b-latest",
        "mistral-medium-latest": "ministral-14b-latest",
    }

    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None):
        model = default_model or self.DEFAULT_MODEL
        model = self.MODEL_ALIASES.get(model, model)
        super().__init__(api_key=api_key, default_model=model)

    def generate(
        self,
        prompt: str,
        response_schema: Optional[Type[BaseModel]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        model: Optional[str] = None
    ) -> LLMResult:
        if not self.is_configured():
            raise LLMProviderError(self.name, "MISTRAL_API_KEY non configurée", status_code=401)

        raw_target = model or self.default_model or self.DEFAULT_MODEL
        target_model = self.MODEL_ALIASES.get(raw_target, raw_target)

        messages = []
        sys_content = system_instruction or ""
        if response_schema:
            schema_json = json.dumps(response_schema.model_json_schema())
            schema_inst = f"\nYou MUST respond with a valid JSON object matching this schema:\n{schema_json}"
            sys_content = (sys_content + "\n" + schema_inst).strip()

        if sys_content:
            messages.append({"role": "system", "content": sys_content})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Modèles à essayer (modèle cible puis candidats de secours)
        models_to_try = [target_model] + [m for m in self.CANDIDATE_MODELS if m != target_model]
        last_error = None
        data = None
        latency = 0.0
        effective_model = target_model

        for current_model in models_to_try:
            effective_model = current_model
            payload: Dict[str, Any] = {
                "model": current_model,
                "messages": messages,
                "temperature": temperature,
            }
            if response_schema:
                payload["response_format"] = {"type": "json_object"}

            def _do_call():
                start_t = time.time()
                with httpx.Client(timeout=45.0) as client:
                    res = client.post(self.API_URL, headers=headers, json=payload)
                    elapsed = time.time() - start_t

                    if res.status_code == 429:
                        raise LLMProviderError(self.name, f"Rate limit / Quota dépassé (429): {res.text}", status_code=429, is_rate_limit=True)
                    if res.status_code == 404:
                        raise LLMProviderError(self.name, f"Modèle indisponible ({res.status_code}): {res.text}", status_code=404)
                    if res.status_code >= 400:
                        raise LLMProviderError(self.name, f"Erreur API ({res.status_code}): {res.text}", status_code=res.status_code)

                    return res.json(), elapsed

            try:
                data, latency = self.execute_with_retry(_do_call)
                break
            except LLMProviderError as pe:
                last_error = pe
                if pe.status_code in (429, 404) and current_model != models_to_try[-1]:
                    logger.warning(f"[MistralProvider] Modèle '{current_model}' en échec ({pe.status_code}). Essai du modèle alternatif...")
                    continue
                raise

        if not data and last_error:
            raise last_error

        try:
            raw_text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as err:
            raise LLMProviderError(self.name, f"Format de réponse inattendu: {err}", status_code=500)

        usage = data.get("usage", {})
        tokens = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

        parsed_data = self.parse_and_validate(raw_text, response_schema=response_schema)

        return LLMResult(
            data=parsed_data,
            provider=self.name,
            model=effective_model,
            latency=round(latency, 3),
            tokens=tokens,
            fallback_used=False
        )
