import re
from typing import Dict, Any, List
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
        title = raw.get("title", "").strip()
        company = raw.get("company", "").strip()
        location = raw.get("location", "").strip()
        description = raw.get("description", "")

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
            domain=comp_domain
        )

job_parser = JobParser()
