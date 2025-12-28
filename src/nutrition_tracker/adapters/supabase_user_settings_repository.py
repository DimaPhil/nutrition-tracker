"""Supabase repository for user settings."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from supabase import Client

from nutrition_tracker.services.user_settings import UserSettingsRepository


@dataclass
class SupabaseUserSettingsRepository(UserSettingsRepository):
    """Supabase implementation for user settings."""

    client: Client

    def get_timezone(self, user_id: UUID) -> str | None:
        """Return the stored timezone for a user."""
        response = (
            self.client.table("user_settings")
            .select("timezone")
            .eq("user_id", str(user_id))
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        return response.data[0].get("timezone")

    def set_timezone(self, user_id: UUID, timezone_name: str) -> None:
        """Update the user's timezone."""
        self.client.table("user_settings").update(
            {
                "timezone": timezone_name,
                "updated_at": datetime.now(tz=UTC).isoformat(),
            }
        ).eq("user_id", str(user_id)).execute()
