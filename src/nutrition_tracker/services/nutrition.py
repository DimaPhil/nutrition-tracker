"""Nutrition service integrating USDA FDC."""

from dataclasses import dataclass

from nutrition_tracker.adapters.fdc_client import FdcClient
from nutrition_tracker.domain.nutrition import FoodDetails, FoodSummary, MacroProfile
from nutrition_tracker.services.cache import Cache

_NUTRIENT_IDS = {
    "calories": 1008,
    "protein": 1003,
    "fat": 1004,
    "carbs": 1005,
}


@dataclass
class NutritionService:
    """Service for nutrition lookups with caching."""

    fdc_client: FdcClient
    cache: Cache
    search_ttl_seconds: int = 3600
    food_ttl_seconds: int = 86400

    async def search(self, query: str, limit: int = 5) -> list[FoodSummary]:
        """Search FDC foods with caching."""
        cache_key = f"fdc:search:{query.lower()}:{limit}"
        cached = self.cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        payload = await self.fdc_client.search_foods(query, page_size=limit)
        foods = [
            FoodSummary(
                fdc_id=food["fdcId"],
                description=food.get("description", ""),
                brand_owner=food.get("brandOwner"),
                brand_name=food.get("brandName"),
                data_type=food.get("dataType"),
            )
            for food in payload.get("foods", [])
        ]
        self.cache.set(cache_key, foods, ttl_seconds=self.search_ttl_seconds)
        return foods

    async def get_food(self, fdc_id: int) -> FoodDetails:
        """Retrieve food details with macros from FDC."""
        cache_key = f"fdc:food:{fdc_id}"
        cached = self.cache.get(cache_key)
        if isinstance(cached, FoodDetails):
            return cached

        payload = await self.fdc_client.get_food(fdc_id)
        summary = FoodSummary(
            fdc_id=payload["fdcId"],
            description=payload.get("description", ""),
            brand_owner=payload.get("brandOwner"),
            brand_name=payload.get("brandName"),
            data_type=payload.get("dataType"),
        )
        macros = _extract_macros(payload.get("foodNutrients", []))
        details = FoodDetails(
            summary=summary,
            macros=macros,
            serving_size_g=payload.get("servingSize"),
        )
        self.cache.set(cache_key, details, ttl_seconds=self.food_ttl_seconds)
        return details


def _extract_macros(food_nutrients: list[dict[str, object]]) -> MacroProfile:
    """Extract calories, protein, fat, carbs from FDC nutrients."""
    values: dict[str, float] = {
        "calories": 0.0,
        "protein": 0.0,
        "fat": 0.0,
        "carbs": 0.0,
    }
    for nutrient in food_nutrients:
        nutrient_info = nutrient.get("nutrient") or {}
        nutrient_id = nutrient_info.get("id") or nutrient.get("nutrientId")
        amount = nutrient.get("amount")
        if nutrient_id == _NUTRIENT_IDS["calories"] and amount is not None:
            values["calories"] = float(amount)
        if nutrient_id == _NUTRIENT_IDS["protein"] and amount is not None:
            values["protein"] = float(amount)
        if nutrient_id == _NUTRIENT_IDS["fat"] and amount is not None:
            values["fat"] = float(amount)
        if nutrient_id == _NUTRIENT_IDS["carbs"] and amount is not None:
            values["carbs"] = float(amount)

    return MacroProfile(
        calories=values["calories"],
        protein_g=values["protein"],
        fat_g=values["fat"],
        carbs_g=values["carbs"],
    )
