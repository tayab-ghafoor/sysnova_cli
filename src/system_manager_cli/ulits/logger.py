from __future__ import annotations

import logging
from datetime import datetime

import os

_CONFIGURED = set()


def get_logger(name: str, log_file: str | None = None) -> logging.Logger:
    """Return a reusable project logger with console and file handlers."""
    from ..config.config import Config
    Config.ensure_directories()

    logger = logging.getLogger(name)
    if name in _CONFIGURED:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    console_handler = logging.StreamHandler()
    console_level = logging.ERROR if os.getenv("SYSTEM_MANAGER_CLI_QUIET_LOGS") == "1" else logging.INFO
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)

    file_name = log_file or f"system_manager_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(Config.LOGS_DIR / file_name, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    _CONFIGURED.add(name)
    return logger


# FIX: Provide a module-level `logger` so that
#      `from ...ulits.logger import logger` works in legacy callers
#      (core/Packager.py, Providers/rclone_provider.py, etc.)
logger = get_logger(__name__)
