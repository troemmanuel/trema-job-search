import logging
from typing import Optional, Dict, Any
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobNormalizedData
from app.schemas.match import MatchResult
from app.services.ai.gemini import gemini_service

logger = logging.getLogger(__name__)

SYSTEM_MATCHER_PROMPT = """Tu es un expert en recrutement et analyse de correspondance de profil de carrière.
Règles strictes :
1. Analyse la correspondance exacte entre le profil maître du candidat (ses compétences, ses expériences réelles, ses préférences) et l'offre d'emploi normalisée.
2. Ne surévalue jamais les compétences. Sois objectif et lucide.
3. Attribue un score global sur 100 ainsi qu'un niveau : HIGH (85-100), MEDIUM (75-84), LOW (60-74), IGNORE (<60).
4. Détaille les dimensions (0-100) : title_match, skills_match, experience_match, seniority_match, location_match, salary_match.
5. Liste les compétences partagées (matched_skills), les compétences manquantes (missing_skills), les points forts (strengths) et les points de vigilance (concerns).
6. Fournis une recommandation : APPLY, REVIEW ou IGNORE.
"""

class MatcherService:
    def __init__(self, ai_service=None):
        self.ai_service = ai_service or gemini_service

    def match(self, profile: CandidateProfile, job_data: JobNormalizedData) -> Optional[MatchResult]:
        prompt = f"""
Profil candidat :
{profile.model_dump_json(indent=2)}

Offre d'emploi :
{job_data.model_dump_json(indent=2)}

Évalue la correspondance de manière rigoureuse selon les instructions.
"""
        return self.ai_service.generate_structured(
            prompt=prompt,
            response_schema=MatchResult,
            system_instruction=SYSTEM_MATCHER_PROMPT,
            operation="MATCHING"
        )

matcher_service = MatcherService()
