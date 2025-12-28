"""Tests for Telegram webhook handling."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from nutrition_tracker.api.app import create_app
from nutrition_tracker.domain.stats import MealLogRow
from tests.conftest import (
    FakeTelegramClient,
    InMemoryMealLogRepository,
    InMemorySessionRepository,
    InMemoryStatsRepository,
    InMemoryUserRepository,
)


def test_webhook_start_creates_user_and_sends_message(
    container,
    user_repository: InMemoryUserRepository,
    telegram_client: FakeTelegramClient,
) -> None:
    app = create_app(container)
    client = TestClient(app)

    payload = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "date": 1700000000,
            "chat": {"id": 99, "type": "private"},
            "from": {"id": 123, "is_bot": False, "first_name": "Test"},
            "text": "/start",
        },
    }

    response = client.post("/telegram/webhook", json=payload)

    assert response.status_code == 200
    assert 123 in user_repository.users
    assert telegram_client.messages
    chat_id, text = telegram_client.messages[0]
    assert chat_id == 99
    assert "timezone" in text.lower()


def test_webhook_photo_starts_session(
    container, telegram_client: FakeTelegramClient
) -> None:
    app = create_app(container)
    client = TestClient(app)

    payload = {
        "update_id": 2,
        "message": {
            "message_id": 20,
            "date": 1700000001,
            "chat": {"id": 101, "type": "private"},
            "from": {"id": 321, "is_bot": False, "first_name": "Test"},
            "photo": [
                {
                    "file_id": "small",
                    "file_unique_id": "small-unique",
                    "width": 64,
                    "height": 64,
                },
                {
                    "file_id": "large",
                    "file_unique_id": "large-unique",
                    "width": 256,
                    "height": 256,
                },
            ],
        },
    }

    response = client.post("/telegram/webhook", json=payload)

    assert response.status_code == 200
    assert telegram_client.messages
    assert "rice" in telegram_client.messages[-1][1].lower()
    session_repo = container.session_service.session_repository
    assert isinstance(session_repo, InMemorySessionRepository)
    assert len(session_repo.sessions) == 1


def test_webhook_callback_advances_session(
    container, telegram_client: FakeTelegramClient
) -> None:
    app = create_app(container)
    client = TestClient(app)

    user = container.user_service.ensure_user(telegram_user_id=555)
    session_id, _ = container.session_service.start_session(
        user_id=user.id,
        telegram_chat_id=202,
        telegram_message_id=30,
        telegram_file_id="file-id",
        telegram_file_unique_id="unique-id",
    )

    payload = {
        "update_id": 3,
        "callback_query": {
            "id": "cbq-1",
            "from": {"id": 555, "is_bot": False, "first_name": "Test"},
            "message": {
                "message_id": 31,
                "date": 1700000002,
                "chat": {"id": 202, "type": "private"},
                "from": {"id": 555, "is_bot": False, "first_name": "Test"},
                "text": "I received your photo.",
            },
            "data": f"s:{session_id}:confirm",
        },
    }

    response = client.post("/telegram/webhook", json=payload)

    assert response.status_code == 200
    assert telegram_client.callbacks
    assert telegram_client.messages
    assert "main item" in telegram_client.messages[-1][1].lower()


def test_webhook_save_creates_meal_log(
    container, telegram_client: FakeTelegramClient
) -> None:
    app = create_app(container)
    client = TestClient(app)

    user = container.user_service.ensure_user(telegram_user_id=777)
    session = container.session_service.session_repository.create_session(
        user_id=user.id,
        photo_id=uuid4(),
        status="AWAITING_SAVE",
        context={
            "resolved_items": [{"label": "Kirkland chicken breast", "grams": 200}]
        },
    )

    payload = {
        "update_id": 4,
        "callback_query": {
            "id": "cbq-2",
            "from": {"id": 777, "is_bot": False, "first_name": "Test"},
            "message": {
                "message_id": 40,
                "date": 1700000003,
                "chat": {"id": 303, "type": "private"},
                "from": {"id": 777, "is_bot": False, "first_name": "Test"},
                "text": "Summary",
            },
            "data": f"s:{session.id}:save",
        },
    }

    response = client.post("/telegram/webhook", json=payload)

    assert response.status_code == 200
    assert telegram_client.messages
    assert "meal saved" in telegram_client.messages[-1][1].lower()
    repo = container.meal_log_service.repository
    assert isinstance(repo, InMemoryMealLogRepository)
    assert repo.meals


def test_webhook_today_command_returns_totals(
    container, telegram_client: FakeTelegramClient
) -> None:
    app = create_app(container)
    client = TestClient(app)

    repo = container.stats_service.repository
    assert isinstance(repo, InMemoryStatsRepository)
    repo.logs.append(
        MealLogRow(
            logged_at=datetime.now(tz=UTC),
            total_calories=700,
            total_protein_g=40,
            total_fat_g=20,
            total_carbs_g=60,
        )
    )

    payload = {
        "update_id": 5,
        "message": {
            "message_id": 50,
            "date": 1700000004,
            "chat": {"id": 404, "type": "private"},
            "from": {"id": 888, "is_bot": False, "first_name": "Test"},
            "text": "/today",
        },
    }

    response = client.post("/telegram/webhook", json=payload)

    assert response.status_code == 200
    assert telegram_client.messages
    assert "calories" in telegram_client.messages[-1][1].lower()
