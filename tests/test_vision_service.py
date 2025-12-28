"""Tests for vision service."""

import asyncio

from nutrition_tracker.services.vision import VisionService
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
