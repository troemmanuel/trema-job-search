import time
import logging
from typing import Dict, Any, List, Optional
import httpx
from app.config import Config
from app.services.storage import supabase_service
from app.services.ingestion.scraper import job_scraper
from app.services.ingestion.importer import job_importer
from app.services.ingestion.parser import job_parser
from app.services.ai.matcher import matcher_service
from app.services.ai.cv_generator import cv_generator_service
from app.services.ai.letter_generator import letter_generator_service
from app.services.ai.answer_generator import answer_generator_service
from app.services.documents.renderer import document_renderer
from app.services.notion.client import notion_service
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobNormalizedData
from app.services.ingestion.filters import is_company_blacklisted, matches_excluded_keyword, is_esn_company

logger = logging.getLogger(__name__)

# Algolia Credentials pour Welcome to the Jungle (Index public)
WTTJ_ALGOLIA_APP_ID = "CSEKHVMS53"
WTTJ_ALGOLIA_API_KEY = "4bd8f6215d0cc52b26430765769e65a0"
WTTJ_ALGOLIA_INDEX = "wttj_jobs_production_fr"

DURATION_SECONDS = {
    "24h": 24 * 3600,
    "1j": 24 * 3600,
    "1d": 24 * 3600,
    "48h": 48 * 3600,
    "2j": 48 * 3600,
    "3j": 3 * 24 * 3600,
    "3d": 3 * 24 * 3600,
    "7j": 7 * 24 * 3600,
    "7d": 7 * 24 * 3600,
    "1w": 7 * 24 * 3600,
}

CONTRACT_TYPE_MAPPING = {
    "cdi": "contract_type:full_time",
    "full_time": "contract_type:full_time",
    "full-time": "contract_type:full_time",
    "cdd": "contract_type:temporary",
    "temporary": "contract_type:temporary",
    "alternance": "contract_type:apprenticeship",
    "apprentissage": "contract_type:apprenticeship",
    "apprenticeship": "contract_type:apprenticeship",
    "stage": "contract_type:internship",
    "internship": "contract_type:internship",
    "freelance": "contract_type:freelance"
}

class JobCollectorService:
    """Service de collecte automatique et scraping batch des offres d'emploi récentes."""

    def __init__(self, config: Config = None):
        self.config = config or Config()

    def derive_candidate_search_criteria(self, candidate_profile: Optional[CandidateProfile]) -> Dict[str, Any]:
        """
        Extrait automatiquement les critères de recherche à partir du profil candidat maître :
        - Hiérarchie ordonnée du plus générique au plus spécifique basée sur les compétences et titres :
          1. Générique métier : "Ingénieur Logiciel", "Ingénieur Backend", "Développeur Backend"
          2. Spécifique stack / langages maîtrisés : "Développeur Java", "Développeur Python", "Développeur Go"...
          3. Spécifique infra / cloud : "Ingénieur DevOps", "Ingénieur Cloud"
        - Filtres stricts de contrats (ex: CDI -> contract_type:full_time)
        """
        if not candidate_profile:
            return {
                "queries": ["Ingénieur Logiciel", "Backend", "Développeur Java"],
                "contract_facets": [],
                "target_titles": [],
                "contract_types": []
            }

        prefs = candidate_profile.preferences
        target_titles = prefs.target_titles if (prefs and prefs.target_titles) else []
        contract_types = prefs.contract_types if (prefs and prefs.contract_types) else []

        tech_skills = candidate_profile.skills.technical if (candidate_profile.skills and candidate_profile.skills.technical) else []
        tools_skills = candidate_profile.skills.tools if (candidate_profile.skills and candidate_profile.skills.tools) else []

        # Identifier si compétences Cloud / DevOps / Infra
        has_devops = any(
            s.lower() in ["kubernetes", "docker", "aws", "terraform", "ci/cd", "devops", "ansible"]
            for s in (tech_skills + tools_skills)
        )

        # Construction de la hiérarchie ordonnée : du plus GÉNÉRIQUE au plus SPÉCIPHIQUE
        queries = []

        # Niveau 1 : Générique métier
        for gen in ["Ingénieur Logiciel", "Ingénieur Backend", "Développeur Backend"]:
            if gen not in queries:
                queries.append(gen)

        # Niveau 2 : Spécifique langages & frameworks majeurs détectés dynamiquement dans le CV
        key_stacks = [
            "java", "python", "go", "golang", "typescript", "flutter", "react",
            "angular", "c#", "rust", "php", "ruby", "kotlin", "swift", "scala",
            "fastapi", "spring boot", "nestjs", "node.js", "fullstack"
        ]
        for skill in (tech_skills + tools_skills):
            s_lower = skill.strip().lower()
            if s_lower in key_stacks:
                label = "Go" if s_lower in ["go", "golang"] else skill.strip()
                dev_title = f"Développeur {label}"
                if dev_title not in queries:
                    queries.append(dev_title)

        # Niveau 3 : Spécifique Infra / DevOps / Cloud
        if has_devops:
            for inf in ["Ingénieur DevOps", "Ingénieur Cloud"]:
                if inf not in queries:
                    queries.append(inf)


        # Compléter avec les target_titles déclarés en évitant les statuts transitoires
        for t in target_titles:
            import re
            cleaned_base = re.sub(r"\(.*?\)", "", t)
            cleaned = cleaned_base.replace("—", "-").replace("&", " ").split("-")[0].strip()
            if cleaned and cleaned not in queries and len(cleaned) > 2:
                if not any(stop in cleaned.lower() for stop in ["alternance", "stage", "junior", "stagiaire"]):
                    queries.append(cleaned)

        # 2. Filtrer par type de contrat (ex: CDI)
        contract_facets = []
        for c in contract_types:
            facet = CONTRACT_TYPE_MAPPING.get(c.strip().lower())
            if facet and facet not in contract_facets:
                contract_facets.append(facet)

        return {
            "queries": queries,
            "contract_facets": contract_facets,
            "target_titles": target_titles if target_titles else queries[:5],
            "contract_types": contract_types
        }

    def parse_duration_to_timestamp(self, duration: str) -> int:
        """Convertit une durée ('24h', '3j', '7j') en timestamp Unix minimum."""
        clean_dur = duration.strip().lower()
        seconds = DURATION_SECONDS.get(clean_dur)
        if not seconds:
            import re
            m = re.match(r"^(\d+)\s*([hjd])$", clean_dur)
            if m:
                val = int(m.group(1))
                unit = m.group(2)
                seconds = val * 3600 if unit == "h" else val * 24 * 3600
            else:
                seconds = 24 * 3600

        return int(time.time() - seconds)

    def search_wttj_recent_jobs(
        self,
        min_timestamp: int,
        query: str = "Backend",
        contract_facets: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Interroge l'index Algolia WTTJ pour récupérer les offres publiées depuis min_timestamp."""
        url = f"https://{WTTJ_ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/*/queries"
        params = {
            "x-algolia-api-key": WTTJ_ALGOLIA_API_KEY,
            "x-algolia-application-id": WTTJ_ALGOLIA_APP_ID
        }
        headers = {
            "Referer": "https://www.welcometothejungle.com/",
            "Origin": "https://www.welcometothejungle.com",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

        facet_param = ""
        if contract_facets:
            import json
            facet_param = f"&facetFilters={json.dumps([contract_facets])}"

        algolia_params = f"query={query}&hitsPerPage={limit}&numericFilters=published_at_timestamp>={min_timestamp}{facet_param}"
        body = {
            "requests": [
                {
                    "indexName": WTTJ_ALGOLIA_INDEX,
                    "params": algolia_params
                }
            ]
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, params=params, headers=headers, json=body)
                if resp.status_code != 200:
                    logger.error(f"Erreur recherche Algolia WTTJ : {resp.status_code} - {resp.text}")
                    return []
                
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    return []
                
                hits = results[0].get("hits", [])
                logger.info(f"Algolia WTTJ: {len(hits)} offres trouvées pour query='{query}' (ts >= {min_timestamp}, facets={contract_facets})")
                
                formatted_jobs = []
                for h in hits:
                    org = h.get("organization") or {}
                    org_slug = org.get("slug") or ""
                    job_slug = h.get("slug") or ""
                    
                    if not org_slug or not job_slug:
                        continue
                    
                    job_url = f"https://www.welcometothejungle.com/fr/companies/{org_slug}/jobs/{job_slug}"
                    formatted_jobs.append({
                        "source": "WTTJ",
                        "source_job_id": str(h.get("reference") or job_slug),
                        "title": h.get("name"),
                        "company": org.get("name"),
                        "url": job_url,
                        "published_at": h.get("published_at"),
                        "published_at_timestamp": h.get("published_at_timestamp"),
                        "location": (h.get("offices") or [{}])[0].get("city") if h.get("offices") else None,
                        "contract_type": h.get("contract_type"),
                        "remote": h.get("remote")
                    })
                return formatted_jobs

        except Exception as e:
            logger.error(f"Erreur lors de l'appel Algolia WTTJ: {e}")
            return []

    def run_collection(
        self,
        duration: str = "24h",
        query: Optional[str] = None,
        limit: int = 5,
        min_match_score: int = 75,
        auto_prepare: bool = True
    ) -> Dict[str, Any]:
        """
        Exécute la collecte automatique de bout en bout en s'appuyant sur le profil maître :
        1. Extraction automatique des critères (postes cibles, contrat ex: CDI) depuis le profil candidat.
        2. Recherche des offres sur la période (24h, 3j, 7j).
        3. Déduplication en base.
        4. Scraping complet des nouvelles offres.
        5. Matching IA contre le profil maître.
        6. Préparation de candidature & sync Notion si score >= seuil.
        """
        min_timestamp = self.parse_duration_to_timestamp(duration)

        # 1. Récupérer le profil candidat actif et ses critères automatiques
        profile_record = supabase_service.get_active_candidate_profile()
        candidate_profile = None
        if profile_record:
            candidate_profile = CandidateProfile.model_validate(profile_record["profile"])
            candidate_profile.preferences = candidate_profile.preferences.model_validate(profile_record.get("preferences", {}))

        criteria = self.derive_candidate_search_criteria(candidate_profile)
        contract_facets = criteria["contract_facets"]

        # Si une query manuelle est fournie, l'utiliser en priorité, sinon parcourir les queries dérivées du profil
        queries_to_run = [query] if query else criteria["queries"]
        logger.info(f"Critères auto dérivés : queries={queries_to_run}, contrats={criteria['contract_types']} ({contract_facets})")

        # 2. Rechercher les offres (déduplication par URL entre plusieurs requêtes)
        found_jobs = []
        seen_urls = set()

        for q in queries_to_run:
            if len(found_jobs) >= limit:
                break
            remaining = limit - len(found_jobs)
            hits = self.search_wttj_recent_jobs(
                min_timestamp=min_timestamp,
                query=q,
                contract_facets=contract_facets,
                limit=remaining * 2
            )
            for h in hits:
                if h["url"] not in seen_urls:
                    seen_urls.add(h["url"])
                    found_jobs.append(h)
                    if len(found_jobs) >= limit:
                        break

        summary = {
            "duration": duration,
            "query": ", ".join(queries_to_run),
            "candidate_name": candidate_profile.name if candidate_profile else None,
            "contract_filter": criteria["contract_types"],
            "total_found": len(found_jobs),
            "processed_count": 0,
            "new_imported_count": 0,
            "qualified_count": 0,
            "prepared_count": 0,
            "notion_synced_count": 0,
            "jobs": []
        }


        # Valeurs par défaut issues des préférences si non spécifiées
        if candidate_profile and candidate_profile.preferences:
            prefs = candidate_profile.preferences
            if min_match_score == 75 and getattr(prefs, "match_threshold_recommended", None):
                min_match_score = prefs.match_threshold_recommended
            if auto_prepare is True and getattr(prefs, "auto_prepare_documents", None) is False:
                auto_prepare = False

        for item in found_jobs:
            job_url = item["url"]
            job_title = item["title"]
            company = item["company"]
            summary["processed_count"] += 1

            job_detail_summary = {
                "title": job_title,
                "company": company,
                "url": job_url,
                "published_at": item.get("published_at"),
                "status": "SKIPPED",
                "match_score": None,
                "notion_page_id": None
            }

            # Étape A0: Filtrage préalable Blacklist & Mots-clés (économie de tokens et scraping)
            if candidate_profile and candidate_profile.preferences:
                prefs = candidate_profile.preferences
                if is_company_blacklisted(company, prefs.excluded_companies):
                    logger.info(f"Offre ignorée (Blacklist entreprise) : {company} - {job_title}")
                    job_detail_summary["status"] = "BLACKLISTED"
                    summary["jobs"].append(job_detail_summary)
                    continue

                matched_kw = matches_excluded_keyword(job_title, prefs.excluded_keywords)
                if matched_kw:
                    logger.info(f"Offre ignorée (Mot-clé exclu '{matched_kw}') : {company} - {job_title}")
                    job_detail_summary["status"] = "FILTERED_KEYWORD"
                    summary["jobs"].append(job_detail_summary)
                    continue

                if getattr(prefs, "filter_esn", False) and is_esn_company(company, job_title):
                    logger.info(f"Offre ignorée (Filtre ESN) : {company} - {job_title}")
                    job_detail_summary["status"] = "FILTERED_ESN"
                    summary["jobs"].append(job_detail_summary)
                    continue

            # Étape A0 bis: Déduplication en amont avant scraping (économie de requêtes et de scraping)
            from app.services.ingestion.deduplicator import deduplicator
            if deduplicator.is_duplicate(item.get("source", "WTTJ"), item.get("source_job_id"), job_url):
                logger.info(f"Offre déjà présente en base (ignorée avant scrape) : {company} - {job_title}")
                job_detail_summary["status"] = "DUPLICATE_OR_EXISTING"
                summary["jobs"].append(job_detail_summary)
                continue

            try:
                # Étape A: Scrape complet de l'offre
                scraped = job_scraper.scrape(job_url)
                
                # Étape B: Import & Déduplication
                import_res = job_importer.import_job(scraped)
                job_record = import_res.get("job")
                
                if not job_record or not job_record.get("id"):
                    job_detail_summary["status"] = "DUPLICATE_OR_EXISTING"
                    summary["jobs"].append(job_detail_summary)
                    continue

                summary["new_imported_count"] += 1
                job_id = job_record["id"]

                if candidate_profile:
                    job_normalized = JobNormalizedData.model_validate(job_record.get("normalized_data", {}))
                    if not (job_record.get("normalized_data") or {}).get("language"):
                        job_normalized.language = job_parser.detect_language(
                            f"{job_record.get('title') or ''}\n{job_record.get('description') or ''}",
                            job_record.get("raw_data") if isinstance(job_record.get("raw_data"), dict) else job_record
                        )
                    match_res = matcher_service.match(candidate_profile, job_normalized)
                    
                    if match_res:
                        score = match_res.score
                        level = match_res.level
                        job_detail_summary["match_score"] = score
                        
                        # Mettre à jour l'offre en base
                        qualified = score >= min_match_score
                        new_status = "QUALIFIED" if qualified else ("REVIEW" if score >= 60 else "REJECTED")
                        
                        if supabase_service.client:
                            supabase_service.client.table("jobs").update({
                                "match_score": score,
                                "match_level": level,
                                "match_analysis": match_res.model_dump(),
                                "status": new_status
                            }).eq("id", job_id).execute()

                        if qualified:
                            summary["qualified_count"] += 1
                            job_detail_summary["status"] = "QUALIFIED"

                            # Étape D: Préparation automatique et synchronisation Notion si demandée
                            if auto_prepare and profile_record:
                                try:
                                    # Créer l'application
                                    existing_app = supabase_service.client.table("applications").select("*").eq("job_id", job_id).execute()
                                    if existing_app.data:
                                        app_id = existing_app.data[0]["id"]
                                    else:
                                        res_app = supabase_service.client.table("applications").insert({
                                            "job_id": job_id,
                                            "candidate_profile_id": profile_record["id"],
                                            "status": "QUALIFIED",
                                            "match_score": score
                                        }).execute()
                                        app_id = res_app.data[0]["id"]

                                    # Générer CV, Lettre, Réponses
                                    tailored_cv = cv_generator_service.generate(
                                        job_id=job_id,
                                        profile=candidate_profile,
                                        job_data=job_normalized,
                                        application_id=app_id
                                    )
                                    cover_letter = letter_generator_service.generate(
                                        profile=candidate_profile,
                                        job_data=job_normalized,
                                        application_id=app_id
                                    )
                                    # Économie de quota : les réponses aux questions d'entretien sont générées à la demande dans l'interface
                                    answers = None

                                    # Render & Save PDFs
                                    cv_url = None
                                    letter_url = None
                                    if tailored_cv:
                                        cv_url = document_renderer.render_and_save_cv(
                                            app_id,
                                            profile_record["profile"],
                                            tailored_cv.model_dump(),
                                            company=company,
                                            job_title=job_title
                                        )
                                    if cover_letter:
                                        letter_url = document_renderer.render_and_save_letter(
                                            app_id,
                                            profile_record["profile"],
                                            cover_letter.model_dump(),
                                            company=company,
                                            job_title=job_title
                                        )

                                    # Update Application status to PREPARED
                                    supabase_service.client.table("applications").update({
                                        "status": "PREPARED",
                                        "tailored_cv": tailored_cv.model_dump() if tailored_cv else None,
                                        "cover_letter": cover_letter.content if cover_letter else None,
                                        "application_answers": answers.model_dump() if answers else None
                                    }).eq("id", app_id).execute()
                                    
                                    summary["prepared_count"] += 1
                                    job_detail_summary["status"] = "PREPARED"

                                    # Détermination du Type et du Domaine d'activité de l'entreprise
                                    from app.services.ingestion.company_classifier import classify_company
                                    cl_type, cl_domain = classify_company(
                                        company=company,
                                        title=job_title,
                                        description=item.get("description", ""),
                                        raw_data=item.get("raw_data")
                                    )
                                    final_type = (match_res.company_type if match_res and match_res.company_type else None) or (job_normalized.company_type if job_normalized else None) or cl_type
                                    final_domain = (match_res.company_domain if match_res and match_res.company_domain else None) or (job_normalized.domain if job_normalized else None) or cl_domain

                                    # Synchronisation Notion
                                    page_id = notion_service.sync_application(
                                        application_id=app_id,
                                        company=company,
                                        job_title=job_title,
                                        job_url=job_url,
                                        score=score,
                                        status="PREPARED",
                                        location=item.get("location"),
                                        contract_type=item.get("contract_type"),
                                        domain=final_domain,
                                        company_type=final_type,
                                        cv_url=cv_url,
                                        letter_url=letter_url,
                                        cover_letter=cover_letter.content if cover_letter else None,
                                        answers=answers.model_dump() if answers else None,
                                        match_analysis=match_res.model_dump()
                                    )
                                    if page_id:
                                        supabase_service.client.table("applications").update({"notion_page_id": page_id}).eq("id", app_id).execute()
                                        summary["notion_synced_count"] += 1
                                        job_detail_summary["notion_page_id"] = page_id
                                        job_detail_summary["notion_url"] = f"https://app.notion.com/p/{page_id.replace('-', '')}"

                                except Exception as prep_err:
                                    logger.error(f"Erreur préparation automatique pour {job_id}: {prep_err}")
                        else:
                            job_detail_summary["status"] = new_status

                summary["jobs"].append(job_detail_summary)

            except Exception as job_err:
                logger.error(f"Erreur traitement offre {job_url}: {job_err}")
                job_detail_summary["error"] = str(job_err)
                summary["jobs"].append(job_detail_summary)

        return summary

    @staticmethod
    def _enrich_incomplete_job(existing: Dict[str, Any], scraped: Dict[str, Any]) -> Dict[str, Any]:
        """Remplace le contenu d'une offre enregistrée incomplète (import précédent raté) par un scraping complet."""
        placeholder_titles = {"", "offre d'emploi", "offre sans titre", "poste"}
        incomplete = (not existing.get("company")
                      or (existing.get("title") or "").strip().lower() in placeholder_titles)
        complete = bool(scraped.get("title") and scraped.get("company"))
        if not (incomplete and complete):
            return existing
        fields = ("source", "source_job_id", "title", "company", "location", "contract_type",
                  "salary_min", "salary_max", "description", "raw_data", "normalized_data")
        update = {k: scraped.get(k) for k in fields if scraped.get(k) is not None}
        if "normalized_data" not in update:
            update["normalized_data"] = job_parser.normalize(scraped).model_dump()
        try:
            res = supabase_service.client.table("jobs").update(update).eq("id", existing["id"]).execute()
            logger.info(f"Offre {existing['id']} enrichie : {update.get('title')} ({update.get('company')})")
            return res.data[0] if res.data else {**existing, **update}
        except Exception as ue:
            logger.warning(f"Enrichissement de l'offre {existing.get('id')} impossible : {ue}")
            return existing

    def import_and_process_url(
        self,
        url: str,
        auto_prepare: bool = True,
        min_match_score: int = 75
    ) -> Dict[str, Any]:
        """
        Importe une offre externe depuis son URL (LinkedIn, WTTJ, Indeed, Apec, etc.),
        calcule le score d'adéquation IA et génère le dossier de candidature (CV, LM, Notion)
        si le score atteint le seuil de qualification.
        """
        from app.services.ingestion.deduplicator import deduplicator

        logger.info(f"Début de l'import externe pour l'URL : {url}")
        # 1. Scraping
        try:
            scraped_data = job_scraper.scrape(url)
        except Exception as se:
            logger.error(f"Erreur lors du scraping de {url}: {se}")
            return {
                "success": False,
                "error": f"Impossible d'extraire l'offre : {str(se)}"
            }

        # 2. Persistance & Déduplication
        import_result = job_importer.import_job(scraped_data)
        job = import_result.get("job") or scraped_data
        normalized_url = deduplicator.normalize_url(url)

        # Si doublon, récupérer l'enregistrement existant (et l'enrichir s'il est incomplet)
        if import_result.get("status") == "DUPLICATE" and supabase_service.client:
            try:
                res_exist = supabase_service.client.table("jobs").select("*").eq("url", normalized_url).execute()
                if res_exist.data:
                    job = self._enrich_incomplete_job(res_exist.data[0], scraped_data)
            except Exception as de:
                logger.warning(f"Impossible de récupérer l'offre existante: {de}")

        job_id = job.get("id") or "simulated_job"
        company = job.get("company") or "Entreprise"
        title = job.get("title") or "Poste"

        # 3. Profil candidat actif
        profile_record = supabase_service.get_active_candidate_profile()
        if not profile_record:
            return {
                "success": True,
                "job": job,
                "status": import_result.get("status"),
                "message": "Offre enregistrée, mais aucun profil candidat configuré pour le matching."
            }

        candidate_profile = CandidateProfile.model_validate(profile_record["profile"])
        candidate_profile.preferences = candidate_profile.preferences.model_validate(profile_record.get("preferences", {}))
        job_normalized = JobNormalizedData.model_validate(job.get("normalized_data") or job)
        if not (job.get("normalized_data") or {}).get("language"):
            job_normalized.language = job_parser.detect_language(
                f"{job.get('title') or ''}\n{job.get('description') or ''}",
                job.get("raw_data") if isinstance(job.get("raw_data"), dict) else job
            )

        prefs = candidate_profile.preferences
        if prefs:
            # Surcharges par défaut issues des préférences
            if min_match_score == 75 and getattr(prefs, "match_threshold_recommended", None):
                min_match_score = prefs.match_threshold_recommended
            if auto_prepare is True and getattr(prefs, "auto_prepare_documents", None) is False:
                auto_prepare = False

            # Filtrage Blacklist entreprise
            if is_company_blacklisted(company, prefs.excluded_companies):
                logger.info(f"Import URL ignoré (Blacklist entreprise) : {company} - {title}")
                if supabase_service.client and job.get("id"):
                    try:
                        supabase_service.client.table("jobs").update({"status": "BLACKLISTED"}).eq("id", job["id"]).execute()
                    except Exception:
                        pass
                return {
                    "success": True,
                    "status": "BLACKLISTED",
                    "job": job,
                    "score": 0,
                    "message": f"Offre enregistrée mais écartée : l'entreprise '{company}' figure dans votre liste noire."
                }

            # Filtrage Mots-clés indésirables
            matched_kw = matches_excluded_keyword(title, prefs.excluded_keywords)
            if matched_kw:
                logger.info(f"Import URL ignoré (Mot-clé exclu '{matched_kw}') : {company} - {title}")
                if supabase_service.client and job.get("id"):
                    try:
                        supabase_service.client.table("jobs").update({"status": "FILTERED_KEYWORD"}).eq("id", job["id"]).execute()
                    except Exception:
                        pass
                return {
                    "success": True,
                    "status": "FILTERED_KEYWORD",
                    "job": job,
                    "score": 0,
                    "message": f"Offre enregistrée mais écartée : le titre contient le mot-clé exclu '{matched_kw}'."
                }

            # Filtrage ESN / Sociétés de conseil si activé
            if getattr(prefs, "filter_esn", False) and is_esn_company(company, title, job.get("description", "")):
                logger.info(f"Import URL ignoré (Filtre ESN) : {company} - {title}")
                if supabase_service.client and job.get("id"):
                    try:
                        supabase_service.client.table("jobs").update({"status": "FILTERED_ESN"}).eq("id", job["id"]).execute()
                    except Exception:
                        pass
                return {
                    "success": True,
                    "status": "FILTERED_ESN",
                    "job": job,
                    "score": 0,
                    "message": f"Offre enregistrée mais écartée : l'entreprise '{company}' a été identifiée comme ESN ou cabinet de conseil."
                }

        # 4. Matching IA
        match_res = None
        if import_result.get("status") == "DUPLICATE" and job.get("match_score") is not None:
            score = job.get("match_score")
            level = job.get("match_level") or "REVIEW"
            if job.get("match_analysis"):
                try:
                    from app.schemas.match import MatchResult
                    match_res = MatchResult.model_validate(job.get("match_analysis"))
                except Exception:
                    pass
            qualified = score >= min_match_score
            logger.info(f"Offre déjà évaluée précédemment (score={score}), matching Gemini ignoré.")
        else:
            match_res = matcher_service.match(candidate_profile, job_normalized)
            score = match_res.score if match_res else 0
            level = match_res.level if match_res else "REJECTED"
            qualified = score >= min_match_score

        if supabase_service.client and job.get("id"):
            try:
                supabase_service.client.table("jobs").update({
                    "match_score": score,
                    "match_level": level,
                    "match_analysis": match_res.model_dump() if match_res else None,
                    "status": "QUALIFIED" if qualified else "REVIEW"
                }).eq("id", job["id"]).execute()
            except Exception as ue:
                logger.warning(f"Erreur mise à jour score job: {ue}")

        response: Dict[str, Any] = {
            "success": True,
            "status": "QUALIFIED" if qualified else "REVIEW",
            "job": job,
            "score": score,
            "match": match_res.model_dump() if match_res else None,
            "prepared": False,
            "cv_url": None,
            "letter_url": None,
            "notion_page_id": None,
            "notion_url": None
        }

        # 5. Préparation automatique et synchronisation Notion si qualifiée
        if auto_prepare and qualified:
            try:
                # Créer ou récupérer l'application
                app_id = f"simulated_app_{job_id}"
                existing_app_data = None
                if supabase_service.client and job.get("id"):
                    existing_app = supabase_service.client.table("applications").select("*").eq("job_id", job["id"]).execute()
                    if existing_app.data:
                        existing_app_data = existing_app.data[0]
                        app_id = existing_app_data["id"]
                    else:
                        res_app = supabase_service.client.table("applications").insert({
                            "job_id": job["id"],
                            "candidate_profile_id": profile_record["id"],
                            "status": "QUALIFIED",
                            "match_score": score
                        }).execute()
                        app_id = res_app.data[0]["id"]

                # Récupération ou génération des livrables IA
                tailored_cv = None
                cover_letter = None
                if existing_app_data and existing_app_data.get("tailored_cv") and existing_app_data.get("cover_letter"):
                    try:
                        from app.schemas.application import TailoredCV, CoverLetter
                        tailored_cv = TailoredCV.model_validate(existing_app_data["tailored_cv"])
                        cover_letter = CoverLetter(content=existing_app_data["cover_letter"])
                        logger.info(f"Candidature {app_id} déjà préparée précédemment, réutilisation sans rappel Gemini.")
                    except Exception:
                        pass

                if not tailored_cv:
                    tailored_cv = cv_generator_service.generate(
                        job_id=job_id,
                        profile=candidate_profile,
                        job_data=job_normalized,
                        application_id=app_id
                    )
                if not cover_letter:
                    cover_letter = letter_generator_service.generate(
                        profile=candidate_profile,
                        job_data=job_normalized,
                        application_id=app_id
                    )
                # Économie de quota : les réponses aux questions d'entretien sont générées à la demande
                answers = None

                # Rendu et stockage PDF avec nommage standardisé
                cv_url = None
                letter_url = None
                if tailored_cv:
                    cv_url = document_renderer.render_and_save_cv(
                        app_id,
                        profile_record["profile"],
                        tailored_cv.model_dump(),
                        company=company,
                        job_title=title
                    )
                if cover_letter:
                    letter_url = document_renderer.render_and_save_letter(
                        app_id,
                        profile_record["profile"],
                        cover_letter.model_dump(),
                        company=company,
                        job_title=title
                    )

                # Mise à jour application
                if supabase_service.client and not app_id.startswith("simulated_"):
                    supabase_service.client.table("applications").update({
                        "status": "PREPARED",
                        "tailored_cv": tailored_cv.model_dump() if tailored_cv else None,
                        "cover_letter": cover_letter.content if cover_letter else None,
                        "application_answers": answers.model_dump() if answers else None
                    }).eq("id", app_id).execute()

                # Détermination du Type et du Domaine d'activité de l'entreprise
                from app.services.ingestion.company_classifier import classify_company
                cl_type, cl_domain = classify_company(
                    company=company,
                    title=title,
                    description=job.get("description", ""),
                    raw_data=job.get("raw_data")
                )
                final_type = (match_res.company_type if match_res and match_res.company_type else None) or (job_normalized.company_type if job_normalized else None) or cl_type
                final_domain = (match_res.company_domain if match_res and match_res.company_domain else None) or (job_normalized.domain if job_normalized else None) or cl_domain

                # Synchronisation Notion avec N suivi incrémental (si activée dans les préférences)
                should_sync_notion = getattr(prefs, "auto_sync_notion", True) if prefs else True
                if should_sync_notion:
                    page_id = notion_service.sync_application(
                        application_id=app_id,
                        company=company,
                        job_title=title,
                        job_url=job.get("url") or url,
                        score=score,
                        status="PREPARED",
                        location=job.get("location"),
                        contract_type=job.get("contract_type"),
                        domain=final_domain,
                        company_type=final_type,
                        cv_url=cv_url,
                        letter_url=letter_url,
                        cover_letter=cover_letter.content if cover_letter else None,
                        answers=answers.model_dump() if answers else None,
                        match_analysis=match_res.model_dump() if match_res else None
                    )

                    if page_id:
                        if supabase_service.client and not app_id.startswith("simulated_"):
                            supabase_service.client.table("applications").update({"notion_page_id": page_id}).eq("id", app_id).execute()
                        response["notion_page_id"] = page_id
                        response["notion_url"] = f"https://app.notion.com/p/{page_id.replace('-', '')}"

                response["prepared"] = True
                response["cv_url"] = cv_url
                response["letter_url"] = letter_url
                response["status"] = "PREPARED"

            except Exception as pe:
                logger.error(f"Erreur préparation automatique pour {url}: {pe}")
                response["preparation_error"] = str(pe)

        return response

    def import_and_process_urls(
        self,
        urls: List[str],
        auto_prepare: bool = True,
        min_match_score: int = 75
    ) -> Dict[str, Any]:
        """
        Importe et traite un lot d'URLs d'offres externes en séquence résiliente.
        Chaque offre est scrapée, matchée avec le profil maître, et préparée si qualifiée.
        Les erreurs individuelles sont isolées sans bloquer le reste du lot.
        """
        from app.services.ingestion.scraper import clean_url

        # Nettoyage et déduplication de la liste reçue
        cleaned_urls: List[str] = []
        for u in urls:
            if not u:
                continue
            normalized_u = clean_url(u.strip())
            if normalized_u and normalized_u not in cleaned_urls:
                cleaned_urls.append(normalized_u)

        summary: Dict[str, Any] = {
            "success": True,
            "is_batch": True,
            "total_requested": len(urls),
            "total_unique": len(cleaned_urls),
            "processed_count": 0,
            "qualified_count": 0,
            "prepared_count": 0,
            "notion_synced_count": 0,
            "error_count": 0,
            "results": []
        }

        if not cleaned_urls:
            summary["success"] = False
            summary["error"] = "Aucune URL valide fournie dans le lot."
            return summary

        for idx, u in enumerate(cleaned_urls, start=1):
            logger.info(f"Traitement lot URL ({idx}/{len(cleaned_urls)}) : {u}")
            try:
                item_res = self.import_and_process_url(
                    url=u,
                    auto_prepare=auto_prepare,
                    min_match_score=min_match_score
                )
                summary["processed_count"] += 1
                if item_res.get("score") and item_res.get("score") >= min_match_score:
                    summary["qualified_count"] += 1
                if item_res.get("prepared"):
                    summary["prepared_count"] += 1
                if item_res.get("notion_page_id"):
                    summary["notion_synced_count"] += 1
                if not item_res.get("success"):
                    summary["error_count"] += 1

                item_summary = {
                    "url": u,
                    "success": item_res.get("success", False),
                    "status": item_res.get("status", "ERROR"),
                    "job": item_res.get("job", {}),
                    "score": item_res.get("score"),
                    "match": item_res.get("match"),
                    "prepared": item_res.get("prepared", False),
                    "cv_url": item_res.get("cv_url"),
                    "letter_url": item_res.get("letter_url"),
                    "notion_url": item_res.get("notion_url"),
                    "notion_page_id": item_res.get("notion_page_id"),
                    "error": item_res.get("error") or item_res.get("preparation_error")
                }
                summary["results"].append(item_summary)

            except Exception as e:
                logger.error(f"Erreur inattendue sur l'URL {u}: {e}")
                summary["processed_count"] += 1
                summary["error_count"] += 1
                summary["results"].append({
                    "url": u,
                    "success": False,
                    "status": "ERROR",
                    "job": {"url": u, "title": "Inconnue", "company": "Inconnue"},
                    "score": None,
                    "error": str(e)
                })

        return summary

job_collector_service = JobCollectorService()
