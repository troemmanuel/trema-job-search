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

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(applications_bp)
    app.register_blueprint(candidate_bp)

    return app
