"""Keep bearer credentials in magic-link paths out of access logs."""

import logging
import re

_MAGIC_PATH = re.compile(r"/auth/verify/[^\s?\"']+")
_SEARCH_QUERY = re.compile(r"(/api/v1/search)\?[^\s\"']*")


class RedactMagicLinkFilter(logging.Filter):
    def filter(self, record):
        def redact(value):
            return (
                _SEARCH_QUERY.sub(
                    r"\1?[REDACTED]", _MAGIC_PATH.sub("/auth/verify/[REDACTED]", value)
                )
                if isinstance(value, str)
                else value
            )

        record.msg = redact(record.msg)
        if isinstance(record.args, dict):
            record.args = {key: redact(value) for key, value in record.args.items()}
        elif isinstance(record.args, tuple):
            record.args = tuple(redact(value) for value in record.args)
        return True


def redact_access_logs():
    for name in ("uvicorn.access", "gunicorn.access"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactMagicLinkFilter) for f in logger.filters):
            logger.addFilter(RedactMagicLinkFilter())
