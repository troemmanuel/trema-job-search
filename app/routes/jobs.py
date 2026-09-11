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
    """Scrape automatiquement une offre depuis son URL et l'enregistre."""
    payload = request.get_json() or {}
    url = payload.get("url", "").strip()
    if not url:
        return jsonify({"error": "L'URL de l'offre est requise"}), 400

    from app.services.ingestion.scraper import job_scraper

    try:
        scraped_data = job_scraper.scrape(url)
        import_result = job_importer.import_job(scraped_data)
        
        job = import_result.get("job")
        auto_match = payload.get("auto_match", True)

        match_data = None
        if auto_match and job and job.get("id"):
            try:
                profile_data = supabase_service.get_active_candidate_profile()
                if profile_data:
                    candidate_profile = CandidateProfile.model_validate(profile_data["profile"])
                    candidate_profile.preferences = candidate_profile.preferences.model_validate(profile_data.get("preferences", {}))
                    job_normalized = JobNormalizedData.model_validate(job.get("normalized_data", {}))
                    match_result = matcher_service.match(candidate_profile, job_normalized)
                    if match_result:
                        match_data = match_result.model_dump()
                        if supabase_service.client:
                            update_data = {
                                "match_score": match_result.score,
                                "match_level": match_result.level,
                                "match_analysis": match_data,
                                "status": "QUALIFIED" if match_result.score >= current_app.config["MATCH_THRESHOLD_RECOMMENDED"] else "REVIEW"
                            }
                            supabase_service.client.table("jobs").update(update_data).eq("id", job["id"]).execute()
                            job["match_score"] = match_result.score
                            job["match_level"] = match_result.level
            except Exception as me:
                current_app.logger.warning(f"Erreur calcul auto-match après scrape: {me}")

        return jsonify({
            "status": import_result.get("status"),
            "job": job,
            "match": match_data,
            "message": import_result.get("message") or "Offre extraite et importée avec succès"
        }), 201 if import_result.get("status") in ["CREATED", "SIMULATED"] else 200

    except Exception as e:
        current_app.logger.error(f"Erreur scraping offre pour {url}: {e}")
        return jsonify({"error": f"Impossible de récupérer l'offre: {str(e)}"}), 500

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
