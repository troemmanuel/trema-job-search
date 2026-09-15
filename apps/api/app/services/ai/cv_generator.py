import logging
from typing import Optional
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobNormalizedData
from app.schemas.application import TailoredCV
from app.services.ai.cv_postprocessor import finalize_tailored_cv
from app.services.ai.gemini import gemini_service
from app.services.ai.prompt_loader import prompt_loader

logger = logging.getLogger(__name__)

class CVGeneratorService:
    def __init__(self, ai_service=None):
        self.ai_service = ai_service or gemini_service

    def generate(self, job_id: str, profile: CandidateProfile, job_data: JobNormalizedData, application_id: Optional[str] = None) -> Optional[TailoredCV]:
        job_lang = (getattr(job_data, "language", None) or "fr").lower()[:2]
        if job_lang not in ("fr", "en"):
            job_lang = "fr"

        system_instruction, user_prompt = prompt_loader.load_and_render(
            "cv_generation",
            job_id=job_id,
            candidate_profile=profile.model_dump_json(),
            job_data=job_data.model_dump_json()
        )

        lang_label = "anglais (English)" if job_lang == "en" else "français"
        system_instruction += (
            f"\n\nEXIGENCE STRICTE DE LANGUE :\n"
            f"L'offre ciblée est identifiée en {lang_label} (code '{job_lang}').\n"
            f"Le champ 'language' de ta réponse DOIT être '{job_lang}'.\n"
            f"Tous les textes générés (titre 'title', accroche 'summary', mobilité 'mobility', "
            f"réalisations reformulées dans 'experience_highlights', libellés des catégories de compétences "
            f"dans 'skill_groups', explications dans 'changes') DOIVENT être rédigés en {lang_label}."
        )

        tailored = self.ai_service.generate_structured(
            prompt=user_prompt,
            response_schema=TailoredCV,
            system_instruction=system_instruction,
            operation="CV_GENERATION",
            application_id=application_id
        )
        if tailored:
            tailored.language = job_lang

        # Garde-fous déterministes (durée annoncée, volume de réalisations, stack) à partir du profil maître
        return finalize_tailored_cv(tailored, profile, job_data.model_dump()) if tailored else None

cv_generator_service = CVGeneratorService()
