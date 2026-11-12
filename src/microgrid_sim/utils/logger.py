"""Structured logging utility for microgrid_sim.

Provides consistent, timestamped, formatted logging across all simulation,
physics, controller, and environment modules.
"""

import logging
import sys
from typing import Optional


def get_logger(name: str, level: int = logging.INFO, log_file: Optional[str] = None) -> logging.Logger:
    """Configure and return a structured logger instance.

    Args:
        name: Name of the logger (typically __name__ of the calling module).
        level: Logging verbosity level (default: logging.INFO).
        log_file: Optional path to write log output to disk.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    # Format: 2026-11-12 16:15:00 [INFO] [microgrid.physics.battery] Battery SoC initialized to 0.50
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Optional File Handler
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
