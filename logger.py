"""
logger.py — Centralized, colorized logging for the YouTube Shorts Agent.
"""

import logging
import sys
from pathlib import Path
import colorlog
import config

LOG_FILE = config.LOGS_DIR / "agent.log"
config.LOGS_DIR.mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    """Return a consistently formatted logger for any module."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # avoid duplicate handlers on re-import

    logger.setLevel(logging.DEBUG)

    # ── Console handler (colorized) ───────────────────────────────────────────
    console = colorlog.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s[%(asctime)s] %(name)s — %(levelname)s%(reset)s: %(message)s",
        datefmt="%H:%M:%S",
        log_colors={
            "DEBUG":    "cyan",
            "INFO":     "green",
            "WARNING":  "yellow",
            "ERROR":    "red",
            "CRITICAL": "bold_red",
        }
    ))

    # ── File handler (plain text) ─────────────────────────────────────────────
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(name)s — %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger
