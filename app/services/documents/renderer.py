import logging
from typing import Dict, Any
from app.services.documents.pdf import pdf_generator
from app.services.storage.supabase import supabase_service

logger = logging.getLogger(__name__)

class DocumentRenderer:
    """Orchestre le rendu et le stockage des documents d'une candidature."""

    @classmethod
    def render_and_save_cv(cls, application_id: str, candidate_profile: Dict[str, Any], tailored_cv: Dict[str, Any]) -> str:
        pdf_bytes = pdf_generator.generate_cv_pdf(candidate_profile, tailored_cv)
        storage_path = f"applications/{application_id}/cv.pdf"
        file_url = supabase_service.upload_document(
            bucket="applications",
            path=storage_path,
            file_bytes=pdf_bytes,
            content_type="application/pdf"
        )
        return file_url or storage_path

    @classmethod
    def render_and_save_letter(cls, application_id: str, candidate_profile: Dict[str, Any], cover_letter: Dict[str, Any]) -> str:
        pdf_bytes = pdf_generator.generate_letter_pdf(candidate_profile, cover_letter)
        storage_path = f"applications/{application_id}/cover-letter.pdf"
        file_url = supabase_service.upload_document(
            bucket="applications",
            path=storage_path,
            file_bytes=pdf_bytes,
            content_type="application/pdf"
        )
        return file_url or storage_path

document_renderer = DocumentRenderer()
