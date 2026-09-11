from flask import Blueprint, jsonify, request, render_template, current_app
from app.services.storage import supabase_service
from app.services.ingestion.importer import job_importer
from app.services.ai.matcher import matcher_service
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobNormalizedData

jobs_bp = Blueprint("jobs", __name__)

@jobs_bp.route("/api/jobs", methods=["GET"])
def list_jobs():
    """Liste les offres enregistrées."""
    limit = request.args.get("limit", 50, type=int)
    jobs = supabase_service.get_jobs(limit=limit) if supabase_service.client else []
    return jsonify({"jobs": jobs, "total": len(jobs)}), 200

@jobs_bp.route("/api/jobs/<job_id>", methods=["GET"])
def get_job(job_id: str):
    """Détail d'une offre."""
    if not supabase_service.client:
        return jsonify({"error": "Supabase non configuré"}), 503
    res = supabase_service.client.table("jobs").select("*").eq("id", job_id).execute()
    if not res.data:
        return jsonify({"error": "Offre introuvable"}), 404
    return jsonify(res.data[0]), 200

@jobs_bp.route("/api/jobs/import", methods=["POST"])
def import_job():
    """Importe une nouvelle offre et la persiste après déduplication."""
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "Données JSON attendues"}), 400

    try:
        result = job_importer.import_job(payload)
        return jsonify(result), 201 if result.get("status") in ["CREATED", "SIMULATED"] else 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Erreur import offre : {e}")
        return jsonify({"error": "Erreur interne lors de l'import"}), 500

@jobs_bp.route("/api/jobs/scrape", methods=["POST"])
def scrape_job():
    """Scrape une ou plusieurs offres depuis leurs URLs (LinkedIn, WTTJ, Indeed, etc.), calcule le match et prépare les livrables."""
    payload = request.get_json() or {}
    raw_urls = payload.get("urls")
    raw_url = payload.get("url")
    urls_list = []

    if isinstance(raw_urls, list):
        urls_list = [u.strip() for u in raw_urls if isinstance(u, str) and u.strip()]
    elif isinstance(raw_url, str) and raw_url.strip():
        # Découper par retour à la ligne ou virgule
        for part in raw_url.replace(",", "\n").splitlines():
            clean_part = part.strip()
            if clean_part:
                urls_list.append(clean_part)

    if not urls_list:
        return jsonify({"error": "Au moins une URL d'offre est requise"}), 400

    auto_prepare = payload.get("auto_prepare", True)
    min_score = payload.get("min_match_score", current_app.config.get("MATCH_THRESHOLD_RECOMMENDED", 75))

    from app.services.ingestion.collector import job_collector_service

    try:
        if len(urls_list) == 1:
            result = job_collector_service.import_and_process_url(
                url=urls_list[0],
                auto_prepare=auto_prepare,
                min_match_score=min_score
            )
            if not result.get("success", False):
                return jsonify({"error": result.get("error", "Erreur lors de l'import")}), 400
            return jsonify(result), 200
        else:
            result = job_collector_service.import_and_process_urls(
                urls=urls_list,
                auto_prepare=auto_prepare,
                min_match_score=min_score
            )
            if not result.get("success", False) and result.get("total_unique", 0) == 0:
                return jsonify({"error": result.get("error", "Erreur lors de l'import du lot")}), 400
            return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f"Erreur scraping offres : {e}")
        return jsonify({"error": f"Impossible de récupérer les offres: {str(e)}"}), 500

@jobs_bp.route("/api/jobs/<job_id>/match", methods=["POST"])
def match_job(job_id: str):
    """Calcule le score de matching IA pour l'offre spécifiée."""
    if not supabase_service.client:
        return jsonify({"error": "Supabase non configuré"}), 503

    # Récupérer l'offre
    res_job = supabase_service.client.table("jobs").select("*").eq("id", job_id).execute()
    if not res_job.data:
        return jsonify({"error": "Offre introuvable"}), 404
    job = res_job.data[0]

    # Récupérer le profil candidat actif
    profile_data = supabase_service.get_active_candidate_profile()
    if not profile_data:
        return jsonify({"error": "Aucun profil candidat actif trouvé"}), 400

    candidate_profile = CandidateProfile.model_validate(profile_data["profile"])
    candidate_profile.preferences = candidate_profile.preferences.model_validate(profile_data.get("preferences", {}))
    job_normalized = JobNormalizedData.model_validate(job.get("normalized_data", {}))

    # Calculer le match
    match_result = matcher_service.match(candidate_profile, job_normalized)
    if not match_result:
        return jsonify({"error": "Échec du calcul de matching Gemini"}), 500

    # Sauvegarder dans la table jobs
    update_data = {
        "match_score": match_result.score,
        "match_level": match_result.level,
        "match_analysis": match_result.model_dump(),
        "status": "QUALIFIED" if match_result.score >= current_app.config["MATCH_THRESHOLD_RECOMMENDED"] else "REVIEW"
    }
    supabase_service.client.table("jobs").update(update_data).eq("id", job_id).execute()

    return jsonify({"message": "Matching effectué", "match": match_result.model_dump()}), 200

@jobs_bp.route("/api/jobs/collect", methods=["POST"])
def collect_jobs():
    """Lance la collecte automatique et scraping batch d'offres récentes (24h, 3j, 7j)."""
    payload = request.get_json() or {}
    duration = payload.get("duration", "24h")
    query = payload.get("query")
    limit = payload.get("limit", 5)
    auto_prepare = payload.get("auto_prepare", True)

    try:
        limit = max(1, min(int(limit), 20))
    except (ValueError, TypeError):
        limit = 5

    try:
        from app.services.ingestion.collector import job_collector_service
        summary = job_collector_service.run_collection(
            duration=duration,
            query=query,
            limit=limit,
            auto_prepare=auto_prepare
        )
        return jsonify(summary), 200
    except Exception as e:
        current_app.logger.error(f"Erreur lors de la collecte d'offres: {e}")
        return jsonify({"error": f"Erreur lors de la collecte: {str(e)}"}), 500

@jobs_bp.route("/jobs", methods=["GET"])
def jobs_view():
    """Vue HTML de listing des offres."""
    jobs = supabase_service.get_jobs(limit=100) if supabase_service.client else []
    return render_template("jobs/index.html", jobs=jobs)

@jobs_bp.route("/jobs/<job_id>", methods=["GET"])
def job_detail_view(job_id: str):
    """Vue HTML détaillée d'une offre (Page Offre spécification 16)."""
    if not supabase_service.client:
        return render_template("jobs/detail.html", job=None)
    res = supabase_service.client.table("jobs").select("*").eq("id", job_id).execute()
    job = res.data[0] if res.data else None
    return render_template("jobs/detail.html", job=job)

