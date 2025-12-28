"""Audit logging service."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class AuditRepository(Protocol):
    """Persistence interface for audit events."""

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


@dataclass
class AuditService:
    """Service for recording audit events."""

    repository: AuditRepository

    def record_event(  # noqa: PLR0913
        self,
        user_id: UUID,
        entity_type: str,
        entity_id: UUID,
        event_type: str,
        before: dict[str, object] | None,
        after: dict[str, object] | None,
    ) -> None:
        """Persist an audit event."""
        self.repository.create_event(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            event_type=event_type,
            before=before,
            after=after,
        )
