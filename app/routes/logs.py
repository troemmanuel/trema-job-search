import os
import re
import logging
from flask import Blueprint, jsonify, request, render_template, send_file

logger = logging.getLogger(__name__)

logs_bp = Blueprint("logs", __name__)

LOG_FILE_PATH = os.path.join(os.getcwd(), "logs", "app.log")

LOG_LINE_REGEX = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\[([A-Z]+)\s*\]\s+\[([^\]]+)\]\s+(.*)$"
)

def _read_recent_log_lines(limit: int = 200, level: str = "ALL", query: str = "") -> list:
    """Lit et filtre les dernières lignes du fichier logs/app.log."""
    if not os.path.exists(LOG_FILE_PATH):
        return []

    results = []
    level_filter = level.upper() if level and level.upper() != "ALL" else None
    query_filter = query.lower().strip() if query else None

    try:
        with open(LOG_FILE_PATH, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # On parcourt de la fin vers le début pour prendre les plus récents
        for line in reversed(lines):
            line_str = line.strip()
            if not line_str:
                continue

            match = LOG_LINE_REGEX.match(line_str)
            if match:
                ts, lvl, comp, msg = match.groups()
                entry = {
                    "timestamp": ts,
                    "level": lvl.strip(),
                    "logger": comp.strip(),
                    "message": msg,
                    "raw": line_str
                }
            else:
                entry = {
                    "timestamp": "",
                    "level": "INFO",
                    "logger": "app",
                    "message": line_str,
                    "raw": line_str
                }

            # Filtre par niveau
            if level_filter and entry["level"] != level_filter:
                continue

            # Filtre par texte/recherche
            if query_filter:
                text_to_search = f"{entry['logger']} {entry['message']}".lower()
                if query_filter not in text_to_search:
                    continue

            results.append(entry)
            if len(results) >= limit:
                break

        # Remettre dans l'ordre chronologique
        results.reverse()
        return results

    except Exception as e:
        logger.error(f"Erreur lecture du fichier de log: {e}")
        return []

@logs_bp.route("/logs", methods=["GET"])
def logs_view():
    """Vue HTML du terminal de logs en direct."""
    return render_template("logs.html")

@logs_bp.route("/api/logs", methods=["GET"])
def get_logs_api():
    """API JSON retournant les dernières lignes de log filtrées."""
    limit = min(int(request.args.get("limit", 200)), 1000)
    level = request.args.get("level", "ALL")
    query = request.args.get("q", "")

    entries = _read_recent_log_lines(limit=limit, level=level, query=query)
    file_size = os.path.getsize(LOG_FILE_PATH) if os.path.exists(LOG_FILE_PATH) else 0

    return jsonify({
        "success": True,
        "count": len(entries),
        "file_size_bytes": file_size,
        "logs": entries
    }), 200

@logs_bp.route("/api/logs/download", methods=["GET"])
def download_logs():
    """Téléchargement direct du fichier app.log."""
    if not os.path.exists(LOG_FILE_PATH):
        return jsonify({"error": "Aucun fichier de log disponible"}), 404

    return send_file(
        LOG_FILE_PATH,
        as_attachment=True,
        download_name="app.log",
        mimetype="text/plain"
    )

@logs_bp.route("/api/logs/clear", methods=["POST"])
def clear_logs():
    """Efface le contenu du fichier de log."""
    try:
        os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
        with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
            f.write("")
        logger.info("[Logs] Fichier de log réinitialisé par l'utilisateur.")
        return jsonify({"success": True, "message": "Fichier de log vidé avec succès."}), 200
    except Exception as e:
        return jsonify({"error": f"Erreur réinitialisation: {str(e)}"}), 500
