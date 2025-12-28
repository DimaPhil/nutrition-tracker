"""Tests for ASGI app module."""

from nutrition_tracker.api import asgi


def test_asgi_app_exists() -> None:
    assert asgi.app is not None
