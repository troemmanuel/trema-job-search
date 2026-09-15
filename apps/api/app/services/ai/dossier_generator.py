import logging
from typing import Optional, Tuple
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobNormalizedData
from app.schemas.application import TailoredCV, CoverLetter
from app.schemas.dossier import ApplicationDossier
from app.services.ai.accents import restore_accents, vocabulary_from
from app.services.ai.cv_postprocessor import finalize_tailored_cv
from app.services.ai.cv_generator import cv_generator_service
from app.services.ai.letter_generator import letter_generator_service
from app.services.ai.gemini import gemini_service
from app.llm import router

logger = logging.getLogger(__name__)

class DossierGeneratorService:
    """Service de génération groupée (Bundle) : CV personnalisé + Lettre de motivation en un seul appel IA."""

    def __init__(self, ai_service=None):
        self.ai_service = ai_service or gemini_service

    def generate(
        self,
        job_id: str,
        profile: CandidateProfile,
        job_data: JobNormalizedData,
        letter_type: str = "cover_letter",
        application_id: Optional[str] = None,
        force_refresh: bool = False
    ) -> Tuple[Optional[TailoredCV], Optional[CoverLetter]]:
        """Génère simultanément le CV adapté et la Lettre de motivation en une seule requête structurée.

        Returns:
            Tuple[Optional[TailoredCV], Optional[CoverLetter]]
        """
        job_lang = (getattr(job_data, "language", None) or "fr").lower()[:2]
        if job_lang not in ("fr", "en"):
            job_lang = "fr"

        lang_label = "anglais (English)" if job_lang == "en" else "français"

        system_instruction = (
            f"Tu es un expert senior en recrutement et en stratégie de candidature.\n"
            f"Ta mission est de produire un DOSSIER DE CANDIDATURE COMPLET comprenant :\n"
            f"1. Un CV adapté et percutant ('tailored_cv')\n"
            f"2. Une lettre de motivation personnalisée et convaincante ('cover_letter')\n\n"
            f"COHÉRENCE DU DOSSIER :\n"
            f"- L'accroche du CV ('summary') et les réalisations mises en avant ('experience_highlights') "
            f"doivent être en parfaite symbiose avec les arguments clés exposés dans la lettre de motivation.\n"
            f"- La lettre doit s'adresser au recruteur avec professionnalisme, sans en-tête ni signature fictive.\n\n"
            f"EXIGENCE STRICTE DE LANGUE :\n"
            f"L'offre est identifiée en {lang_label} (code '{job_lang}').\n"
            f"Tous les textes générés (titres, accroches, réalisations, compétences, corps de la lettre) "
            f"DOIVENT être intégralement rédigés en {lang_label}.\n"
        )

        if profile.preferences and getattr(profile.preferences, "ai_custom_instructions", None):
            system_instruction += (
                f"\nDirectives spécifiques et ton souhaité par le candidat :\n"
                f"{profile.preferences.ai_custom_instructions}\n"
            )

        user_prompt = (
            f"CANDIDAT (Profil maître) :\n"
            f"{profile.model_dump_json()}\n\n"
            f"OFFRE D'EMPLOI CIBLÉE (id: {job_id}) :\n"
            f"{job_data.model_dump_json()}\n\n"
            f"Génère le dossier de candidature complet (tailored_cv + cover_letter) en respectant scrupuleusement le schéma demandé."
        )

        try:
            # Appel au LLM Router via le schéma groupé
            llm_res = router.generate(
                task="doc_content_generation",
                prompt=user_prompt,
                response_schema=ApplicationDossier,
                system_instruction=system_instruction,
                temperature=0.2,
                force_refresh=force_refresh
            )

            dossier: ApplicationDossier = llm_res.data
            tailored_cv = dossier.tailored_cv
            cover_letter = dossier.cover_letter

            # Post-traitement du CV
            tailored_cv.language = job_lang
            final_cv = finalize_tailored_cv(tailored_cv, profile, job_data.model_dump())

            # Post-traitement de la Lettre
            cover_letter.language = job_lang
            if job_lang == "fr":
                cover_letter.content = restore_accents(
                    cover_letter.content,
                    vocabulary_from(profile.model_dump(), job_data.model_dump())
                )

            logger.info(f"[DossierGenerator] Génération groupée réussie pour l'offre {job_id} via {llm_res.provider} ({llm_res.latency}s)")
            return final_cv, cover_letter

        except Exception as e:
            logger.warning(
                f"[DossierGenerator] La génération groupée a échoué ({e}). "
                f"Bascule de sécurité vers les générateurs individuels (CV puis Lettre)..."
            )

            # Repli de sécurité : générateurs individuels
            cv = cv_generator_service.generate(
                job_id=job_id,
                profile=profile,
                job_data=job_data,
                application_id=application_id
            )
            letter = letter_generator_service.generate(
                profile=profile,
                job_data=job_data,
                letter_type=letter_type,
                application_id=application_id
            )
            return cv, letter

dossier_generator_service = DossierGeneratorService()
