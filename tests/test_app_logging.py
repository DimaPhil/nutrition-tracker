"""Tests for logging configuration."""

import logging

from nutrition_tracker.app_logging import configure_logging


def test_configure_logging_idempotent() -> None:
    logger = logging.getLogger("nutrition_tracker")
    logger.handlers.clear()

    configure_logging()
    first_count = len(logger.handlers)

    configure_logging()
    second_count = len(logger.handlers)

    assert first_count == 1
    assert second_count == 1
