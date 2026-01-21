from __future__ import annotations

import logging
from typing import Optional



class PackageRenamingFilter(logging.Filter):
    """Filter to rename third-party package loggers to Siphon branding."""
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name.startswith("livekit"):
            record.name = record.name.replace("livekit", "siphon")
        return True

def configure_logging(level: int = logging.INFO, fmt: Optional[str] = None) -> None:
    """Configure root logging once.

    This function is safe to call multiple times; subsequent calls are no-ops
    if handlers already exist.
    """

    if logging.getLogger().handlers:
        # Logging already configured.
        return

    if fmt is None:
        fmt = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"

    # Create handler with renaming filter
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))
    handler.addFilter(PackageRenamingFilter())

    logging.basicConfig(level=level, handlers=[handler], force=True)

    # Also apply to existing handlers if any (just in case of reload/edge cases)
    # logic above prevents this block usually, but good for safety if refactored
    root_logger = logging.getLogger()
    for h in root_logger.handlers:
        # Avoid adding duplicate filters
        if not any(isinstance(f, PackageRenamingFilter) for f in h.filters):
            h.addFilter(PackageRenamingFilter())


def get_logger(name: str) -> logging.Logger:
    """Return a logger with sensible defaults configured.

    Ensures that basic logging configuration is applied once before
    returning the named logger.
    """

    configure_logging()
    return logging.getLogger(name)
