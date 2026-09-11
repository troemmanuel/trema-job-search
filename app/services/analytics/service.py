import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict

from app.services.storage.supabase_service import supabase_service
from app.services.ingestion.company_classifier import classify_company

logger = logging.getLogger(__name__)

TECH_CATEGORIES = {
    "Go / Golang": ["go", "golang"],
    "Java / Spring Boot": ["java", "spring", "spring boot", "springboot"],
    "Python / FastAPI": ["python", "fastapi", "django", "flask"],
    "TypeScript / Node / React": ["typescript", "node", "nodejs", "node.js", "react", "next.js"],
    "Docker / Kubernetes / CI-CD": ["docker", "kubernetes", "k8s", "ci/cd", "cicd", "ansible", "terraform", "devops"],
    "Cloud (AWS / GCP / Azure)": ["cloud", "aws", "gcp", "azure"],
    "SQL / PostgreSQL / Data": ["sql", "postgresql", "postgres", "mysql", "mongodb", "database", "elk"]
}

class AnalyticsService:
    """Service d'agrégation et de calcul des métriques et taux de conversion."""

    def get_analytics(self, period: str = "all") -> Dict[str, Any]:
        """
        Récupère et calcule l'ensemble des métriques d'entonnoir, de performance et de répartition.
        period: 'all', '30d', ou '7d'
        """
        jobs, applications = self._fetch_raw_data()
        
        # Filtrage par période si demandée
        if period in ["30d", "7d"]:
            days = 30 if period == "30d" else 7
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            jobs = [j for j in jobs if self._is_after(j.get("created_at"), cutoff)]
            applications = [a for a in applications if self._is_after(a.get("created_at"), cutoff)]

        funnel = self._compute_funnel(jobs, applications)
        tech_performance = self._compute_tech_performance(jobs, applications)
        geography, workplace = self._compute_geography_and_workplace(jobs)
        company_types = self._compute_company_types(jobs)
        timeline = self._compute_timeline(jobs, applications)
        kpis = self._compute_kpis(jobs, applications, funnel)

        return {
            "period": period,
            "kpis": kpis,
            "funnel": funnel,
            "tech_performance": tech_performance,
            "geography": geography,
            "workplace": workplace,
            "company_types": company_types,
            "timeline": timeline,
            "total_jobs": len(jobs),
            "total_applications": len(applications)
        }

    def _fetch_raw_data(self) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Récupère les offres et candidatures depuis Supabase avec gestion résiliente."""
        if not supabase_service.client:
            return [], []

        jobs = []
        applications = []

        try:
            res_jobs = supabase_service.client.table("jobs").select("*").order("created_at", desc=False).execute()
            jobs = res_jobs.data or []
        except Exception as e:
            logger.warning(f"Erreur récupération jobs pour analytique: {e}")

        try:
            res_apps = supabase_service.client.table("applications").select("*, jobs(*)").order("created_at", desc=False).execute()
            applications = res_apps.data or []
        except Exception as e:
            logger.warning(f"Erreur récupération candidatures pour analytique: {e}")

        return jobs, applications

    def _is_after(self, dt_str: Optional[str], cutoff: datetime) -> bool:
        if not dt_str:
            return False
        try:
            from app.services.notion.sync import parse_iso_datetime
            dt = parse_iso_datetime(dt_str)
            return dt is not None and dt >= cutoff
        except Exception:
            return False

    def _compute_funnel(self, jobs: List[Dict[str, Any]], applications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calcule les volumes et taux de conversion du funnel :
        Détectées -> Qualifiées (>=75) -> Préparées -> Envoyées -> Entretiens -> Offres
        """
        detected = len(jobs)
        qualified = 0
        for j in jobs:
            score = j.get("match_score") or 0
            status = (j.get("status") or "").upper()
            if status != "IGNORED" and (score >= 75 or status in ["QUALIFIED", "PREPARING", "PREPARED", "READY", "APPLIED", "INTERVIEW", "INTERVIEW_HR", "INTERVIEW_TECH", "OFFER"]):
                qualified += 1

        # Statuts applications
        prepared = 0
        applied = 0
        interview = 0
        offer = 0
        rejected = 0

        for a in applications:
            st = (a.get("status") or "").upper()
            prepared += 1  # Toute candidature enregistrée a été au moins préparée
            if st in ["APPLIED", "INTERVIEW", "INTERVIEW_HR", "INTERVIEW_TECH", "OFFER", "REJECTED"]:
                applied += 1
            if st in ["INTERVIEW", "INTERVIEW_HR", "INTERVIEW_TECH", "OFFER"]:
                interview += 1
            if st == "OFFER":
                offer += 1
            if st == "REJECTED":
                rejected += 1

        def pct(numerator: int, denominator: int) -> float:
            if denominator <= 0:
                return 0.0
            val = round((numerator / denominator) * 100.0, 1)
            return min(100.0, val)

        return {
            "counts": {
                "detected": detected,
                "qualified": qualified,
                "prepared": prepared,
                "applied": applied,
                "interview": interview,
                "offer": offer,
                "rejected": rejected
            },
            "rates": {
                "qualification_rate": pct(qualified, detected),
                "preparation_rate": pct(prepared, qualified),
                "application_rate": pct(applied, prepared),
                "interview_rate": pct(interview, applied),
                "offer_rate": pct(offer, interview),
                "global_conversion_rate": pct(interview, detected)
            }
        }

    def _compute_tech_performance(self, jobs: List[Dict[str, Any]], applications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Calcule le volume, le score moyen et le taux d'engagement par technologie."""
        tech_data = {
            name: {
                "name": name,
                "keywords": kws,
                "job_count": 0,
                "total_score": 0,
                "applied_count": 0,
                "interview_count": 0
            }
            for name, kws in TECH_CATEGORIES.items()
        }

        # Indexer les applications par job_id
        apps_by_job_id = defaultdict(list)
        for a in applications:
            jid = a.get("job_id")
            if jid:
                apps_by_job_id[jid].append(a)

        for job in jobs:
            score = job.get("match_score") or 0
            # Récupérer texte concaténé pour recherche de stack
            norm = job.get("normalized_data") or {}
            skills = [s.lower() for s in norm.get("skills", [])]
            title = (job.get("title") or "").lower()
            desc = (job.get("description") or "")[:2000].lower()
            combined_tech = set(skills + title.split() + desc.split())

            for name, meta in tech_data.items():
                kws = meta["keywords"]
                matched = any(kw in skills or kw in title or f" {kw} " in f" {desc} " for kw in kws)
                if matched:
                    meta["job_count"] += 1
                    meta["total_score"] += score
                    # Vérifier candidatures liées
                    jid = job.get("id")
                    if jid and jid in apps_by_job_id:
                        for app in apps_by_job_id[jid]:
                            st = (app.get("status") or "").upper()
                            if st in ["APPLIED", "INTERVIEW", "INTERVIEW_HR", "INTERVIEW_TECH", "OFFER", "REJECTED"]:
                                meta["applied_count"] += 1
                            if st in ["INTERVIEW", "INTERVIEW_HR", "INTERVIEW_TECH", "OFFER"]:
                                meta["interview_count"] += 1

        results = []
        for name, meta in tech_data.items():
            count = meta["job_count"]
            avg_score = round(meta["total_score"] / count, 1) if count > 0 else 0.0
            results.append({
                "tech": name,
                "job_count": count,
                "avg_score": avg_score,
                "applied_count": meta["applied_count"],
                "interview_count": meta["interview_count"]
            })

        # Trier par nombre d'offres décroissant
        results.sort(key=lambda x: x["job_count"], reverse=True)
        return results

    def _compute_geography_and_workplace(self, jobs: List[Dict[str, Any]]) -> tuple[Dict[str, int], Dict[str, int]]:
        """Calcule la répartition géographique et le mode de télétravail."""
        geo_counts = {
            "Paris & Île-de-France": 0,
            "Rennes & Bretagne": 0,
            "Nantes & Pays de la Loire": 0,
            "Lyon & Rhône-Alpes": 0,
            "Toulouse & Occitanie": 0,
            "Bordeaux & Nouvelle-Aquitaine": 0,
            "Autres régions / Non précisé": 0
        }

        workplace_counts = {
            "Full Remote (100%)": 0,
            "Hybride / Partiel": 0,
            "Présentiel": 0
        }

        for job in jobs:
            loc = (job.get("location") or "").lower()
            desc = (job.get("description") or "").lower()
            norm = job.get("normalized_data") or {}

            # Géographie
            if any(k in loc for k in ["paris", "ile-de-france", "île-de-france", "boulogne", "courbevoie", "la défense", "nanterre", "saint-denis"]):
                geo_counts["Paris & Île-de-France"] += 1
            elif any(k in loc for k in ["rennes", "bretagne", "cesson", "saint-malo", "brest"]):
                geo_counts["Rennes & Bretagne"] += 1
            elif any(k in loc for k in ["nantes", "loire-atlantique", "angers"]):
                geo_counts["Nantes & Pays de la Loire"] += 1
            elif any(k in loc for k in ["lyon", "rhône", "grenoble"]):
                geo_counts["Lyon & Rhône-Alpes"] += 1
            elif any(k in loc for k in ["toulouse", "haute-garonne", "labège", "montpellier"]):
                geo_counts["Toulouse & Occitanie"] += 1
            elif any(k in loc for k in ["bordeaux", "gironde", "mérignac"]):
                geo_counts["Bordeaux & Nouvelle-Aquitaine"] += 1
            else:
                geo_counts["Autres régions / Non précisé"] += 1

            # Télétravail
            is_remote_flag = norm.get("remote") is True or job.get("remote") is True
            if "full remote" in loc or "full remote" in desc or "100% télétravail" in desc or "télétravail complet" in desc:
                workplace_counts["Full Remote (100%)"] += 1
            elif is_remote_flag or any(k in desc for k in ["télétravail partiel", "hybride", "2 jours", "3 jours", "jours de télétravail"]):
                workplace_counts["Hybride / Partiel"] += 1
            else:
                workplace_counts["Présentiel"] += 1

        return geo_counts, workplace_counts

    def _compute_company_types(self, jobs: List[Dict[str, Any]]) -> Dict[str, int]:
        """Agrège les typologies d'entreprises selon le classifieur contextuel."""
        type_counts = {
            "Grand groupe": 0,
            "Scale-up / Éditeur SaaS": 0,
            "ESN / Conseil": 0,
            "Startup tech": 0,
            "PME / ETI": 0
        }

        for job in jobs:
            comp = job.get("company", "")
            title = job.get("title", "")
            desc = job.get("description", "")
            raw_data = job.get("raw_data")

            c_type, _ = classify_company(comp, title, desc, raw_data)
            c_type_lower = (c_type or "").lower()

            if "grand groupe" in c_type_lower:
                type_counts["Grand groupe"] += 1
            elif "esn" in c_type_lower or "conseil" in c_type_lower:
                type_counts["ESN / Conseil"] += 1
            elif "scale-up" in c_type_lower or "éditeur" in c_type_lower or "saas" in c_type_lower:
                type_counts["Scale-up / Éditeur SaaS"] += 1
            elif "startup" in c_type_lower:
                type_counts["Startup tech"] += 1
            else:
                type_counts["PME / ETI"] += 1

        return type_counts

    def _compute_timeline(self, jobs: List[Dict[str, Any]], applications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Génère une série temporelle sur les 30 derniers jours."""
        today = datetime.now(timezone.utc).date()
        date_map_jobs = defaultdict(int)
        date_map_apps = defaultdict(int)

        for j in jobs:
            created = j.get("created_at")
            if created and isinstance(created, str) and len(created) >= 10:
                d_str = created[:10]
                date_map_jobs[d_str] += 1

        for a in applications:
            # Compter par date d'envoi si dispo, sinon création
            app_date = a.get("applied_at") or a.get("created_at")
            if app_date and isinstance(app_date, str) and len(app_date) >= 10:
                d_str = app_date[:10]
                date_map_apps[d_str] += 1

        # Construire les 14 derniers points (tous les 2 jours ou 14 derniers jours)
        labels = []
        jobs_series = []
        apps_series = []

        for i in range(14, -1, -1):
            day = today - timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")
            display_label = day.strftime("%d/%m")
            labels.append(display_label)
            jobs_series.append(date_map_jobs.get(day_str, 0))
            apps_series.append(date_map_apps.get(day_str, 0))

        return {
            "labels": labels,
            "jobs_series": jobs_series,
            "applications_series": apps_series
        }

    def _compute_kpis(self, jobs: List[Dict[str, Any]], applications: List[Dict[str, Any]], funnel: Dict[str, Any]) -> Dict[str, Any]:
        """Calcule les indicateurs clés pour les cartes d'en-tête."""
        scores = [j.get("match_score") for j in jobs if j.get("match_score") is not None]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

        recommendations = {"APPLY": 0, "REVIEW": 0, "IGNORE": 0}
        for j in jobs:
            analysis = j.get("match_analysis") or {}
            rec = analysis.get("recommendation")
            if rec in recommendations:
                recommendations[rec] += 1
            else:
                score = j.get("match_score") or 0
                if score >= 75:
                    recommendations["APPLY"] += 1
                elif score >= 50:
                    recommendations["REVIEW"] += 1
                else:
                    recommendations["IGNORE"] += 1

        return {
            "total_jobs": len(jobs),
            "total_applications": len(applications),
            "avg_match_score": avg_score,
            "qualified_count": funnel["counts"]["qualified"],
            "applied_count": funnel["counts"]["applied"],
            "interview_count": funnel["counts"]["interview"],
            "offer_count": funnel["counts"]["offer"],
            "global_conversion_rate": funnel["rates"]["global_conversion_rate"],
            "recommendations": recommendations
        }

analytics_service = AnalyticsService()
