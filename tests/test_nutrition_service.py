"""Tests for nutrition service."""

import asyncio
from dataclasses import dataclass

from nutrition_tracker.adapters.fdc_client import FdcClient
from nutrition_tracker.services.cache import InMemoryCache
from nutrition_tracker.services.nutrition import NutritionService


@dataclass
class CountingFdcClient(FdcClient):
    search_calls: int = 0
    food_calls: int = 0

    async def search_foods(self, query: str, page_size: int = 10) -> dict[str, object]:
        self.search_calls += 1
        return {
            "foods": [
                {
                    "fdcId": 999,
                    "description": "Kirkland chicken breast",
                    "brandOwner": "Costco",
                    "brandName": "Kirkland",
                    "dataType": "Branded",
                }
            ]
        }

    async def get_food(self, fdc_id: int) -> dict[str, object]:
        self.food_calls += 1
        return {
            "fdcId": fdc_id,
            "description": "Kirkland chicken breast",
            "brandOwner": "Costco",
            "brandName": "Kirkland",
            "dataType": "Branded",
            "servingSize": 100,
            "foodNutrients": [
                {"nutrientId": 1008, "amount": 165},
                {"nutrientId": 1003, "amount": 31},
                {"nutrientId": 1004, "amount": 3.6},
                {"nutrientId": 1005, "amount": 0},
            ],
        }


def test_search_uses_cache() -> None:
    client = CountingFdcClient()
    service = NutritionService(client, InMemoryCache())

    results = asyncio.run(service.search("kirkland", limit=1))
    assert results[0].fdc_id == 999
    assert client.search_calls == 1

    cached = asyncio.run(service.search("kirkland", limit=1))
    assert cached[0].fdc_id == 999
    assert client.search_calls == 1


def test_get_food_returns_macros() -> None:
    client = CountingFdcClient()
    service = NutritionService(client, InMemoryCache())

    details = asyncio.run(service.get_food(999))

    assert details.summary.description == "Kirkland chicken breast"
    assert details.macros.calories == 165
    assert details.macros.protein_g == 31
    assert details.macros.fat_g == 3.6
    assert details.macros.carbs_g == 0
