"""Supabase repository for meal logs."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from supabase import Client

from nutrition_tracker.domain.meals import MealItemSnapshot
from nutrition_tracker.domain.nutrition import MacroProfile
from nutrition_tracker.services.meals import MealLogRepository


@dataclass
class SupabaseMealLogRepository(MealLogRepository):
    """Supabase implementation for meal logs."""

    client: Client

    def create_meal_log(
        self, user_id: UUID, logged_at: datetime, totals: MacroProfile
    ) -> UUID:
        """Create a meal log row and return its id."""
        response = (
            self.client.table("meal_logs")
            .insert(
                {
                    "user_id": str(user_id),
                    "logged_at": logged_at.isoformat(),
                    "total_calories": totals.calories,
                    "total_protein_g": totals.protein_g,
                    "total_fat_g": totals.fat_g,
                    "total_carbs_g": totals.carbs_g,
                }
            )
            .execute()
        )
        if not response.data:
            raise RuntimeError("Failed to create meal log")
        return UUID(response.data[0]["id"])

    def create_meal_items(
        self, meal_log_id: UUID, items: list[MealItemSnapshot]
    ) -> None:
        """Create meal item rows."""
        payload = []
        for item in items:
            payload.append(
                {
                    "meal_log_id": str(meal_log_id),
                    "name_snapshot": item.name,
                    "nutrition_snapshot": {
                        "calories": item.calories,
                        "protein_g": item.protein_g,
                        "fat_g": item.fat_g,
                        "carbs_g": item.carbs_g,
                    },
                    "portion_grams": item.grams,
                    "item_calories": item.calories,
                    "item_protein_g": item.protein_g,
                    "item_fat_g": item.fat_g,
                    "item_carbs_g": item.carbs_g,
                }
            )
        if payload:
            self.client.table("meal_items").insert(payload).execute()
