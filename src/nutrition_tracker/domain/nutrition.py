"""Nutrition domain models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MacroProfile:
    """Macronutrient profile for a food item."""

    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float


@dataclass(frozen=True)
class FoodSummary:
    """Summary information about a food from FDC."""

    fdc_id: int
    description: str
    brand_owner: str | None
    brand_name: str | None
    data_type: str | None


@dataclass(frozen=True)
class FoodDetails:
    """Full food details with macros."""

    summary: FoodSummary
    macros: MacroProfile
    serving_size_g: float | None
