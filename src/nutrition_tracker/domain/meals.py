"""Domain models for meal logging."""

from dataclasses import dataclass
from datetime import datetime
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
    food_id: UUID | None = None
    nutrition_snapshot: dict[str, object] | None = None


@dataclass(frozen=True)
class MealLogSummary:
    """Summary of a logged or previewed meal."""

    meal_id: UUID | None
    total_calories: float
    total_protein_g: float
    total_fat_g: float
    total_carbs_g: float
    items: list[MealItemSnapshot]


@dataclass(frozen=True)
class MealItemRecord:
    """Meal item row with identifiers."""

    id: UUID
    meal_log_id: UUID
    food_id: UUID | None
    name: str
    grams: float
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    nutrition_snapshot: dict[str, object]


@dataclass(frozen=True)
class MealLogDetail:
    """Meal log with items."""

    id: UUID
    logged_at: datetime
    total_calories: float
    total_protein_g: float
    total_fat_g: float
    total_carbs_g: float
    items: list[MealItemRecord]
