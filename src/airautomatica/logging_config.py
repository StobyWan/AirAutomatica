"""Minimal logging configuration."""

import logging
import os
import sys


def setup_logging(level: int | None = None, force: bool = False) -> None:
    """Configure root logger with sensible defaults.
    Use force=True to override uvicorn's logging config (e.g. in app startup).
    Set LOG_LEVEL=DEBUG in env for parse diagnostics (Ollama raw response, list-field normalization).
    """
    if level is None:
        level = getattr(
            logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO
        )
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=force,
    )
    # Reduce noise from third-party libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
