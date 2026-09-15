# syntax=docker/dockerfile:1.7
# API FastAPI Trema Job Search — image de production (uv, sans dépendances de dev)
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PORT=8000 \
    LOCAL_STORAGE_DIR=/app/candidatures

WORKDIR /app

# curl pour le healthcheck ; polices Liberation / Carlito pour un rendu PDF (ReportLab) identique au poste de dev
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl fonts-liberation fonts-crosextra-carlito \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/

# Dépendances d'abord (calque mis en cache tant que pyproject/uv.lock ne changent pas)
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Code source de l'API
COPY apps/api/ ./
RUN mkdir -p /app/instance /app/candidatures /app/logs

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:${PORT}/health || exit 1

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
