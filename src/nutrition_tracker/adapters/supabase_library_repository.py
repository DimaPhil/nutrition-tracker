"""Supabase implementation for the user food library."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from supabase import Client

from nutrition_tracker.domain.library import LibraryFood
from nutrition_tracker.services.library import LibraryRepository


@dataclass
class SupabaseLibraryRepository(LibraryRepository):
    """Supabase-backed repository for user food libraries."""

    client: Client

    def create_food(self, user_id: UUID, payload: dict[str, object]) -> LibraryFood:
        """Create a food entry and return it."""
        response = (
            self.client.table("foods_user_library")
            .insert({"user_id": str(user_id), **payload})
            .execute()
        )
        if not response.data:
            raise RuntimeError("Failed to create food entry")
        return _parse_food(response.data[0])

    def update_food(self, food_id: UUID, payload: dict[str, object]) -> LibraryFood:
        """Update a food entry and return it."""
        response = (
            self.client.table("foods_user_library")
            .update(payload)
            .eq("id", str(food_id))
            .execute()
        )
        if not response.data:
            raise RuntimeError("Failed to update food entry")
        return _parse_food(response.data[0])

    def get_food(self, food_id: UUID) -> LibraryFood | None:
        """Return a food entry by id, if present."""
        response = (
            self.client.table("foods_user_library")
            .select("*")
            .eq("id", str(food_id))
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        return _parse_food(response.data[0])

    def search_foods(self, user_id: UUID, query: str, limit: int) -> list[LibraryFood]:
        """Search foods by name and aliases."""
        pattern = f"%{query}%"
        foods_response = (
            self.client.table("foods_user_library")
            .select("*")
            .eq("user_id", str(user_id))
            .ilike("name", pattern)
            .limit(limit)
            .execute()
        )
        foods = [_parse_food(row) for row in foods_response.data or []]

        alias_response = (
            self.client.table("food_aliases")
            .select("food_id")
            .eq("user_id", str(user_id))
            .ilike("alias_text", pattern)
            .execute()
        )
        alias_ids = {row["food_id"] for row in alias_response.data or []}
        if alias_ids:
            alias_foods_response = (
                self.client.table("foods_user_library")
                .select("*")
                .in_("id", list(alias_ids))
                .execute()
            )
            foods.extend(_parse_food(row) for row in alias_foods_response.data or [])

        return foods[:limit]

    def list_top_foods(self, user_id: UUID, limit: int) -> list[LibraryFood]:
        """Return top foods for a user by usage."""
        response = (
            self.client.table("foods_user_library")
            .select("*")
            .eq("user_id", str(user_id))
            .order("last_used_at", desc=True)
            .order("use_count", desc=True)
            .limit(limit)
            .execute()
        )
        return [_parse_food(row) for row in response.data or []]

    def add_alias(self, user_id: UUID, food_id: UUID, alias_text: str) -> None:
        """Add an alias for a food entry."""
        self.client.table("food_aliases").insert(
            {
                "user_id": str(user_id),
                "food_id": str(food_id),
                "alias_text": alias_text,
            }
        ).execute()

    def increment_usage(self, food_id: UUID, used_at: datetime) -> None:
        """Increment usage counters for a food entry."""
        response = (
            self.client.table("foods_user_library")
            .select("use_count")
            .eq("id", str(food_id))
            .limit(1)
            .execute()
        )
        current = 0
        if response.data:
            current = int(response.data[0].get("use_count", 0))
        self.client.table("foods_user_library").update(
            {
                "use_count": current + 1,
                "last_used_at": used_at.isoformat(),
            }
        ).eq("id", str(food_id)).execute()


def _parse_food(row: dict[str, object]) -> LibraryFood:
    """Parse a library food row into a domain model."""
    last_used_raw = row.get("last_used_at")
    last_used_at = (
        datetime.fromisoformat(last_used_raw)
        if isinstance(last_used_raw, str) and last_used_raw
        else None
    )
    return LibraryFood(
        id=UUID(row["id"]),
        user_id=UUID(row["user_id"]),
        name=str(row.get("name", "")),
        brand=row.get("brand"),
        store=row.get("store"),
        source_type=str(row.get("source_type", "")),
        source_ref=row.get("source_ref"),
        basis=str(row.get("basis", "")),
        serving_size_g=row.get("serving_size_g"),
        calories=float(row.get("calories", 0.0)),
        protein_g=float(row.get("protein_g", 0.0)),
        fat_g=float(row.get("fat_g", 0.0)),
        carbs_g=float(row.get("carbs_g", 0.0)),
        use_count=int(row.get("use_count", 0)),
        last_used_at=last_used_at,
    )
