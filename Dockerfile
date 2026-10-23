FROM python:3.11.17-slim-bookworm@sha256:f06d01d4ba3f8ad5af45a3ec87df19c1d317d8e8961edc0fabda61811af6f7cf AS python-base

FROM python-base AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy
WORKDIR /build
COPY pyproject.toml uv.lock .python-version ./
COPY rag/pyproject.toml rag/README.md ./rag/
COPY rag/src/ ./rag/src/
ARG SEARCH_RUNTIME=disabled
RUN case "$SEARCH_RUNTIME" in \
      disabled) uv sync --locked --no-default-groups --no-install-project --no-cache ;; \
      cpu) uv sync --locked --no-default-groups --group search --no-install-project --no-cache \
        && /opt/venv/bin/python -c "import torch; assert torch.version.cuda is None" ;; \
      *) exit 1 ;; \
    esac

FROM python-base AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HOME=/tmp/huggingface \
    PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home --shell /bin/bash app
WORKDIR /home/app
COPY --from=dependencies /opt/venv /opt/venv
COPY --from=dependencies --chown=app:app /build/rag /build/rag
COPY --chown=app:app app ./app
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app alembic.ini .
COPY --chown=app:app scripts/benchmark_public_search.py ./scripts/benchmark_public_search.py
USER app
ARG SEARCH_RUNTIME=disabled
# Validate the final image, including current application and H1 sources.
# This check is offline and never loads the BGE snapshot or connects to a DB.
RUN if [ "$SEARCH_RUNTIME" = cpu ]; then python -m app.search_packaging; fi
EXPOSE 8000
CMD ["gunicorn", "app.app:app", "-w", "1", "-k", "uvicorn_worker.UvicornWorker", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-", "--worker-tmp-dir", "/tmp"]
