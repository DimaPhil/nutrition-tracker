"""Vision extraction service using LLMs."""

import base64
from dataclasses import dataclass
from typing import Protocol

from nutrition_tracker.domain.vision import VisionExtract

VISION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "estimated_grams_low": {
                        "anyOf": [{"type": "integer", "minimum": 0}, {"type": "null"}]
                    },
                    "estimated_grams_high": {
                        "anyOf": [{"type": "integer", "minimum": 0}, {"type": "null"}]
                    },
                    "notes": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                },
                "required": [
                    "label",
                    "confidence",
                    "estimated_grams_low",
                    "estimated_grams_high",
                    "notes",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


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
            schema=VISION_SCHEMA,
            prompt=prompt,
        )
        return VisionExtract.model_validate(raw)


def _to_data_url(image_bytes: bytes) -> str:
    """Convert bytes to a base64 data URL for image input."""
    mime_type = _detect_mime_type(image_bytes)
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _detect_mime_type(image_bytes: bytes) -> str:
    """Infer a basic image MIME type from file signatures."""
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"
