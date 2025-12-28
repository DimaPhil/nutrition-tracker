"""Logging configuration helpers."""

import logging


def configure_logging() -> None:
    """Configure application logging with a single stream handler."""
    logger = logging.getLogger("nutrition_tracker")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s: %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
