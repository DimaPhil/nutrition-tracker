"""Meal logging service."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from nutrition_tracker.domain.meals import MealItemSnapshot, MealLogSummary
from nutrition_tracker.domain.nutrition import MacroProfile
from nutrition_tracker.services.nutrition import NutritionService


class MealLogRepository(Protocol):
    """Persistence interface for meal logs."""

    def create_meal_log(
        self,
        user_id: UUID,
        logged_at: datetime,
        totals: MacroProfile,
    ) -> UUID:
        """Create a meal log and return its id."""

    def create_meal_items(
        self, meal_log_id: UUID, items: list[MealItemSnapshot]
    ) -> None:
        """Create meal item rows for a meal log."""


@dataclass
class MealLogService:
    """Service that computes macros and persists meal logs."""

    nutrition_service: NutritionService
    repository: MealLogRepository

    async def save_meal(
        self, user_id: UUID, items: list[dict[str, object]]
    ) -> MealLogSummary:
        """Compute macros for items and persist the meal log."""
        snapshots: list[MealItemSnapshot] = []
        total = MacroProfile(0.0, 0.0, 0.0, 0.0)

        for item in items:
            label = str(item.get("label", "item"))
            grams = float(item.get("grams", 0.0))
            macros = await _lookup_macros(self.nutrition_service, label, grams)
            snapshots.append(
                MealItemSnapshot(
                    name=label,
                    grams=grams,
                    calories=macros.calories,
                    protein_g=macros.protein_g,
                    fat_g=macros.fat_g,
                    carbs_g=macros.carbs_g,
                )
            )
            total = MacroProfile(
                calories=total.calories + macros.calories,
                protein_g=total.protein_g + macros.protein_g,
                fat_g=total.fat_g + macros.fat_g,
                carbs_g=total.carbs_g + macros.carbs_g,
            )

        meal_id = self.repository.create_meal_log(
            user_id=user_id,
            logged_at=datetime.now(tz=UTC),
            totals=total,
        )
        self.repository.create_meal_items(meal_id, snapshots)

        return MealLogSummary(
            meal_id=meal_id,
            total_calories=total.calories,
            total_protein_g=total.protein_g,
            total_fat_g=total.fat_g,
            total_carbs_g=total.carbs_g,
            items=snapshots,
        )


async def _lookup_macros(
    nutrition_service: NutritionService, label: str, grams: float
) -> MacroProfile:
    results = await nutrition_service.search(label, limit=1)
    if not results:
        return MacroProfile(0.0, 0.0, 0.0, 0.0)
    details = await nutrition_service.get_food(results[0].fdc_id)
    factor = grams / 100.0 if grams > 0 else 0.0
    return MacroProfile(
        calories=details.macros.calories * factor,
        protein_g=details.macros.protein_g * factor,
        fat_g=details.macros.fat_g * factor,
        carbs_g=details.macros.carbs_g * factor,
    )
