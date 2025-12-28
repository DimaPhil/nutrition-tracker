"""Meal logging service."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from nutrition_tracker.domain.library import LibraryFood
from nutrition_tracker.domain.meals import (
    MealItemRecord,
    MealItemSnapshot,
    MealLogDetail,
    MealLogSummary,
)
from nutrition_tracker.domain.nutrition import MacroProfile
from nutrition_tracker.domain.stats import MealLogRow
from nutrition_tracker.services.library import LibraryService
from nutrition_tracker.services.nutrition import NutritionService


class MealLogRepository(Protocol):
    """Persistence interface for meal logs."""

    def create_meal_log(
        self,
        user_id: UUID,
        logged_at: datetime,
        totals: MacroProfile,
    ) -> UUID:
        """Create a meal log and return its id."""

    def create_meal_items(
        self, meal_log_id: UUID, items: list[MealItemSnapshot]
    ) -> None:
        """Create meal item rows for a meal log."""

    def get_meal_log(self, meal_log_id: UUID) -> MealLogRow | None:
        """Return a meal log row by id."""

    def list_meal_items(self, meal_log_id: UUID) -> list[MealItemRecord]:
        """Return meal items for a meal log."""

    def get_meal_item(self, meal_item_id: UUID) -> MealItemRecord | None:
        """Return a meal item by id."""

    def update_meal_item(
        self, meal_item_id: UUID, grams: float, macros: MacroProfile
    ) -> None:
        """Update meal item grams and macros."""

    def update_meal_log_totals(self, meal_log_id: UUID, totals: MacroProfile) -> None:
        """Update totals for a meal log."""


@dataclass
class MealLogService:
    """Service that computes macros and persists meal logs."""

    nutrition_service: NutritionService
    library_service: LibraryService
    repository: MealLogRepository

    async def compute_summary(self, items: list[dict[str, object]]) -> MealLogSummary:
        """Compute totals and snapshots without persisting."""
        snapshots, total = await _build_snapshots(self.nutrition_service, items)
        return MealLogSummary(
            meal_id=None,
            total_calories=total.calories,
            total_protein_g=total.protein_g,
            total_fat_g=total.fat_g,
            total_carbs_g=total.carbs_g,
            items=snapshots,
        )

    async def save_meal(
        self, user_id: UUID, items: list[dict[str, object]]
    ) -> MealLogSummary:
        """Compute macros for items and persist the meal log."""
        resolved_items = _ensure_library_refs(self.library_service, items, user_id)
        snapshots, total = await _build_snapshots(
            self.nutrition_service, resolved_items
        )
        meal_id = self.repository.create_meal_log(
            user_id=user_id,
            logged_at=datetime.now(tz=UTC),
            totals=total,
        )
        self.repository.create_meal_items(meal_id, snapshots)
        for snapshot in snapshots:
            if snapshot.food_id:
                self.library_service.record_use(snapshot.food_id)

        return MealLogSummary(
            meal_id=meal_id,
            total_calories=total.calories,
            total_protein_g=total.protein_g,
            total_fat_g=total.fat_g,
            total_carbs_g=total.carbs_g,
            items=snapshots,
        )

    def get_meal_detail(self, meal_log_id: UUID) -> MealLogDetail | None:
        """Return a meal log with items."""
        log = self.repository.get_meal_log(meal_log_id)
        if log is None:
            return None
        items = self.repository.list_meal_items(meal_log_id)
        return MealLogDetail(
            id=log.meal_id,
            logged_at=log.logged_at,
            total_calories=log.total_calories,
            total_protein_g=log.total_protein_g,
            total_fat_g=log.total_fat_g,
            total_carbs_g=log.total_carbs_g,
            items=items,
        )

    def update_meal_item_grams(
        self, meal_item_id: UUID, grams: float
    ) -> MealLogDetail | None:
        """Update a meal item's grams and refresh totals."""
        item = self.repository.get_meal_item(meal_item_id)
        if item is None:
            return None
        base_macros, basis, serving_size = _macros_from_snapshot(
            item.nutrition_snapshot
        )
        updated_macros = _compute_portion_macros(
            base_macros, grams, basis, serving_size
        )
        self.repository.update_meal_item(meal_item_id, grams, updated_macros)
        items = self.repository.list_meal_items(item.meal_log_id)
        totals = _sum_totals(items)
        self.repository.update_meal_log_totals(item.meal_log_id, totals)
        log = self.repository.get_meal_log(item.meal_log_id)
        if log is None:
            return None
        return MealLogDetail(
            id=log.meal_id,
            logged_at=log.logged_at,
            total_calories=totals.calories,
            total_protein_g=totals.protein_g,
            total_fat_g=totals.fat_g,
            total_carbs_g=totals.carbs_g,
            items=items,
        )


async def _build_snapshots(
    nutrition_service: NutritionService, items: list[dict[str, object]]
) -> tuple[list[MealItemSnapshot], MacroProfile]:
    snapshots: list[MealItemSnapshot] = []
    total = MacroProfile(0.0, 0.0, 0.0, 0.0)
    for item in items:
        label = str(item.get("name") or item.get("label") or "item")
        grams = _to_float(item.get("grams"))
        base_macros, basis, serving_size = await _resolve_base_macros(
            nutrition_service, item
        )
        portion = _compute_portion_macros(base_macros, grams, basis, serving_size)
        food_id = _parse_uuid(item.get("food_id"))
        nutrition_snapshot = {
            "basis": basis,
            "serving_size_g": serving_size,
            "calories": base_macros.calories,
            "protein_g": base_macros.protein_g,
            "fat_g": base_macros.fat_g,
            "carbs_g": base_macros.carbs_g,
            "source_type": item.get("source_type"),
            "source_ref": item.get("source_ref"),
        }
        snapshots.append(
            MealItemSnapshot(
                name=label,
                grams=grams,
                calories=portion.calories,
                protein_g=portion.protein_g,
                fat_g=portion.fat_g,
                carbs_g=portion.carbs_g,
                food_id=food_id,
                nutrition_snapshot=nutrition_snapshot,
            )
        )
        total = MacroProfile(
            calories=total.calories + portion.calories,
            protein_g=total.protein_g + portion.protein_g,
            fat_g=total.fat_g + portion.fat_g,
            carbs_g=total.carbs_g + portion.carbs_g,
        )
    return snapshots, total


async def _resolve_base_macros(
    nutrition_service: NutritionService, item: dict[str, object]
) -> tuple[MacroProfile, str, float | None]:
    if _has_macros(item):
        basis = str(item.get("basis") or "per100g")
        serving_size = (
            float(item["serving_size_g"])
            if isinstance(item.get("serving_size_g"), int | float)
            else None
        )
        return (
            MacroProfile(
                calories=float(item.get("calories", 0.0)),
                protein_g=float(item.get("protein_g", 0.0)),
                fat_g=float(item.get("fat_g", 0.0)),
                carbs_g=float(item.get("carbs_g", 0.0)),
            ),
            basis,
            serving_size,
        )
    label = str(item.get("label") or item.get("name") or "item")
    return await _lookup_fdc_macros(nutrition_service, label)


async def _lookup_fdc_macros(
    nutrition_service: NutritionService, label: str
) -> tuple[MacroProfile, str, float | None]:
    results = await nutrition_service.search(label, limit=1)
    if not results:
        return MacroProfile(0.0, 0.0, 0.0, 0.0), "per100g", None
    details = await nutrition_service.get_food(results[0].fdc_id)
    return details.macros, "per100g", details.serving_size_g


def _compute_portion_macros(
    base: MacroProfile, grams: float, basis: str, serving_size_g: float | None
) -> MacroProfile:
    if grams <= 0:
        return MacroProfile(0.0, 0.0, 0.0, 0.0)
    if basis == "perServing" and serving_size_g and serving_size_g > 0:
        factor = grams / serving_size_g
    else:
        factor = grams / 100.0
    return MacroProfile(
        calories=base.calories * factor,
        protein_g=base.protein_g * factor,
        fat_g=base.fat_g * factor,
        carbs_g=base.carbs_g * factor,
    )


def _has_macros(item: dict[str, object]) -> bool:
    return all(key in item for key in ("calories", "protein_g", "fat_g", "carbs_g"))


def _parse_uuid(value: object) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            return None
    return None


def _to_float(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _macros_from_snapshot(
    snapshot: dict[str, object],
) -> tuple[MacroProfile, str, float | None]:
    basis = str(snapshot.get("basis") or "per100g")
    serving_size = (
        float(snapshot["serving_size_g"])
        if isinstance(snapshot.get("serving_size_g"), int | float)
        else None
    )
    return (
        MacroProfile(
            calories=float(snapshot.get("calories", 0.0)),
            protein_g=float(snapshot.get("protein_g", 0.0)),
            fat_g=float(snapshot.get("fat_g", 0.0)),
            carbs_g=float(snapshot.get("carbs_g", 0.0)),
        ),
        basis,
        serving_size,
    )


def _sum_totals(items: list[MealItemRecord]) -> MacroProfile:
    total = MacroProfile(0.0, 0.0, 0.0, 0.0)
    for item in items:
        total = MacroProfile(
            calories=total.calories + item.calories,
            protein_g=total.protein_g + item.protein_g,
            fat_g=total.fat_g + item.fat_g,
            carbs_g=total.carbs_g + item.carbs_g,
        )
    return total


def _ensure_library_refs(
    library_service: LibraryService,
    items: list[dict[str, object]],
    user_id: UUID,
) -> list[dict[str, object]]:
    resolved: list[dict[str, object]] = []
    for item in items:
        if item.get("food_id"):
            resolved.append(item)
            continue
        source_type = str(item.get("source_type") or "manual")
        if source_type == "library":
            resolved.append(item)
            continue
        payload = {
            "name": str(item.get("name") or item.get("label") or "item"),
            "brand": item.get("brand"),
            "store": item.get("store"),
            "source_type": source_type,
            "source_ref": item.get("source_ref"),
            "basis": str(item.get("basis") or "per100g"),
            "serving_size_g": item.get("serving_size_g"),
            "calories": float(item.get("calories", 0.0)),
            "protein_g": float(item.get("protein_g", 0.0)),
            "fat_g": float(item.get("fat_g", 0.0)),
            "carbs_g": float(item.get("carbs_g", 0.0)),
        }
        food = _get_or_create_food(library_service, user_id, payload)
        resolved_item = dict(item)
        resolved_item["food_id"] = str(food.id)
        resolved.append(resolved_item)
    return resolved


def _get_or_create_food(
    library_service: LibraryService, user_id: UUID, payload: dict[str, object]
) -> LibraryFood:
    source_ref = payload.get("source_ref")
    if source_ref:
        existing = library_service.find_by_source_ref(
            user_id, str(payload.get("source_type")), str(source_ref)
        )
        if existing:
            return existing
    return library_service.create_manual_food(user_id, payload)
