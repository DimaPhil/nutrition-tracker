"""Tests for vision service."""

import asyncio

from nutrition_tracker.services.vision import VisionService, _to_data_url
from tests.conftest import FakeVisionClient


def test_vision_service_returns_structured_items() -> None:
    service = VisionService(
        client=FakeVisionClient(),
        model="gpt-5.2",
        reasoning_effort="high",
        store=False,
    )

    result = asyncio.run(service.extract(b"image-bytes"))

    assert result.items
    assert result.items[0].label == "rice"


def test_to_data_url_uses_png_header() -> None:
    data = b"\x89PNG\r\n\x1a\n" + b"rest"
    url = _to_data_url(data)

    assert url.startswith("data:image/png;base64,")


def test_to_data_url_defaults_to_jpeg() -> None:
    data = b"unknown"
    url = _to_data_url(data)

    assert url.startswith("data:image/jpeg;base64,")
