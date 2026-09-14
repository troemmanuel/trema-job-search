from flask import Blueprint, jsonify, render_template, request
from app.services.analytics import analytics_service, interfaces_analytics_service

analytics_bp = Blueprint("analytics", __name__)

@analytics_bp.route("/analytics", methods=["GET"])
def analytics_view():
    """Page du Dashboard Analytique : Entonnoir Recrutement et Observabilité des Interfaces."""
    tab = request.args.get("tab", "funnel")
    if tab not in ["funnel", "interfaces"]:
        tab = "funnel"

    period = request.args.get("period", "all")
    if period not in ["all", "30d", "7d"]:
        period = "all"

    funnel_data = analytics_service.get_analytics(period=period)
    interfaces_data = interfaces_analytics_service.get_interfaces_analytics()

    router_stats = None
    try:
        from app.llm import router
        router_stats = router.get_stats()
    except Exception:
        pass

    return render_template(
        "analytics.html",
        analytics=funnel_data,
        interfaces=interfaces_data,
        active_tab=tab,
        active_period=period,
        router_stats=router_stats
    )

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

@analytics_bp.route("/api/analytics/interfaces", methods=["GET"])
def api_analytics_interfaces():
    """API JSON des métriques d'observabilité des interfaces et APIs (LLM, Cache, Connecteurs)."""
    interfaces_data = interfaces_analytics_service.get_interfaces_analytics()
    return jsonify({
        "success": True,
        **interfaces_data
    }), 200
