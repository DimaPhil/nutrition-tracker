"""User settings service."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class UserSettingsRepository(Protocol):
    """Persistence interface for user settings."""

    def get_timezone(self, user_id: UUID) -> str | None:
        """Return the user's timezone if set."""

    def set_timezone(self, user_id: UUID, timezone: str) -> None:
        """Update the user's timezone."""


@dataclass
class UserSettingsService:
    """Service for user settings."""

    repository: UserSettingsRepository

    def get_timezone(self, user_id: UUID) -> str:
        """Return the user timezone or UTC if unset."""
        return self.repository.get_timezone(user_id) or "UTC"

    def set_timezone(self, user_id: UUID, timezone: str) -> None:
        """Persist a user's timezone."""
        self.repository.set_timezone(user_id, timezone)

    def is_timezone_set(self, user_id: UUID) -> bool:
        """Return True when the user's timezone is configured."""
        return self.repository.get_timezone(user_id) is not None
