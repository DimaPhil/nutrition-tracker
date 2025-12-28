"""Models for vision extraction results."""

from pydantic import BaseModel, Field


class VisionItem(BaseModel):
    """Single detected food item from vision."""

    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    estimated_grams_low: int | None = Field(default=None, ge=0)
    estimated_grams_high: int | None = Field(default=None, ge=0)
    notes: str | None = None


class VisionExtract(BaseModel):
    """Structured output for vision extraction."""

    items: list[VisionItem]
