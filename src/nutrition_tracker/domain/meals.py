"""Domain models for meal logging."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class MealItemSnapshot:
    """Snapshot of a meal item with macros."""

    name: str
    grams: float
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float


@dataclass(frozen=True)
class MealLogSummary:
    """Summary of a logged meal."""

    meal_id: UUID
    total_calories: float
    total_protein_g: float
    total_fat_g: float
    total_carbs_g: float
    items: list[MealItemSnapshot]
