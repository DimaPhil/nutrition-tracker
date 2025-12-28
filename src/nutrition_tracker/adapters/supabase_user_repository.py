"""Supabase-backed user repository."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from supabase import Client

from nutrition_tracker.domain.models import UserRecord
from nutrition_tracker.services.users import UserRepository


@dataclass
class SupabaseUserRepository(UserRepository):
    """Supabase implementation for user persistence."""

    client: Client

    def get_by_telegram_id(self, telegram_user_id: int) -> UserRecord | None:
        """Return the user for a Telegram user id, if present."""
        response = (
            self.client.table("users")
            .select("id, telegram_user_id")
            .eq("telegram_user_id", telegram_user_id)
            .limit(1)
            .execute()
        )
        if response.data:
            row = response.data[0]
            return UserRecord(
                id=UUID(row["id"]),
                telegram_user_id=row["telegram_user_id"],
            )
        return None

    def create_user(self, telegram_user_id: int) -> UserRecord:
        """Create a new user row and return it."""
        response = (
            self.client.table("users")
            .insert({"telegram_user_id": telegram_user_id})
            .execute()
        )
        if not response.data:
            raise RuntimeError("Failed to create user in Supabase")
        row = response.data[0]
        return UserRecord(id=UUID(row["id"]), telegram_user_id=row["telegram_user_id"])

    def create_settings(self, user_id: UUID, timezone: str | None) -> None:
        """Create the default settings row for a user."""
        self.client.table("user_settings").insert(
            {"user_id": str(user_id), "timezone": timezone}
        ).execute()

    def touch_last_active(self, user_id: UUID) -> None:
        """Update the last_active_at timestamp for a user."""
        self.client.table("users").update(
            {"last_active_at": datetime.now(tz=UTC).isoformat()}
        ).eq("id", str(user_id)).execute()
