"""Logging utilities for MCP DevBench."""

import logging
import sys

from pythonjsonlogger import jsonlogger


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """
    Setup structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type (json or text)
    """
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level.upper()))

    # Set formatter based on format type
    if log_format.lower() == "json":
        formatter = jsonlogger.JsonFormatter(
            "%(timestamp)s %(level)s %(name)s %(message)s",
            rename_fields={"levelname": "level", "asctime": "timestamp"},
            timestamp=True,
        )
    else:
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    handler.setFormatter(formatter)
    logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.

    Args:
        name: Name for the logger (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
