import logging
from typing import Optional, Dict, Any
from app.config import Config

logger = logging.getLogger(__name__)

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
        salary: Optional[int] = None,
        cv_url: Optional[str] = None,
        letter_url: Optional[str] = None,
        notes: Optional[str] = None,
        notion_page_id: Optional[str] = None
    ) -> Optional[str]:
        """Crée ou met à jour une page de candidature dans la base Notion."""
        if not self.client or not self.config.NOTION_DATABASE_ID:
            logger.info(f"Notion non configuré. Synchronisation simulée pour application {application_id}")
            return notion_page_id or f"simulated_page_{application_id}"

        # Déterminer la priorité textuelle
        priority_label = "🟠 À revoir"
        if score is not None:
            if score >= self.config.MATCH_THRESHOLD_PRIORITY:
                priority_label = "🔥 Priorité"
            elif score >= self.config.MATCH_THRESHOLD_RECOMMENDED:
                priority_label = "✅ Recommandée"
            elif score < self.config.MATCH_THRESHOLD_REVIEW:
                priority_label = "❌ Ignorer"

        properties: Dict[str, Any] = {
            "Company": {"title": [{"text": {"content": company or "N/A"}}]},
            "Job": {"rich_text": [{"text": {"content": job_title or "N/A"}}]},
            "URL": {"url": job_url},
            "Status": {"select": {"name": status}},
            "Priority": {"select": {"name": priority_label}}
        }

        if score is not None:
            properties["Score"] = {"number": score}
        if location:
            properties["Location"] = {"rich_text": [{"text": {"content": location}}]}
        if salary:
            properties["Salary"] = {"number": salary}
        if cv_url:
            properties["CV"] = {"url": cv_url}
        if letter_url:
            properties["Letter"] = {"url": letter_url}
        if notes:
            properties["Notes"] = {"rich_text": [{"text": {"content": notes}}]}

        try:
            if notion_page_id and not notion_page_id.startswith("simulated_"):
                # Mise à jour
                self.client.pages.update(page_id=notion_page_id, properties=properties)
                logger.info(f"Page Notion mise à jour : {notion_page_id}")
                return notion_page_id
            else:
                # Création
                response = self.client.pages.create(
                    parent={"database_id": self.config.NOTION_DATABASE_ID},
                    properties=properties
                )
                new_page_id = response.get("id")
                logger.info(f"Page Notion créée : {new_page_id}")
                return new_page_id
        except Exception as e:
            logger.error(f"Erreur lors de la synchronisation Notion: {e}")
            return None

notion_service = NotionService()
