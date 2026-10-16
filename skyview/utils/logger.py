"""Logging configuration."""

import json
import logging
import sys

from skyview.utils.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError) as exc:
            logging.getLogger(__name__).debug(
                "Standard output encoding unchanged: %s", type(exc).__name__
            )
    handler = logging.StreamHandler(sys.stdout)
    if settings.LOG_FORMAT.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(settings.LOG_FORMAT))
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        handlers=[handler],
    )

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "time": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            },
            ensure_ascii=False,
        )
