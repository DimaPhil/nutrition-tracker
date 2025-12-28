"""Supabase repository for audit events."""

from dataclasses import dataclass
from uuid import UUID

from supabase import Client

from nutrition_tracker.services.audit import AuditRepository


@dataclass
class SupabaseAuditRepository(AuditRepository):
    """Supabase-backed audit repository."""

    client: Client

    def create_event(  # noqa: PLR0913
        self,
        user_id: UUID,
        entity_type: str,
        entity_id: UUID,
        event_type: str,
        before: dict[str, object] | None,
        after: dict[str, object] | None,
    ) -> None:
        """Create an audit event row."""
        self.client.table("audit_events").insert(
            {
                "user_id": str(user_id),
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "event_type": event_type,
                "before_json": before,
                "after_json": after,
            }
        ).execute()
