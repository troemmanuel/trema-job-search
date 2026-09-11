FROM python:3.11-slim

# Variables d'environnement système pour Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5001 \
    LOCAL_STORAGE_DIR=/app/candidatures

WORKDIR /app

# Installation de curl pour le HEALTHCHECK et dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python (mise en cache des calques Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copie du code source
COPY . .

# Création des dossiers de persistance
RUN mkdir -p /app/instance /app/candidatures

# Exposition du port Web
EXPOSE 5001

# Vérification d'état de l'application
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Démarrage du serveur Trema Job Search
CMD ["python", "run.py"]
