FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --shell /bin/bash app
WORKDIR /home/app
COPY requirements.txt .
RUN pip install --upgrade pip==26.2.1 setuptools==84.0.0 && pip install -r requirements.txt
COPY --chown=app:app app ./app
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app alembic.ini .
USER app
EXPOSE 8000
CMD ["gunicorn", "app.app:app", "-w", "2", "-k", "uvicorn_worker.UvicornWorker", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-", "--worker-tmp-dir", "/tmp"]
