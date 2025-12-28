"""Supabase repository for meal log statistics."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from supabase import Client

from nutrition_tracker.domain.stats import MealLogRow
from nutrition_tracker.services.stats import StatsRepository


@dataclass
class SupabaseStatsRepository(StatsRepository):
    """Supabase implementation for stats queries."""

    client: Client

    def list_meal_logs(
        self, user_id: UUID, start: datetime, end: datetime
    ) -> list[MealLogRow]:
        """Return meal logs in the time range."""
        response = (
            self.client.table("meal_logs")
            .select(
                "logged_at, total_calories, total_protein_g, total_fat_g, total_carbs_g"
            )
            .eq("user_id", str(user_id))
            .gte("logged_at", start.isoformat())
            .lt("logged_at", end.isoformat())
            .order("logged_at", desc=False)
            .execute()
        )
        return [_parse_row(row) for row in response.data or []]

    def list_recent_meal_logs(self, user_id: UUID, limit: int) -> list[MealLogRow]:
        """Return recent meal logs for a user."""
        response = (
            self.client.table("meal_logs")
            .select(
                "logged_at, total_calories, total_protein_g, total_fat_g, total_carbs_g"
            )
            .eq("user_id", str(user_id))
            .order("logged_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [_parse_row(row) for row in response.data or []]


def _parse_row(row: dict[str, object]) -> MealLogRow:
    logged_at_raw = row.get("logged_at")
    logged_at = (
        datetime.fromisoformat(logged_at_raw)
        if isinstance(logged_at_raw, str) and logged_at_raw
        else datetime.min
    )
    return MealLogRow(
        logged_at=logged_at,
        total_calories=float(row.get("total_calories", 0.0)),
        total_protein_g=float(row.get("total_protein_g", 0.0)),
        total_fat_g=float(row.get("total_fat_g", 0.0)),
        total_carbs_g=float(row.get("total_carbs_g", 0.0)),
    )
