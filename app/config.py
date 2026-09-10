import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration de base de l'application Flask."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-fallback-secret-key-change-in-production")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"
    PORT = int(os.getenv("PORT", "5001"))

    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

    # Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Notion
    NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")

    # Matching Thresholds
    MATCH_THRESHOLD_PRIORITY = int(os.getenv("MATCH_THRESHOLD_PRIORITY", "85"))
    MATCH_THRESHOLD_RECOMMENDED = int(os.getenv("MATCH_THRESHOLD_RECOMMENDED", "75"))
    MATCH_THRESHOLD_REVIEW = int(os.getenv("MATCH_THRESHOLD_REVIEW", "60"))
