"""Services for managing the user food library."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from nutrition_tracker.domain.library import LibraryFood


class LibraryRepository(Protocol):
    """Persistence interface for the user food library."""

    def create_food(self, user_id: UUID, payload: dict[str, object]) -> LibraryFood:
        """Create a food entry and return it."""

    def update_food(self, food_id: UUID, payload: dict[str, object]) -> LibraryFood:
        """Update a food entry and return it."""

    def get_food(self, food_id: UUID) -> LibraryFood | None:
        """Return a food entry by id, if present."""

    def search_foods(self, user_id: UUID, query: str, limit: int) -> list[LibraryFood]:
        """Search foods by name or alias."""

    def list_top_foods(self, user_id: UUID, limit: int) -> list[LibraryFood]:
        """Return top foods for a user by usage."""

    def add_alias(self, user_id: UUID, food_id: UUID, alias_text: str) -> None:
        """Add an alias for a food entry."""

    def increment_usage(self, food_id: UUID, used_at: datetime) -> None:
        """Increment usage counters for a food entry."""


@dataclass
class LibraryService:
    """Application service for library operations."""

    repository: LibraryRepository

    def create_manual_food(
        self, user_id: UUID, payload: dict[str, object]
    ) -> LibraryFood:
        """Create a manual food entry."""
        return self.repository.create_food(user_id, payload)

    def update_food(self, food_id: UUID, payload: dict[str, object]) -> LibraryFood:
        """Update an existing food entry."""
        return self.repository.update_food(food_id, payload)

    def add_alias(self, user_id: UUID, food_id: UUID, alias_text: str) -> None:
        """Add an alias for a food entry."""
        self.repository.add_alias(user_id, food_id, alias_text)

    def search(
        self, user_id: UUID, query: str | None, limit: int = 5
    ) -> list[LibraryFood]:
        """Search the library, falling back to top foods when query is empty."""
        if not query:
            return self._rank(self.repository.list_top_foods(user_id, limit))
        return self._rank(self.repository.search_foods(user_id, query, limit))

    def record_use(self, food_id: UUID) -> None:
        """Record that a food item has been used."""
        self.repository.increment_usage(food_id, used_at=datetime.now(tz=UTC))

    @staticmethod
    def _rank(items: list[LibraryFood]) -> list[LibraryFood]:
        """Rank foods by recent use then frequency."""
        return sorted(
            items,
            key=lambda item: (
                item.last_used_at or datetime.min.replace(tzinfo=UTC),
                item.use_count,
            ),
            reverse=True,
        )
