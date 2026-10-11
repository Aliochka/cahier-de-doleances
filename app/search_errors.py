"""Translate cancelled SQL searches without losing the transaction rollback."""

from contextlib import contextmanager

from sqlalchemy.exc import DBAPIError


class SearchTimeout(Exception):
    """A database search exceeded its execution deadline."""


@contextmanager
def handle_search_errors(db):
    try:
        yield
    except DBAPIError as exc:
        db.rollback()
        if getattr(exc.orig, "pgcode", None) == "57014":
            raise SearchTimeout() from exc
        raise
