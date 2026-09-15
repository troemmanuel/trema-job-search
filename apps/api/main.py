import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import Config
from app.logging_config import http_logging_middleware, setup_logging
from app.api.router import api_v1_router
from app.schemas.api import HealthResponse, RootInfoResponse, ScrapeStreamEvent
from app.services.storage import supabase_service
from app.services.ai.gemini import gemini_service
from app.services.notion.client import notion_service
from app.services.scheduler.daily_scheduler import daily_scheduler_service

setup_logging()
logger = logging.getLogger("trema_api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Démarrage de l'API Trema Job Search (FastAPI)...")
    if Config.ENABLE_SCHEDULER:
        try:
            daily_scheduler_service.start()
            logger.info("Planificateur quotidien initialisé avec succès.")
        except Exception as e:
            logger.warning(f"Impossible de démarrer le planificateur: {e}")
    yield
    # Shutdown
    logger.info("Arrêt de l'API Trema Job Search...")

app = FastAPI(
    title="Trema Job Search API",
    description="Backend API moderne pour l'agent IA de recherche d'emploi et de génération de candidatures sur mesure.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Traçage HTTP (méthode, chemin, statut, durée) dans logs/app.log
app.middleware("http")(http_logging_middleware)


# Les exceptions non gérées deviennent un 500 JSON *à l'intérieur* du middleware CORS :
# sinon la réponse d'erreur part sans en-têtes CORS et le navigateur ne voit qu'un "Failed to fetch".
# (Déclaré avant CORS : le dernier middleware ajouté est le plus externe.)
@app.middleware("http")
async def unhandled_errors_to_json(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:  # noqa: BLE001 - filet de sécurité global
        logger.exception(f"Erreur non gérée sur {request.method} {request.url.path}: {exc}")
        return JSONResponse(status_code=500, content={"detail": f"Erreur interne : {exc}"})


# Configuration CORS pour Next.js (port 3000 par défaut)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusion des routers API v1
app.include_router(api_v1_router)


def custom_openapi():
    """Schéma OpenAPI enrichi : expose aussi les modèles qui ne transitent pas en JSON classique (SSE)."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    sse_schema = ScrapeStreamEvent.model_json_schema(ref_template="#/components/schemas/{model}")
    for name, definition in sse_schema.pop("$defs", {}).items():
        components.setdefault(name, definition)
    components["ScrapeStreamEvent"] = sse_schema
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi

@app.get("/health", tags=["System"], response_model=HealthResponse)
def root_health():
    """Healthcheck global pour Docker et proxies."""
    return {
        "status": "ok",
        "version": "2.0.0",
        "services": {
            "supabase": "connected" if supabase_service.is_configured() else "unconfigured",
            "gemini": "configured" if gemini_service.is_configured() else "unconfigured",
            "notion": "configured" if notion_service.is_configured() else "unconfigured",
        },
    }

@app.get("/", tags=["System"], response_model=RootInfoResponse)
def root_info():
    """Information racine de l'API."""
    return {
        "name": "Trema Job Search API",
        "version": "2.0.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
