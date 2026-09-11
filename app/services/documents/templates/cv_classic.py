"""
Template CV « classique » - mise en page figée reproduisant le CV de référence.

Seul le contenu (profil maître + sélection ciblée) varie d'une candidature à l'autre :
la structure, l'ordre des sections, les polices et les couleurs sont fixés ici.
"""
import io
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- Polices
# Polices TTF embarquées pour un rendu identique quel que soit le lecteur PDF.
# Chaque famille liste des candidats (repo, Linux, macOS) ; à défaut, polices PDF standard.
FONT_DIRS = [
    Path(__file__).resolve().parents[3] / "static" / "fonts",
    Path("/usr/share/fonts/truetype/liberation"),
    Path("/usr/share/fonts/truetype/crosextra"),
    Path("/System/Library/Fonts/Supplemental"),
    Path.home() / "Library" / "Fonts",
]
FONT_FAMILIES = {
    # family -> (regular, bold, italic, bolditalic) candidats par ordre de préférence
    "CVSerif": [
        ("LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf", "LiberationSerif-Italic.ttf", "LiberationSerif-BoldItalic.ttf"),
        ("Times New Roman.ttf", "Times New Roman Bold.ttf", "Times New Roman Italic.ttf", "Times New Roman Bold Italic.ttf"),
    ],
    "CVSans": [
        ("Carlito-Regular.ttf", "Carlito-Bold.ttf", "Carlito-Italic.ttf", "Carlito-BoldItalic.ttf"),
        ("Arial.ttf", "Arial Bold.ttf", "Arial Italic.ttf", "Arial Bold Italic.ttf"),
    ],
}
FALLBACK_FONTS = {
    "CVSerif": ("Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic"),
    "CVSans": ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique"),
}
_REGISTERED: Dict[str, tuple] = {}


def _register_family(family: str) -> tuple:
    """Enregistre la première famille TTF trouvée et retourne (regular, bold, italic, bolditalic)."""
    if family in _REGISTERED:
        return _REGISTERED[family]
    for candidates in FONT_FAMILIES[family]:
        for font_dir in FONT_DIRS:
            paths = [font_dir / name for name in candidates]
            if all(p.exists() for p in paths):
                names = (family, f"{family}-Bold", f"{family}-Italic", f"{family}-BoldItalic")
                for name, path in zip(names, paths):
                    pdfmetrics.registerFont(TTFont(name, str(path)))
                addMapping(family, 0, 0, names[0])
                addMapping(family, 1, 0, names[1])
                addMapping(family, 0, 1, names[2])
                addMapping(family, 1, 1, names[3])
                logger.info(f"Police CV « {family} » embarquée depuis {font_dir}")
                _REGISTERED[family] = names
                return names
    logger.warning(f"Aucune TTF trouvée pour « {family} », repli sur les polices PDF standard")
    _REGISTERED[family] = FALLBACK_FONTS[family]
    return _REGISTERED[family]


_SERIF = _register_family("CVSerif")
_SANS = _register_family("CVSans")

# --------------------------------------------------------------------------- Thème
THEME = {
    "font": _SERIF[0],
    "font_bold": _SERIF[1],
    "font_italic": _SERIF[2],
    "font_heading": _SANS[1],
    "accent": colors.HexColor("#2F5597"),
    "heading": colors.HexColor("#1F3864"),
    "text": colors.HexColor("#111111"),
    "muted": colors.HexColor("#555555"),
    "rule": colors.HexColor("#8A8A8A"),
    "margin_x": 14 * mm,
    "margin_y": 12 * mm,
    "body_size": 9.5,
    "body_leading": 12,
}

LABELS = {
    "fr": {
        "profile": "PROFIL", "experience": "EXPÉRIENCE", "projects": "PROJETS",
        "skills": "COMPÉTENCES TECHNIQUES", "education": "FORMATION", "languages": "LANGUES",
        "stack": "Stack :", "mission": "Mission :", "present": "Présent",
        "months": ["Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin", "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."],
        "skill_categories": {"technical": "Techniques", "tools": "Outils & Méthodes",
                             "business": "Métier", "soft_skills": "Savoir-être"},
        "contact": {"location": "Localisation :", "email": "Email :", "phone": "Tél. :",
                    "linkedin": "LinkedIn :", "portfolio": "Portfolio :"},
    },
    "en": {
        "profile": "PROFILE", "experience": "EXPERIENCE", "projects": "PROJECTS",
        "skills": "TECHNICAL SKILLS", "education": "EDUCATION", "languages": "LANGUAGES",
        "stack": "Stack:", "mission": "Mission:", "present": "Present",
        "months": ["Jan.", "Feb.", "Mar.", "Apr.", "May", "Jun.", "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec."],
        "skill_categories": {"technical": "Technical", "tools": "Tools & Methods",
                             "business": "Business", "soft_skills": "Soft skills"},
        "contact": {"location": "Location:", "email": "Email:", "phone": "Phone:",
                    "linkedin": "LinkedIn:", "portfolio": "Portfolio:"},
    },
}

SEP = " · "
DASH = " - "


def _styles() -> Dict[str, ParagraphStyle]:
    t = THEME
    base = ParagraphStyle("Base", fontName=t["font"], fontSize=t["body_size"],
                          leading=t["body_leading"], textColor=t["text"])
    return {
        "name": ParagraphStyle("Name", parent=base, fontName=t["font_bold"], fontSize=22, leading=26),
        "title": ParagraphStyle("Title", parent=base, fontName=t["font_bold"], fontSize=11.5,
                                leading=14, textColor=t["accent"], spaceBefore=1),
        "contact": ParagraphStyle("Contact", parent=base, fontSize=8, leading=11,
                                  textColor=t["muted"], spaceBefore=4),
        "section": ParagraphStyle("Section", parent=base, fontName=t["font_heading"], fontSize=9.5,
                                  leading=12, textColor=t["heading"], spaceBefore=12, spaceAfter=3),
        "body": ParagraphStyle("Body", parent=base, alignment=TA_JUSTIFY),
        "entry": ParagraphStyle("Entry", parent=base, fontSize=10, leading=13),
        "role": ParagraphStyle("Role", parent=base, fontName=t["font_bold"], fontSize=9.5, leading=12),
        "dates": ParagraphStyle("Dates", parent=base, fontName=t["font_italic"], fontSize=8.5,
                                leading=12, textColor=t["muted"], alignment=TA_RIGHT),
        "meta": ParagraphStyle("Meta", parent=base, fontName=t["font_italic"], fontSize=8,
                               leading=10, textColor=t["muted"]),
        "bullet": ParagraphStyle("Bullet", parent=base, leftIndent=16, bulletIndent=6, spaceBefore=1),
        "stack": ParagraphStyle("Stack", parent=base, fontSize=8.5, leading=11,
                                textColor=t["muted"], spaceBefore=2),
        "line": ParagraphStyle("Line", parent=base, spaceBefore=1),
    }


# --------------------------------------------------------------------------- Helpers
def _esc(value: Any) -> str:
    return escape(str(value)) if value is not None else ""


def _bold(text: str) -> str:
    return f"<b>{text}</b>"


def _accent(text: str) -> str:
    return f'<font color="{THEME["accent"].hexval()}">{text}</font>'


def _format_date(raw: Optional[str], labels: Dict[str, Any]) -> str:
    """Convertit '2024-04' → 'Avr. 2024' ; laisse passer toute autre forme telle quelle."""
    if not raw:
        return ""
    m = re.fullmatch(r"(\d{4})-(\d{1,2})(?:-\d{1,2})?", raw.strip())
    if m:
        year, month = m.group(1), int(m.group(2))
        if 1 <= month <= 12:
            return f"{labels['months'][month - 1]} {year}"
    return raw.strip()


def _date_range(start: Optional[str], end: Optional[str], labels: Dict[str, Any]) -> str:
    start_txt = _format_date(start, labels)
    end_txt = _format_date(end, labels) if end else labels["present"]
    if start_txt and end_txt:
        # "Janv. - Juin 2021" quand les deux bornes partagent la même année
        s_parts, e_parts = start_txt.rsplit(" ", 1), end_txt.rsplit(" ", 1)
        if len(s_parts) == 2 and len(e_parts) == 2 and s_parts[1] == e_parts[1] and s_parts[1].isdigit():
            return f"{s_parts[0]}{DASH}{end_txt}"
        return f"{start_txt}{DASH}{end_txt}"
    return start_txt or end_txt


def _two_cols(left: Paragraph, right: Paragraph, width: float, right_width: float = 95) -> Table:
    table = Table([[left, right]], colWidths=[width - right_width, right_width])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


def _group_experiences(experiences: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Regroupe les expériences consécutives d'une même entreprise (plusieurs postes chez un employeur)."""
    groups: List[List[Dict[str, Any]]] = []
    for exp in experiences:
        key = (exp.get("company") or "").strip().lower()
        if groups and (groups[-1][0].get("company") or "").strip().lower() == key:
            groups[-1].append(exp)
        else:
            groups.append([exp])
    return groups


def _sort_key(exp: Dict[str, Any]) -> str:
    # Poste en cours d'abord, puis du plus récent au plus ancien
    return exp.get("end_date") or "9999-99"


def _resolve_experiences(profile: Dict[str, Any], tailored: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Applique la sélection ciblée : ids retenus, et réalisations réécrites par id (experience_highlights)."""
    ids = [item.get("id") if isinstance(item, dict) else item for item in tailored.get("selected_experiences") or []]
    overrides = {h["id"]: h["achievements"] for h in tailored.get("experience_highlights") or []
                 if h.get("id") and h.get("achievements")}
    experiences = []
    for exp in profile.get("experiences", []):
        if ids and exp.get("id") not in ids:
            continue
        merged = dict(exp)
        if exp.get("id") in overrides:
            merged["achievements"] = overrides[exp["id"]]
        experiences.append(merged)
    return sorted(experiences, key=_sort_key, reverse=True)


def _resolve_skill_groups(profile: Dict[str, Any], tailored: Dict[str, Any], labels: Dict[str, Any]) -> List[Dict[str, Any]]:
    groups = tailored.get("skill_groups") or []
    if groups:
        return groups
    if tailored.get("skills"):
        return [{"label": labels["skill_categories"]["technical"], "items": tailored["skills"]}]
    profile_skills = profile.get("skills") or {}
    return [
        {"label": labels["skill_categories"][cat], "items": profile_skills.get(cat) or []}
        for cat in ("technical", "tools", "business", "soft_skills")
        if profile_skills.get(cat)
    ]


# --------------------------------------------------------------------------- Rendu
class ClassicCVTemplate:
    """Construit le PDF à partir du profil maître (dict) et du CV ciblé (dict)."""

    def __init__(self, profile: Dict[str, Any], tailored_cv: Optional[Dict[str, Any]] = None):
        self.profile = profile or {}
        self.tailored = tailored_cv or {}
        self.labels = LABELS.get((self.tailored.get("language") or "fr").lower()[:2], LABELS["fr"])
        self.st = _styles()
        self.width = A4[0] - 2 * THEME["margin_x"]

    # -- Blocs -------------------------------------------------------------
    def _section(self, key: str) -> List[Any]:
        return [
            Paragraph(self.labels[key], self.st["section"]),
            HRFlowable(width="100%", thickness=0.75, color=THEME["rule"], spaceBefore=0, spaceAfter=7),
        ]

    def _assemble(self, key: str, blocks: List[List[Any]], gap: float = 0) -> List[Any]:
        """Titre de section soudé au premier bloc (jamais orphelin), chaque bloc insécable."""
        if not blocks:
            return []
        story: List[Any] = [KeepTogether(self._section(key) + blocks[0])]
        for block in blocks[1:]:
            if gap:
                story.append(Spacer(1, gap))
            story.append(KeepTogether(block))
        return story

    def _stack_line(self, skills: List[str]) -> Optional[Paragraph]:
        if not skills:
            return None
        items = SEP.join(_esc(s) for s in skills)
        return Paragraph(f'<font color="{THEME["text"].hexval()}"><b>{self.labels["stack"]}</b></font> {items}', self.st["stack"])

    def _header(self) -> List[Any]:
        personal = self.profile.get("personal") or {}
        full_name = f"{personal.get('first_name', '')} {personal.get('last_name', '')}".strip() or self.profile.get("name", "")
        title = self.tailored.get("title") or self.profile.get("title")
        # Espaces insécables : un item « Libellé : valeur » ne se coupe jamais, seul le séparateur peut passer à la ligne
        contact = [
            f"{_bold(self.labels['contact'][key])} {_esc(personal[key])}".replace(" ", "\u00a0")
            for key in ("location", "email", "phone", "linkedin", "portfolio")
            if personal.get(key)
        ]
        story: List[Any] = [Paragraph(_esc(full_name), self.st["name"])]
        if title:
            story.append(Paragraph(_esc(title), self.st["title"]))
        story.append(Paragraph(SEP.join(contact), self.st["contact"]))
        story.append(Spacer(1, 6))
        return story

    def _profile(self) -> List[Any]:
        summary = self.tailored.get("summary") or self.profile.get("summary")
        if not summary:
            return []
        return self._assemble("profile", [[Paragraph(_esc(summary), self.st["body"])]])

    def _experience_block(self, exp: Dict[str, Any], show_company: bool) -> List[Any]:
        contract = f" ({_esc(exp['contract_type'])})" if exp.get("contract_type") else ""
        if show_company:
            left = _bold(_esc(exp.get("role"))) + SEP + _accent(_bold(_esc(exp.get("company")) + contract))
            style = self.st["entry"]
        else:
            left = _bold(_esc(exp.get("role")) + contract)
            style = self.st["role"]
        dates = Paragraph(_date_range(exp.get("start_date"), exp.get("end_date"), self.labels), self.st["dates"])
        block: List[Any] = [_two_cols(Paragraph(left, style), dates, self.width)]
        if show_company and exp.get("location"):
            block.append(Paragraph(_esc(exp["location"]), self.st["meta"]))
        if exp.get("description"):
            block.append(Paragraph(_esc(exp["description"]), self.st["body"]))
        for ach in exp.get("achievements") or []:
            block.append(Paragraph(_esc(ach), self.st["bullet"], bulletText="•"))
        stack = self._stack_line(exp.get("skills") or [])
        if stack:
            block.append(stack)
        return block

    def _experiences(self) -> List[Any]:
        experiences = _resolve_experiences(self.profile, self.tailored)
        blocks: List[List[Any]] = []
        for group in _group_experiences(experiences):
            if len(group) == 1:
                blocks.append(self._experience_block(group[0], show_company=True) + [Spacer(1, 8)])
                continue
            head = group[0]
            company = _bold(_esc(head.get("company")))
            if head.get("client"):
                company += SEP + _accent(_bold(_esc(head["client"])))
            starts = [e.get("start_date") for e in group if e.get("start_date")]
            ends = [e.get("end_date") for e in group]
            span = _date_range(min(starts) if starts else None,
                               None if any(e is None for e in ends) else max(ends), self.labels)
            header: List[Any] = [_two_cols(Paragraph(company, self.st["entry"]),
                                           Paragraph(span, self.st["dates"]), self.width)]
            if head.get("location"):
                header.append(Paragraph(_esc(head["location"]), self.st["meta"]))
            header.append(Spacer(1, 3))
            blocks.append(header + self._experience_block(group[0], show_company=False))
            for exp in group[1:-1]:
                blocks.append([Spacer(1, 5)] + self._experience_block(exp, show_company=False))
            blocks.append([Spacer(1, 5)] + self._experience_block(group[-1], show_company=False) + [Spacer(1, 8)])
        return self._assemble("experience", blocks)

    def _projects(self) -> List[Any]:
        selected = self.tailored.get("selected_projects") or []
        projects = [p for p in self.profile.get("projects", []) if not selected or p.get("id") in selected]
        blocks: List[List[Any]] = []
        for project in projects:
            meta = SEP.join(_esc(x) for x in (project.get("kind"), project.get("status")) if x)
            block: List[Any] = [_two_cols(Paragraph(_bold(_esc(project.get("name"))), self.st["entry"]),
                                          Paragraph(meta, self.st["dates"]), self.width)]
            if project.get("description"):
                block.append(Paragraph(_esc(project["description"]), self.st["body"]))
            if project.get("mission"):
                block.append(Paragraph(f"<b>{self.labels['mission']}</b> {_esc(project['mission'])}", self.st["line"]))
            stack = self._stack_line(project.get("skills") or [])
            if stack:
                block.append(stack)
            blocks.append(block)
        return self._assemble("projects", blocks, gap=7)

    def _skills(self) -> List[Any]:
        groups = _resolve_skill_groups(self.profile, self.tailored, self.labels)
        lines: List[Any] = []
        for group in groups:
            if not group.get("items"):
                continue
            label = _accent(_bold(_esc(group["label"]) + (" :" if self.labels is LABELS["fr"] else ":")))
            lines.append(Paragraph(f"{label} {', '.join(_esc(i) for i in group['items'])}", self.st["line"]))
        return self._assemble("skills", [lines] if lines else [])

    def _education(self) -> List[Any]:
        lines: List[Any] = []
        for edu in self.profile.get("education") or []:
            degree = _esc(edu.get("degree"))
            if edu.get("field_of_study"):
                degree += f" ({_esc(edu['field_of_study'])})"
            years = SEP.join(x for x in ["-".join(y for y in (edu.get("start_date"), edu.get("end_date")) if y)] if x)
            text = _bold(degree) + DASH + _esc(edu.get("institution"))
            if years:
                text += SEP + years
            lines.append(Paragraph(text, self.st["line"]))
        return self._assemble("education", [lines] if lines else [])

    def _languages(self) -> List[Any]:
        lines: List[Any] = []
        for lang in self.profile.get("languages") or []:
            if isinstance(lang, dict):
                name, level = lang.get("name", ""), lang.get("level", "")
            else:
                name, _, level = str(lang).partition(":")
            text = _bold(_esc(name.strip()) + (" :" if level.strip() else ""))
            if level.strip():
                text += f' <font color="{THEME["muted"].hexval()}">{_esc(level.strip())}</font>'
            lines.append(Paragraph(text, self.st["line"]))
        return self._assemble("languages", [lines] if lines else [])

    # -- Assemblage --------------------------------------------------------
    def build(self) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=THEME["margin_x"], rightMargin=THEME["margin_x"],
            topMargin=THEME["margin_y"], bottomMargin=THEME["margin_y"],
            title=f"CV - {self.profile.get('name', '')}", author=self.profile.get("name", ""),
        )
        story: List[Any] = []
        for block in (self._header, self._profile, self._experiences, self._projects,
                      self._skills, self._education, self._languages):
            story.extend(block())
        doc.build(story)
        return buffer.getvalue()


def render_cv(profile: Dict[str, Any], tailored_cv: Optional[Dict[str, Any]] = None) -> bytes:
    return ClassicCVTemplate(profile, tailored_cv).build()
