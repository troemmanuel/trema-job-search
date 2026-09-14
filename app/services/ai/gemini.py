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

    def get_configured_model(self) -> str:
        """Récupère le modèle IA configuré dans les préférences candidat, ou la valeur Config par défaut."""
        try:
            from app.services.storage import supabase_service
            profile = supabase_service.get_active_candidate_profile()
            if profile and profile.get("preferences") and profile["preferences"].get("ai_model"):
                return profile["preferences"]["ai_model"]
        except Exception:
            pass
        return self.config.GEMINI_MODEL

    def get_configured_temperature(self) -> float:
        """Récupère la température configurée dans les préférences candidat, ou 0.2 par défaut."""
        try:
            from app.services.storage import supabase_service
            profile = supabase_service.get_active_candidate_profile()
            if profile and profile.get("preferences") and "ai_temperature" in profile["preferences"]:
                return float(profile["preferences"]["ai_temperature"])
        except Exception:
            pass
        return 0.2

    def test_connection(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Teste la connectivité à l'API Gemini et au modèle spécifié."""
        if not self.client:
            return {
                "success": False,
                "error": "Clé API Gemini non configurée (GEMINI_API_KEY manquante)."
            }

        target_model = model_name or self.get_configured_model()
        import time
        start_time = time.time()
        try:
            response = self.client.models.generate_content(
                model=target_model,
                contents="Réponds simplement par le mot 'OK'.",
            )
            elapsed = round((time.time() - start_time) * 1000)
            text = (response.text or "").strip()
            return {
                "success": True,
                "model": target_model,
                "response_time_ms": elapsed,
                "output": text
            }
        except Exception as e:
            elapsed = round((time.time() - start_time) * 1000)
            return {
                "success": False,
                "model": target_model,
                "response_time_ms": elapsed,
                "error": str(e)
            }

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[BaseModel],
        system_instruction: Optional[str] = None,
        operation: str = "GENERIC",
        application_id: Optional[str] = None,
        override_model: Optional[str] = None
    ) -> Optional[BaseModel]:
        """Génère un résultat structuré validé par un schéma Pydantic via le LLM Router multi-provider."""
        from app.llm import router

        temperature = self.get_configured_temperature()
        target_model = override_model or self.get_configured_model()

        try:
            llm_result = router.generate(
                task=operation,
                prompt=prompt,
                response_schema=response_schema,
                system_instruction=system_instruction,
                temperature=temperature,
                override_model=target_model
            )
            data = llm_result.data
            output_dump = data.model_dump() if hasattr(data, "model_dump") else (data if isinstance(data, dict) else {"output": str(data)})
            self.log_ai_run(
                operation=operation,
                input_data={
                    "prompt": prompt,
                    "system_instruction": system_instruction,
                    "model": llm_result.model,
                    "provider": llm_result.provider,
                    "fallback_used": llm_result.fallback_used
                },
                output_data=output_dump,
                status="SUCCESS",
                application_id=application_id
            )
            return data
        except Exception as e:
            logger.error(f"[GeminiService] Échec génération structurée via LLM Router ({operation}): {e}")
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
