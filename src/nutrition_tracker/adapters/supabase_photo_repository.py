"""Supabase-backed photo repository."""

from dataclasses import dataclass
from uuid import UUID

from supabase import Client

from nutrition_tracker.services.sessions import PhotoRepository


@dataclass
class SupabasePhotoRepository(PhotoRepository):
    """Supabase implementation for photo metadata persistence."""

    client: Client

    def create_photo(
        self,
        user_id: UUID,
        telegram_chat_id: int,
        telegram_message_id: int,
        telegram_file_id: str,
        telegram_file_unique_id: str | None,
    ) -> UUID:
        """Create a photo metadata row and return its id."""
        response = (
            self.client.table("photos")
            .insert(
                {
                    "user_id": str(user_id),
                    "telegram_chat_id": telegram_chat_id,
                    "telegram_message_id": telegram_message_id,
                    "telegram_file_id": telegram_file_id,
                    "telegram_file_unique_id": telegram_file_unique_id,
                }
            )
            .execute()
        )
        if not response.data:
            raise RuntimeError("Failed to create photo metadata")
        row = response.data[0]
        return UUID(row["id"])

    def delete_photo(self, photo_id: UUID) -> None:
        """Delete a photo metadata row."""
        self.client.table("photos").delete().eq("id", str(photo_id)).execute()
