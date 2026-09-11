import io
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, render_template, current_app, send_file
from app.services.storage import supabase_service
from app.services.ai.cv_generator import cv_generator_service
from app.services.ai.letter_generator import letter_generator_service
from app.services.ai.answer_generator import answer_generator_service
from app.services.documents.renderer import document_renderer
from app.services.documents.pdf import pdf_generator
from app.services.notion.client import notion_service
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobNormalizedData

applications_bp = Blueprint("applications", __name__)

@applications_bp.route("/api/applications", methods=["GET"])
def list_applications():
    """Liste les candidatures existantes."""
    apps = supabase_service.get_applications(limit=100) if supabase_service.client else []
    return jsonify({"applications": apps, "total": len(apps)}), 200

@applications_bp.route("/api/applications/<app_id>", methods=["GET"])
def get_application(app_id: str):
    """Détail d'une candidature."""
    if not supabase_service.client:
        return jsonify({"error": "Supabase non configuré"}), 503
    res = supabase_service.client.table("applications").select("*, jobs(*)").eq("id", app_id).execute()
    if not res.data:
        return jsonify({"error": "Candidature introuvable"}), 404
    return jsonify(res.data[0]), 200

@applications_bp.route("/api/applications/create-from-job/<job_id>", methods=["POST"])
def create_application_from_job(job_id: str):
    """Crée une candidature à partir d'une offre d'emploi."""
    if not supabase_service.client:
        return jsonify({"error": "Supabase non configuré"}), 503

    profile_data = supabase_service.get_active_candidate_profile()
    if not profile_data:
        return jsonify({"error": "Aucun profil candidat actif trouvé"}), 400

    existing = supabase_service.client.table("applications").select("*").eq("job_id", job_id).execute()
    if existing.data:
        app_id = existing.data[0]["id"]
        return jsonify({"message": "Candidature existante", "application_id": app_id}), 200

    res_job = supabase_service.client.table("jobs").select("*").eq("id", job_id).execute()
    match_score = res_job.data[0].get("match_score") if res_job.data else None

    new_app = {
        "job_id": job_id,
        "candidate_profile_id": profile_data["id"],
        "status": "QUALIFIED",
        "match_score": match_score
    }
    res_create = supabase_service.client.table("applications").insert(new_app).execute()
    app_id = res_create.data[0]["id"]
    return jsonify({"message": "Candidature créée", "application_id": app_id}), 201

@applications_bp.route("/api/applications/<app_id>/prepare", methods=["POST"])
def prepare_application(app_id: str):
    """Génère le CV personnalisé, la lettre et les réponses, puis génère les PDFs."""
    if not supabase_service.client:
        return jsonify({"error": "Supabase non configuré"}), 503

    # Récupérer l'application et l'offre associée
    res_app = supabase_service.client.table("applications").select("*, jobs(*)").eq("id", app_id).execute()
    if not res_app.data:
        return jsonify({"error": "Candidature introuvable"}), 404
    application = res_app.data[0]
    job = application.get("jobs", {})

    # Mettre à jour le statut en PREPARING
    supabase_service.client.table("applications").update({"status": "PREPARING"}).eq("id", app_id).execute()

    # Récupérer le profil candidat
    profile_data = supabase_service.get_active_candidate_profile()
    if not profile_data:
        return jsonify({"error": "Profil candidat non trouvé"}), 400

    profile = CandidateProfile.model_validate(profile_data["profile"])
    job_normalized = JobNormalizedData.model_validate(job.get("normalized_data", {}))

    try:
        # 1. Génération CV JSON
        tailored_cv = cv_generator_service.generate(
            job_id=job.get("id", ""),
            profile=profile,
            job_data=job_normalized,
            application_id=app_id
        )

        # 2. Génération Lettre
        cover_letter = letter_generator_service.generate(
            profile=profile,
            job_data=job_normalized,
            application_id=app_id
        )

        # 3. Réponses aux questions
        answers = answer_generator_service.generate(
            profile=profile,
            job_data=job_normalized,
            application_id=app_id
        )

        # 4. Rendu PDF et upload Storage
        cv_url = None
        letter_url = None
        company_name = job.get("company") or ""
        job_name = job.get("title") or ""
        if tailored_cv:
            cv_url = document_renderer.render_and_save_cv(
                app_id,
                profile_data["profile"],
                tailored_cv.model_dump(),
                company=company_name,
                job_title=job_name
            )
        if cover_letter:
            letter_url = document_renderer.render_and_save_letter(
                app_id,
                profile_data["profile"],
                cover_letter.model_dump(),
                company=company_name,
                job_title=job_name
            )

        # Mettre à jour l'application en PREPARED
        update_payload = {
            "status": "PREPARED",
            "tailored_cv": tailored_cv.model_dump() if tailored_cv else None,
            "cover_letter": cover_letter.content if cover_letter else None,
            "application_answers": answers.model_dump() if answers else None,
            "prepared_at": datetime.now(timezone.utc).isoformat()
        }
        supabase_service.client.table("applications").update(update_payload).eq("id", app_id).execute()

        return jsonify({
            "message": "Candidature préparée avec succès",
            "cv_url": cv_url,
            "letter_url": letter_url
        }), 200

    except Exception as e:
        current_app.logger.error(f"Erreur lors de la préparation de la candidature {app_id}: {e}")
        supabase_service.client.table("applications").update({"status": "ERROR"}).eq("id", app_id).execute()
        return jsonify({"error": f"Erreur de préparation: {str(e)}"}), 500

@applications_bp.route("/api/applications/<app_id>/ready", methods=["POST"])
def mark_as_ready(app_id: str):
    """Validation humaine : l'utilisateur passe le statut à READY."""
    if not supabase_service.client:
        return jsonify({"error": "Supabase non configuré"}), 503

    supabase_service.client.table("applications").update({"status": "READY"}).eq("id", app_id).execute()
    return jsonify({"message": "Candidature marquée comme READY", "status": "READY"}), 200

@applications_bp.route("/api/applications/<app_id>/applied", methods=["POST"])
def mark_as_applied(app_id: str):
    """L'utilisateur confirme avoir postulé manuellement (statut APPLIED)."""
    if not supabase_service.client:
        return jsonify({"error": "Supabase non configuré"}), 503

    now_iso = datetime.now(timezone.utc).isoformat()
    supabase_service.client.table("applications").update({
        "status": "APPLIED",
        "applied_at": now_iso
    }).eq("id", app_id).execute()
    return jsonify({"message": "Candidature marquée comme APPLIED", "status": "APPLIED", "applied_at": now_iso}), 200

@applications_bp.route("/api/notion/sync/<app_id>", methods=["POST"])
def sync_notion(app_id: str):
    """Synchronise la candidature dans Notion."""
    if not supabase_service.client:
        return jsonify({"error": "Supabase non configuré"}), 503

    res = supabase_service.client.table("applications").select("*, jobs(*)").eq("id", app_id).execute()
    if not res.data:
        return jsonify({"error": "Candidature introuvable"}), 404

    app_data = res.data[0]
    job = app_data.get("jobs", {}) or {}

    tailored_cv = app_data.get("tailored_cv")
    cv_url = None
    if tailored_cv and current_app.config.get("SUPABASE_URL"):
        cv_url = f"{current_app.config['SUPABASE_URL']}/storage/v1/object/public/applications/applications/{app_id}/cv.pdf"

    page_id = notion_service.sync_application(
        application_id=app_id,
        company=job.get("company", ""),
        job_title=job.get("title", ""),
        job_url=job.get("url", ""),
        score=app_data.get("match_score"),
        status=app_data.get("status", "QUALIFIED"),
        location=job.get("location"),
        contract_type=job.get("contract_type"),
        domain="Ingénierie Logicielle / Backend & Cloud",
        cv_url=cv_url,
        cover_letter=app_data.get("cover_letter"),
        answers=app_data.get("application_answers"),
        match_analysis=job.get("match_analysis"),
        notes=app_data.get("notes"),
        notion_page_id=app_data.get("notion_page_id")
    )

    if page_id:
        supabase_service.client.table("applications").update({"notion_page_id": page_id}).eq("id", app_id).execute()

    return jsonify({"message": "Synchronisation Notion effectuée", "notion_page_id": page_id}), 200

@applications_bp.route("/api/applications/<app_id>/download/<doc_type>", methods=["GET"])
def download_application_document(app_id: str, doc_type: str):
    """Télécharge le document PDF généré (cv ou letter)."""
    if not supabase_service.client:
        return jsonify({"error": "Supabase non configuré"}), 503

    try:
        res = supabase_service.client.table("applications").select("*, jobs(*)").eq("id", app_id).execute()
        if not res.data:
            return jsonify({"error": "Candidature introuvable"}), 404
        app_data = res.data[0]
    except Exception as e:
        current_app.logger.warning(f"Erreur Supabase lors du téléchargement: {e}")
        return jsonify({"error": "Service Supabase indisponible"}), 503
    job = app_data.get("jobs", {}) or {}
    raw_company = job.get("company") or "Entreprise"
    raw_title = job.get("title") or ""
    clean_company = "".join(c for c in raw_company if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
    clean_title = "".join(c for c in raw_title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")[:35]

    profile_data = supabase_service.get_active_candidate_profile()
    raw_profile = profile_data["profile"] if profile_data else {}

    if doc_type == "cv":
        cv_data = app_data.get("tailored_cv")
        if not cv_data:
            return jsonify({"error": "CV non encore généré"}), 404
        pdf_bytes = pdf_generator.generate_cv_pdf(raw_profile, cv_data)
        download_name = f"Emmanuel_TRO_CV_{clean_company}_{clean_title}.pdf" if clean_title else f"Emmanuel_TRO_CV_{clean_company}.pdf"
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=download_name
        )
    elif doc_type in ["letter", "cover-letter"]:
        cover_letter = app_data.get("cover_letter")
        if not cover_letter:
            return jsonify({"error": "Lettre non encore générée"}), 404
        pdf_bytes = pdf_generator.generate_letter_pdf(raw_profile, {"content": cover_letter})
        download_name = f"Emmanuel_TRO_LM_{clean_company}_{clean_title}.pdf" if clean_title else f"Emmanuel_TRO_LM_{clean_company}.pdf"
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=download_name
        )
    else:
        return jsonify({"error": "Type de document invalide (attendu: 'cv' ou 'letter')"}), 400

@applications_bp.route("/applications", methods=["GET"])
def applications_view():
    """Vue HTML listant les candidatures."""
    apps = supabase_service.get_applications(limit=100) if supabase_service.client else []
    return render_template("applications/index.html", applications=apps)

@applications_bp.route("/applications/<app_id>", methods=["GET"])
def application_detail_view(app_id: str):
    """Vue HTML détaillée d'une candidature (Page Candidature spécification 17)."""
    if not supabase_service.client:
        return render_template("applications/detail.html", application=None)
    res = supabase_service.client.table("applications").select("*, jobs(*)").eq("id", app_id).execute()
    app_data = res.data[0] if res.data else None
    return render_template("applications/detail.html", application=app_data)
