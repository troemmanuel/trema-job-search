import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from app.config import Config

logger = logging.getLogger(__name__)

STATUS_MAPPING = {
    "QUALIFIED": "Action requise",
    "PREPARING": "Candidature prête - en attente de validation",
    "PREPARED": "Candidature prête - en attente de validation",
    "READY": "Candidature prête - en attente de validation",
    "APPLIED": "Candidature envoyée",
    "REVIEW": "À vérifier",
    "REJECTED": "Refusée",
}

class NotionService:
    """Service d'intégration Notion API pour le suivi CRM des candidatures."""

    def __init__(self, config: Config = None):
        self.config = config or Config()
        self._client: Optional[Any] = None

    @property
    def client(self):
        if self._client is None:
            if not self.config.NOTION_TOKEN:
                logger.warning("NOTION_TOKEN non configuré.")
                return None
            try:
                from notion_client import Client
                self._client = Client(auth=self.config.NOTION_TOKEN)
            except Exception as e:
                logger.error(f"Erreur initialisation client Notion: {e}")
                return None
        return self._client

    def is_configured(self) -> bool:
        return bool(self.config.NOTION_TOKEN and self.config.NOTION_DATABASE_ID)

    def sync_application(
        self,
        application_id: str,
        company: str,
        job_title: str,
        job_url: str,
        score: Optional[int],
        status: str,
        location: Optional[str] = None,
        contract_type: Optional[str] = None,
        domain: Optional[str] = None,
        cv_url: Optional[str] = None,
        letter_url: Optional[str] = None,
        cover_letter: Optional[str] = None,
        answers: Optional[Dict[str, Any]] = None,
        match_analysis: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
        notion_page_id: Optional[str] = None
    ) -> Optional[str]:
        """Crée ou met à jour une page de candidature dans la base Notion de suivi."""
        if not self.client or not self.config.NOTION_DATABASE_ID:
            logger.info(f"Notion non configuré. Synchronisation simulée pour application {application_id}")
            return notion_page_id or f"simulated_page_{application_id}"

        clean_status = STATUS_MAPPING.get(status, "Candidature prête - en attente de validation")

        # 1. Propriétés alignées sur le schéma de la base 'Suivi candidatures'
        properties: Dict[str, Any] = {
            "Entreprise": {"title": [{"text": {"content": (company or "Entreprise")[:2000]}}]},
            "Poste": {"rich_text": [{"text": {"content": (job_title or "Poste inconnu")[:2000]}}]},
            "Statut": {"select": {"name": clean_status}}
        }

        if job_url and (job_url.startswith("http://") or job_url.startswith("https://")):
            properties["Lien de l'offre"] = {"url": job_url}

        if location:
            properties["Lieu"] = {"rich_text": [{"text": {"content": location[:2000]}}]}

        if contract_type:
            properties["Type"] = {"rich_text": [{"text": {"content": contract_type[:2000]}}]}

        if domain:
            properties["Domaine"] = {"rich_text": [{"text": {"content": domain[:2000]}}]}

        if cv_url:
            clean_company = "".join(c for c in company if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
            properties["CV utilisé"] = {"rich_text": [{"text": {"content": f"CV_{clean_company}.pdf", "link": {"url": cv_url}}}]}

        if status == "APPLIED":
            properties["Date de candidature"] = {"date": {"start": datetime.now(timezone.utc).strftime("%Y-%m-%d")}}

        # 2. Construction des blocs de contenu pour le corps de la page
        children_blocks = self._build_page_blocks(
            score=score,
            match_analysis=match_analysis,
            cover_letter=cover_letter,
            answers=answers,
            cv_url=cv_url,
            notes=notes
        )

        try:
            if notion_page_id and not notion_page_id.startswith("simulated_"):
                # Mise à jour des propriétés
                self.client.pages.update(page_id=notion_page_id, properties=properties)
                logger.info(f"Page Notion mise à jour : {notion_page_id}")
                return notion_page_id
            else:
                # Création de la page avec ses blocs enfants
                payload = {
                    "parent": {"database_id": self.config.NOTION_DATABASE_ID},
                    "properties": properties
                }
                if children_blocks:
                    payload["children"] = children_blocks[:100]  # Notion limite à 100 blocs par requête

                response = self.client.pages.create(**payload)
                new_page_id = response.get("id")
                logger.info(f"Page Notion créée avec succès : {new_page_id}")
                return new_page_id
        except Exception as e:
            logger.error(f"Erreur lors de la synchronisation Notion: {e}")
            return None

    def _build_page_blocks(
        self,
        score: Optional[int],
        match_analysis: Optional[Dict[str, Any]],
        cover_letter: Optional[str],
        answers: Optional[Dict[str, Any]],
        cv_url: Optional[str],
        notes: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Construit les blocs riches de la page Notion (synthèse IA, lettre, réponses)."""
        blocks: List[Dict[str, Any]] = []

        # En-tête Callout Matching
        if score is not None:
            analysis = match_analysis or {}
            level = analysis.get("level", "RECOMMENDED")
            recommendation = analysis.get("recommendation", "APPLY")
            blocks.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": f"Score de Matching IA : {score}/100 ({level}) — Recommandation : {recommendation}"}
                    }],
                    "icon": {"type": "emoji", "emoji": "🎯"},
                    "color": "green_background" if score >= 80 else "yellow_background"
                }
            })

        # Points forts & Points de vigilance
        if match_analysis:
            strengths = match_analysis.get("strengths", [])
            concerns = match_analysis.get("concerns", [])
            if strengths or concerns:
                blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Analyse de correspondance"}}]}
                })
                for s in strengths:
                    blocks.append({
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": f"✅ {s}"}}]}
                    })
                for c in concerns:
                    blocks.append({
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": f"⚠️ {c}"}}]}
                    })

        # Lettre de motivation
        if cover_letter:
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Lettre de motivation générée"}}]}
            })
            # Notion limite les blocs texte à 2000 caractères
            paragraphs = cover_letter.split("\n\n")
            for p in paragraphs:
                p_clean = p.strip()
                if p_clean:
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"type": "text", "text": {"content": p_clean[:2000]}}]}
                    })

        # Réponses préparées
        if answers and isinstance(answers, dict):
            questions = answers.get("questions", [])
            if questions:
                blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Réponses préparées (Entretiens / Formulaires)"}}]}
                })
                for q in questions:
                    q_text = q.get("question", "")
                    a_text = q.get("answer", "")
                    conf = q.get("confidence", "HIGH")
                    flag = " ⚠️ [À VALIDER]" if q.get("validation_required") else ""
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [
                                {"type": "text", "text": {"content": f"Q : {q_text}\n", "link": None}, "annotations": {"bold": True}},
                                {"type": "text", "text": {"content": f"R : {a_text}\n", "link": None}},
                                {"type": "text", "text": {"content": f"Confiance : {conf}{flag}", "link": None}, "annotations": {"italic": True, "color": "gray"}}
                            ]
                        }
                    })

        # Lien de téléchargement CV PDF
        if cv_url:
            blocks.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": "📥 Télécharger le CV personnalisé (PDF)", "link": {"url": cv_url}}
                    }],
                    "icon": {"type": "emoji", "emoji": "📄"},
                    "color": "blue_background"
                }
            })

        return blocks

notion_service = NotionService()
