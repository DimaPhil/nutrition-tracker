"""Domain models for statistics."""

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True)
class MealLogRow:
    """Summary data for a logged meal."""

    meal_id: UUID
    logged_at: datetime
    total_calories: float
    total_protein_g: float
    total_fat_g: float
    total_carbs_g: float


@dataclass(frozen=True)
class DailyTotals:
    """Daily total macros."""

    day: date
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
