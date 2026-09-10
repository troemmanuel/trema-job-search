import logging
from typing import Dict, Any, Optional
from app.schemas.job import JobImport
from app.services.ingestion.parser import job_parser
from app.services.ingestion.deduplicator import deduplicator
from app.services.storage import supabase_service

logger = logging.getLogger(__name__)

class JobImporter:
    """Orchestre la réception, déduplication et persistance des offres."""

    @classmethod
    def import_job(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        source = payload.get("source", "MANUAL")
        source_job_id = payload.get("source_job_id")
        url = payload.get("url", "").strip()

        if not url or not payload.get("title"):
            raise ValueError("L'URL et le titre de l'offre sont obligatoires.")

        # Vérification déduplication
        if deduplicator.is_duplicate(source, source_job_id, url):
            return {
                "status": "DUPLICATE",
                "message": f"Offre déjà existante ({source}:{source_job_id or url})"
            }

        # Normalisation
        normalized = job_parser.normalize(payload)

        job_record = {
            "source": source,
            "source_job_id": source_job_id,
            "title": payload.get("title"),
            "company": payload.get("company"),
            "location": payload.get("location"),
            "contract_type": payload.get("contract_type"),
            "salary_min": payload.get("salary_min"),
            "salary_max": payload.get("salary_max"),
            "salary_currency": payload.get("salary_currency", "EUR"),
            "url": deduplicator.normalize_url(url),
            "description": payload.get("description"),
            "raw_data": payload,
            "normalized_data": normalized.model_dump(),
            "status": "NEW"
        }

        if supabase_service.client:
            res = supabase_service.client.table("jobs").insert(job_record).execute()
            created_job = res.data[0] if res.data else job_record
            return {
                "status": "CREATED",
                "job": created_job
            }
        else:
            logger.info(f"Supabase non connecté. Offre simulée : {job_record['title']}")
            return {
                "status": "SIMULATED",
                "job": job_record
            }

job_importer = JobImporter()
