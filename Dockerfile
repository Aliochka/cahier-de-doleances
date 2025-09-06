# Utilisation d'une image Python avec les dépendances Playwright
FROM mcr.microsoft.com/playwright/python:v1.50.0-focal

# Configuration des variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Création d'un utilisateur non-root pour la sécurité
RUN useradd --create-home --shell /bin/bash app
WORKDIR /home/app

# Installation des dépendances système
RUN apt-get update && apt-get install -y \
    # Dépendances pour psycopg2
    libpq-dev \
    # Outils de build
    gcc \
    g++ \
    # Nettoyage des packages temporaires
    && rm -rf /var/lib/apt/lists/*

# Copie des requirements et installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Installation des navigateurs Playwright (déjà inclus dans l'image de base)
RUN playwright install chromium

# Copie du code de l'application
COPY --chown=app:app . .

# Configuration des permissions et du cache OG
RUN mkdir -p /home/app/og_cache && \
    chown -R app:app /home/app/og_cache && \
    chmod 755 /home/app/og_cache

# Configuration des variables d'environnement pour la production
ENV OG_CACHE_DIR=/home/app/og_cache \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Basculement vers l'utilisateur non-root
USER app

# Exposition du port
EXPOSE 8000

# Commande de démarrage
CMD ["gunicorn", "app.app:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]