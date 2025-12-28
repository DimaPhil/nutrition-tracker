"""Supabase-backed session repository."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from supabase import Client

from nutrition_tracker.domain.sessions import SessionRecord
from nutrition_tracker.services.sessions import SessionRepository

_ACTIVE_STATUSES = {
    "AWAITING_CONFIRMATION",
    "AWAITING_ITEM_LIST",
    "AWAITING_ITEM_CONFIRMATION",
    "AWAITING_ITEM_SELECTION",
    "AWAITING_MANUAL_NAME",
    "AWAITING_MANUAL_STORE",
    "AWAITING_MANUAL_BASIS",
    "AWAITING_MANUAL_SERVING",
    "AWAITING_MANUAL_MACROS",
    "AWAITING_PORTION_CHOICE",
    "AWAITING_MANUAL_GRAMS",
    "AWAITING_SAVE",
    "AWAITING_EDIT_CHOICE",
    "AWAITING_EDIT_GRAMS",
    "EDIT_SELECT_ITEM",
    "EDIT_ENTER_GRAMS",
}


@dataclass
class SupabaseSessionRepository(SessionRepository):
    """Supabase implementation for photo sessions."""

    client: Client

    def create_session(
        self,
        user_id: UUID,
        photo_id: UUID | None,
        status: str,
        context: dict[str, object],
    ) -> SessionRecord:
        """Create a session row and return it."""
        response = (
            self.client.table("photo_sessions")
            .insert(
                {
                    "user_id": str(user_id),
                    "photo_id": str(photo_id) if photo_id else None,
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
