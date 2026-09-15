"""
Template lettre de motivation « classique » : mise en page figée, une page A4.

L'en-tête (expéditeur, destinataire, date, objet) est dérivé des données (profil, offre, date de
préparation). L'IA ne fournit que le corps : de la formule d'appel à la formule de politesse.
"""
import io
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.documents.templates.common import location_line, sender_city
from app.services.documents.templates.fonts import register_font_family

_SANS = register_font_family("CVSans")

THEME = {
    "font": _SANS[0],
    "font_bold": _SANS[1],
    "text": colors.HexColor("#111111"),
    "margin_x": 20 * mm,
    "margin_y": 18 * mm,
    "body_size": 10.5,
    "body_leading": 15,
    "min_body_size": 9,   # borne basse de la réduction automatique pour tenir sur une page
}

LABELS = {
    "fr": {
        "recruiting": "Service Recrutement",
        "subject": "Objet : candidature au poste {of}{title}",
        "reference": "réf. {ref}",
        "greeting": "Madame, Monsieur,",
        "closing": "Je vous prie d'agréer, Madame, Monsieur, mes salutations distinguées.",
        "date": "{city}, le {day} {month} {year}",
        "months": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
                   "septembre", "octobre", "novembre", "décembre"],
        "greeting_markers": ("madame", "monsieur", "bonjour", "chère", "cher "),
        "closing_markers": ("salutations", "agréer", "cordialement", "respectueusement", "considération"),
    },
    "en": {
        "recruiting": "Recruitment Team",
        "subject": "Subject: application for the {title} position",
        "reference": "ref. {ref}",
        "greeting": "Dear Hiring Manager,",
        "closing": "Yours sincerely,",
        "date": "{city}, {month} {day}, {year}",
        "months": ["January", "February", "March", "April", "May", "June", "July", "August",
                   "September", "October", "November", "December"],
        "greeting_markers": ("dear", "hello", "hi ", "to whom"),
        "closing_markers": ("sincerely", "regards", "faithfully", "thank you for your consideration"),
    },
}

SEP = " · "


def _esc(value: Any) -> str:
    return escape(str(value)) if value is not None else ""


def _french_of(title: str) -> str:
    """« de » ou « d' » selon l'initiale du titre : « d'Ingénieur », « de Développeur »."""
    return "d'" if title[:1].lower() in "aeiouyhéèêàâîôû" else "de "


def _parse_date(raw: Any) -> date:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return datetime.fromisoformat(raw.strip().replace("Z", "+00:00")).date()
        except ValueError:
            pass
    return date.today()




def _paragraphs(content: str) -> List[str]:
    """Découpe le corps en paragraphes : lignes vides, ou à défaut retours simples."""
    text = (content or "").replace("\r\n", "\n").strip()
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(parts) <= 1 and "\n" in text:
        parts = [p.strip() for p in text.split("\n") if p.strip()]
    return [re.sub(r"\s*\n\s*", " ", p) for p in parts]


def _detect_language(content: str) -> str:
    """Repli quand la langue n'est pas stockée : formule d'appel anglaise → « en », sinon « fr »."""
    first = _paragraphs(content)[:1]
    if first and any(first[0].lower().startswith(m) for m in LABELS["en"]["greeting_markers"]):
        return "en"
    return "fr"


class ClassicLetterTemplate:
    """Construit le PDF à partir du profil (dict) et de la lettre (dict : content, job, date, language...)."""

    def __init__(self, profile: Dict[str, Any], letter: Dict[str, Any]):
        self.profile = profile or {}
        self.letter = letter or {}
        self.job = self.letter.get("job") or {}
        language = self.letter.get("language") or _detect_language(self.letter.get("content") or "")
        self.labels = LABELS.get(language.lower()[:2], LABELS["fr"])
        self.is_fr = self.labels is LABELS["fr"]

    # -- Contenu dérivé ----------------------------------------------------
    def sender_lines(self) -> List[str]:
        personal = self.profile.get("personal") or {}
        lines = [location_line(personal.get("location"), self.letter.get("mobility"))]
        lines.append(SEP.join(x for x in (personal.get("email"), personal.get("phone")) if x))
        lines.append(personal.get("linkedin"))
        return [l for l in lines if l]

    def recipient_lines(self) -> List[str]:
        explicit = self.letter.get("recipient_lines")
        if explicit:
            return [l for l in explicit if l]
        return [l for l in (self.job.get("company"), self.labels["recruiting"], self.job.get("location")) if l]

    def date_line(self) -> str:
        d = _parse_date(self.letter.get("date"))
        city = sender_city((self.profile.get("personal") or {}).get("location"))
        text = self.labels["date"].format(city=city, day=d.day, month=self.labels["months"][d.month - 1], year=d.year)
        return text.lstrip(", ").strip()

    def subject_line(self) -> Optional[str]:
        if self.letter.get("subject"):
            return self.letter["subject"]
        title = (self.job.get("title") or "").strip()
        if not title:
            return None
        subject = self.labels["subject"].format(title=title, of=_french_of(title) if self.is_fr else "")
        ref = str(self.job.get("reference") or "").strip()
        if ref and re.fullmatch(r"[A-Za-z0-9._/-]{2,20}", ref):
            subject += " - " + self.labels["reference"].format(ref=ref)
        return subject

    def body_paragraphs(self) -> List[str]:
        """Corps normalisé : formule d'appel, paragraphes, formule de politesse ; sans signature."""
        paragraphs = _paragraphs(self.letter.get("content") or "")
        full_name = self.full_name().lower()
        # Retire une signature éventuellement produite par l'IA (le template la rend en gras)
        while paragraphs and paragraphs[-1].lower().strip(" ,.") in (full_name, self.profile.get("name", "").lower()):
            paragraphs.pop()
        if not paragraphs:
            return []
        first, last = paragraphs[0].lower(), paragraphs[-1].lower()
        if not any(first.startswith(m) for m in self.labels["greeting_markers"]):
            paragraphs.insert(0, self.labels["greeting"])
        if not any(m in last for m in self.labels["closing_markers"]):
            paragraphs.append(self.labels["closing"])
        return paragraphs

    def full_name(self) -> str:
        personal = self.profile.get("personal") or {}
        return f"{personal.get('first_name', '')} {personal.get('last_name', '')}".strip() or self.profile.get("name", "")

    # -- Rendu -------------------------------------------------------------
    def _styles(self, body_size: float) -> Dict[str, ParagraphStyle]:
        t = THEME
        leading = round(body_size * t["body_leading"] / t["body_size"], 1)
        base = ParagraphStyle("Base", fontName=t["font"], fontSize=body_size, leading=leading, textColor=t["text"])
        return {
            "name": ParagraphStyle("Name", parent=base, fontName=t["font_bold"], fontSize=15, leading=19, spaceAfter=2),
            "line": ParagraphStyle("Line", parent=base, fontSize=body_size - 0.5, leading=leading - 1),
            "recipient": ParagraphStyle("Recipient", parent=base, fontSize=body_size - 0.5, leading=leading - 1,
                                        alignment=TA_RIGHT),
            "subject": ParagraphStyle("Subject", parent=base, fontName=t["font_bold"]),
            "body": ParagraphStyle("Body", parent=base, alignment=TA_JUSTIFY, spaceAfter=leading * 0.6),
            "signature": ParagraphStyle("Signature", parent=base, fontName=t["font_bold"]),
        }

    def _story(self, body_size: float) -> List[Any]:
        st = self._styles(body_size)
        gap = body_size * 1.3
        # En-tête sur deux colonnes : expéditeur à gauche, destinataire à droite, alignés en haut
        sender = [Paragraph(_esc(self.full_name()), st["name"])]
        sender += [Paragraph(_esc(l), st["line"]) for l in self.sender_lines()]
        recipient = [Paragraph(_esc(l), st["recipient"]) for l in self.recipient_lines()]
        width = A4[0] - 2 * THEME["margin_x"] - 12  # 12 = paddings gauche/droite du cadre SimpleDocTemplate
        header = Table([[sender, recipient or ""]], colWidths=[width * 0.6, width * 0.4])
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story: List[Any] = [header, Spacer(1, gap * 2)]
        story.append(Paragraph(_esc(self.date_line()), st["line"]))
        story.append(Spacer(1, gap * 1.5))
        subject = self.subject_line()
        if subject:
            story.append(Paragraph(_esc(subject), st["subject"]))
            story.append(Spacer(1, gap * 1.2))
        story += [Paragraph(_esc(p), st["body"]) for p in self.body_paragraphs()]
        story.append(Spacer(1, gap * 0.6))
        story.append(Paragraph(_esc(self.full_name()), st["signature"]))
        return story

    def build(self) -> bytes:
        """Rend la lettre ; réduit la taille du corps par pas de 0,5 pt jusqu'à tenir sur une page."""
        body_size = THEME["body_size"]
        while True:
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer, pagesize=A4,
                leftMargin=THEME["margin_x"], rightMargin=THEME["margin_x"],
                topMargin=THEME["margin_y"], bottomMargin=THEME["margin_y"],
                title=f"Lettre de motivation - {self.full_name()}", author=self.full_name(),
            )
            doc.build(self._story(body_size))
            if doc.page <= 1 or body_size <= THEME["min_body_size"]:
                return buffer.getvalue()
            body_size -= 0.5


def render_letter(profile: Dict[str, Any], letter: Dict[str, Any]) -> bytes:
    return ClassicLetterTemplate(profile, letter).build()
