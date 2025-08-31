release: alembic upgrade head
web: gunicorn -k uvicorn.workers.UvicornWorker app.app:app --bind 0.0.0.0:$PORT --log-file -
