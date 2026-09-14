from flask import Blueprint, jsonify, render_template, request
from app.services.analytics import analytics_service

analytics_bp = Blueprint("analytics", __name__)

@analytics_bp.route("/analytics", methods=["GET"])
def analytics_view():
    """Page du Dashboard Analytique & Taux de Conversion."""
    period = request.args.get("period", "all")
    if period not in ["all", "30d", "7d"]:
        period = "all"

    data = analytics_service.get_analytics(period=period)
    router_stats = None
    try:
        from app.llm import router
        router_stats = router.get_stats()
    except Exception:
        pass

    return render_template("analytics.html", analytics=data, active_period=period, router_stats=router_stats)

@analytics_bp.route("/api/analytics/stats", methods=["GET"])
def api_analytics_stats():
    """API JSON des métriques d'entonnoir et de conversion."""
    period = request.args.get("period", "all")
    if period not in ["all", "30d", "7d"]:
        period = "all"

    data = analytics_service.get_analytics(period=period)
    router_stats = None
    try:
        from app.llm import router
        router_stats = router.get_stats()
    except Exception:
        pass

    return jsonify({
        "success": True,
        **data,
        "router_stats": router_stats
    }), 200
