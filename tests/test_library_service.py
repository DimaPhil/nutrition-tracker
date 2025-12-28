"""Tests for library service."""

from datetime import UTC, datetime
from uuid import uuid4

from nutrition_tracker.domain.library import LibraryFood
from nutrition_tracker.services.library import LibraryService
from tests.conftest import InMemoryLibraryRepository


def test_library_search_falls_back_to_top() -> None:
    repository = InMemoryLibraryRepository()
    service = LibraryService(repository)
    user_id = uuid4()

    food = service.create_manual_food(
        user_id,
        {
            "name": "Greek Yogurt",
            "source_type": "manual",
            "basis": "per100g",
            "calories": 60,
            "protein_g": 10,
            "fat_g": 0,
            "carbs_g": 4,
        },
    )

    results = service.search(user_id, query=None, limit=5)

    assert results == [food]


def test_library_search_by_alias() -> None:
    repository = InMemoryLibraryRepository()
    service = LibraryService(repository)
    user_id = uuid4()

    food = service.create_manual_food(
        user_id,
        {
            "name": "Chicken Breast",
            "source_type": "manual",
            "basis": "per100g",
            "calories": 165,
            "protein_g": 31,
            "fat_g": 3.6,
            "carbs_g": 0,
        },
    )
    service.add_alias(user_id, food.id, "Kirkland chicken")

    results = service.search(user_id, query="Kirkland", limit=5)

    assert results
    assert results[0].name == "Chicken Breast"


def test_library_ranking_prefers_recent_then_frequency() -> None:
    user_id = uuid4()
    now = datetime.now(tz=UTC)
    older = now.replace(year=now.year - 1)

    items = [
        LibraryFood(
            id=uuid4(),
            user_id=user_id,
            name="A",
            brand=None,
            store=None,
            source_type="manual",
            source_ref=None,
            basis="per100g",
            serving_size_g=None,
            calories=100,
            protein_g=10,
            fat_g=1,
            carbs_g=5,
            use_count=5,
            last_used_at=older,
        ),
        LibraryFood(
            id=uuid4(),
            user_id=user_id,
            name="B",
            brand=None,
            store=None,
            source_type="manual",
            source_ref=None,
            basis="per100g",
            serving_size_g=None,
            calories=120,
            protein_g=12,
            fat_g=2,
            carbs_g=6,
            use_count=1,
            last_used_at=now,
        ),
    ]

    ranked = LibraryService._rank(items)

    assert ranked[0].name == "B"
