"""Tests for container wiring."""

import asyncio

from nutrition_tracker.containers import build_container


def test_build_container_creates_services(settings) -> None:
    container = build_container(settings)
    assert container.session_service is not None
    asyncio.run(container.close_resources())
