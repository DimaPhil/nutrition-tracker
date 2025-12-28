"""Admin domain models."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class AdminUser:
    """Minimal admin view of a user."""

    id: UUID
    telegram_user_id: int
    last_active_at: datetime | None
