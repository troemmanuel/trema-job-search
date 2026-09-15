import re
from typing import Dict, Any, List, Optional
from app.schemas.job import JobNormalizedData

class JobParser:
    """Analyse et normalise le texte brut d'une offre d'emploi."""

    COMMON_SKILLS = [
        "Python", "Flask", "Django", "FastAPI", "SQL", "PostgreSQL",
        "Docker", "Kubernetes", "AWS", "GCP", "Git", "CI/CD",
        "Product Management", "Product Owner", "Scrum", "Agile",
        "Analytics", "Amplitude", "Mixpanel", "Jira", "Figma",
        "React", "TypeScript", "JavaScript", "Node.js"
    ]

    FRENCH_INDICATORS = {
        "le", "la", "les", "un", "une", "des", "du", "de", "d", "et", "en", "dans", "pour",
        "avec", "sur", "qui", "que", "nous", "vous", "ils", "elles", "au", "aux", "est",
        "sont", "être", "avoir", "notre", "nos", "votre", "vos", "chez", "par", "ce",
        "cette", "ces", "son", "sa", "ses", "faire", "plus", "poste", "équipe", "ingénieur",
        "développeur", "logiciel", "stage", "alternance", "candidature", "recherche",
        "recherchons", "missions", "profil", "expérience", "conception", "gestion"
    }

    ENGLISH_INDICATORS = {
        "the", "and", "with", "for", "from", "this", "that", "these", "those", "have",
        "has", "had", "will", "would", "should", "can", "could", "is", "are", "was",
        "were", "been", "being", "our", "their", "your", "they", "them", "which", "what",
        "who", "when", "where", "why", "how", "about", "into", "you", "we", "looking",
        "join", "team", "role", "building", "requirements", "skills", "experience",
        "software", "engineer", "developer", "at", "fullstack", "full-stack", "responsibilities"
    }

    @classmethod
    def detect_language(cls, text: str, raw: Optional[Dict[str, Any]] = None) -> str:
        """Détecte la langue principale d'une offre ('fr' ou 'en')."""
        if raw:
            for key in ("language", "locale", "lang"):
                val = raw.get(key)
                if isinstance(val, str) and val.strip():
                    clean = val.strip().lower()
                    if clean.startswith("en"):
                        return "en"
                    if clean.startswith("fr"):
                        return "fr"

        if not text:
            return "fr"

        accents = len(re.findall(r"[éèêëàâùûüîïçœæÉÈÊËÀÂÙÛÜÎÏÇŒÆ]", text))
        words = [w.lower() for w in re.findall(r"\b[a-zA-ZàâäéèêëîïôöùûüÿçœæÀÂÄÉÈÊËÎÏÔÖÙÛÜŸÇŒÆ]+\b", text)]
        if not words:
            return "fr"

        fr_score = sum(1 for w in words if w in cls.FRENCH_INDICATORS) + (accents * 2)
        en_score = sum(1 for w in words if w in cls.ENGLISH_INDICATORS)

        if en_score > fr_score:
            return "en"
        return "fr"

    @classmethod
    def parse_skills(cls, text: str) -> List[str]:
        """Extrait les mots-clés techniques basiques présents dans la description."""
        found = set()
        lower_text = text.lower()
        for skill in cls.COMMON_SKILLS:
            # Recherche avec frontières de mots
            pattern = rf"\b{re.escape(skill.lower())}\b"
            if re.search(pattern, lower_text):
                found.add(skill)
        return sorted(list(found))

    @classmethod
    def normalize(cls, raw: Dict[str, Any]) -> JobNormalizedData:
        """Produit un objet JobNormalizedData à partir des données brutes."""
        # `or ""` : les scrapers renvoient explicitement None quand une info manque (get() ne suffit pas)
        title = (raw.get("title") or "").strip()
        company = (raw.get("company") or "").strip()
        location = (raw.get("location") or "").strip()
        description = raw.get("description") or ""

        # Détection télétravail basique
        remote = False
        desc_lower = (description + " " + location).lower()
        if "remote" in desc_lower or "télétravail" in desc_lower:
            remote = True

        contract_type = raw.get("contract_type") or "CDI"
        seniority = raw.get("seniority") or "Mid-level"
        extracted_skills = cls.parse_skills(description)

        from app.services.ingestion.company_classifier import classify_company
        comp_type, comp_domain = classify_company(
            company=company,
            title=title,
            description=description,
            raw_data=raw.get("raw_data")
        )

        language = cls.detect_language(f"{title}\n{description}", raw)

        return JobNormalizedData(
            title=title,
            company=company,
            location=location,
            remote=remote,
            contract_type=contract_type,
            seniority=seniority,
            skills=extracted_skills,
            requirements=raw.get("requirements", []),
            nice_to_have=raw.get("nice_to_have", []),
            company_type=comp_type,
            domain=comp_domain,
            language=language
        )

job_parser = JobParser()
