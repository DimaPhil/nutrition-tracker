"""Tests for meal log service."""

import asyncio
from uuid import uuid4

from nutrition_tracker.services.cache import InMemoryCache
from nutrition_tracker.services.library import LibraryService
from nutrition_tracker.services.meals import MealLogService
from nutrition_tracker.services.nutrition import NutritionService
from tests.conftest import (
    FakeFdcClient,
    InMemoryLibraryRepository,
    InMemoryMealLogRepository,
)


def test_meal_log_service_saves_and_computes_totals() -> None:
    nutrition_service = NutritionService(
        fdc_client=FakeFdcClient(),
        cache=InMemoryCache(),
    )
    library_service = LibraryService(InMemoryLibraryRepository())
    repository = InMemoryMealLogRepository()
    service = MealLogService(
        nutrition_service=nutrition_service,
        library_service=library_service,
        repository=repository,
    )

    summary = asyncio.run(
        service.save_meal(
            user_id=uuid4(),
            items=[
                {
                    "name": "Chicken breast",
                    "grams": 200,
                    "source_type": "manual",
                    "basis": "per100g",
                    "calories": 165,
                    "protein_g": 31,
                    "fat_g": 3.6,
                    "carbs_g": 0,
                }
            ],
        )
    )

    assert summary.total_calories == 330
    assert summary.total_protein_g == 62
    assert summary.items[0].grams == 200
    assert repository.meals


def test_meal_log_service_updates_item_grams() -> None:
    nutrition_service = NutritionService(
        fdc_client=FakeFdcClient(),
        cache=InMemoryCache(),
    )
    library_service = LibraryService(InMemoryLibraryRepository())
    repository = InMemoryMealLogRepository()
    service = MealLogService(
        nutrition_service=nutrition_service,
        library_service=library_service,
        repository=repository,
    )
    user_id = uuid4()
    summary = asyncio.run(
        service.save_meal(
            user_id=user_id,
            items=[
                {
                    "name": "Rice",
                    "grams": 100,
                    "source_type": "manual",
                    "basis": "per100g",
                    "calories": 130,
                    "protein_g": 2.5,
                    "fat_g": 0.3,
                    "carbs_g": 28,
                }
            ],
        )
    )
    meal_id = summary.meal_id
    assert meal_id is not None
    detail = service.get_meal_detail(meal_id)
    assert detail is not None
    item_id = detail.items[0].id
    updated = service.update_meal_item_grams(item_id, 200)
    assert updated is not None
    assert updated.total_calories == 260
