import logging
from typing import Optional, Any, Dict
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
        try:
            res = self.client.table("jobs").select("*").order("created_at", desc=True).limit(limit).execute()
            return res.data or []
        except Exception as e:
            logger.warning(f"Impossible de récupérer les offres Supabase: {e}")
            return []

    def get_jobs_paginated(
        self,
        page: int = 1,
        per_page: int = 15,
        status: Optional[str] = None,
        contract_type: Optional[str] = None,
        min_score: Optional[int] = None,
        search: Optional[str] = None,
        order_by: str = "created_at",
        desc: bool = True
    ) -> Dict[str, Any]:
        """
        Récupère les offres d'emploi avec pagination et filtres.
        Par défaut : ordonnées du plus récent au plus ancien (created_at DESC).
        """
        import math

        page = max(1, int(page or 1))
        per_page = max(1, min(int(per_page or 15), 100))
        empty_result = {
            "items": [],
            "total": 0,
            "page": page,
            "per_page": per_page,
            "total_pages": 1,
            "has_prev": False,
            "has_next": False,
            "prev_page": None,
            "next_page": None
        }

        if not self.client:
            return empty_result

        try:
            query = self.client.table("jobs").select("*", count="exact")

            # Filtre par statut
            if status and status.upper() != "ALL":
                query = query.eq("status", status.upper())

            # Filtre par type de contrat
            if contract_type and contract_type.upper() != "ALL":
                query = query.eq("contract_type", contract_type)

            # Filtre par score minimum
            if min_score is not None and int(min_score) > 0:
                query = query.gte("match_score", int(min_score))

            # Filtre par recherche textuelle (titre, entreprise, localisation)
            if search and search.strip():
                s = search.strip()
                query = query.or_(f"title.ilike.%{s}%,company.ilike.%{s}%,location.ilike.%{s}%")

            # Tri systématique du plus récent au plus ancien
            query = query.order(order_by, desc=desc)

            # Pagination range (start, end) inclusif
            start = (page - 1) * per_page
            end = start + per_page - 1
            query = query.range(start, end)

            res = query.execute()
            items = res.data or []
            total = res.count if res.count is not None else len(items)
            total_pages = max(1, math.ceil(total / per_page))

            return {
                "items": items,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "has_prev": page > 1,
                "has_next": page < total_pages,
                "prev_page": page - 1 if page > 1 else None,
                "next_page": page + 1 if page < total_pages else None
            }

        except Exception as e:
            logger.warning(f"Erreur lors de la récupération paginée des offres: {e}")
            return empty_result

    def get_applications(self, limit: int = 50):
        if not self.client:
            return []
        try:
            res = self.client.table("applications").select("*, jobs(*)").order("created_at", desc=True).limit(limit).execute()
            return res.data or []
        except Exception as e:
            logger.warning(f"Impossible de récupérer les candidatures Supabase: {e}")
            return []

    def get_applications_paginated(
        self,
        page: int = 1,
        per_page: int = 15,
        status: Optional[str] = None,
        min_score: Optional[int] = None,
        search: Optional[str] = None,
        order_by: str = "created_at",
        desc: bool = True
    ) -> Dict[str, Any]:
        """
        Récupère les candidatures avec pagination et filtres.
        Par défaut : ordonnées du plus récent au plus ancien (created_at DESC).
        """
        import math

        page = max(1, int(page or 1))
        per_page = max(1, min(int(per_page or 15), 100))
        empty_result = {
            "items": [],
            "total": 0,
            "page": page,
            "per_page": per_page,
            "total_pages": 1,
            "has_prev": False,
            "has_next": False,
            "prev_page": None,
            "next_page": None
        }

        if not self.client:
            return empty_result

        try:
            query = self.client.table("applications").select("*, jobs(*)", count="exact")

            if status and status.upper() != "ALL":
                query = query.eq("status", status.upper())

            if min_score is not None and int(min_score) > 0:
                query = query.gte("match_score", int(min_score))

            query = query.order(order_by, desc=desc)

            start = (page - 1) * per_page
            end = start + per_page - 1
            query = query.range(start, end)

            res = query.execute()
            items = res.data or []

            # Si recherche textuelle sur l'offre associée (titre / entreprise)
            if search and search.strip():
                s_lower = search.strip().lower()
                items = [
                    app for app in items
                    if (app.get("jobs") and (
                        s_lower in (app["jobs"].get("title") or "").lower() or
                        s_lower in (app["jobs"].get("company") or "").lower()
                    ))
                ]
                total = len(items)
                total_pages = max(1, math.ceil(total / per_page))
            else:
                total = res.count if res.count is not None else len(items)
                total_pages = max(1, math.ceil(total / per_page))

            return {
                "items": items,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "has_prev": page > 1,
                "has_next": page < total_pages,
                "prev_page": page - 1 if page > 1 else None,
                "next_page": page + 1 if page < total_pages else None
            }

        except Exception as e:
            logger.warning(f"Erreur lors de la récupération paginée des candidatures: {e}")
            return empty_result

    def get_active_candidate_profile(self):
        if not self.client:
            return None
        try:
            res = self.client.table("candidate_profiles").select("*").eq("is_active", True).limit(1).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.warning(f"Impossible de récupérer le profil candidat Supabase: {e}")
            return None

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
