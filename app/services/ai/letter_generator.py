import logging
from typing import Optional
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobNormalizedData
from app.schemas.application import CoverLetter
from app.services.ai.gemini import gemini_service
from app.services.ai.prompt_loader import prompt_loader

logger = logging.getLogger(__name__)

class LetterGeneratorService:
    def __init__(self, ai_service=None):
        self.ai_service = ai_service or gemini_service

    def generate(self, profile: CandidateProfile, job_data: JobNormalizedData, letter_type: str = "cover_letter", application_id: Optional[str] = None) -> Optional[CoverLetter]:
        system_instruction, user_prompt = prompt_loader.load_and_render(
            "letter_generation",
            letter_type=letter_type,
            candidate_profile=profile.model_dump_json(indent=2),
            job_data=job_data.model_dump_json(indent=2)
        )
        return self.ai_service.generate_structured(
            prompt=user_prompt,
            response_schema=CoverLetter,
            system_instruction=system_instruction,
            operation="LETTER_GENERATION",
            application_id=application_id
        )

letter_generator_service = LetterGeneratorService()
