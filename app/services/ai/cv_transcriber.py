import logging
from typing import Optional
from app.schemas.candidate import CandidateProfile
from app.services.ai.gemini import gemini_service

logger = logging.getLogger(__name__)

SYSTEM_TRANSCRIBER_PROMPT = """Tu es un expert RH et analyseur de CV.
Ta mission est de transcrire fidèlement un CV fourni au format Markdown en un objet structuré conforme au schéma CandidateProfile.

RÈGLES ABSOLUES :
1. RÈGLE ANTI-HALLUCINATION : Ne jamais inventer d'expérience, d'entreprise, de diplôme ou de compétence qui ne figure pas dans le texte Markdown.
2. Identifiants d'expérience : Attribue à chaque expérience professionnelle un identifiant unique séquentiel (ex: "exp_001", "exp_002", etc.).
3. Catégorisation des compétences : Répartis les compétences listées dans les 4 catégories appropriées :
   - technical (langages de programmation, frameworks, bases de données, architectures)
   - tools (logiciels, SaaS, IDE, outils de productivité, Jira, Git, etc.)
   - business (méthodologies produit, gestion de projet, KPI, vente, analyse de marché)
   - soft_skills (communication, leadership, pédagogie, résolution de problèmes)
4. Préférences : Si le document contient des souhaits (titres visés, télétravail, salaire minimum, localisation), extrais-les dans 'preferences'. Sinon, déduis les 'target_titles' probables à partir du rôle le plus récent du candidat.
"""

class CVTranscriberService:
    def __init__(self, ai_service=None):
        self.ai_service = ai_service or gemini_service

    def transcribe_markdown(self, markdown_content: str) -> Optional[CandidateProfile]:
        """Transcrit le contenu d'un fichier Markdown en un profil candidat structuré."""
        prompt = f"""
Voici le CV rédigé en Markdown à transcrire :

---
{markdown_content}
---

Transcris toutes ces informations dans la structure exacte de CandidateProfile.
"""
        return self.ai_service.generate_structured(
            prompt=prompt,
            response_schema=CandidateProfile,
            system_instruction=SYSTEM_TRANSCRIBER_PROMPT,
            operation="CV_MARKDOWN_TRANSCRIPTION"
        )

cv_transcriber_service = CVTranscriberService()
