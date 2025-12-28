"""Statistics service for meal logs."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from nutrition_tracker.domain.stats import DailyTotals, MealLogRow

DECEMBER = 12


class StatsRepository(Protocol):
    """Persistence interface for meal log statistics."""

    def list_meal_logs(
        self, user_id: UUID, start: datetime, end: datetime
    ) -> list[MealLogRow]:
        """Return meal logs within a time range."""

    def list_recent_meal_logs(self, user_id: UUID, limit: int) -> list[MealLogRow]:
        """Return recent meal logs."""


@dataclass
class PeriodSummary:
    """Aggregated totals for a period."""

    daily: list[DailyTotals]
    avg_calories: float
    avg_protein_g: float
    avg_fat_g: float
    avg_carbs_g: float


@dataclass
class StatsService:
    """Service for computing user stats by timezone."""

    repository: StatsRepository

    def get_today(self, user_id: UUID, timezone_name: str) -> DailyTotals:
        """Return today's totals in the user's timezone."""
        tz = ZoneInfo(timezone_name)
        now = datetime.now(tz=tz)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        logs = self.repository.list_meal_logs(
            user_id, start.astimezone(UTC), end.astimezone(UTC)
        )
        return _aggregate_day(start.date(), logs, tz)

    def get_today_with_logs(
        self, user_id: UUID, timezone_name: str
    ) -> tuple[DailyTotals, list[MealLogRow]]:
        """Return today's totals and meal logs."""
        tz = ZoneInfo(timezone_name)
        now = datetime.now(tz=tz)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        logs = self.repository.list_meal_logs(
            user_id, start.astimezone(UTC), end.astimezone(UTC)
        )
        totals = _aggregate_day(start.date(), logs, tz)
        return totals, logs

    def get_week(self, user_id: UUID, timezone_name: str) -> PeriodSummary:
        """Return week-to-date totals and averages."""
        tz = ZoneInfo(timezone_name)
        now = datetime.now(tz=tz)
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = start + timedelta(days=7)
        logs = self.repository.list_meal_logs(
            user_id, start.astimezone(UTC), end.astimezone(UTC)
        )
        return _aggregate_period(start, 7, logs, tz)

    def get_month(self, user_id: UUID, timezone_name: str) -> PeriodSummary:
        """Return month-to-date totals and averages."""
        tz = ZoneInfo(timezone_name)
        now = datetime.now(tz=tz)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == DECEMBER:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        days = (end - start).days
        logs = self.repository.list_meal_logs(
            user_id, start.astimezone(UTC), end.astimezone(UTC)
        )
        return _aggregate_period(start, days, logs, tz)

    def get_history(self, user_id: UUID, limit: int = 10) -> list[MealLogRow]:
        """Return recent meal logs."""
        return self.repository.list_recent_meal_logs(user_id, limit)


def _aggregate_day(day: date, logs: list[MealLogRow], tz: ZoneInfo) -> DailyTotals:
    total = DailyTotals(day=day, calories=0, protein_g=0, fat_g=0, carbs_g=0)
    for log in logs:
        log_day = log.logged_at.astimezone(tz).date()
        if log_day != day:
            continue
        total = DailyTotals(
            day=day,
            calories=total.calories + log.total_calories,
            protein_g=total.protein_g + log.total_protein_g,
            fat_g=total.fat_g + log.total_fat_g,
            carbs_g=total.carbs_g + log.total_carbs_g,
        )
    return total


def _aggregate_period(
    start: datetime, days: int, logs: list[MealLogRow], tz: ZoneInfo
) -> PeriodSummary:
    daily = []
    for offset in range(days):
        day = (start + timedelta(days=offset)).date()
        daily.append(_aggregate_day(day, logs, tz))

    total_days = max(len(daily), 1)
    totals = DailyTotals(day=start.date(), calories=0, protein_g=0, fat_g=0, carbs_g=0)
    for entry in daily:
        totals = DailyTotals(
            day=totals.day,
            calories=totals.calories + entry.calories,
            protein_g=totals.protein_g + entry.protein_g,
            fat_g=totals.fat_g + entry.fat_g,
            carbs_g=totals.carbs_g + entry.carbs_g,
        )

    return PeriodSummary(
        daily=daily,
        avg_calories=totals.calories / total_days,
        avg_protein_g=totals.protein_g / total_days,
        avg_fat_g=totals.fat_g / total_days,
        avg_carbs_g=totals.carbs_g / total_days,
    )
