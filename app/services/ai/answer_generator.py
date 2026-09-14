import logging
from typing import Optional
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobNormalizedData
from app.schemas.application import ApplicationAnswers
from app.services.ai.gemini import gemini_service
from app.services.ai.prompt_loader import prompt_loader

logger = logging.getLogger(__name__)

class AnswerGeneratorService:
    def __init__(self, ai_service=None):
        self.ai_service = ai_service or gemini_service

    def generate(self, profile: CandidateProfile, job_data: JobNormalizedData, application_id: Optional[str] = None) -> Optional[ApplicationAnswers]:
        system_instruction, user_prompt = prompt_loader.load_and_render(
            "answer_generation",
            candidate_profile=profile.model_dump_json(),
            job_data=job_data.model_dump_json()
        )
        return self.ai_service.generate_structured(
            prompt=user_prompt,
            response_schema=ApplicationAnswers,
            system_instruction=system_instruction,
            operation="ANSWERS_GENERATION",
            application_id=application_id
        )

answer_generator_service = AnswerGeneratorService()
