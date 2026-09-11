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
        """Génère un PDF pour la lettre de motivation."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
            styles = getSampleStyleSheet()

            body_style = ParagraphStyle(
                'LetterBody',
                parent=styles['Normal'],
                fontSize=11,
                leading=16,
                textColor=colors.HexColor('#1E293B'),
                spaceAfter=12
            )

            story = []
            personal = candidate_profile.get("personal", {})
            full_name = f"{personal.get('first_name', '')} {personal.get('last_name', '')}".strip() or "Candidat"
            story.append(Paragraph(f"<b>{full_name}</b>", body_style))
            if personal.get("email"):
                story.append(Paragraph(personal.get("email"), body_style))
            story.append(Spacer(1, 20))

            content = cover_letter.get("content", "")
            for para in content.split("\n\n"):
                if para.strip():
                    story.append(Paragraph(para.replace("\n", "<br/>"), body_style))

            doc.build(story)
            pdf_data = buffer.getvalue()
            buffer.close()
            return pdf_data
        except ImportError:
            return b"%PDF-1.4 Mock Letter PDF Content"

pdf_generator = PDFGenerator()
