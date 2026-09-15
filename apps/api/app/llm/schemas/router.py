import logging
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class LLMResult(BaseModel):
    """Résultat normalisé retourné par le LLM Router."""
    data: Any = Field(description="Données structurées (Pydantic model, dict, ou str)")
    provider: str = Field(description="Nom du provider utilisé (gemini, groq, mistral, openrouter)")
    model: str = Field(description="Modèle utilisé pour la génération")
    latency: float = Field(description="Durée de l'appel en secondes")
    tokens: Union[int, Dict[str, int]] = Field(default=0, description="Statistiques de tokens ou total")
    fallback_used: bool = Field(default=False, description="Indique si un fallback a été sollicité après échec d'un provider primaire")

    model_config = {
        "arbitrary_types_allowed": True
    }

class ProviderStats(BaseModel):
    """Métriques d'utilisation en mémoire pour un provider."""
    provider: str
    requests_count: int = 0
    success_count: int = 0
    errors_count: int = 0
    total_latency_seconds: float = 0.0
    total_tokens: int = 0
    last_used_at: Optional[str] = None
    last_error: Optional[str] = None

class LLMError(Exception):
    """Exception de base pour le module LLM Router."""
    pass

class LLMProviderError(LLMError):
    """Erreur spécifique à un provider (429, 500, network, parsing)."""
    def __init__(self, provider: str, message: str, status_code: Optional[int] = None, is_rate_limit: bool = False):
        super().__init__(f"[{provider}] {message} (code: {status_code})")
        self.provider = provider
        self.message = message
        self.status_code = status_code
        self.is_rate_limit = is_rate_limit

class LLMAllProvidersFailedError(LLMError):
    """Exception levée lorsque l'ensemble de la chaîne de fallback a échoué."""
    def __init__(self, task: str, errors: Dict[str, str]):
        super().__init__(f"Tous les providers configurés pour la tâche '{task}' ont échoué: {errors}")
        self.task = task
        self.errors = errors
