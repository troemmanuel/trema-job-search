"""
Polices TTF embarquées partagées par les templates de documents (CV, lettre).

Chaque famille liste des candidats (repo, Linux, macOS) ; à défaut, polices PDF standard.
"""
import logging
from pathlib import Path
from typing import Dict

from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

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


def register_font_family(family: str) -> tuple:
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


