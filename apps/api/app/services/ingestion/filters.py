import re
import logging
from typing import Optional, List, Tuple, Any, Dict
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

def evaluate_heuristic_mismatch(profile: Any, job: Any) -> Optional[dict]:
    """
    Évalue algorithmiquement si une offre est manifestement incompatible (contrat ou compétences),
    permettant de lui attribuer un score de rejet (score <= 30) sans appeler l'API Gemini.
    Retourne un dictionnaire compatible MatchResult si rejetée, ou None si l'offre doit être évaluée par Gemini.
    """
    if not profile or not job:
        return None

    prefs = getattr(profile, "preferences", None)
    job_contract = (getattr(job, "contract_type", "") or "").strip().upper()
    job_title = (getattr(job, "title", "") or "").strip().lower()
    job_skills_raw = getattr(job, "skills", []) or []
    job_skills = {s.strip().lower() for s in job_skills_raw if isinstance(s, str) and s.strip()}

    # 1. Vérification stricte d'incompatibilité de contrat
    if prefs and getattr(prefs, "contract_types", None):
        cand_contracts = {c.strip().upper() for c in prefs.contract_types if isinstance(c, str) and c.strip()}
        # Si le candidat ne souhaite que du CDI et que l'offre est un Stage ou une Alternance explicite
        incompatible_stages = {"STAGE", "INTERNSHIP", "ALTERNANCE", "APPRENTISSAGE"}
        if job_contract in incompatible_stages and job_contract not in cand_contracts:
            reason = f"Type de contrat '{job_contract}' incompatible avec vos souhaits ({', '.join(cand_contracts)})."
            logger.info(f"Rejet déterministe contrat : {reason}")
            return {
                "score": 20,
                "level": "REJECTED",
                "recommendation": "IGNORE",
                "dimensions": {
                    "title_match": 30,
                    "skills_match": 30,
                    "experience_match": 20,
                    "seniority_match": 30,
                    "location_match": 85,
                    "salary_match": 20
                },
                "matched_skills": [],
                "missing_skills": list(job_skills_raw)[:5],
                "strengths": [],
                "concerns": [reason],
                "company_type": getattr(job, "company_type", None),
                "company_domain": getattr(job, "domain", None)
            }

    # 2. Collecte de toutes les compétences et mots-clés du candidat
    cand_skills = set()
    skills_obj = getattr(profile, "skills", None)
    if skills_obj:
        if isinstance(skills_obj, dict):
            for cat_list in skills_obj.values():
                if isinstance(cat_list, list):
                    cand_skills.update(s.lower().strip() for s in cat_list if isinstance(s, str))
        else:
            for attr in ("technical", "tools", "business", "soft_skills"):
                cat_list = getattr(skills_obj, attr, []) or []
                cand_skills.update(s.lower().strip() for s in cat_list if isinstance(s, str))

    # Ajouter compétences des expériences et projets
    for exp in getattr(profile, "experiences", []) or []:
        for s in getattr(exp, "skills", []) or []:
            if isinstance(s, str):
                cand_skills.add(s.lower().strip())
    for prj in getattr(profile, "projects", []) or []:
        for s in getattr(prj, "skills", []) or []:
            if isinstance(s, str):
                cand_skills.add(s.lower().strip())

    # Mots-clés cibles du candidat (titre et préférences)
    cand_target_keywords = set()
    if prefs and getattr(prefs, "target_titles", None):
        for tt in prefs.target_titles:
            cand_target_keywords.update(re.findall(r"\b[a-zA-Z0-9+#.-]{3,}\b", tt.lower()))
    profile_title = (getattr(profile, "title", "") or "").lower()
    if profile_title:
        cand_target_keywords.update(re.findall(r"\b[a-zA-Z0-9+#.-]{3,}\b", profile_title))

    # Mots-clés informatiques universels
    generic_tech_keywords = {"developer", "développeur", "engineer", "ingénieur", "software", "logiciel", "backend", "fullstack", "devops", "cloud", "data"}

    # 3. Vérification de l'absence totale de recouvrement technique
    # Si l'offre comporte au moins 2 compétences techniques répertoriées mais 0 recouvrement
    if len(job_skills) >= 2:
        overlap = cand_skills.intersection(job_skills)
        if len(overlap) == 0:
            # Vérifier si le titre de l'offre partage au moins un mot-clé significatif avec le candidat
            job_title_words = set(re.findall(r"\b[a-zA-Z0-9+#.-]{3,}\b", job_title))
            has_title_match = bool(cand_target_keywords.intersection(job_title_words))
            has_generic_tech = bool(generic_tech_keywords.intersection(job_title_words))

            # Si ni le titre ni les compétences ne correspondent (métier tiers ou stack 100% étrangère)
            if not has_title_match and not has_generic_tech:
                reason = f"Aucun mot-clé ni compétence technique en commun avec votre profil ({', '.join(list(job_skills)[:4])})."
                logger.info(f"Rejet déterministe technique : {reason}")
                return {
                    "score": 25,
                    "level": "REJECTED",
                    "recommendation": "IGNORE",
                    "dimensions": {
                        "title_match": 20,
                        "skills_match": 10,
                        "experience_match": 20,
                        "seniority_match": 40,
                        "location_match": 85,
                        "salary_match": 50
                    },
                    "matched_skills": [],
                    "missing_skills": list(job_skills_raw)[:5],
                    "strengths": [],
                    "concerns": [reason],
                    "company_type": getattr(job, "company_type", None),
                    "company_domain": getattr(job, "domain", None)
                }

    return None

