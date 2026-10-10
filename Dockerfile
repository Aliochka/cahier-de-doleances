FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --shell /bin/bash app
WORKDIR /home/app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY --chown=app:app . .
USER app
EXPOSE 8000
CMD ["gunicorn", "app.app:app", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
