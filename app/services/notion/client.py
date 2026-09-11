import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from app.config import Config

logger = logging.getLogger(__name__)

# Mapping Supabase status -> Notion status
SUPABASE_TO_NOTION_STATUS = {
    "QUALIFIED": "Action requise",
    "PREPARING": "Candidature prête - en attente de validation",
    "PREPARED": "Candidature prête - en attente de validation",
    "READY": "Candidature prête - en attente de validation",
    "APPLIED": "Candidature envoyée",
    "INTERVIEW_HR": "Entretien RH confirmé",
    "INTERVIEW_TECH": "Entretien RH confirmé",
    "INTERVIEW": "Entretien RH confirmé",
    "OFFER": "Offre reçue/Acceptée",
    "REJECTED": "Refusée",
    "REVIEW": "À vérifier",
}

# Mapping Notion status -> Supabase status
NOTION_TO_SUPABASE_STATUS = {
    "Candidature prête - en attente de validation": "PREPARED",
    "Candidature envoyée": "APPLIED",
    "En attente de reponse": "APPLIED",
    "Entretien RH confirmé": "INTERVIEW_HR",
    "Etretien telephonique": "INTERVIEW_HR",
    "Offre reçue/Acceptée": "OFFER",
    "Refusée": "REJECTED",
    "Refusée - Après entretien RH": "REJECTED",
    "Action requise": "QUALIFIED",
    "À vérifier": "REVIEW",
    "Contacter via LinkedIn": "QUALIFIED",
}

STATUS_MAPPING = SUPABASE_TO_NOTION_STATUS

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

    def get_next_suivi_number(self) -> int:
        """Récupère le plus grand 'N suivi' existant dans Notion et l'incrémente de 1."""
        if not self.client or not self.config.NOTION_DATABASE_ID:
            return 1

        try:
            db_res = self.client.request(path=f"databases/{self.config.NOTION_DATABASE_ID}", method="GET")
            data_sources = db_res.get("data_sources", [])
            query_path = f"data_sources/{data_sources[0]['id']}/query" if data_sources else f"databases/{self.config.NOTION_DATABASE_ID}/query"

            res = self.client.request(
                path=query_path,
                method="POST",
                body={
                    "page_size": 100,
                    "sorts": [{"property": "N suivi", "direction": "descending"}]
                }
            )
            results = res.get("results", [])
            max_n = 0
            for page in results:
                n = page.get("properties", {}).get("N suivi", {}).get("number")
                if n and isinstance(n, (int, float)) and n > max_n:
                    max_n = int(n)
            return max_n + 1 if max_n > 0 else 163
        except Exception as e:
            logger.warning(f"Impossible de récupérer le max N suivi dans Notion ({e}), repli sur 163")
            return 163

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
        company_type: Optional[str] = None,
        cv_url: Optional[str] = None,
        letter_url: Optional[str] = None,
        cover_letter: Optional[str] = None,
        answers: Optional[Dict[str, Any]] = None,
        match_analysis: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
        notion_page_id: Optional[str] = None
    ) -> Optional[str]:
        """Crée ou met à jour une page de candidature dans la base Notion de suivi avec N suivi incrémental."""
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

        # N suivi incrémental si nouvelle page
        if not notion_page_id or notion_page_id.startswith("simulated_"):
            next_n = self.get_next_suivi_number()
            properties["N suivi"] = {"number": next_n}

        if job_url and (job_url.startswith("http://") or job_url.startswith("https://")):
            properties["Lien de l'offre"] = {"url": job_url}

        if location:
            properties["Lieu"] = {"rich_text": [{"text": {"content": location[:2000]}}]}

        if company_type:
            properties["Type"] = {"rich_text": [{"text": {"content": company_type[:2000]}}]}

        if domain:
            properties["Domaine"] = {"rich_text": [{"text": {"content": domain[:2000]}}]}

        if cv_url:
            from app.services.documents.renderer import sanitize_name
            clean_company = sanitize_name(company, 30) or "Entreprise"
            clean_title = sanitize_name(job_title, 35)
            cv_filename = f"Emmanuel_TRO_CV_{clean_company}_{clean_title}.pdf" if clean_title else f"Emmanuel_TRO_CV_{clean_company}.pdf"
            is_valid_url = bool(cv_url and (cv_url.startswith("http://") or cv_url.startswith("https://")))
            rich_item = {"type": "text", "text": {"content": cv_filename}}
            if is_valid_url:
                rich_item["text"]["link"] = {"url": cv_url}
            properties["CV utilisé"] = {"rich_text": [rich_item]}

        if status == "APPLIED":
            properties["Date de candidature"] = {"date": {"start": datetime.now(timezone.utc).strftime("%Y-%m-%d")}}


        # 2. Construction des blocs de contenu pour le corps de la page
        children_blocks = self._build_page_blocks(
            score=score,
            match_analysis=match_analysis,
            cover_letter=cover_letter,
            answers=answers,
            cv_url=cv_url,
            letter_url=letter_url,
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

    def update_page_status(self, page_id: str, status_name: str, applied_date: Optional[str] = None) -> bool:
        """Met à jour le statut et optionnellement la date de candidature d'une page Notion existante."""
        if not self.client:
            logger.info(f"Notion non configuré. Mise à jour statut simulée pour {page_id} -> {status_name}")
            return True

        properties: Dict[str, Any] = {
            "Statut": {"select": {"name": status_name}}
        }
        if applied_date:
            properties["Date de candidature"] = {"date": {"start": applied_date}}

        return self.update_page_properties(page_id, properties)

    def update_page_properties(self, page_id: str, properties: Dict[str, Any]) -> bool:
        """Met à jour des propriétés quelconques sur une page Notion existante."""
        if not self.client:
            logger.info(f"Notion non configuré. Mise à jour propriétés simulée pour {page_id}")
            return True
        try:
            self.client.pages.update(page_id=page_id, properties=properties)
            logger.info(f"Propriétés de la page Notion {page_id} mises à jour avec succès.")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des propriétés Notion {page_id}: {e}")
            return False

    def _build_page_blocks(
        self,
        score: Optional[int],
        match_analysis: Optional[Dict[str, Any]],
        cover_letter: Optional[str],
        answers: Optional[Dict[str, Any]],
        cv_url: Optional[str],
        letter_url: Optional[str] = None,
        notes: Optional[str] = None
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

        # Callout Statut Administratif & Mobilité Candidat
        blocks.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{
                    "type": "text",
                    "text": {
                        "content": (
                            "📌 Candidat : Emmanuel TRO (Master MIAGE Rennes)\n"
                            "• Mobilité : Toute la France (Rennes, Paris/IDF, Nantes, Lyon, Toulouse, Bordeaux, Lille, remote)\n"
                            "• Statut administratif : Étudiant en transition vers statut travailleur (démarche standard post-promesse d'embauche)\n"
                            "• Rémunération indicative : Fourchette offre ou 42k€ - 46k€ brut annuel [À VALIDER]"
                        )
                    }
                }],
                "icon": {"type": "emoji", "emoji": "👤"},
                "color": "blue_background"
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

        # Liens de téléchargement CV & Lettre
        valid_cv_url = cv_url if (cv_url and (cv_url.startswith("http://") or cv_url.startswith("https://"))) else None
        valid_letter_url = letter_url if (letter_url and (letter_url.startswith("http://") or letter_url.startswith("https://"))) else None

        if valid_cv_url or valid_letter_url:
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Documents PDF générés"}}]}
            })
            if valid_cv_url:
                blocks.append({
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": "📥 Télécharger le CV personnalisé (PDF)", "link": {"url": valid_cv_url}}
                        }],
                        "icon": {"type": "emoji", "emoji": "📄"},
                        "color": "blue_background"
                    }
                })
            if valid_letter_url:
                blocks.append({
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": "📥 Télécharger la Lettre de motivation (PDF)", "link": {"url": valid_letter_url}}
                        }],
                        "icon": {"type": "emoji", "emoji": "✉️"},
                        "color": "purple_background"
                    }
                })

        return blocks

notion_service = NotionService()
