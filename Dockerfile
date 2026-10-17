FROM python:3.11-slim-bookworm AS python-base

FROM python-base AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy
WORKDIR /build
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project --no-cache

FROM python-base AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home --shell /bin/bash app
WORKDIR /home/app
COPY --from=dependencies /opt/venv /opt/venv
COPY --chown=app:app app ./app
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app alembic.ini .
USER app
EXPOSE 8000
CMD ["gunicorn", "app.app:app", "-w", "2", "-k", "uvicorn_worker.UvicornWorker", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-", "--worker-tmp-dir", "/tmp"]
