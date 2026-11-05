"""
Rotating file + console logger configuration, shared across the whole backend.
Import `get_logger(__name__)` from any module instead of using print().
"""

import logging
from logging.handlers import RotatingFileHandler

from app.config import settings

_CONFIGURED = False


def _configure_root_logger() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL.upper())

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        filename=str(settings.log_path),
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Returns a module-scoped logger, configuring the root logger on first call."""
    _configure_root_logger()
    return logging.getLogger(name)
