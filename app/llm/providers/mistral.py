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

    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = "mistral-small-latest"):
        super().__init__(api_key=api_key, default_model=default_model or "mistral-small-latest")

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

        target_model = model or self.default_model or "mistral-small-latest"

        messages = []
        sys_content = system_instruction or ""
        if response_schema:
            schema_json = json.dumps(response_schema.model_json_schema())
            schema_inst = f"\nYou MUST respond with a valid JSON object matching this schema:\n{schema_json}"
            sys_content = (sys_content + "\n" + schema_inst).strip()

        if sys_content:
            messages.append({"role": "system", "content": sys_content})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_schema:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        def _do_call():
            start_t = time.time()
            with httpx.Client(timeout=45.0) as client:
                res = client.post(self.API_URL, headers=headers, json=payload)
                elapsed = time.time() - start_t

                if res.status_code == 429:
                    raise LLMProviderError(self.name, f"Rate limit / Quota dépassé (429): {res.text}", status_code=429, is_rate_limit=True)
                if res.status_code >= 400:
                    raise LLMProviderError(self.name, f"Erreur API ({res.status_code}): {res.text}", status_code=res.status_code)

                return res.json(), elapsed

        data, latency = self.execute_with_retry(_do_call)

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
            model=target_model,
            latency=round(latency, 3),
            tokens=tokens,
            fallback_used=False
        )
