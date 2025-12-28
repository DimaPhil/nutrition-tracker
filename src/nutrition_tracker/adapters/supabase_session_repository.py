"""Supabase-backed session repository."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from supabase import Client

from nutrition_tracker.domain.sessions import SessionRecord
from nutrition_tracker.services.sessions import SessionRepository

_ACTIVE_STATUSES = {
    "AWAITING_CONFIRMATION",
    "AWAITING_ITEM_NAME",
    "AWAITING_ITEM_WEIGHT",
}


@dataclass
class SupabaseSessionRepository(SessionRepository):
    """Supabase implementation for photo sessions."""

    client: Client

    def create_session(
        self, user_id: UUID, photo_id: UUID, status: str, context: dict[str, object]
    ) -> SessionRecord:
        """Create a session row and return it."""
        response = (
            self.client.table("photo_sessions")
            .insert(
                {
                    "user_id": str(user_id),
                    "photo_id": str(photo_id),
                    "status": status,
                    "context_json": context,
                }
            )
            .execute()
        )
        if not response.data:
            raise RuntimeError("Failed to create session")
        row = response.data[0]
        return SessionRecord(
            id=UUID(row["id"]),
            user_id=UUID(row["user_id"]),
            photo_id=UUID(row["photo_id"]) if row.get("photo_id") else None,
            status=row["status"],
            context=row["context_json"],
        )

    def get_session(self, session_id: UUID) -> SessionRecord | None:
        """Return a session by id, if present."""
        response = (
            self.client.table("photo_sessions")
            .select("id, user_id, photo_id, status, context_json")
            .eq("id", str(session_id))
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        row = response.data[0]
        return SessionRecord(
            id=UUID(row["id"]),
            user_id=UUID(row["user_id"]),
            photo_id=UUID(row["photo_id"]) if row.get("photo_id") else None,
            status=row["status"],
            context=row["context_json"],
        )

    def get_active_session(self, user_id: UUID) -> SessionRecord | None:
        """Return the most recent active session for a user."""
        response = (
            self.client.table("photo_sessions")
            .select("id, user_id, photo_id, status, context_json")
            .eq("user_id", str(user_id))
            .in_("status", list(_ACTIVE_STATUSES))
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        row = response.data[0]
        return SessionRecord(
            id=UUID(row["id"]),
            user_id=UUID(row["user_id"]),
            photo_id=UUID(row["photo_id"]) if row.get("photo_id") else None,
            status=row["status"],
            context=row["context_json"],
        )

    def update_session(
        self, session_id: UUID, status: str, context: dict[str, object]
    ) -> None:
        """Update session status and context."""
        self.client.table("photo_sessions").update(
            {
                "status": status,
                "context_json": context,
                "updated_at": datetime.now(tz=UTC).isoformat(),
            }
        ).eq("id", str(session_id)).execute()
