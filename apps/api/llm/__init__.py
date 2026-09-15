"""Alias de compatibilité pour importer directement depuis `llm` ou `app.llm`."""
from app.llm import (
    LLMRouter,
    router,
    LLMResult,
    ProviderStats,
    LLMError,
    LLMProviderError,
    LLMAllProvidersFailedError
)

__all__ = [
    "LLMRouter",
    "router",
    "LLMResult",
    "ProviderStats",
    "LLMError",
    "LLMProviderError",
    "LLMAllProvidersFailedError"
]
