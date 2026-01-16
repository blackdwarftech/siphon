from __future__ import annotations

import logging
from typing import Optional


def configure_logging(level: int = logging.INFO, fmt: Optional[str] = None) -> None:
    """Configure root logging once.

    This function is safe to call multiple times; subsequent calls are no-ops
    if handlers already exist.
    """

    if logging.getLogger().handlers:
        # Logging already configured by the application.
        return

    if fmt is None:
        fmt = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"

    logging.basicConfig(level=level, format=fmt)


def get_logger(name: str) -> logging.Logger:
    """Return a logger with sensible defaults configured.

    Ensures that basic logging configuration is applied once before
    returning the named logger.
    """

    configure_logging()
    return logging.getLogger(name)
