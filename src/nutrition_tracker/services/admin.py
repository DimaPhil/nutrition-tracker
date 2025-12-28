"""Admin service for reporting."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from nutrition_tracker.domain.admin import AdminUser
from nutrition_tracker.domain.library import LibraryFood
from nutrition_tracker.domain.stats import MealLogRow
from nutrition_tracker.services.library import LibraryRepository
from nutrition_tracker.services.stats import StatsRepository


class AdminRepository(Protocol):
    """Persistence interface for admin data."""

    def list_users(self) -> list[AdminUser]:
        """Return all users."""

    def list_sessions(self, limit: int) -> list[dict[str, object]]:
        """Return recent photo sessions."""

    def list_costs(self, limit: int) -> list[dict[str, object]]:
        """Return recent model usage entries."""

    def list_audit_events(self, user_id: UUID, limit: int) -> list[dict[str, object]]:
        """Return recent audit events for a user."""


@dataclass
class AdminService:
    """Service for admin dashboards."""

    admin_repository: AdminRepository
    stats_repository: StatsRepository
    library_repository: LibraryRepository

    def list_users(self) -> list[dict[str, object]]:
        """Return users with usage summaries."""
        users = self.admin_repository.list_users()
        now = datetime.now(tz=UTC)
        start_7d = now - timedelta(days=7)
        start_30d = now - timedelta(days=30)
        summaries = []
        for user in users:
            logs_7d = self.stats_repository.list_meal_logs(user.id, start_7d, now)
            logs_30d = self.stats_repository.list_meal_logs(user.id, start_30d, now)
            total_calories_7d = sum(log.total_calories for log in logs_7d)
            summaries.append(
                {
                    "id": str(user.id),
                    "telegram_user_id": user.telegram_user_id,
                    "last_active_at": user.last_active_at.isoformat()
                    if user.last_active_at
                    else None,
                    "logs_last_7d": len(logs_7d),
                    "logs_last_30d": len(logs_30d),
                    "avg_calories_7d": total_calories_7d / 7,
                }
            )
        return summaries

    def get_user_detail(self, user_id: UUID) -> dict[str, object]:
        """Return detailed info for a user."""
        recent_logs = self.stats_repository.list_recent_meal_logs(user_id, limit=10)
        library = self.library_repository.list_top_foods(user_id, limit=20)
        audits = self.admin_repository.list_audit_events(user_id, limit=20)
        return {
            "user_id": str(user_id),
            "recent_meals": [_serialize_meal_log(log) for log in recent_logs],
            "library": [_serialize_library(food) for food in library],
            "audit_events": audits,
        }

    def list_sessions(self, limit: int = 20) -> list[dict[str, object]]:
        """Return recent sessions."""
        return self.admin_repository.list_sessions(limit)

    def list_costs(self, limit: int = 30) -> list[dict[str, object]]:
        """Return model usage entries."""
        return self.admin_repository.list_costs(limit)


def _serialize_meal_log(log: MealLogRow) -> dict[str, object]:
    return {
        "logged_at": log.logged_at.isoformat(),
        "total_calories": log.total_calories,
        "total_protein_g": log.total_protein_g,
        "total_fat_g": log.total_fat_g,
        "total_carbs_g": log.total_carbs_g,
    }


def _serialize_library(food: LibraryFood) -> dict[str, object]:
    return {
        "id": str(food.id),
        "name": food.name,
        "brand": food.brand,
        "store": food.store,
        "use_count": food.use_count,
        "last_used_at": food.last_used_at.isoformat() if food.last_used_at else None,
    }
