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
    """Liste les candidatures existantes avec pagination, filtres et tri chronologique."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", request.args.get("limit", 20), type=int)
    status = request.args.get("status")
    min_score = request.args.get("min_score", type=int)
    search = request.args.get("q") or request.args.get("search")

    paginated = supabase_service.get_applications_paginated(
        page=page,
        per_page=per_page,
        status=status,
        min_score=min_score,
        search=search,
        order_by="created_at",
        desc=True
    )
    return jsonify({
        "applications": paginated["items"],
        "total": paginated["total"],
        "page": paginated["page"],
        "per_page": paginated["per_page"],
        "total_pages": paginated["total_pages"],
        "has_prev": paginated["has_prev"],
        "has_next": paginated["has_next"]
    }), 200

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
        prepared_at = datetime.now(timezone.utc).isoformat()
        if cover_letter:
            letter_url = document_renderer.render_and_save_letter(
                app_id,
                profile_data["profile"],
                cover_letter.model_dump(),
                company=company_name,
                job_title=job_name,
                job=job,
                prepared_at=prepared_at,
                mobility=tailored_cv.mobility if tailored_cv else None
            )

        # Mettre à jour l'application en PREPARED
        update_payload = {
            "status": "PREPARED",
            "tailored_cv": tailored_cv.model_dump() if tailored_cv else None,
            "cover_letter": cover_letter.content if cover_letter else None,
            "application_answers": answers.model_dump() if answers else None,
            "prepared_at": prepared_at
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
    """Validation humaine : l'utilisateur passe le statut à READY et synchronise Notion."""
    if not supabase_service.client:
        return jsonify({"error": "Supabase non configuré"}), 503

    supabase_service.update_application(app_id, {"status": "READY"})

    # Synchronisation immédiate Notion si la fiche est liée
    res = supabase_service.client.table("applications").select("notion_page_id").eq("id", app_id).execute()
    if res.data and res.data[0].get("notion_page_id"):
        notion_service.update_page_status(
            page_id=res.data[0]["notion_page_id"],
            status_name="Candidature prête - en attente de validation"
        )

    return jsonify({"message": "Candidature marquée comme READY", "status": "READY"}), 200

@applications_bp.route("/api/applications/<app_id>/applied", methods=["POST"])
def mark_as_applied(app_id: str):
    """L'utilisateur confirme avoir postulé manuellement (statut APPLIED). Met à jour Supabase et Notion."""
    if not supabase_service.client:
        return jsonify({"error": "Supabase non configuré"}), 503

    now_iso = datetime.now(timezone.utc).isoformat()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1. Mise à jour Supabase
    supabase_service.update_application(app_id, {
        "status": "APPLIED",
        "applied_at": now_iso
    })

    # 2. Synchronisation immédiate Notion si lié
    res = supabase_service.client.table("applications").select("notion_page_id").eq("id", app_id).execute()
    if res.data and res.data[0].get("notion_page_id"):
        notion_service.update_page_status(
            page_id=res.data[0]["notion_page_id"],
            status_name="Candidature envoyée",
            applied_date=today_str
        )

    return jsonify({"message": "Candidature marquée comme APPLIED et synchronisée dans Notion", "status": "APPLIED", "applied_at": now_iso}), 200

@applications_bp.route("/api/notion/reconcile", methods=["POST"])
def reconcile_notion():
    """Déclenche la réconciliation bidirectionnelle complète Notion ↔ Supabase."""
    from app.services.notion.sync import notion_sync_service
    try:
        report = notion_sync_service.reconcile()
        return jsonify(report), 200
    except Exception as e:
        current_app.logger.error(f"Erreur lors de la réconciliation Notion: {e}")
        return jsonify({"error": f"Erreur de réconciliation: {str(e)}"}), 500

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

    company = job.get("company", "")
    job_title = job.get("title", "")

    # URLs signées vers les PDF déjà uploadés dans le bucket privé (None si absents)
    from app.services.documents.renderer import build_document_filename
    cv_url = letter_url = None
    if app_data.get("tailored_cv"):
        cv_url = supabase_service.get_document_url(
            "applications", f"applications/{app_id}/{build_document_filename('CV', company, job_title)}"
        )
    if app_data.get("cover_letter"):
        letter_url = supabase_service.get_document_url(
            "applications", f"applications/{app_id}/{build_document_filename('LM', company, job_title)}"
        )
    match_analysis = job.get("match_analysis") or {}
    normalized_data = job.get("normalized_data") or {}

    from app.services.ingestion.company_classifier import classify_company
    cl_type, cl_domain = classify_company(
        company=company,
        title=job_title,
        description=job.get("description", ""),
        raw_data=job.get("raw_data")
    )
    company_type = match_analysis.get("company_type") or normalized_data.get("company_type") or cl_type
    domain = match_analysis.get("company_domain") or normalized_data.get("domain") or cl_domain

    page_id = notion_service.sync_application(
        application_id=app_id,
        company=company,
        job_title=job_title,
        job_url=job.get("url", ""),
        score=app_data.get("match_score"),
        status=app_data.get("status", "QUALIFIED"),
        location=job.get("location"),
        contract_type=job.get("contract_type"),
        domain=domain,
        company_type=company_type,
        cv_url=cv_url,
        letter_url=letter_url,
        cover_letter=app_data.get("cover_letter"),
        answers=app_data.get("application_answers"),
        match_analysis=match_analysis,
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
        from app.services.documents.renderer import build_letter_payload
        pdf_bytes = pdf_generator.generate_letter_pdf(
            raw_profile,
            build_letter_payload(
                cover_letter, job=job, prepared_at=app_data.get("prepared_at"),
                mobility=(app_data.get("tailored_cv") or {}).get("mobility")
            )
        )
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
    """Vue HTML listant les candidatures avec pagination, filtres et tri chronologique."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 15, type=int)
    status = request.args.get("status", "").strip()
    min_score_raw = request.args.get("min_score", "").strip()
    min_score = int(min_score_raw) if min_score_raw.isdigit() else None
    search = (request.args.get("q") or request.args.get("search") or "").strip()

    paginated = supabase_service.get_applications_paginated(
        page=page,
        per_page=per_page,
        status=status,
        min_score=min_score,
        search=search,
        order_by="created_at",
        desc=True
    )
    filters = {
        "q": search,
        "status": status,
        "min_score": min_score_raw
    }
    return render_template(
        "applications/index.html",
        applications=paginated["items"],
        pagination=paginated,
        filters=filters
    )

@applications_bp.route("/applications/<app_id>", methods=["GET"])
def application_detail_view(app_id: str):
    """Vue HTML détaillée d'une candidature (Page Candidature spécification 17)."""
    if not supabase_service.client:
        return render_template("applications/detail.html", application=None)
    res = supabase_service.client.table("applications").select("*, jobs(*)").eq("id", app_id).execute()
    app_data = res.data[0] if res.data else None
    return render_template("applications/detail.html", application=app_data)
