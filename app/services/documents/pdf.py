import io
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class PDFGenerator:
    """Générateur de PDF pour CV et lettres de motivation."""

    @classmethod
    def generate_cv_pdf(cls, candidate_profile: Dict[str, Any], tailored_cv: Dict[str, Any]) -> bytes:
        """Génère un PDF épuré et professionnel pour le CV personnalisé."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
            styles = getSampleStyleSheet()

            # Styles personnalisés
            title_style = ParagraphStyle(
                'DocTitle',
                parent=styles['Heading1'],
                fontSize=20,
                leading=24,
                textColor=colors.HexColor('#1E293B'),
                spaceAfter=4
            )
            subtitle_style = ParagraphStyle(
                'DocSubtitle',
                parent=styles['Normal'],
                fontSize=10,
                leading=14,
                textColor=colors.HexColor('#64748B'),
                spaceAfter=12
            )
            section_heading = ParagraphStyle(
                'SectionHeading',
                parent=styles['Heading2'],
                fontSize=12,
                leading=16,
                textColor=colors.HexColor('#0F172A'),
                spaceBefore=10,
                spaceAfter=6
            )
            body_style = ParagraphStyle(
                'Body',
                parent=styles['Normal'],
                fontSize=9.5,
                leading=13,
                textColor=colors.HexColor('#334155'),
                spaceAfter=6
            )

            story = []

            # Entête
            personal = candidate_profile.get("personal", {})
            full_name = f"{personal.get('first_name', '')} {personal.get('last_name', '')}".strip() or candidate_profile.get("name", "Candidat")
            story.append(Paragraph(full_name, title_style))

            contact_parts = [
                personal.get("email"),
                personal.get("phone"),
                personal.get("location"),
                personal.get("linkedin")
            ]
            contact_str = " · ".join([p for p in contact_parts if p])
            story.append(Paragraph(contact_str, subtitle_style))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E2E8F0'), spaceAfter=10))

            # Résumé ciblé
            summary = tailored_cv.get("summary") or candidate_profile.get("summary")
            if summary:
                story.append(Paragraph("PROFIL & OBJECTIF", section_heading))
                story.append(Paragraph(summary, body_style))
                story.append(Spacer(1, 8))

            # Compétences ciblées
            skills = tailored_cv.get("skills", [])
            if skills:
                story.append(Paragraph("COMPÉTENCES CLÉS", section_heading))
                story.append(Paragraph(" • " + " • ".join(skills), body_style))
                story.append(Spacer(1, 8))

            # Expériences sélectionnées
            selected_ids = set(tailored_cv.get("selected_experiences", []))
            all_exps = candidate_profile.get("experiences", [])
            exps_to_render = [e for e in all_exps if not selected_ids or e.get("id") in selected_ids]

            if exps_to_render:
                story.append(Paragraph("PARCOURS PROFESSIONNEL", section_heading))
                for exp in exps_to_render:
                    dates = f"{exp.get('start_date', '')} - {exp.get('end_date') or 'Présent'}"
                    role_text = f"<b>{exp.get('role', '')}</b> — {exp.get('company', '')} ({dates})"
                    story.append(Paragraph(role_text, body_style))
                    if exp.get("description"):
                        story.append(Paragraph(exp.get("description"), body_style))
                    for ach in exp.get("achievements", []):
                        story.append(Paragraph(f"• {ach}", body_style))
                    story.append(Spacer(1, 6))

            doc.build(story)
            pdf_data = buffer.getvalue()
            buffer.close()
            return pdf_data

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
