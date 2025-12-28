"""Domain models for photo sessions."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SessionRecord:
    """Represents a persisted photo session."""

    id: UUID
    user_id: UUID
    photo_id: UUID | None
    status: str
    context: dict[str, object]
