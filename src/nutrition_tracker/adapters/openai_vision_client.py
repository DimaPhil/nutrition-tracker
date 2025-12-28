"""OpenAI Responses API client for vision extraction."""

import json
from dataclasses import dataclass

from openai import AsyncOpenAI

from nutrition_tracker.services.vision import VisionClient


@dataclass
class OpenAIVisionClient(VisionClient):
    """Vision client backed by OpenAI Responses API."""

    client: AsyncOpenAI

    @classmethod
    def create(cls, api_key: str) -> "OpenAIVisionClient":
        """Create an OpenAI vision client."""
        return cls(client=AsyncOpenAI(api_key=api_key))

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
        """Call OpenAI Responses API with structured outputs."""
        request_payload: dict[str, object] = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": image_data_url},
                    ],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "vision_extract",
                    "strict": True,
                    "schema": schema,
                }
            },
            "store": store,
        }
        if reasoning_effort:
            request_payload["reasoning"] = {"effort": reasoning_effort}

        response = await self.client.responses.create(**request_payload)
        output_text = response.output_text
        if not output_text:
            raise RuntimeError("OpenAI returned an empty response")
        return json.loads(output_text)
