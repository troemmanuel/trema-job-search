from datetime import datetime, timezone
import hashlib
import json
import logging
import threading
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel

from app.llm.schemas.router import LLMResult

logger = logging.getLogger(__name__)

class CacheEntry:
    """Entrée de cache avec horodatage d'expiration."""
    def __init__(self, result: LLMResult, expires_at: Optional[float] = None):
        self.result = result
        self.expires_at = expires_at

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        import time
        return time.time() > self.expires_at

class LLMCache:
    """Cache en mémoire thread-safe avec clés SHA-256 et expiration TTL."""

    def __init__(self, default_ttl_seconds: int = 86400, max_size: int = 1000):
        self.default_ttl_seconds = default_ttl_seconds
        self.max_size = max_size
        self._entries: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self.hits: int = 0
        self.misses: int = 0

    def compute_key(
        self,
        task: str,
        prompt: str,
        response_schema: Optional[Type[BaseModel]] = None,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """Calcule un hash SHA-256 déterministe pour une requête LLM."""
        schema_name = response_schema.__name__ if response_schema else "None"
        sys_str = system_instruction or ""
        model_str = model or ""

        raw_key = f"task={task}|schema={schema_name}|model={model_str}|sys={sys_str}|prompt={prompt}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[LLMResult]:
        """Récupère un résultat en cache s'il est présent et non expiré."""
        with self._lock:
            entry = self._entries.get(key)
            if not entry:
                self.misses += 1
                return None

            if entry.is_expired():
                del self._entries[key]
                self.misses += 1
                return None

            self.hits += 1
            cached = entry.result
            # Retourne une copie avec latency=0.0
            return LLMResult(
                data=cached.data,
                provider=cached.provider,
                model=cached.model,
                latency=0.0,
                tokens=cached.tokens,
                fallback_used=False
            )

    def set(self, key: str, result: LLMResult, ttl_seconds: Optional[int] = None):
        """Enregistre un résultat en cache avec TTL."""
        import time
        with self._lock:
            # Nettoyage simple si la taille max est atteinte
            if len(self._entries) >= self.max_size:
                # Supprimer les entrées expirées
                now = time.time()
                keys_to_remove = [k for k, v in self._entries.items() if v.is_expired()]
                for k in keys_to_remove:
                    del self._entries[k]
                # Si encore plein, supprimer la plus ancienne
                if len(self._entries) >= self.max_size:
                    first_key = next(iter(self._entries))
                    del self._entries[first_key]

            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
            expires_at = time.time() + ttl if ttl > 0 else None
            self._entries[key] = CacheEntry(result=result, expires_at=expires_at)

    def clear(self):
        """Vide le cache."""
        with self._lock:
            self._entries.clear()
            self.hits = 0
            self.misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les métriques d'efficacité du cache."""
        with self._lock:
            total = self.hits + self.misses
            hit_ratio = round((self.hits / total * 100), 2) if total > 0 else 0.0
            return {
                "size": len(self._entries),
                "hits": self.hits,
                "misses": self.misses,
                "hit_ratio_percent": hit_ratio
            }

llm_cache = LLMCache()
