import logging
from typing import Optional, Dict, Any
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobNormalizedData
from app.schemas.match import MatchResult
from app.services.ai.gemini import gemini_service
from app.services.ai.prompt_loader import prompt_loader

logger = logging.getLogger(__name__)

class MatcherService:
    def __init__(self, ai_service=None):
        self.ai_service = ai_service or gemini_service

    def match(self, profile: CandidateProfile, job_data: JobNormalizedData) -> Optional[MatchResult]:
        system_instruction, user_prompt = prompt_loader.load_and_render(
            "matching",
            candidate_profile=profile.model_dump_json(indent=2),
            job_data=job_data.model_dump_json(indent=2)
        )
        if profile.preferences and getattr(profile.preferences, "ai_custom_instructions", None):
            system_instruction += f"\n\nDirectives spécifiques et priorités du candidat :\n{profile.preferences.ai_custom_instructions}"
        return self.ai_service.generate_structured(
            prompt=user_prompt,
            response_schema=MatchResult,
            system_instruction=system_instruction,
            operation="MATCHING"
        )

matcher_service = MatcherService()
