import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration de base de l'application Flask."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-fallback-secret-key-change-in-production")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"
    PORT = int(os.getenv("PORT", "8000"))
    # Origines autorisées (CORS) pour le frontend Next.js, séparées par des virgules
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]

    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

    # Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    # Groq
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    # Mistral
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
    MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "ministral-8b-latest")

    # OpenRouter
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct")

    # Notion
    NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")

    # Matching Thresholds
    MATCH_THRESHOLD_PRIORITY = int(os.getenv("MATCH_THRESHOLD_PRIORITY", "85"))
    MATCH_THRESHOLD_RECOMMENDED = int(os.getenv("MATCH_THRESHOLD_RECOMMENDED", "75"))
    MATCH_THRESHOLD_REVIEW = int(os.getenv("MATCH_THRESHOLD_REVIEW", "60"))

    # Scheduler / Cron Quotidien
    CRON_SCHEDULE_TIME = os.getenv("CRON_SCHEDULE_TIME", "08:00")
    ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "1") == "1"

    # Stockage local des dossiers de candidature (PDFs)
    LOCAL_STORAGE_DIR = os.getenv("LOCAL_STORAGE_DIR", "/Users/trema/Documents/RECHERCHE EMPLOIE/CANDIDATURES")
