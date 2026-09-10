from datetime import datetime
from flask import Blueprint, jsonify, request, render_template, current_app
from app.services.storage.supabase import supabase_service
from app.schemas.candidate import CandidateProfile, CandidatePreferences

candidate_bp = Blueprint("candidate", __name__)

@candidate_bp.route("/api/candidate", methods=["GET"])
def get_candidate_profile():
    """Récupère le profil maître actif."""
    profile = supabase_service.get_active_candidate_profile() if supabase_service.client else None
    if not profile:
        return jsonify({"message": "Aucun profil configuré"}), 404
    return jsonify(profile), 200

@candidate_bp.route("/api/candidate", methods=["PUT", "POST"])
def save_candidate_profile():
    """Crée ou met à jour le profil maître (incrémentant la version)."""
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "Données JSON attendues"}), 400

    try:
        # Validation Pydantic
        profile_obj = CandidateProfile.model_validate(payload.get("profile", payload))
        preferences_obj = CandidatePreferences.model_validate(payload.get("preferences", profile_obj.preferences.model_dump()))

        current_profile = supabase_service.get_active_candidate_profile() if supabase_service.client else None
        new_version = (current_profile.get("version", 1) + 1) if current_profile else 1

        record = {
            "name": profile_obj.name,
            "profile": profile_obj.model_dump(exclude={"preferences"}),
            "preferences": preferences_obj.model_dump(),
            "version": new_version,
            "is_active": True,
            "updated_at": datetime.utcnow().isoformat()
        }

        if supabase_service.client:
            if current_profile:
                res = supabase_service.client.table("candidate_profiles").update(record).eq("id", current_profile["id"]).execute()
            else:
                res = supabase_service.client.table("candidate_profiles").insert(record).execute()
            saved = res.data[0] if res.data else record
            return jsonify({"message": "Profil enregistré", "profile": saved}), 200
        else:
            return jsonify({"message": "Supabase non connecté, profil simulé", "profile": record}), 200

    except Exception as e:
        current_app.logger.error(f"Erreur validation ou sauvegarde profil: {e}")
        return jsonify({"error": str(e)}), 400

@candidate_bp.route("/candidate", methods=["GET"])
def candidate_view():
    """Vue HTML de consultation et édition du profil candidat."""
    profile = supabase_service.get_active_candidate_profile() if supabase_service.client else None
    return render_template("candidate/profile.html", profile=profile)
