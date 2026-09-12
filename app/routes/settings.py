import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
from flask import Blueprint, jsonify, request, render_template, current_app
from app.services.storage import supabase_service
from app.services.ai.gemini import gemini_service
from app.schemas.candidate import CandidatePreferences

logger = logging.getLogger(__name__)

settings_bp = Blueprint("settings", __name__)

AVAILABLE_AI_MODELS = [
    {
        "id": "gemini-3.5-flash",
        "name": "Gemini 3.5 Flash",
        "description": "Modèle ultra-rapide par défaut, idéal pour le tri et le matching intensif",
        "recommended": True
    },
    {
        "id": "gemini-2.5-flash",
        "name": "Gemini 2.5 Flash",
        "description": "Très rapide, équilibré pour l'extraction et l'analyse de CV",
        "recommended": False
    },
    {
        "id": "gemini-2.5-pro",
        "name": "Gemini 2.5 Pro",
        "description": "Raisonnement avancé, excellent pour les lettres de motivation orales de haut niveau",
        "recommended": False
    },
    {
        "id": "gemini-2.5-flash-lite",
        "name": "Gemini 2.5 Flash Lite",
        "description": "Ultra léger et très économe en quota",
        "recommended": False
    }
]

def _get_active_preferences() -> Dict[str, Any]:
    """Extrait et normalise les préférences du profil candidat actif."""
    profile = supabase_service.get_active_candidate_profile() if supabase_service.client else None
    raw_prefs = (profile.get("preferences") or {}) if profile else {}
    # Validation avec CandidatePreferences pour garantir toutes les valeurs par défaut
    validated = CandidatePreferences.model_validate(raw_prefs)
    return validated.model_dump()

@settings_bp.route("/settings", methods=["GET"])
def settings_view():
    """Vue HTML du centre de paramétrage."""
    preferences = _get_active_preferences()
    return render_template(
        "settings/index.html",
        preferences=preferences,
        available_models=AVAILABLE_AI_MODELS
    )

@settings_bp.route("/api/settings", methods=["GET"])
def get_settings():
    """API : Récupère les préférences et paramètres actuels."""
    preferences = _get_active_preferences()
    return jsonify({
        "preferences": preferences,
        "available_models": AVAILABLE_AI_MODELS
    }), 200

@settings_bp.route("/api/settings", methods=["PUT", "POST"])
def update_settings():
    """API : Met à jour les paramètres dans le profil candidat actif."""
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "Corps JSON attendu"}), 400

    try:
        # Extraire les préférences
        prefs_payload = payload.get("preferences", payload)
        validated_prefs = CandidatePreferences.model_validate(prefs_payload)

        profile = supabase_service.get_active_candidate_profile() if supabase_service.client else None
        if profile and supabase_service.client:
            profile_id = profile.get("id")
            update_data = {
                "preferences": validated_prefs.model_dump(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            supabase_service.client.table("candidate_profiles").update(update_data).eq("id", profile_id).execute()
            return jsonify({
                "message": "Paramètres enregistrés avec succès dans Supabase.",
                "preferences": validated_prefs.model_dump()
            }), 200
        else:
            return jsonify({
                "message": "Paramètres validés avec succès (mode simulation / Supabase déconnecté).",
                "preferences": validated_prefs.model_dump()
            }), 200

    except Exception as e:
        logger.error(f"Erreur enregistrement des paramètres : {e}")
        return jsonify({"error": f"Erreur de validation ou sauvegarde: {str(e)}"}), 400

@settings_bp.route("/api/settings/blacklist", methods=["POST"])
def add_to_blacklist():
    """API : Ajoute une entreprise à la liste noire (avec rétro-mise à jour optionnelle des offres)."""
    payload = request.get_json() or {}
    company = (payload.get("company") or "").strip()
    if not company:
        return jsonify({"error": "Le nom de l'entreprise est requis."}), 400

    try:
        profile = supabase_service.get_active_candidate_profile() if supabase_service.client else None
        current_prefs = (profile.get("preferences") or {}) if profile else {}
        excluded = list(current_prefs.get("excluded_companies") or [])

        # Éviter les doublons insensibles à la casse
        if not any(c.lower() == company.lower() for c in excluded):
            excluded.append(company)
            current_prefs["excluded_companies"] = excluded

            if profile and supabase_service.client:
                supabase_service.client.table("candidate_profiles").update({
                    "preferences": current_prefs,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", profile["id"]).execute()

        # Rétro-mise à jour optionnelle des offres existantes de cette entreprise vers BLACKLISTED
        updated_jobs_count = 0
        if supabase_service.client:
            try:
                res = supabase_service.client.table("jobs").select("id, company").execute()
                for j in (res.data or []):
                    j_comp = (j.get("company") or "").strip().lower()
                    if company.lower() == j_comp or (len(company) >= 3 and (company.lower() in j_comp or j_comp in company.lower())):
                        supabase_service.client.table("jobs").update({"status": "BLACKLISTED"}).eq("id", j["id"]).execute()
                        updated_jobs_count += 1
            except Exception as je:
                logger.warning(f"Erreur mise à jour offres existantes pour blacklist: {je}")

        return jsonify({
            "message": f"'{company}' a été ajoutée à la blacklist.",
            "excluded_companies": excluded,
            "retro_updated_jobs": updated_jobs_count
        }), 200

    except Exception as e:
        logger.error(f"Erreur ajout blacklist: {e}")
        return jsonify({"error": str(e)}), 500

@settings_bp.route("/api/settings/blacklist", methods=["DELETE"])
def remove_from_blacklist():
    """API : Retire une entreprise de la liste noire."""
    payload = request.get_json() or {}
    company = (payload.get("company") or "").strip()
    if not company:
        return jsonify({"error": "Le nom de l'entreprise est requis."}), 400

    try:
        profile = supabase_service.get_active_candidate_profile() if supabase_service.client else None
        current_prefs = (profile.get("preferences") or {}) if profile else {}
        excluded = list(current_prefs.get("excluded_companies") or [])

        new_excluded = [c for c in excluded if c.lower() != company.lower()]
        current_prefs["excluded_companies"] = new_excluded

        if profile and supabase_service.client:
            supabase_service.client.table("candidate_profiles").update({
                "preferences": current_prefs,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", profile["id"]).execute()

        return jsonify({
            "message": f"'{company}' a été retirée de la blacklist.",
            "excluded_companies": new_excluded
        }), 200

    except Exception as e:
        logger.error(f"Erreur suppression blacklist: {e}")
        return jsonify({"error": str(e)}), 500

@settings_bp.route("/api/settings/test-ai", methods=["POST"])
def test_ai():
    """API : Teste la connectivité avec l'API Gemini et le modèle sélectionné."""
    payload = request.get_json() or {}
    model_name = payload.get("model")
    result = gemini_service.test_connection(model_name=model_name)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code
