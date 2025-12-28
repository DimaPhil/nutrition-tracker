"""Tests for meal log service."""

import asyncio
from uuid import uuid4

from nutrition_tracker.services.cache import InMemoryCache
from nutrition_tracker.services.meals import MealLogService
from nutrition_tracker.services.nutrition import NutritionService
from tests.conftest import FakeFdcClient, InMemoryMealLogRepository


def test_meal_log_service_saves_and_computes_totals() -> None:
    nutrition_service = NutritionService(
        fdc_client=FakeFdcClient(),
        cache=InMemoryCache(),
    )
    repository = InMemoryMealLogRepository()
    service = MealLogService(
        nutrition_service=nutrition_service,
        repository=repository,
    )

    summary = asyncio.run(
        service.save_meal(
            user_id=uuid4(),
            items=[{"label": "Kirkland chicken breast", "grams": 200}],
        )
    )

    assert summary.total_calories == 330
    assert summary.total_protein_g == 62
    assert summary.items[0].grams == 200
    assert repository.meals
