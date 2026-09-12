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
        system_instruction, user_prompt = prompt_loader.load_and_render(
            "cv_generation",
            job_id=job_id,
            candidate_profile=profile.model_dump_json(indent=2),
            job_data=job_data.model_dump_json(indent=2)
        )
        tailored = self.ai_service.generate_structured(
            prompt=user_prompt,
            response_schema=TailoredCV,
            system_instruction=system_instruction,
            operation="CV_GENERATION",
            application_id=application_id
        )
        # Garde-fous déterministes (durée annoncée, volume de réalisations, stack) à partir du profil maître
        return finalize_tailored_cv(tailored, profile, job_data.model_dump()) if tailored else None

cv_generator_service = CVGeneratorService()
