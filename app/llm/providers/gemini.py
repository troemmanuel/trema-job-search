import logging
import time
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel

from app.llm.providers.base import BaseLLMProvider
from app.llm.schemas.router import LLMResult, LLMProviderError

logger = logging.getLogger(__name__)

class GeminiProvider(BaseLLMProvider):
    """Fournisseur pour Google Gemini via le SDK officiel google-genai."""

    name: str = "gemini"

    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = "gemini-2.5-flash"):
        super().__init__(api_key=api_key, default_model=default_model or "gemini-2.5-flash")
        self._client = None

    @property
    def client(self):
        if self._client is None and self.is_configured():
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"[gemini] Erreur initialisation client GenAI: {e}")
        return self._client

    def generate(
        self,
        prompt: str,
        response_schema: Optional[Type[BaseModel]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        model: Optional[str] = None
    ) -> LLMResult:
        if not self.is_configured():
            raise LLMProviderError(self.name, "GEMINI_API_KEY non configurée", status_code=401)
        if not self.client:
            raise LLMProviderError(self.name, "Client Google GenAI indisponible", status_code=500)

        target_model = model or self.default_model or "gemini-2.5-flash"
        from google.genai import types

        config_kwargs: Dict[str, Any] = {
            "temperature": temperature,
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True)
        }
        if response_schema:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        call_config = types.GenerateContentConfig(**config_kwargs)

        def _do_call():
            start_t = time.time()
            resp = self.client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=call_config
            )
            elapsed = time.time() - start_t
            return resp, elapsed

        # Exécute avec retry
        response, latency = self.execute_with_retry(_do_call)

        # Extraction des tokens si disponible
        tokens_data: Dict[str, int] = {}
        total_tokens = 0
        try:
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                p_tok = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                c_tok = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
                t_tok = getattr(response.usage_metadata, "total_token_count", 0) or (p_tok + c_tok)
                tokens_data = {
                    "prompt_tokens": p_tok,
                    "completion_tokens": c_tok,
                    "total_tokens": t_tok
                }
                total_tokens = t_tok
        except Exception:
            pass

        raw_text = response.text or ""
        parsed_data = self.parse_and_validate(raw_text, response_schema=response_schema)

        return LLMResult(
            data=parsed_data,
            provider=self.name,
            model=target_model,
            latency=round(latency, 3),
            tokens=tokens_data if tokens_data else total_tokens,
            fallback_used=False
        )
