"""Domain models for the user food library."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class LibraryFood:
    """Represents a food entry in a user's library."""

    id: UUID
    user_id: UUID
    name: str
    brand: str | None
    store: str | None
    source_type: str
    source_ref: str | None
    basis: str
    serving_size_g: float | None
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    use_count: int
    last_used_at: datetime | None
