import os
from flask import Flask
from app.config import Config

def create_app(config_class=Config):
    """Application Factory Flask."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Assurer que les dossiers templates et static sont trouvés
    # Enregistrement des Blueprints
    from app.routes.dashboard import dashboard_bp
    from app.routes.jobs import jobs_bp
    from app.routes.applications import applications_bp
    from app.routes.candidate import candidate_bp
    from app.routes.scheduler import scheduler_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(applications_bp)
    app.register_blueprint(candidate_bp)
    app.register_blueprint(scheduler_bp)

    # Démarrage du planificateur en tâche de fond si activé et hors tests
    if app.config.get("ENABLE_SCHEDULER") and not app.testing:
        # Éviter le double démarrage avec le reloader Werkzeug
        if os.environ.get("WERKZEUG_RUN_MAIN") in (None, "true"):
            from app.services.scheduler.daily_scheduler import daily_scheduler_service
            daily_scheduler_service.start(app)

    @app.context_processor
    def inject_candidate():
        try:
            from app.services.storage import supabase_service
            from app.services.scheduler.daily_scheduler import daily_scheduler_service
            profile_data = supabase_service.get_active_candidate_profile() if supabase_service.client else None
            scheduler_status = daily_scheduler_service.get_status()
            return dict(active_candidate=profile_data, scheduler_status=scheduler_status)
        except Exception:
            return dict(active_candidate=None, scheduler_status=None)

    return app

