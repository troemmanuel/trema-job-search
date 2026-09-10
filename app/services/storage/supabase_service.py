import logging
from typing import Optional, Any
from app.config import Config

logger = logging.getLogger(__name__)

class SupabaseService:
    """Service d'interaction avec Supabase (PostgreSQL & Storage)."""

    def __init__(self, config: Config = None):
        self.config = config or Config()
        self._client: Optional[Any] = None

    @property
    def client(self):
        if self._client is None:
            if not self.config.SUPABASE_URL or not self.config.SUPABASE_KEY:
                logger.warning("SUPABASE_URL ou SUPABASE_KEY non configurés. Mode dégradé/local.")
                return None
            try:
                from supabase import create_client
                self._client = create_client(self.config.SUPABASE_URL, self.config.SUPABASE_KEY)
            except Exception as e:
                logger.error(f"Erreur lors de l'initialisation du client Supabase: {e}")
                return None
        return self._client

    def is_configured(self) -> bool:
        return bool(self.config.SUPABASE_URL and self.config.SUPABASE_KEY)

    # Database helpers
    def get_jobs(self, limit: int = 50):
        if not self.client:
            return []
        res = self.client.table("jobs").select("*").order("created_at", desc=True).limit(limit).execute()
        return res.data

    def get_applications(self, limit: int = 50):
        if not self.client:
            return []
        res = self.client.table("applications").select("*, jobs(*)").order("created_at", desc=True).limit(limit).execute()
        return res.data

    def get_active_candidate_profile(self):
        if not self.client:
            return None
        res = self.client.table("candidate_profiles").select("*").eq("is_active", True).limit(1).execute()
        return res.data[0] if res.data else None

    # Storage helpers
    def upload_document(self, bucket: str, path: str, file_bytes: bytes, content_type: str) -> Optional[str]:
        if not self.client:
            logger.warning(f"Simulé: upload de {path} dans {bucket} ({len(file_bytes)} bytes)")
            return f"local://{bucket}/{path}"
        try:
            self.client.storage.from_(bucket).upload(path, file_bytes, {"content-type": content_type, "upsert": "true"})
            return self.client.storage.from_(bucket).get_public_url(path)
        except Exception as e:
            logger.error(f"Erreur upload document Supabase Storage: {e}")
            return None

# Singleton par défaut
supabase_service = SupabaseService()
