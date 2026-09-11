import logging
from typing import Optional
from app.schemas.candidate import CandidateProfile
from app.services.ai.gemini import gemini_service
from app.services.ai.prompt_loader import prompt_loader

logger = logging.getLogger(__name__)

class CVTranscriberService:
    def __init__(self, ai_service=None):
        self.ai_service = ai_service or gemini_service

    def transcribe_markdown(self, markdown_content: str) -> Optional[CandidateProfile]:
        """Transcrit le contenu d'un fichier Markdown en un profil candidat structuré."""
        system_instruction, user_prompt = prompt_loader.load_and_render(
            "cv_transcription",
            markdown_content=markdown_content
        )
        return self.ai_service.generate_structured(
            prompt=user_prompt,
            response_schema=CandidateProfile,
            system_instruction=system_instruction,
            operation="CV_MARKDOWN_TRANSCRIPTION"
        )

cv_transcriber_service = CVTranscriberService()
