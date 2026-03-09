"""
Structured JSON logging setup.

Provides a pre-configured logger that emits single-line JSON records,
suitable for ingestion by log aggregation services (Datadog, Loki, etc.).

Usage:
    from app.core.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Something happened")
"""

import json
import logging
import sys
from datetime import datetime, timezone


class _JSONFormatter(logging.Formatter):
    """Render log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_record: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


def get_logger(name: str) -> logging.Logger:
    """Return a JSON-formatted logger for the given module name."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger
