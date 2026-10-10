"""Readiness check: no migrations, schema repair or expensive data counts."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import engine

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/healthz", include_in_schema=False)
def healthz():
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '2000'"))
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("Database readiness check failed")
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "ok"}
