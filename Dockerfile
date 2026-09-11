# =============================================================================
# NurseLog AI — Dockerfile
# Assistant de documentation infirmière par IA — Belgium Edition
# =============================================================================

FROM python:3.11-slim AS base

# Éviter les warnings Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Variables de sécurité
ENV HOME=/app \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# =============================================================================
# Stage 1 : Installation des dépendances
# =============================================================================
FROM base AS builder

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Stage 2 : Image finale
# =============================================================================
FROM base AS production

# Utilisateur non-root (sécurité)
RUN groupadd -r nurselog && useradd -r -g nurselog nurselog

# Copier les dépendances du builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copier le code source
COPY src/ ./src/
COPY .streamlit/ ./.streamlit/
COPY README.md .

# Volume pour la base de données (persistance)
VOLUME ["/app/data"]

# Changer le propriétaire
RUN chown -R nurselog:nurselog /app

# Utilisateur non-root
USER nurselog

# Port Streamlit
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# Lancer Streamlit
ENTRYPOINT ["streamlit", "run", "src/app.py"]
CMD ["--server.headless=true", "--server.port=8501", "--server.address=0.0.0.0", "--browser.gatherUsageStats=false"]
