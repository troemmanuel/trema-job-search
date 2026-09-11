import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from app.config import Config
from app.services.notion.client import (
    notion_service,
    SUPABASE_TO_NOTION_STATUS,
    NOTION_TO_SUPABASE_STATUS,
)
from app.services.storage.supabase_service import supabase_service

logger = logging.getLogger(__name__)

def parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse une chaîne ISO 8601 en objet datetime timezone-aware UTC."""
    if not dt_str:
        return None
    try:
        # Gérer le 'Z' de fin
        clean_str = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

class NotionSyncService:
    """Service de synchronisation bidirectionnelle entre Notion CRM et Supabase."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()

    def fetch_all_notion_pages(self) -> List[Dict[str, Any]]:
        """Récupère et normalise toutes les pages de la base/data-source Notion."""
        client = notion_service.client
        if not client or not self.config.NOTION_DATABASE_ID:
            logger.warning("Notion non configuré pour la récupération des fiches.")
            return []

        try:
            # Récupération du chemin de requête (compatible tables / data sources)
            db_res = client.request(path=f"databases/{self.config.NOTION_DATABASE_ID}", method="GET")
            data_sources = db_res.get("data_sources", [])
            query_path = f"data_sources/{data_sources[0]['id']}/query" if data_sources else f"databases/{self.config.NOTION_DATABASE_ID}/query"

            pages_raw: List[Dict[str, Any]] = []
            has_more = True
            start_cursor = None

            while has_more:
                body: Dict[str, Any] = {"page_size": 100}
                if start_cursor:
                    body["start_cursor"] = start_cursor

                res = client.request(path=query_path, method="POST", body=body)
                results = res.get("results", [])
                pages_raw.extend(results)

                has_more = res.get("has_more", False)
                start_cursor = res.get("next_cursor")

            normalized_pages: List[Dict[str, Any]] = []
            for p in pages_raw:
                parsed = self._parse_notion_page(p)
                if parsed:
                    normalized_pages.append(parsed)

            logger.info(f"{len(normalized_pages)} pages extraites de la base Notion.")
            return normalized_pages

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des pages Notion: {e}")
            return []

    def _parse_notion_page(self, page: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extrait les champs pertinents d'une page Notion brute."""
        page_id = page.get("id")
        if not page_id:
            return None

        props = page.get("properties", {})

        # Entreprise (title)
        company = ""
        title_items = props.get("Entreprise", {}).get("title", [])
        if title_items:
            company = title_items[0].get("plain_text", "").strip()

        # Poste (rich_text)
        job_title = ""
        poste_items = props.get("Poste", {}).get("rich_text", [])
        if poste_items:
            job_title = poste_items[0].get("plain_text", "").strip()

        # Statut (select)
        status = None
        statut_obj = props.get("Statut", {})
        if statut_obj.get("type") == "select" and statut_obj.get("select"):
            status = statut_obj["select"].get("name")

        # Date de candidature
        applied_date = None
        date_cand = props.get("Date de candidature", {}).get("date")
        if date_cand:
            applied_date = date_cand.get("start")

        # Date de refus & motif
        refusal_date = None
        date_ref = props.get("Date de refus", {}).get("date")
        if date_ref:
            refusal_date = date_ref.get("start")

        refusal_reason = ""
        motif_obj = props.get("Motif de refus", {})
        if motif_obj.get("type") == "rich_text" and motif_obj.get("rich_text"):
            refusal_reason = motif_obj["rich_text"][0].get("plain_text", "").strip()
        elif motif_obj.get("type") == "select" and motif_obj.get("select"):
            refusal_reason = motif_obj["select"].get("name", "").strip()

        # Lien de l'offre
        job_url = props.get("Lien de l'offre", {}).get("url")

        # N suivi
        n_suivi = props.get("N suivi", {}).get("number")

        # Type de l'entreprise (rich_text)
        company_type = ""
        type_items = props.get("Type", {}).get("rich_text", [])
        if type_items:
            company_type = type_items[0].get("plain_text", "").strip()

        # Domaine d'activité (rich_text)
        domain = ""
        domain_items = props.get("Domaine", {}).get("rich_text", [])
        if domain_items:
            domain = domain_items[0].get("plain_text", "").strip()

        return {
            "id": page_id,
            "last_edited_time": page.get("last_edited_time"),
            "company": company,
            "job_title": job_title,
            "status": status,
            "applied_date": applied_date,
            "refusal_date": refusal_date,
            "refusal_reason": refusal_reason,
            "job_url": job_url,
            "n_suivi": n_suivi,
            "company_type": company_type,
            "domain": domain,
        }

    def reconcile(self) -> Dict[str, Any]:
        """
        Exécute la réconciliation bidirectionnelle complète :
        1. Compare les horodatages de modification entre Notion et Supabase.
        2. Propage les changements de statut Notion -> Supabase si Notion est plus récent.
        3. Propage les changements de statut Supabase -> Notion si Supabase est plus récent.
        4. Aligne les dates de candidature et les motifs de refus.
        5. Associe automatiquement les fiches non liées par identifiant.
        """
        report: Dict[str, Any] = {
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_notion_pages": 0,
            "total_supabase_apps": 0,
            "matched_count": 0,
            "updated_supabase_count": 0,
            "updated_notion_count": 0,
            "details": [],
            "errors": []
        }

        # 1. Récupération des données des deux côtés
        notion_pages = self.fetch_all_notion_pages()
        supabase_apps = supabase_service.get_all_applications_for_sync()

        report["total_notion_pages"] = len(notion_pages)
        report["total_supabase_apps"] = len(supabase_apps)

        if not notion_pages and not supabase_apps:
            logger.info("Aucune donnée à réconcilier.")
            return report

        # 2. Indexation des candidatures Supabase
        apps_by_notion_id: Dict[str, Dict[str, Any]] = {}
        apps_by_company_title: Dict[str, Dict[str, Any]] = {}

        for app in supabase_apps:
            notion_id = app.get("notion_page_id")
            if notion_id:
                apps_by_notion_id[notion_id] = app

            job = app.get("jobs") or {}
            comp = (job.get("company") or "").strip().lower()
            title = (job.get("title") or "").strip().lower()
            if comp and title:
                apps_by_company_title[f"{comp}::{title}"] = app

        # 3. Parcours des pages Notion pour rapprochement et réconciliation
        matched_app_ids = set()

        for page in notion_pages:
            page_id = page["id"]
            company = page.get("company") or ""
            job_title = page.get("job_title") or ""
            notion_status = page.get("status")
            notion_last_edited = parse_iso_datetime(page.get("last_edited_time"))

            # Rapprochement primaire par ID Notion
            matched_app = apps_by_notion_id.get(page_id)

            # Rapprochement secondaire par Entreprise + Titre
            if not matched_app and company and job_title:
                key = f"{company.strip().lower()}::{job_title.strip().lower()}"
                matched_app = apps_by_company_title.get(key)
                if matched_app:
                    # Lier l'ID Notion dans Supabase
                    supabase_service.update_application(matched_app["id"], {"notion_page_id": page_id})
                    matched_app["notion_page_id"] = page_id
                    report["details"].append({
                        "action": "LINKED_NOTION_ID",
                        "application_id": matched_app["id"],
                        "notion_page_id": page_id,
                        "company": company,
                        "title": job_title
                    })

            if not matched_app:
                continue

            report["matched_count"] += 1
            matched_app_ids.add(matched_app["id"])

            # Comparaison des statuts
            supabase_status = matched_app.get("status")
            mapped_supabase_status = NOTION_TO_SUPABASE_STATUS.get(notion_status) if notion_status else None
            mapped_notion_status = SUPABASE_TO_NOTION_STATUS.get(supabase_status) if supabase_status else None

            supabase_updated_at = parse_iso_datetime(matched_app.get("updated_at") or matched_app.get("created_at"))

            # Cas A : Statuts divergents -> arbitrage par horodatage
            if mapped_supabase_status and mapped_supabase_status != supabase_status:
                is_notion_newer = True
                if notion_last_edited and supabase_updated_at:
                    is_notion_newer = notion_last_edited >= supabase_updated_at

                if is_notion_newer:
                    # Notion gagne : on met à jour Supabase
                    update_data: Dict[str, Any] = {"status": mapped_supabase_status}

                    # Mise à jour date de candidature si passage en APPLIED
                    if mapped_supabase_status == "APPLIED":
                        app_date = page.get("applied_date")
                        if app_date:
                            update_data["applied_at"] = app_date
                        elif not matched_app.get("applied_at"):
                            update_data["applied_at"] = (notion_last_edited or datetime.now(timezone.utc)).isoformat()

                    # Mise à jour des motifs de refus éventuels
                    if mapped_supabase_status == "REJECTED":
                        notes = matched_app.get("notes") or ""
                        extra_notes = []
                        if page.get("refusal_date"):
                            extra_notes.append(f"Refus le : {page['refusal_date']}")
                        if page.get("refusal_reason"):
                            extra_notes.append(f"Motif : {page['refusal_reason']}")
                        if extra_notes:
                            update_data["notes"] = (notes + "\n" + " | ".join(extra_notes)).strip()

                    ok = supabase_service.update_application(matched_app["id"], update_data)
                    if ok:
                        report["updated_supabase_count"] += 1
                        report["details"].append({
                            "action": "UPDATED_SUPABASE",
                            "application_id": matched_app["id"],
                            "company": company,
                            "title": job_title,
                            "old_status": supabase_status,
                            "new_status": mapped_supabase_status,
                            "source_notion_status": notion_status
                        })
                else:
                    # Supabase gagne : on met à jour Notion
                    if mapped_notion_status:
                        applied_date = matched_app.get("applied_at")
                        if applied_date and isinstance(applied_date, str) and "T" in applied_date:
                            applied_date = applied_date.split("T")[0]

                        ok = notion_service.update_page_status(
                            page_id=page_id,
                            status_name=mapped_notion_status,
                            applied_date=applied_date if mapped_notion_status == "Candidature envoyée" else None
                        )
                        if ok:
                            report["updated_notion_count"] += 1
                            report["details"].append({
                                "action": "UPDATED_NOTION",
                                "page_id": page_id,
                                "company": company,
                                "title": job_title,
                                "old_status": notion_status,
                                "new_status": mapped_notion_status
                            })

            # Cas B : Statuts concordants mais date de candidature manquante dans Supabase
            elif mapped_supabase_status == "APPLIED" and not matched_app.get("applied_at"):
                applied_date_val = page.get("applied_date") or (notion_last_edited.isoformat() if notion_last_edited else datetime.now(timezone.utc).isoformat())
                supabase_service.update_application(matched_app["id"], {"applied_at": applied_date_val})
                report["updated_supabase_count"] += 1
                report["details"].append({
                    "action": "BACKFILLED_APPLIED_AT",
                    "application_id": matched_app["id"],
                    "company": company,
                    "applied_at": applied_date_val
                })

            # Cas C : Enrichissement automatique du Type et du Domaine d'activité si absent dans Notion
            job_obj = matched_app.get("jobs") or {}
            match_analysis = job_obj.get("match_analysis") or {}
            normalized_data = job_obj.get("normalized_data") or {}

            from app.services.ingestion.company_classifier import classify_company
            cl_type, cl_domain = classify_company(
                company=company,
                title=job_title,
                description=job_obj.get("description", ""),
                raw_data=job_obj.get("raw_data")
            )
            expected_type = match_analysis.get("company_type") or normalized_data.get("company_type") or cl_type
            expected_domain = match_analysis.get("company_domain") or normalized_data.get("domain") or cl_domain

            notion_type = page.get("company_type")
            notion_dom = page.get("domain")
            props_to_enrich = {}

            if not notion_type and expected_type:
                props_to_enrich["Type"] = {"rich_text": [{"text": {"content": expected_type[:2000]}}]}
            if (not notion_dom or notion_dom == "Ingénierie Logicielle / Backend & Cloud") and expected_domain:
                props_to_enrich["Domaine"] = {"rich_text": [{"text": {"content": expected_domain[:2000]}}]}

            if props_to_enrich:
                enriched = notion_service.update_page_properties(page_id, props_to_enrich)
                if enriched:
                    report["details"].append({
                        "action": "ENRICHED_NOTION_TYPE_DOMAIN",
                        "page_id": page_id,
                        "company": company,
                        "type": expected_type,
                        "domain": expected_domain
                    })

        logger.info(
            f"Réconciliation terminée : {report['matched_count']} fiches appariées, "
            f"{report['updated_supabase_count']} màj Supabase, {report['updated_notion_count']} màj Notion."
        )
        return report

# Singleton
notion_sync_service = NotionSyncService()
