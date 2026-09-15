import io
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class PDFGenerator:
    """Générateur de PDF pour CV et lettres de motivation."""

    @classmethod
    def generate_cv_pdf(cls, candidate_profile: Dict[str, Any], tailored_cv: Dict[str, Any]) -> bytes:
        """Génère le CV via le template classique (mise en page figée, contenu variable)."""
        try:
            from app.services.documents.templates.cv_classic import render_cv
            return render_cv(candidate_profile, tailored_cv)
        except ImportError:
            logger.warning("ReportLab non installé, génération d'un PDF brut textuel.")
            return b"%PDF-1.4 Mock PDF Content"

    @classmethod
    def generate_letter_pdf(cls, candidate_profile: Dict[str, Any], cover_letter: Dict[str, Any]) -> bytes:
        """Génère la lettre via le template classique.

        `cover_letter` : content (corps), et optionnellement job (company/title/location/reference),
        date (ISO), language, subject, recipient_lines.
        """
        try:
            from app.services.documents.templates.letter_classic import render_letter
            return render_letter(candidate_profile, cover_letter)
        except ImportError:
            return b"%PDF-1.4 Mock Letter PDF Content"

pdf_generator = PDFGenerator()
