import os
import sys
import time
import logging
from logging.handlers import RotatingFileHandler
from flask import request, g

class ColoredFormatter(logging.Formatter):
    """Formateur de logs avec coloration ANSI pour la console."""

    GREY = "\x1b[38;20m"
    CYAN = "\x1b[36;20m"
    GREEN = "\x1b[32;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"

    FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    COLORS = {
        logging.DEBUG: GREY,
        logging.INFO: CYAN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD_RED,
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        formatter = logging.Formatter(
            f"{color}%(asctime)s{self.RESET} [{color}%(levelname)-7s{self.RESET}] [{self.CYAN}%(name)s{self.RESET}] %(message)s",
            datefmt=self.DATE_FORMAT
        )
        return formatter.format(record)

def setup_logging(app=None, log_level: str = None):
    """Configure le système de logging pour toute l'application (Console + Fichier logs/app.log)."""
    level_name = log_level or os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Évite les handlers dupliqués
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        # 1. Console Handler (avec couleurs)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(ColoredFormatter())
        root_logger.addHandler(console_handler)

    # 2. File Handler rotatif (logs/app.log)
    try:
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "app.log")

        if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=5 * 1024 * 1024,  # 5 Mo par fichier
                backupCount=3,
                encoding="utf-8"
            )
            file_handler.setLevel(numeric_level)
            file_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)-7s] [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
    except Exception as e:
        sys.stderr.write(f"Impossible d'initialiser le fichier de log logs/app.log: {e}\n")

    # Réduire le bruit des bibliothèques externes tierces
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.INFO)

    # Si Flask app est fourni, enregistrer le traçage des requêtes HTTP
    if app:
        @app.before_request
        def log_request_start():
            g.request_start_time = time.time()
            # Ignorer les assets statiques pour ne pas polluer les logs
            if not request.path.startswith("/static"):
                logging.getLogger("app.http").info(f"➡️  {request.method} {request.path}")

        @app.after_request
        def log_request_end(response):
            if not request.path.startswith("/static"):
                start_time = getattr(g, "request_start_time", None)
                duration_ms = round((time.time() - start_time) * 1000, 1) if start_time else 0.0
                status_code = response.status_code
                level = logging.INFO if status_code < 400 else (logging.WARNING if status_code < 500 else logging.ERROR)
                logging.getLogger("app.http").log(
                    level,
                    f"⬅️  {request.method} {request.path} → {status_code} ({duration_ms}ms)"
                )
            return response

    return root_logger
