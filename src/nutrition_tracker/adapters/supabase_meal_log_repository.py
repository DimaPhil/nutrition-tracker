"""Supabase repository for meal logs."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from supabase import Client

from nutrition_tracker.domain.meals import MealItemRecord, MealItemSnapshot
from nutrition_tracker.domain.nutrition import MacroProfile
from nutrition_tracker.domain.stats import MealLogRow
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
                    "food_id": str(item.food_id) if item.food_id else None,
                    "name_snapshot": item.name,
                    "nutrition_snapshot": item.nutrition_snapshot
                    or {
                        "calories": item.calories,
                        "protein_g": item.protein_g,
                        "fat_g": item.fat_g,
                        "carbs_g": item.carbs_g,
                        "basis": "per100g",
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

    def get_meal_log(self, meal_log_id: UUID) -> MealLogRow | None:
        """Return a meal log row by id."""
        response = (
            self.client.table("meal_logs")
            .select(
                "id, logged_at, total_calories, total_protein_g, total_fat_g, "
                "total_carbs_g"
            )
            .eq("id", str(meal_log_id))
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        row = response.data[0]
        logged_at = datetime.fromisoformat(row["logged_at"])
        return MealLogRow(
            meal_id=UUID(row["id"]),
            logged_at=logged_at,
            total_calories=float(row.get("total_calories", 0.0)),
            total_protein_g=float(row.get("total_protein_g", 0.0)),
            total_fat_g=float(row.get("total_fat_g", 0.0)),
            total_carbs_g=float(row.get("total_carbs_g", 0.0)),
        )

    def list_meal_items(self, meal_log_id: UUID) -> list[MealItemRecord]:
        """Return meal items for a meal log."""
        response = (
            self.client.table("meal_items")
            .select(
                "id, meal_log_id, food_id, name_snapshot, nutrition_snapshot, "
                "portion_grams, item_calories, item_protein_g, item_fat_g, item_carbs_g"
            )
            .eq("meal_log_id", str(meal_log_id))
            .order("id", desc=False)
            .execute()
        )
        return [_parse_item(row) for row in response.data or []]

    def get_meal_item(self, meal_item_id: UUID) -> MealItemRecord | None:
        """Return a meal item by id."""
        response = (
            self.client.table("meal_items")
            .select(
                "id, meal_log_id, food_id, name_snapshot, nutrition_snapshot, "
                "portion_grams, item_calories, item_protein_g, item_fat_g, item_carbs_g"
            )
            .eq("id", str(meal_item_id))
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        return _parse_item(response.data[0])

    def update_meal_item(
        self, meal_item_id: UUID, grams: float, macros: MacroProfile
    ) -> None:
        """Update a meal item row."""
        self.client.table("meal_items").update(
            {
                "portion_grams": grams,
                "item_calories": macros.calories,
                "item_protein_g": macros.protein_g,
                "item_fat_g": macros.fat_g,
                "item_carbs_g": macros.carbs_g,
            }
        ).eq("id", str(meal_item_id)).execute()

    def update_meal_log_totals(self, meal_log_id: UUID, totals: MacroProfile) -> None:
        """Update totals for a meal log."""
        self.client.table("meal_logs").update(
            {
                "total_calories": totals.calories,
                "total_protein_g": totals.protein_g,
                "total_fat_g": totals.fat_g,
                "total_carbs_g": totals.carbs_g,
            }
        ).eq("id", str(meal_log_id)).execute()


def _parse_item(row: dict[str, object]) -> MealItemRecord:
    return MealItemRecord(
        id=UUID(row["id"]),
        meal_log_id=UUID(row["meal_log_id"]),
        food_id=UUID(row["food_id"]) if row.get("food_id") else None,
        name=str(row.get("name_snapshot", "")),
        grams=float(row.get("portion_grams", 0.0)),
        calories=float(row.get("item_calories", 0.0)),
        protein_g=float(row.get("item_protein_g", 0.0)),
        fat_g=float(row.get("item_fat_g", 0.0)),
        carbs_g=float(row.get("item_carbs_g", 0.0)),
        nutrition_snapshot=row.get("nutrition_snapshot") or {},
    )
