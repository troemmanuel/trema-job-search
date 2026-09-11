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

DOC_TYPE_DIRS = {"CV": "CV", "LM": "Lettre"}


def build_document_filename(doc_type: str, company: Optional[str], job_title: Optional[str]) -> str:
    """Nom de fichier canonique d'un document (CV ou LM), identique pour le local, Supabase et Notion."""
    clean_company = sanitize_name(company, 30) or "Entreprise"
    clean_title = sanitize_name(job_title, 40)
    if clean_title:
        return f"Emmanuel_TRO_{doc_type}_{clean_company}_{clean_title}.pdf"
    return f"Emmanuel_TRO_{doc_type}_{clean_company}.pdf"


def local_document_path(doc_type: str, company: Optional[str], job_title: Optional[str]) -> Path:
    """Chemin du miroir local d'un document : <LOCAL_STORAGE_DIR>/<Entreprise>/<CV|Lettre>/<fichier>."""
    from app.config import Config
    base_dir = Path(getattr(Config, "LOCAL_STORAGE_DIR", "/Users/trema/Documents/RECHERCHE EMPLOIE/CANDIDATURES"))
    clean_company = sanitize_name(company, 30) or "Entreprise"
    return base_dir / clean_company / DOC_TYPE_DIRS[doc_type] / build_document_filename(doc_type, company, job_title)


def build_letter_payload(
    content: Optional[str],
    job: Optional[Dict[str, Any]] = None,
    prepared_at: Optional[str] = None,
    language: Optional[str] = None,
    mobility: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble les données du template lettre : corps IA + en-tête dérivé de l'offre et de la date de préparation."""
    job = job or {}
    return {
        "content": content or "",
        "job": {
            "company": job.get("company"),
            "title": job.get("title"),
            "location": job.get("location"),
            "reference": job.get("reference") or job.get("source_job_id"),
        },
        "date": prepared_at,
        "language": language,
        "mobility": mobility,
    }


def existing_document_urls(application_id: str, company: Optional[str], job_title: Optional[str],
                           has_cv: bool = True, has_letter: bool = True) -> tuple[Optional[str], Optional[str]]:
    """URLs signées (cv_url, letter_url) des PDF déjà présents dans le bucket privé ; None si absents.

    Tente le nom canonique, puis les anciens noms fixes (cv.pdf / cover-letter.pdf) des premières candidatures.
    """
    def _first_existing(candidates):
        for name in candidates:
            url = supabase_service.get_document_url("applications", f"applications/{application_id}/{name}")
            if url:
                return url
        return None

    cv_url = _first_existing([build_document_filename("CV", company, job_title), "cv.pdf"]) if has_cv else None
    letter_url = _first_existing([build_document_filename("LM", company, job_title), "cover-letter.pdf"]) if has_letter else None
    return cv_url, letter_url


class DocumentRenderer:
    """Orchestre le rendu et le stockage des documents d'une candidature."""

    @classmethod
    def _save_local_backup(cls, pdf_bytes: bytes, target_file: Path) -> None:
        """Tente de sauvegarder le document dans le dossier local du candidat."""
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_bytes(pdf_bytes)
            logger.info(f"Fichier sauvegardé localement : {target_file}")
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
        filename = build_document_filename("CV", company, job_title)

        # 1. Sauvegarde locale (si autorisée par l'environnement)
        cls._save_local_backup(pdf_bytes, local_document_path("CV", company, job_title))

        # 2. Upload Supabase Storage
        storage_path = f"applications/{application_id}/{filename}"
        file_url = supabase_service.upload_document(
            bucket="applications",
            path=storage_path,
            file_bytes=pdf_bytes,
            content_type="application/pdf"
        )
        return file_url or storage_path

    @classmethod
    def render_and_save_letter(
        cls,
        application_id: str,
        candidate_profile: Dict[str, Any],
        cover_letter: Dict[str, Any],
        company: Optional[str] = None,
        job_title: Optional[str] = None,
        job: Optional[Dict[str, Any]] = None,
        prepared_at: Optional[str] = None,
        mobility: Optional[str] = None
    ) -> str:
        payload = build_letter_payload(
            cover_letter.get("content"),
            job=job or {"company": company, "title": job_title},
            prepared_at=prepared_at,
            language=cover_letter.get("language"),
            mobility=mobility,
        )
        pdf_bytes = pdf_generator.generate_letter_pdf(candidate_profile, payload)
        filename = build_document_filename("LM", company, job_title)

        # 1. Sauvegarde locale
        cls._save_local_backup(pdf_bytes, local_document_path("LM", company, job_title))

        # 2. Upload Supabase Storage
        storage_path = f"applications/{application_id}/{filename}"
        file_url = supabase_service.upload_document(
            bucket="applications",
            path=storage_path,
            file_bytes=pdf_bytes,
            content_type="application/pdf"
        )
        return file_url or storage_path

document_renderer = DocumentRenderer()

