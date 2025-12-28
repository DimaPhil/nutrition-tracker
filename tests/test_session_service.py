"""Tests for session state machine."""

import asyncio
from uuid import uuid4

from nutrition_tracker.adapters.fdc_client import FdcClient
from nutrition_tracker.services.audit import AuditService
from nutrition_tracker.services.cache import InMemoryCache
from nutrition_tracker.services.library import LibraryService
from nutrition_tracker.services.meals import MealLogService
from nutrition_tracker.services.nutrition import NutritionService
from nutrition_tracker.services.sessions import SessionService
from tests.conftest import (
    FakeFdcClient,
    InMemoryAuditRepository,
    InMemoryLibraryRepository,
    InMemoryMealLogRepository,
    InMemoryPhotoRepository,
    InMemorySessionRepository,
)


class FailingFdcClient(FdcClient):
    async def search_foods(self, query: str, page_size: int = 10) -> dict[str, object]:
        return {
            "foods": [
                {
                    "fdcId": 123,
                    "description": "Example Food",
                    "dataType": "Branded",
                }
            ]
        }

    async def get_food(self, fdc_id: int) -> dict[str, object]:
        raise RuntimeError("timeout")


def test_session_flow_prompts_for_item_and_weight() -> None:
    photo_repository = InMemoryPhotoRepository()
    session_repository = InMemorySessionRepository()
    nutrition_service = NutritionService(FakeFdcClient(), InMemoryCache())
    library_service = LibraryService(InMemoryLibraryRepository())
    meal_log_service = MealLogService(
        nutrition_service=nutrition_service,
        library_service=library_service,
        repository=InMemoryMealLogRepository(),
    )
    audit_service = AuditService(InMemoryAuditRepository())
    service = SessionService(
        photo_repository=photo_repository,
        session_repository=session_repository,
        library_service=library_service,
        nutrition_service=nutrition_service,
        meal_log_service=meal_log_service,
        audit_service=audit_service,
    )

    user_id = uuid4()
    session_id, prompt = asyncio.run(
        service.start_session(
            user_id=user_id,
            telegram_chat_id=1,
            telegram_message_id=2,
            telegram_file_id="file-id",
            telegram_file_unique_id="unique-id",
            vision_items=[
                {
                    "label": "Chicken",
                    "estimated_grams_low": 100,
                    "estimated_grams_high": 200,
                }
            ],
        )
    )

    assert session_repository.sessions[session_id].status == "AWAITING_CONFIRMATION"
    assert prompt.reply_markup is not None

    prompt = asyncio.run(service.handle_callback(session_id, "confirm"))
    assert prompt is not None
    assert (
        session_repository.sessions[session_id].status == "AWAITING_ITEM_CONFIRMATION"
    )

    prompt = asyncio.run(service.handle_callback(session_id, "item_yes"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_PORTION_CHOICE"

    prompt = asyncio.run(service.handle_callback(session_id, "portion_est"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_SAVE"


def test_session_flow_handles_multiple_items() -> None:
    photo_repository = InMemoryPhotoRepository()
    session_repository = InMemorySessionRepository()
    nutrition_service = NutritionService(FakeFdcClient(), InMemoryCache())
    library_service = LibraryService(InMemoryLibraryRepository())
    meal_log_service = MealLogService(
        nutrition_service=nutrition_service,
        library_service=library_service,
        repository=InMemoryMealLogRepository(),
    )
    audit_service = AuditService(InMemoryAuditRepository())
    service = SessionService(
        photo_repository=photo_repository,
        session_repository=session_repository,
        library_service=library_service,
        nutrition_service=nutrition_service,
        meal_log_service=meal_log_service,
        audit_service=audit_service,
    )

    user_id = uuid4()
    session_id, _ = asyncio.run(
        service.start_session(
            user_id=user_id,
            telegram_chat_id=1,
            telegram_message_id=2,
            telegram_file_id="file-id",
            telegram_file_unique_id="unique-id",
            vision_items=[
                {
                    "label": "Rice",
                    "estimated_grams_low": 100,
                    "estimated_grams_high": 150,
                },
                {
                    "label": "Chicken",
                    "estimated_grams_low": 200,
                    "estimated_grams_high": 250,
                },
            ],
        )
    )

    prompt = asyncio.run(service.handle_callback(session_id, "confirm"))
    assert prompt is not None
    assert (
        session_repository.sessions[session_id].status == "AWAITING_ITEM_CONFIRMATION"
    )

    prompt = asyncio.run(service.handle_callback(session_id, "item_yes"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_PORTION_CHOICE"

    prompt = asyncio.run(service.handle_callback(session_id, "portion_est"))
    assert prompt is not None
    assert (
        session_repository.sessions[session_id].status == "AWAITING_ITEM_CONFIRMATION"
    )

    prompt = asyncio.run(service.handle_callback(session_id, "item_yes"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_PORTION_CHOICE"

    prompt = asyncio.run(service.handle_callback(session_id, "portion_manual"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_MANUAL_GRAMS"

    prompt = asyncio.run(service.handle_text(user_id, "220"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_SAVE"


def test_session_manual_entry_flow() -> None:
    photo_repository = InMemoryPhotoRepository()
    session_repository = InMemorySessionRepository()
    nutrition_service = NutritionService(FakeFdcClient(), InMemoryCache())
    library_service = LibraryService(InMemoryLibraryRepository())
    meal_log_service = MealLogService(
        nutrition_service=nutrition_service,
        library_service=library_service,
        repository=InMemoryMealLogRepository(),
    )
    audit_repo = InMemoryAuditRepository()
    audit_service = AuditService(audit_repo)
    service = SessionService(
        photo_repository=photo_repository,
        session_repository=session_repository,
        library_service=library_service,
        nutrition_service=nutrition_service,
        meal_log_service=meal_log_service,
        audit_service=audit_service,
    )

    user_id = uuid4()
    session_id, _ = asyncio.run(
        service.start_session(
            user_id=user_id,
            telegram_chat_id=1,
            telegram_message_id=2,
            telegram_file_id="file-id",
            telegram_file_unique_id="unique-id",
            vision_items=[
                {
                    "label": "Oats",
                    "estimated_grams_low": 50,
                    "estimated_grams_high": 80,
                }
            ],
        )
    )

    asyncio.run(service.handle_callback(session_id, "confirm"))
    asyncio.run(service.handle_callback(session_id, "item_no"))
    prompt = asyncio.run(service.handle_callback(session_id, "choose", "1"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_MANUAL_NAME"

    prompt = asyncio.run(service.handle_text(user_id, "Rolled oats"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_MANUAL_STORE"

    prompt = asyncio.run(service.handle_callback(session_id, "store_costco"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_MANUAL_BASIS"

    prompt = asyncio.run(service.handle_callback(session_id, "basis_serv"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_MANUAL_SERVING"

    prompt = asyncio.run(service.handle_text(user_id, "40"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_MANUAL_MACROS"

    prompt = asyncio.run(service.handle_text(user_id, "150 5 3 27"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_PORTION_CHOICE"

    asyncio.run(service.handle_callback(session_id, "portion_manual"))
    prompt = asyncio.run(service.handle_text(user_id, "80"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_SAVE"


def test_session_fdc_timeout_falls_back_to_selection() -> None:
    photo_repository = InMemoryPhotoRepository()
    session_repository = InMemorySessionRepository()
    nutrition_service = NutritionService(FailingFdcClient(), InMemoryCache())
    library_service = LibraryService(InMemoryLibraryRepository())
    meal_log_service = MealLogService(
        nutrition_service=nutrition_service,
        library_service=library_service,
        repository=InMemoryMealLogRepository(),
    )
    audit_service = AuditService(InMemoryAuditRepository())
    service = SessionService(
        photo_repository=photo_repository,
        session_repository=session_repository,
        library_service=library_service,
        nutrition_service=nutrition_service,
        meal_log_service=meal_log_service,
        audit_service=audit_service,
    )

    user_id = uuid4()
    session_id, _ = asyncio.run(
        service.start_session(
            user_id=user_id,
            telegram_chat_id=1,
            telegram_message_id=2,
            telegram_file_id="file-id",
            telegram_file_unique_id="unique-id",
            vision_items=[
                {
                    "label": "Oats",
                    "estimated_grams_low": 50,
                    "estimated_grams_high": 80,
                }
            ],
        )
    )

    asyncio.run(service.handle_callback(session_id, "confirm"))
    prompt = asyncio.run(service.handle_callback(session_id, "item_no"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_ITEM_SELECTION"

    prompt = asyncio.run(service.handle_callback(session_id, "choose", "0"))
    assert prompt is not None
    assert "USDA lookup timed out" in prompt.text
    assert session_repository.sessions[session_id].status == "AWAITING_ITEM_SELECTION"


def test_session_edit_flow_records_audit() -> None:
    photo_repository = InMemoryPhotoRepository()
    session_repository = InMemorySessionRepository()
    nutrition_service = NutritionService(FakeFdcClient(), InMemoryCache())
    library_service = LibraryService(InMemoryLibraryRepository())
    meal_log_service = MealLogService(
        nutrition_service=nutrition_service,
        library_service=library_service,
        repository=InMemoryMealLogRepository(),
    )
    audit_repo = InMemoryAuditRepository()
    audit_service = AuditService(audit_repo)
    service = SessionService(
        photo_repository=photo_repository,
        session_repository=session_repository,
        library_service=library_service,
        nutrition_service=nutrition_service,
        meal_log_service=meal_log_service,
        audit_service=audit_service,
    )

    user_id = uuid4()
    summary = asyncio.run(
        meal_log_service.save_meal(
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
    prompt = service.start_edit_session(user_id, meal_id)
    assert prompt is not None
    session_id = list(session_repository.sessions.keys())[-1]

    prompt = asyncio.run(service.handle_callback(session_id, "edit_item", "0"))
    assert prompt is not None
    prompt = asyncio.run(service.handle_text(user_id, "150"))
    assert prompt is not None
    assert audit_repo.events


def test_cancel_active_session_deletes_photo() -> None:
    photo_repository = InMemoryPhotoRepository()
    session_repository = InMemorySessionRepository()
    nutrition_service = NutritionService(FakeFdcClient(), InMemoryCache())
    library_service = LibraryService(InMemoryLibraryRepository())
    meal_log_service = MealLogService(
        nutrition_service=nutrition_service,
        library_service=library_service,
        repository=InMemoryMealLogRepository(),
    )
    audit_service = AuditService(InMemoryAuditRepository())
    service = SessionService(
        photo_repository=photo_repository,
        session_repository=session_repository,
        library_service=library_service,
        nutrition_service=nutrition_service,
        meal_log_service=meal_log_service,
        audit_service=audit_service,
    )
    user_id = uuid4()
    session_id, _ = asyncio.run(
        service.start_session(
            user_id=user_id,
            telegram_chat_id=1,
            telegram_message_id=2,
            telegram_file_id="file-id",
            telegram_file_unique_id="unique-id",
            vision_items=[{"label": "Salad"}],
        )
    )
    assert photo_repository.photos
    prompt = service.cancel_active_session(user_id)
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "CANCELLED"
    assert not photo_repository.photos


def test_library_add_flow_creates_food() -> None:
    photo_repository = InMemoryPhotoRepository()
    session_repository = InMemorySessionRepository()
    nutrition_service = NutritionService(FakeFdcClient(), InMemoryCache())
    library_repo = InMemoryLibraryRepository()
    library_service = LibraryService(library_repo)
    meal_log_service = MealLogService(
        nutrition_service=nutrition_service,
        library_service=library_service,
        repository=InMemoryMealLogRepository(),
    )
    audit_service = AuditService(InMemoryAuditRepository())
    service = SessionService(
        photo_repository=photo_repository,
        session_repository=session_repository,
        library_service=library_service,
        nutrition_service=nutrition_service,
        meal_log_service=meal_log_service,
        audit_service=audit_service,
    )

    user_id = uuid4()
    prompt = service.start_library_add_session(user_id)
    assert "food name" in prompt.text.lower()
    session_id = list(session_repository.sessions.keys())[-1]

    prompt = asyncio.run(service.handle_text(user_id, "Trail mix"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_MANUAL_STORE"

    prompt = asyncio.run(service.handle_callback(session_id, "store_other"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_MANUAL_BASIS"

    prompt = asyncio.run(service.handle_callback(session_id, "basis_100"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_MANUAL_MACROS"

    prompt = asyncio.run(service.handle_text(user_id, "450 10 25 40"))
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "COMPLETED"
    assert library_repo.foods
