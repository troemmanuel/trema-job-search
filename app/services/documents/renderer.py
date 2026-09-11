import logging
import re
import unicodedata
from pathlib import Path
from typing import Optional, Dict, Any
from app.services.documents.pdf import pdf_generator
from app.services.storage import supabase_service

logger = logging.getLogger(__name__)

def sanitize_name(text: Optional[str], max_len: int = 40) -> str:
    """Nettoie une chaîne pour former un nom de fichier ou de clé S3 valide (ASCII strict sans accents)."""
    if not text:
        return ""
    # Décomposition et suppression des accents (NFKD)
    normalized = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    cleaned = re.sub(r'[^a-zA-Z0-9_\s-]', '', normalized).strip()
    cleaned = re.sub(r'[-\s]+', '_', cleaned)
    return cleaned[:max_len]

class DocumentRenderer:
    """Orchestre le rendu et le stockage des documents d'une candidature."""

    @classmethod
    def _save_local_backup(cls, pdf_bytes: bytes, clean_company: str, doc_type: str, filename: str) -> None:
        """Tente de sauvegarder le document dans le dossier local du candidat."""
        try:
            from app.config import Config
            base_dir = Path(getattr(Config, "LOCAL_STORAGE_DIR", "/Users/trema/Documents/RECHERCHE EMPLOIE/CANDIDATURES"))
            target_dir = base_dir / clean_company / doc_type
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / filename
            target_file.write_bytes(pdf_bytes)
            logger.info(f"Fichier {doc_type} sauvegardé localement : {target_file}")
        except Exception as e:
            logger.debug(f"Sauvegarde locale ignorée ou restreinte ({e})")

    @classmethod
    def render_and_save_cv(
        cls,
        application_id: str,
        candidate_profile: Dict[str, Any],
        tailored_cv: Dict[str, Any],
        company: Optional[str] = None,
        job_title: Optional[str] = None
    ) -> str:
        pdf_bytes = pdf_generator.generate_cv_pdf(candidate_profile, tailored_cv)
        clean_company = sanitize_name(company, 30) or "Entreprise"
        clean_title = sanitize_name(job_title, 40)
        filename = f"Emmanuel_TRO_CV_{clean_company}_{clean_title}.pdf" if clean_title else f"Emmanuel_TRO_CV_{clean_company}.pdf"

        # 1. Sauvegarde locale (si autorisée par l'environnement)
        cls._save_local_backup(pdf_bytes, clean_company, "CV", filename)

        # 2. Upload Supabase Storage
        storage_path = f"applications/{application_id}/{filename}"
        file_url = supabase_service.upload_document(
            bucket="applications",
            path=storage_path,
            file_bytes=pdf_bytes,
            content_type="application/pdf"
        )
        if not file_url and supabase_service.config and supabase_service.config.SUPABASE_URL:
            file_url = f"{supabase_service.config.SUPABASE_URL}/storage/v1/object/public/applications/{storage_path}"
        return file_url or storage_path

    @classmethod
    def render_and_save_letter(
        cls,
        application_id: str,
        candidate_profile: Dict[str, Any],
        cover_letter: Dict[str, Any],
        company: Optional[str] = None,
        job_title: Optional[str] = None
    ) -> str:
        pdf_bytes = pdf_generator.generate_letter_pdf(candidate_profile, cover_letter)
        clean_company = sanitize_name(company, 30) or "Entreprise"
        clean_title = sanitize_name(job_title, 40)
        filename = f"Emmanuel_TRO_LM_{clean_company}_{clean_title}.pdf" if clean_title else f"Emmanuel_TRO_LM_{clean_company}.pdf"

        # 1. Sauvegarde locale
        cls._save_local_backup(pdf_bytes, clean_company, "Lettre", filename)

        # 2. Upload Supabase Storage
        storage_path = f"applications/{application_id}/{filename}"
        file_url = supabase_service.upload_document(
            bucket="applications",
            path=storage_path,
            file_bytes=pdf_bytes,
            content_type="application/pdf"
        )
        if not file_url and supabase_service.config and supabase_service.config.SUPABASE_URL:
            file_url = f"{supabase_service.config.SUPABASE_URL}/storage/v1/object/public/applications/{storage_path}"
        return file_url or storage_path

document_renderer = DocumentRenderer()

