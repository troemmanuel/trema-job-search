import re
import logging
from typing import Optional, List, Tuple
from app.services.ingestion.company_classifier import classify_company

logger = logging.getLogger(__name__)

def is_company_blacklisted(company: Optional[str], excluded_companies: Optional[List[str]]) -> bool:
    """
    Vérifie si une entreprise figure dans la liste noire du candidat.
    Comparaison insensible à la casse et tolérante aux variantes (ex: 'Capgemini' matchera 'Capgemini France').
    """
    if not company or not excluded_companies:
        return False

    company_clean = company.strip().lower()
    for exc in excluded_companies:
        exc_clean = (exc or "").strip().lower()
        if not exc_clean:
            continue
        # Correspondance exacte
        if exc_clean == company_clean:
            return True
        # Correspondance par sous-chaîne significative (au moins 3 caractères pour éviter les faux positifs)
        if len(exc_clean) >= 3 and (exc_clean in company_clean or company_clean in exc_clean):
            return True

    return False

def matches_excluded_keyword(text: Optional[str], excluded_keywords: Optional[List[str]]) -> Optional[str]:
    """
    Vérifie si un texte (titre ou description d'offre) contient l'un des mots-clés indésirables.
    Retourne le mot-clé coupable s'il est trouvé, sinon None.
    """
    if not text or not excluded_keywords:
        return None

    text_lower = text.lower()
    for kw in excluded_keywords:
        kw_clean = (kw or "").strip().lower()
        if not kw_clean:
            continue
        # Recherche avec délimiteurs de mots pour éviter de matcher 'stage' dans 'stagecraft'
        pattern = r"(?:\b|\W)" + re.escape(kw_clean) + r"(?:\b|\W)"
        if re.search(pattern, f" {text_lower} "):
            return kw

    return None

def is_esn_company(company: Optional[str], title: str = "", description: str = "") -> bool:
    """
    Détermine si une entreprise est une ESN / cabinet de conseil en s'appuyant sur le classifieur d'entreprise.
    """
    if not company:
        return False
    try:
        comp_type, comp_domain = classify_company(company, title=title, description=description)
        type_domain = f"{comp_type} {comp_domain}".lower()
        return any(term in type_domain for term in ["esn", "conseil en technologies", "services numériques", "conseil it"])
    except Exception as e:
        logger.warning(f"Erreur classification ESN pour {company}: {e}")
        return False
