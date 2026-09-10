import json
import logging
from typing import Optional, Dict, Any, Type
from pydantic import BaseModel
from app.config import Config
from app.services.storage import supabase_service

logger = logging.getLogger(__name__)

class GeminiService:
    """Service d'interaction avec l'API Gemini pour matching et génération structurée."""

    def __init__(self, config: Config = None):
        self.config = config or Config()
        self._client: Optional[Any] = None

    @property
    def client(self):
        if self._client is None:
            if not self.config.GEMINI_API_KEY:
                logger.warning("GEMINI_API_KEY non configurée.")
                return None
            try:
                from google import genai
                self._client = genai.Client(api_key=self.config.GEMINI_API_KEY)
            except Exception as e:
                logger.error(f"Erreur initialisation Google GenAI client: {e}")
                return None
        return self._client

    def is_configured(self) -> bool:
        return bool(self.config.GEMINI_API_KEY)

    def log_ai_run(
        self,
        operation: str,
        input_data: Dict[str, Any],
        output_data: Optional[Dict[str, Any]],
        status: str,
        error_message: Optional[str] = None,
        application_id: Optional[str] = None
    ):
        """Enregistre l'exécution IA dans la table ai_runs pour la traçabilité."""
        if not supabase_service.client:
            logger.info(f"[AI RUN] {operation} - Status: {status}")
            return
        try:
            supabase_service.client.table("ai_runs").insert({
                "operation": operation,
                "model": self.config.GEMINI_MODEL,
                "prompt_version": "v1.0",
                "input_data": input_data,
                "output_data": output_data,
                "status": status,
                "error_message": error_message,
                "application_id": application_id
            }).execute()
        except Exception as e:
            logger.error(f"Erreur enregistrement ai_run: {e}")

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[BaseModel],
        system_instruction: Optional[str] = None,
        operation: str = "GENERIC",
        application_id: Optional[str] = None
    ) -> Optional[BaseModel]:
        """Génère un résultat structuré validé par un schéma Pydantic."""
        if not self.client:
            logger.warning("Client Gemini non disponible.")
            return None

        from google.genai import types

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0.2, # Faible température pour éviter les hallucinations
        )
        if system_instruction:
            config.system_instruction = system_instruction

        try:
            response = self.client.models.generate_content(
                model=self.config.GEMINI_MODEL,
                contents=prompt,
                config=config,
            )
            result = response_schema.model_validate_json(response.text)
            self.log_ai_run(
                operation=operation,
                input_data={"prompt": prompt, "system_instruction": system_instruction},
                output_data=result.model_dump(),
                status="SUCCESS",
                application_id=application_id
            )
            return result
        except Exception as e:
            logger.error(f"Erreur appel Gemini generate_structured: {e}")
            self.log_ai_run(
                operation=operation,
                input_data={"prompt": prompt, "system_instruction": system_instruction},
                output_data=None,
                status="ERROR",
                error_message=str(e),
                application_id=application_id
            )
            return None

gemini_service = GeminiService()
