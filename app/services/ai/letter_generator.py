import logging
from typing import Optional
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobNormalizedData
from app.schemas.application import CoverLetter
from app.services.ai.gemini import gemini_service

logger = logging.getLogger(__name__)

SYSTEM_LETTER_PROMPT = """Tu es un expert en rédaction de lettres et messages de motivation pour candidatures ciblées.
Règles strictes :
1. Rédige un message ou une lettre percutante, sobre, directe et personnalisée pour l'entreprise et l'offre visée.
2. Basé exclusivement sur les faits réels du profil maître du candidat. N'invente aucun accomplissement.
3. Mets en avant 2 à 3 arguments clés concrets faisant le lien entre les réalisations du candidat et les défis du poste.
4. Si une donnée doit être confirmée par le candidat, insère '[À VALIDER]' et passe validation_required à true.
"""

class LetterGeneratorService:
    def __init__(self, ai_service=None):
        self.ai_service = ai_service or gemini_service

    def generate(self, profile: CandidateProfile, job_data: JobNormalizedData, letter_type: str = "cover_letter", application_id: Optional[str] = None) -> Optional[CoverLetter]:
        prompt = f"""
Type de format souhaité : {letter_type} (cover_letter ou short_message)

Profil candidat :
{profile.model_dump_json(indent=2)}

Offre ciblée :
{job_data.model_dump_json(indent=2)}

Rédige le document de motivation ciblé.
"""
        return self.ai_service.generate_structured(
            prompt=prompt,
            response_schema=CoverLetter,
            system_instruction=SYSTEM_LETTER_PROMPT,
            operation="LETTER_GENERATION",
            application_id=application_id
        )

letter_generator_service = LetterGeneratorService()
