import logging
from typing import Optional
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobNormalizedData
from app.schemas.application import TailoredCV
from app.services.ai.gemini import gemini_service

logger = logging.getLogger(__name__)

SYSTEM_CV_PROMPT = """Tu es un coach carrière et expert CV.
RÈGLES ANTI-HALLUCINATION ABSOLUES :
1. Tu ne dois JAMAIS inventer une expérience, une entreprise, une compétence, une certification, un diplôme, un chiffre ou un résultat.
2. Tu ne dois JAMAIS transformer une compétence faible en expertise.
3. Tu peux : reformuler, raccourcir, réorganiser, sélectionner les expériences les plus pertinentes (via leurs IDs), mettre en avant et adapter le vocabulaire aux termes de l'offre.
4. Si une information est incertaine ou manque, indique explicitement '[À VALIDER]' et passe validation_required à true.
"""

class CVGeneratorService:
    def __init__(self, ai_service=None):
        self.ai_service = ai_service or gemini_service

    def generate(self, job_id: str, profile: CandidateProfile, job_data: JobNormalizedData, application_id: Optional[str] = None) -> Optional[TailoredCV]:
        prompt = f"""
Job ID : {job_id}

Profil candidat maître :
{profile.model_dump_json(indent=2)}

Offre ciblée :
{job_data.model_dump_json(indent=2)}

Génère une sélection et synthèse adaptée au poste, en sélectionnant les identifiants d'expériences (`selected_experiences`) et les compétences clés à mettre en avant.
"""
        return self.ai_service.generate_structured(
            prompt=prompt,
            response_schema=TailoredCV,
            system_instruction=SYSTEM_CV_PROMPT,
            operation="CV_GENERATION",
            application_id=application_id
        )

cv_generator_service = CVGeneratorService()
