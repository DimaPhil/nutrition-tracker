"""Tests for stats service."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from nutrition_tracker.domain.stats import MealLogRow
from nutrition_tracker.services.stats import StatsService
from tests.conftest import InMemoryStatsRepository


def test_get_today_aggregates_by_timezone() -> None:
    user_id = uuid4()
    repo = InMemoryStatsRepository()
    now = datetime.now(tz=UTC)
    repo.logs = [
        MealLogRow(
            logged_at=now,
            total_calories=500,
            total_protein_g=30,
            total_fat_g=10,
            total_carbs_g=50,
        ),
        MealLogRow(
            logged_at=now - timedelta(days=1),
            total_calories=200,
            total_protein_g=10,
            total_fat_g=5,
            total_carbs_g=20,
        ),
    ]

    service = StatsService(repo)
    totals = service.get_today(user_id, "UTC")

    assert totals.calories == 500
    assert totals.protein_g == 30


def test_get_history_returns_recent() -> None:
    user_id = uuid4()
    repo = InMemoryStatsRepository()
    now = datetime.now(tz=UTC)
    repo.logs = [
        MealLogRow(
            logged_at=now,
            total_calories=400,
            total_protein_g=20,
            total_fat_g=8,
            total_carbs_g=40,
        ),
        MealLogRow(
            logged_at=now - timedelta(days=2),
            total_calories=600,
            total_protein_g=40,
            total_fat_g=12,
            total_carbs_g=60,
        ),
    ]

    service = StatsService(repo)
    history = service.get_history(user_id, limit=1)

    assert len(history) == 1
    assert history[0].total_calories == 400
