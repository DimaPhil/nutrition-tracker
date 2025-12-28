"""Supabase admin data access."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from supabase import Client

from nutrition_tracker.domain.admin import AdminUser
from nutrition_tracker.services.admin import AdminRepository


@dataclass
class SupabaseAdminRepository(AdminRepository):
    """Supabase implementation for admin queries."""

    client: Client

    def list_users(self) -> list[AdminUser]:
        """Return all users ordered by last activity."""
        response = (
            self.client.table("users")
            .select("id, telegram_user_id, last_active_at")
            .order("last_active_at", desc=True)
            .execute()
        )
        users = []
        for row in response.data or []:
            last_active = row.get("last_active_at")
            last_active_at = (
                datetime.fromisoformat(last_active)
                if isinstance(last_active, str) and last_active
                else None
            )
            users.append(
                AdminUser(
                    id=UUID(row["id"]),
                    telegram_user_id=row["telegram_user_id"],
                    last_active_at=last_active_at,
                )
            )
        return users

    def list_sessions(self, limit: int) -> list[dict[str, object]]:
        """Return recent photo sessions."""
        response = (
            self.client.table("photo_sessions")
            .select("id, user_id, status, updated_at, context_json")
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    def list_costs(self, limit: int) -> list[dict[str, object]]:
        """Return recent model usage entries."""
        response = (
            self.client.table("model_usage_daily")
            .select("day, user_id, model, requests, input_tokens, output_tokens")
            .order("day", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    def list_audit_events(self, user_id: UUID, limit: int) -> list[dict[str, object]]:
        """Return recent audit events for a user."""
        response = (
            self.client.table("audit_events")
            .select("*")
            .eq("user_id", str(user_id))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []
