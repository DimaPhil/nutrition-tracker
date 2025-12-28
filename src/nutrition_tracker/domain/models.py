"""Domain models for the nutrition tracker."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class UserRecord:
    """Represents a user stored in the database."""

    id: UUID
    telegram_user_id: int
