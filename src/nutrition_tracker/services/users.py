"""User-related business logic."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from nutrition_tracker.domain.models import UserRecord


class UserRepository(Protocol):
    """Persistence interface for user data."""

    def get_by_telegram_id(self, telegram_user_id: int) -> UserRecord | None:
        """Return the user for a Telegram user id, if present."""

    def create_user(self, telegram_user_id: int) -> UserRecord:
        """Create and return a new user record."""

    def create_settings(self, user_id: UUID, timezone: str | None) -> None:
        """Create initial settings for a user."""

    def touch_last_active(self, user_id: UUID) -> None:
        """Update the last active timestamp for the user."""


@dataclass
class UserService:
    """Application service for user lifecycle actions."""

    repository: UserRepository

    def ensure_user(self, telegram_user_id: int) -> UserRecord:
        """Ensure a user exists for the Telegram id and return it."""
        existing = self.repository.get_by_telegram_id(telegram_user_id)
        if existing:
            self.repository.touch_last_active(existing.id)
            return existing

        created = self.repository.create_user(telegram_user_id)
        self.repository.create_settings(created.id, timezone=None)
        return created
