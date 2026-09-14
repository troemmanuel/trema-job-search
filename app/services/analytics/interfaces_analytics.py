from collections import defaultdict
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from app.config import Config
from app.services.storage.supabase_service import supabase_service

logger = logging.getLogger(__name__)

PROVIDER_METADATA = {
    "gemini": {
        "name": "Google Gemini",
        "description": "Fournisseur primaire multimodal & raisonnement complexe",
        "benchmark_latency_ms": 1950,
        "color": "#3b82f6",
        "icon": "✨"
    },
    "groq": {
        "name": "Groq Cloud (LPU)",
        "description": "Inférence ultra-rapide basse latence (LPU)",
        "benchmark_latency_ms": 580,
        "color": "#f59e0b",
        "icon": "⚡"
    },
    "mistral": {
        "name": "Mistral AI",
        "description": "Modèles souverains européens haute vélocité",
        "benchmark_latency_ms": 420,
        "color": "#ec4899",
        "icon": "🌪️"
    },
    "openrouter": {
        "name": "OpenRouter",
        "description": "Passerelle universelle multi-modèles de secours",
        "benchmark_latency_ms": 1990,
        "color": "#8b5cf6",
        "icon": "🌐"
    }
}

class InterfacesAnalyticsService:
    """Service d'agrégation et de calcul des métriques d'observabilité des interfaces et APIs."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()

    def get_interfaces_analytics(self) -> Dict[str, Any]:
        """Agrège l'ensemble des métriques d'interfaces : LLM Router, Cache SHA-256, Notion, Supabase et Scraper."""
        router_stats = self._fetch_router_stats()
        raw_db_data = self._fetch_db_telemetry()

        # Calcul des métriques par provider
        providers_bench = self._compute_providers_benchmark(router_stats, raw_db_data.get("ai_runs", []))

        # Calcul de la distribution par tâche
        task_dist = self._compute_task_distribution(router_stats, raw_db_data.get("ai_runs", []))

        # Calcul des métriques des connecteurs externes
        external_connectors = self._compute_external_connectors(raw_db_data)

        # Liste unifiée des exécutions récentes
        recent_runs = self._compute_recent_runs(router_stats, raw_db_data.get("ai_runs", []))

        # Calcul des KPIs globaux
        kpis = self._compute_kpis(router_stats, providers_bench, raw_db_data, external_connectors)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kpis": kpis,
            "providers": providers_bench,
            "task_distribution": task_dist,
            "external_connectors": external_connectors,
            "cache": router_stats.get("cache", {}),
            "recent_runs": recent_runs[:35]
        }

    def _fetch_router_stats(self) -> Dict[str, Any]:
        """Récupère les compteurs en mémoire du routeur LLM."""
        try:
            from app.llm import router
            return router.get_stats()
        except Exception as e:
            logger.warning(f"Impossible de récupérer router.get_stats(): {e}")
            return {
                "gemini": {},
                "groq": {},
                "mistral": {},
                "openrouter": {},
                "cache": {},
                "failover_count": 0,
                "recent_runs": []
            }

    def _fetch_db_telemetry(self) -> Dict[str, List[Dict[str, Any]]]:
        """Récupère avec tolérance de panne les enregistrements de télémétrie Supabase."""
        data: Dict[str, List[Dict[str, Any]]] = {
            "ai_runs": [],
            "applications": [],
            "documents": [],
            "jobs": []
        }
        if not supabase_service.client:
            return data

        # 1. ai_runs (derniers 50)
        try:
            res_runs = supabase_service.client.table("ai_runs").select("*").order("created_at", desc=True).limit(50).execute()
            data["ai_runs"] = res_runs.data or []
        except Exception as e:
            logger.warning(f"Erreur lecture Supabase ai_runs: {e}")

        # 2. applications
        try:
            res_apps = supabase_service.client.table("applications").select("id, status, notion_page_id, created_at").execute()
            data["applications"] = res_apps.data or []
        except Exception as e:
            logger.warning(f"Erreur lecture Supabase applications: {e}")

        # 3. documents
        try:
            res_docs = supabase_service.client.table("documents").select("id, type, storage_path, created_at").execute()
            data["documents"] = res_docs.data or []
        except Exception as e:
            logger.warning(f"Erreur lecture Supabase documents: {e}")

        # 4. jobs
        try:
            res_jobs = supabase_service.client.table("jobs").select("id, status, match_score, source, created_at").execute()
            data["jobs"] = res_jobs.data or []
        except Exception as e:
            logger.warning(f"Erreur lecture Supabase jobs: {e}")

        return data

    def _compute_providers_benchmark(self, router_stats: Dict[str, Any], ai_runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Calcule la synthèse comparative des 4 fournisseurs LLM."""
        providers = []

        # Compter les occurrences depuis ai_runs pour croiser avec les compteurs mémoire
        db_stats_by_provider = defaultdict(lambda: {"count": 0, "success": 0, "errors": 0, "tokens": 0, "latency_sum": 0.0})
        for run in ai_runs:
            in_data = run.get("input_data") or {}
            p_name = (in_data.get("provider") or "").lower()
            if not p_name:
                model_str = (run.get("model") or "").lower()
                if "gemini" in model_str:
                    p_name = "gemini"
                elif "groq" in model_str or "llama" in model_str or "gpt-oss" in model_str:
                    p_name = "groq"
                elif "mistral" in model_str:
                    p_name = "mistral"
                else:
                    p_name = "gemini"

            db_stats_by_provider[p_name]["count"] += 1
            if run.get("status") == "SUCCESS":
                db_stats_by_provider[p_name]["success"] += 1
            elif run.get("status") == "ERROR":
                db_stats_by_provider[p_name]["errors"] += 1

            # Latence / tokens si présents
            lat = in_data.get("latency")
            if isinstance(lat, (int, float)) and lat > 0:
                db_stats_by_provider[p_name]["latency_sum"] += float(lat)
            tok = in_data.get("tokens")
            if isinstance(tok, int):
                db_stats_by_provider[p_name]["tokens"] += tok

        for p_id, meta in PROVIDER_METADATA.items():
            st = router_stats.get(p_id) or {}
            mem_requests = st.get("requests_count", 0)
            mem_success = st.get("success_count", 0)
            mem_errors = st.get("errors_count", 0)
            mem_latency_sec = st.get("total_latency_seconds", 0.0)
            mem_tokens = st.get("total_tokens", 0)
            mem_last_used = st.get("last_used_at")
            mem_last_error = st.get("last_error")

            db_st = db_stats_by_provider.get(p_id, {"count": 0, "success": 0, "errors": 0, "tokens": 0, "latency_sum": 0.0})

            # Cumul cohérent : max(mémoire, base) pour conserver l'historique persistent tout en captant le temps réel
            total_requests = max(mem_requests, db_st["count"])
            total_success = max(mem_success, db_st["success"])
            total_errors = max(mem_errors, db_st["errors"])
            total_tokens = max(mem_tokens, db_st["tokens"])

            # Calcul latence moyenne en ms
            if mem_requests > 0 and mem_latency_sec > 0:
                avg_lat_ms = round((mem_latency_sec / mem_requests) * 1000)
            elif db_st["count"] > 0 and db_st["latency_sum"] > 0:
                avg_lat_ms = round((db_st["latency_sum"] / db_st["count"]) * 1000)
            else:
                avg_lat_ms = meta["benchmark_latency_ms"]

            # Taux de succès
            if total_requests > 0:
                success_rate = round((total_success / total_requests) * 100, 1)
            else:
                success_rate = 100.0

            # Détection de configuration de la clé API
            is_configured = False
            active_model = ""
            try:
                from app.llm import router
                p_instance = router.providers.get(p_id)
                if p_instance:
                    is_configured = p_instance.is_configured()
                    active_model = p_instance.default_model
            except Exception:
                if p_id == "gemini":
                    is_configured = bool(getattr(self.config, "GEMINI_API_KEY", ""))
                    active_model = getattr(self.config, "GEMINI_MODEL", "gemini-3.6-flash")
                elif p_id == "groq":
                    is_configured = bool(getattr(self.config, "GROQ_API_KEY", ""))
                    active_model = getattr(self.config, "GROQ_MODEL", "openai/gpt-oss-120b")
                elif p_id == "mistral":
                    is_configured = bool(getattr(self.config, "MISTRAL_API_KEY", ""))
                    active_model = getattr(self.config, "MISTRAL_MODEL", "ministral-8b-latest")
                elif p_id == "openrouter":
                    is_configured = bool(getattr(self.config, "OPENROUTER_API_KEY", ""))
                    active_model = getattr(self.config, "OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct")

            # Statut opérationnel
            if not is_configured:
                status_label = "NON CONFIGURÉ"
                status_class = "muted"
            elif total_errors > 0 and total_requests > 0 and (total_errors / total_requests) > 0.5:
                status_label = "EN ERREUR"
                status_class = "danger"
            elif mem_errors > 0 and mem_success > 0:
                status_label = "REPLI ACTIF"
                status_class = "warning"
            else:
                status_label = "OPÉRATIONNEL"
                status_class = "success"

            providers.append({
                "id": p_id,
                "name": meta["name"],
                "icon": meta["icon"],
                "color": meta["color"],
                "description": meta["description"],
                "is_configured": is_configured,
                "status": status_label,
                "status_class": status_class,
                "default_model": active_model,
                "requests_count": total_requests,
                "success_count": total_success,
                "errors_count": total_errors,
                "success_rate": success_rate,
                "avg_latency_ms": avg_lat_ms,
                "benchmark_latency_ms": meta["benchmark_latency_ms"],
                "total_tokens": total_tokens,
                "last_used_at": mem_last_used,
                "last_error": mem_last_error
            })

        return providers

    def _compute_task_distribution(self, router_stats: Dict[str, Any], ai_runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcule la répartition des appels par type de tâche métier."""
        task_counts = {"job_scoring": 0, "doc_content_generation": 0, "other": 0}

        # 1. Compter depuis ai_runs
        for run in ai_runs:
            op = (run.get("operation") or "").lower()
            if any(k in op for k in ["score", "match", "qualif"]):
                task_counts["job_scoring"] += 1
            elif any(k in op for k in ["letter", "lettre", "cv", "answer", "doc", "dossier"]):
                task_counts["doc_content_generation"] += 1
            else:
                task_counts["other"] += 1

        # 2. Compter depuis les récents en mémoire si DB vide
        if sum(task_counts.values()) == 0:
            for r in router_stats.get("recent_runs", []):
                op = (r.get("operation") or "").lower()
                if op == "job_scoring":
                    task_counts["job_scoring"] += 1
                elif op == "doc_content_generation":
                    task_counts["doc_content_generation"] += 1
                else:
                    task_counts["other"] += 1

        total = sum(task_counts.values())
        return {
            "counts": task_counts,
            "total": total,
            "percentages": {
                k: round((v / total) * 100, 1) if total > 0 else 0.0
                for k, v in task_counts.items()
            }
        }

    def _compute_external_connectors(self, raw_db_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Calcule les métriques de connecteurs externes (Notion CRM, Supabase Storage, Scraper Shield)."""
        apps = raw_db_data.get("applications", [])
        docs = raw_db_data.get("documents", [])
        jobs = raw_db_data.get("jobs", [])

        # Notion CRM
        notion_synced = sum(1 for a in apps if a.get("notion_page_id"))
        total_apps = len(apps)
        notion_rate = round((notion_synced / total_apps * 100), 1) if total_apps > 0 else 0.0
        notion_token = getattr(self.config, "NOTION_TOKEN", "") or getattr(self.config, "NOTION_API_KEY", "")
        notion_db = getattr(self.config, "NOTION_DATABASE_ID", "")
        notion_configured = bool(notion_token and notion_db)

        # Supabase Storage & Documents
        cv_count = sum(1 for d in docs if (d.get("type") or "").upper() in ["CV", "RESUME"])
        letter_count = sum(1 for d in docs if (d.get("type") or "").upper() in ["COVER_LETTER", "LETTRE", "LETTER"])
        answers_count = sum(1 for d in docs if (d.get("type") or "").upper() in ["APPLICATION_ANSWERS", "ANSWERS"])

        # Heuristic Shield & Scraper
        total_jobs = len(jobs)
        heuristic_filtered = sum(1 for j in jobs if (j.get("status") or "").upper() == "IGNORED" and j.get("match_score") is None)
        llm_scored = sum(1 for j in jobs if j.get("match_score") is not None)
        quota_saved_percent = round((heuristic_filtered / total_jobs * 100), 1) if total_jobs > 0 else 0.0
        estimated_tokens_saved = heuristic_filtered * 1200  # ~1200 tokens par scoring d'offre évité

        return {
            "notion": {
                "configured": notion_configured,
                "synced_count": notion_synced,
                "total_applications": total_apps,
                "sync_rate_percent": notion_rate,
                "status": "Opérationnel" if notion_configured else "Non configuré"
            },
            "supabase_storage": {
                "connected": bool(supabase_service.client),
                "total_documents": len(docs),
                "cv_count": cv_count,
                "letter_count": letter_count,
                "answers_count": answers_count,
                "buckets": ["resumes", "letters"]
            },
            "scraper_shield": {
                "total_jobs": total_jobs,
                "heuristic_filtered": heuristic_filtered,
                "llm_scored": llm_scored,
                "quota_saved_percent": quota_saved_percent,
                "estimated_tokens_saved": estimated_tokens_saved
            }
        }

    def _compute_recent_runs(self, router_stats: Dict[str, Any], ai_runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Combine les exécutions en mémoire et Supabase en une chronologie unifiée."""
        unified_runs: List[Dict[str, Any]] = []
        seen_ids = set()

        # 1. Événements récents en mémoire du routeur (ultra frais)
        for r in router_stats.get("recent_runs", []):
            rid = r.get("id")
            if rid and rid not in seen_ids:
                seen_ids.add(rid)
                unified_runs.append({
                    "id": rid,
                    "timestamp": self._format_timestamp(r.get("timestamp")),
                    "operation": (r.get("operation") or "GENERIC").upper(),
                    "provider": r.get("provider", "unknown"),
                    "model": r.get("model", "unknown"),
                    "status": r.get("status", "SUCCESS"),
                    "latency_ms": round(r.get("latency", 0.0) * 1000) if r.get("latency") else 0,
                    "tokens": r.get("tokens", 0),
                    "fallback_used": r.get("fallback_used", False),
                    "error_message": r.get("error")
                })

        # 2. Enregistrements persistants de Supabase ai_runs
        for run in ai_runs:
            rid = run.get("id")
            if rid and rid not in seen_ids:
                seen_ids.add(rid)
                in_data = run.get("input_data") or {}
                prov = in_data.get("provider") or "gemini"
                mod = run.get("model") or in_data.get("model") or "gemini-3.6-flash"
                status = run.get("status") or "SUCCESS"
                fallback_flag = in_data.get("fallback_used", False)
                if fallback_flag and status == "SUCCESS":
                    status = "FALLBACK"

                lat = in_data.get("latency")
                lat_ms = round(float(lat) * 1000) if isinstance(lat, (int, float)) else None
                tok = in_data.get("tokens") or 0

                unified_runs.append({
                    "id": str(rid)[:8],
                    "timestamp": self._format_timestamp(run.get("created_at")),
                    "operation": (run.get("operation") or "AI_OPERATION").upper(),
                    "provider": prov,
                    "model": mod,
                    "status": status,
                    "latency_ms": lat_ms,
                    "tokens": tok,
                    "fallback_used": fallback_flag,
                    "error_message": run.get("error_message")
                })

        return unified_runs

    def _compute_kpis(
        self,
        router_stats: Dict[str, Any],
        providers: List[Dict[str, Any]],
        raw_db_data: Dict[str, List[Dict[str, Any]]],
        external_connectors: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calcule les 6 KPIs de tête d'affiche du tableau d'observabilité."""
        total_calls = sum(p["requests_count"] for p in providers)
        total_success = sum(p["success_count"] for p in providers)
        total_tokens = sum(p["total_tokens"] for p in providers)

        # Si 0 appels répertoriés dans les providers mais présents dans ai_runs
        ai_runs_len = len(raw_db_data.get("ai_runs", []))
        if total_calls < ai_runs_len:
            total_calls = ai_runs_len

        # Taux de succès global
        global_success_rate = round((total_success / total_calls * 100), 1) if total_calls > 0 else 100.0

        # Latence moyenne globale pondérée
        active_latencies = [p["avg_latency_ms"] for p in providers if p["requests_count"] > 0]
        if active_latencies:
            avg_latency_ms = round(sum(active_latencies) / len(active_latencies))
        else:
            # Baseline moyenne des providers configurés
            configured_benchmarks = [p["benchmark_latency_ms"] for p in providers if p["is_configured"]]
            avg_latency_ms = round(sum(configured_benchmarks) / len(configured_benchmarks)) if configured_benchmarks else 950

        # Cache SHA-256
        cache_st = router_stats.get("cache", {})
        cache_hit_rate = cache_st.get("hit_ratio_percent", 0.0)
        cache_hits = cache_st.get("hits", 0)
        cache_saved_seconds = cache_st.get("total_saved_seconds", 0.0)

        # Failovers
        failover_count = router_stats.get("failover_count", 0)

        # Économies Bouclier Heuristique
        shield_data = external_connectors.get("scraper_shield", {})
        heuristic_savings_count = shield_data.get("heuristic_filtered", 0)

        return {
            "total_calls": total_calls,
            "global_success_rate": global_success_rate,
            "avg_latency_ms": avg_latency_ms,
            "total_tokens": total_tokens,
            "cache_hit_rate": cache_hit_rate,
            "cache_hits": cache_hits,
            "cache_saved_seconds": cache_saved_seconds,
            "failover_count": failover_count,
            "heuristic_shield_count": heuristic_savings_count,
            "notion_sync_count": external_connectors.get("notion", {}).get("synced_count", 0)
        }

    def _format_timestamp(self, ts: Optional[str]) -> str:
        """Formate une date ISO en affichage compact 'DD/MM HH:MM:SS'."""
        if not ts:
            return "--/-- --:--"
        try:
            from app.services.notion.sync import parse_iso_datetime
            dt = parse_iso_datetime(ts)
            if dt:
                return dt.strftime("%d/%m %H:%M:%S")
            return str(ts)[:19].replace("T", " ")
        except Exception:
            return str(ts)[:19].replace("T", " ")

interfaces_analytics_service = InterfacesAnalyticsService()
