"""Tests for session state machine."""

from uuid import uuid4

from nutrition_tracker.services.sessions import SessionService
from tests.conftest import InMemoryPhotoRepository, InMemorySessionRepository


def test_session_flow_prompts_for_item_and_weight() -> None:
    photo_repository = InMemoryPhotoRepository()
    session_repository = InMemorySessionRepository()
    service = SessionService(photo_repository, session_repository)

    user_id = uuid4()
    session_id, prompt = service.start_session(
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

    assert session_repository.sessions[session_id].status == "AWAITING_CONFIRMATION"
    assert prompt.reply_markup is not None

    prompt = service.handle_callback(session_id, "confirm")
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_PORTION_CHOICE"

    prompt = service.handle_callback(session_id, "use_estimate")
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_SAVE"


def test_session_flow_handles_multiple_items() -> None:
    photo_repository = InMemoryPhotoRepository()
    session_repository = InMemorySessionRepository()
    service = SessionService(photo_repository, session_repository)

    user_id = uuid4()
    session_id, _ = service.start_session(
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

    prompt = service.handle_callback(session_id, "confirm")
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_PORTION_CHOICE"

    prompt = service.handle_callback(session_id, "use_estimate")
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_PORTION_CHOICE"

    prompt = service.handle_callback(session_id, "enter_grams")
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_MANUAL_GRAMS"

    prompt = service.handle_text(user_id, "220")
    assert prompt is not None
    assert session_repository.sessions[session_id].status == "AWAITING_SAVE"
