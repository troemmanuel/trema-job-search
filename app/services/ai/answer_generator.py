import logging
from typing import Optional
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobNormalizedData
from app.schemas.application import ApplicationAnswers
from app.services.ai.gemini import gemini_service

logger = logging.getLogger(__name__)

SYSTEM_ANSWERS_PROMPT = """Tu es un assistant de préparation aux candidatures d'emploi.
Règles :
1. Identifie 2 à 4 questions classiques et probables pour cette offre (ex: motivation pour l'entreprise, adéquation technique, prétentions salariales, disponibilité).
2. Prépare des suggestions de réponses concises et adaptées au profil du candidat.
3. Pour les éléments personnels sensibles (prétentions salariales, disponibilité immédiate), attribue une confiance MEDIUM ou LOW et validation_required = true.
"""

class AnswerGeneratorService:
    def __init__(self, ai_service=None):
        self.ai_service = ai_service or gemini_service

    def generate(self, profile: CandidateProfile, job_data: JobNormalizedData, application_id: Optional[str] = None) -> Optional[ApplicationAnswers]:
        prompt = f"""
Profil candidat :
{profile.model_dump_json(indent=2)}

Offre :
{job_data.model_dump_json(indent=2)}

Prépare les réponses potentielles aux questions de candidature.
"""
        return self.ai_service.generate_structured(
            prompt=prompt,
            response_schema=ApplicationAnswers,
            system_instruction=SYSTEM_ANSWERS_PROMPT,
            operation="ANSWERS_GENERATION",
            application_id=application_id
        )

answer_generator_service = AnswerGeneratorService()
