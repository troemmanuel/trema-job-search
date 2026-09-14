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
        """Génère un résultat structuré validé par un schéma Pydantic avec bascule automatique de modèle."""
        if not self.client:
            logger.warning("Client Gemini non disponible.")
            return None

        from google.genai import types
        import time

        temperature = self.get_configured_temperature()
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=temperature,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
        )
        if system_instruction:
            config.system_instruction = system_instruction

        configured_model = override_model or self.get_configured_model()

        # Modèles ordonnés avec bascule automatique si quota 429 ou indisponibilité 503
        candidate_models = [
            configured_model,
            self.config.GEMINI_MODEL,
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-2.5-flash-lite",
            "gemini-flash-latest"
        ]
        models_to_try = [m for i, m in enumerate(candidate_models) if m and m not in candidate_models[:i]]
        last_error = None

        for model_name in models_to_try:
            max_retries_per_model = 2
            for attempt in range(1, max_retries_per_model + 1):
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config,
                    )
                    result = response_schema.model_validate_json(response.text)
                    self.log_ai_run(
                        operation=operation,
                        input_data={"prompt": prompt, "system_instruction": system_instruction, "model": model_name},
                        output_data=result.model_dump(),
                        status="SUCCESS",
                        application_id=application_id
                    )
                    return result
                except Exception as e:
                    last_error = e
                    err_str = str(e)
                    logger.warning(f"Tentative {attempt}/{max_retries_per_model} échouée pour {model_name} ({operation}): {err_str}")

                    # Si quota atteint ou modèle surchargé (503), basculer immédiatement vers le modèle suivant
                    if any(code in err_str for code in ["RESOURCE_EXHAUSTED", "Quota exceeded", "503", "UNAVAILABLE", "high demand"]):
                        logger.warning(f"Modèle {model_name} indisponible ou quota atteint ({err_str[:80]}), bascule vers le modèle suivant...")
                        break

                    # Autre erreur, courte pause et tentative suivante
                    time.sleep(1)

        logger.error(f"Erreur définitive appel Gemini generate_structured (tous modèles épuisés): {last_error}")
        self.log_ai_run(
            operation=operation,
            input_data={"prompt": prompt, "system_instruction": system_instruction},
            output_data=None,
            status="ERROR",
            error_message=str(last_error),
            application_id=application_id
        )
        return None

gemini_service = GeminiService()
