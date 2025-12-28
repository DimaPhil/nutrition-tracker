"""Vision extraction service using LLMs."""

import base64
from dataclasses import dataclass
from typing import Protocol

from nutrition_tracker.domain.vision import VisionExtract


class VisionClient(Protocol):
    """Interface for LLM vision extraction."""

    async def extract(  # noqa: PLR0913
        self,
        *,
        model: str,
        reasoning_effort: str | None,
        store: bool,
        image_data_url: str,
        schema: dict[str, object],
        prompt: str,
    ) -> dict[str, object]:
        """Return structured vision extraction data."""


@dataclass
class VisionService:
    """Service that prepares vision prompts and validates results."""

    client: VisionClient
    model: str
    reasoning_effort: str | None
    store: bool

    async def extract(self, image_bytes: bytes) -> VisionExtract:
        """Extract food items from an image via the configured client."""
        data_url = _to_data_url(image_bytes)
        schema = VisionExtract.model_json_schema()
        prompt = (
            "Identify food items in the image. "
            "Return each item with a short label, confidence (0-1), "
            "and a rough estimated grams range if visible."
        )
        raw = await self.client.extract(
            model=self.model,
            reasoning_effort=self.reasoning_effort,
            store=self.store,
            image_data_url=data_url,
            schema=schema,
            prompt=prompt,
        )
        return VisionExtract.model_validate(raw)


def _to_data_url(image_bytes: bytes) -> str:
    """Convert bytes to a base64 data URL for image input."""
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"
