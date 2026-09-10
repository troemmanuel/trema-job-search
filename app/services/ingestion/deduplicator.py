import logging
from typing import Optional
from urllib.parse import urlparse, urlunparse
from app.services.storage import supabase_service

logger = logging.getLogger(__name__)

class Deduplicator:
    """Vérifie si une offre d'emploi a déjà été importée."""

    @staticmethod
    def normalize_url(url: str) -> str:
        """Nettoie l'URL pour supprimer les query params de tracking (ex: utm_*)."""
        parsed = urlparse(url.strip())
        # Enlever fragments et query strings superflus si besoin
        clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        return clean_url.rstrip('/')

    @classmethod
    def is_duplicate(cls, source: str, source_job_id: Optional[str], url: str) -> bool:
        """Retourne True si l'offre existe déjà dans Supabase."""
        if not supabase_service.client:
            return False

        try:
            # 1. Vérification par (source, source_job_id)
            if source_job_id:
                res = supabase_service.client.table("jobs").select("id").eq("source", source).eq("source_job_id", source_job_id).execute()
                if res.data:
                    return True

            # 2. Vérification de secours par URL canonique
            clean_url = cls.normalize_url(url)
            res_url = supabase_service.client.table("jobs").select("id").eq("url", clean_url).execute()
            if res_url.data:
                return True

            return False
        except Exception as e:
            logger.error(f"Erreur lors du contrôle de déduplication : {e}")
            return False

deduplicator = Deduplicator()
