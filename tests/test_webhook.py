"""Tests for Telegram webhook handling."""

import asyncio
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
    session_id, _ = asyncio.run(
        container.session_service.start_session(
            user_id=user.id,
            telegram_chat_id=202,
            telegram_message_id=30,
            telegram_file_id="file-id",
            telegram_file_unique_id="unique-id",
        )
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
    assert "use this" in telegram_client.messages[-1][1].lower()


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
            "resolved_items": [
                {
                    "name": "Kirkland chicken breast",
                    "grams": 200,
                    "source_type": "manual",
                    "basis": "per100g",
                    "calories": 165,
                    "protein_g": 31,
                    "fat_g": 3.6,
                    "carbs_g": 0,
                }
            ]
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
            meal_id=uuid4(),
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


def test_webhook_library_and_add_flow(
    container, telegram_client: FakeTelegramClient
) -> None:
    app = create_app(container)
    client = TestClient(app)

    payload = {
        "update_id": 6,
        "message": {
            "message_id": 60,
            "date": 1700000005,
            "chat": {"id": 505, "type": "private"},
            "from": {"id": 999, "is_bot": False, "first_name": "Test"},
            "text": "/library",
        },
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert telegram_client.messages
    assert "library" in telegram_client.messages[-1][1].lower()

    callback_payload = {
        "update_id": 7,
        "callback_query": {
            "id": "cbq-3",
            "from": {"id": 999, "is_bot": False, "first_name": "Test"},
            "message": {
                "message_id": 61,
                "date": 1700000006,
                "chat": {"id": 505, "type": "private"},
                "from": {"id": 999, "is_bot": False, "first_name": "Test"},
                "text": "Library",
            },
            "data": "lib:add",
        },
    }
    response = client.post("/telegram/webhook", json=callback_payload)
    assert response.status_code == 200
    assert "food name" in telegram_client.messages[-1][1].lower()


def test_webhook_cancel_command_cancels_session(
    container, telegram_client: FakeTelegramClient
) -> None:
    app = create_app(container)
    client = TestClient(app)

    user = container.user_service.ensure_user(telegram_user_id=222)
    session_id, _ = asyncio.run(
        container.session_service.start_session(
            user_id=user.id,
            telegram_chat_id=606,
            telegram_message_id=70,
            telegram_file_id="file-id",
            telegram_file_unique_id="unique-id",
            vision_items=[{"label": "Soup"}],
        )
    )
    payload = {
        "update_id": 8,
        "message": {
            "message_id": 71,
            "date": 1700000007,
            "chat": {"id": 606, "type": "private"},
            "from": {"id": 222, "is_bot": False, "first_name": "Test"},
            "text": "/cancel",
        },
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert "cancelled" in telegram_client.messages[-1][1].lower()
    session = container.session_service.session_repository.get_session(session_id)
    assert session is not None
    assert session.status == "CANCELLED"


def test_webhook_history_callbacks_show_detail_and_edit(
    container, telegram_client: FakeTelegramClient
) -> None:
    app = create_app(container)
    client = TestClient(app)

    user = container.user_service.ensure_user(telegram_user_id=333)
    summary = asyncio.run(
        container.meal_log_service.save_meal(
            user_id=user.id,
            items=[
                {
                    "name": "Yogurt",
                    "grams": 100,
                    "source_type": "manual",
                    "basis": "per100g",
                    "calories": 60,
                    "protein_g": 10,
                    "fat_g": 0,
                    "carbs_g": 4,
                }
            ],
        )
    )
    meal_id = summary.meal_id
    assert meal_id is not None

    payload = {
        "update_id": 9,
        "message": {
            "message_id": 80,
            "date": 1700000008,
            "chat": {"id": 707, "type": "private"},
            "from": {"id": 333, "is_bot": False, "first_name": "Test"},
            "text": "/history",
        },
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert "recent meals" in telegram_client.messages[-1][1].lower()

    view_payload = {
        "update_id": 10,
        "callback_query": {
            "id": "cbq-4",
            "from": {"id": 333, "is_bot": False, "first_name": "Test"},
            "message": {
                "message_id": 81,
                "date": 1700000009,
                "chat": {"id": 707, "type": "private"},
                "from": {"id": 333, "is_bot": False, "first_name": "Test"},
                "text": "History",
            },
            "data": f"h:{meal_id}",
        },
    }
    response = client.post("/telegram/webhook", json=view_payload)
    assert response.status_code == 200
    assert "meal" in telegram_client.messages[-1][1].lower()

    edit_payload = {
        "update_id": 11,
        "callback_query": {
            "id": "cbq-5",
            "from": {"id": 333, "is_bot": False, "first_name": "Test"},
            "message": {
                "message_id": 82,
                "date": 1700000010,
                "chat": {"id": 707, "type": "private"},
                "from": {"id": 333, "is_bot": False, "first_name": "Test"},
                "text": "Meal",
            },
            "data": f"e:{meal_id}",
        },
    }
    response = client.post("/telegram/webhook", json=edit_payload)
    assert response.status_code == 200
    assert "which item" in telegram_client.messages[-1][1].lower()


def test_webhook_timezone_setting(
    container, telegram_client: FakeTelegramClient
) -> None:
    app = create_app(container)
    client = TestClient(app)

    payload = {
        "update_id": 12,
        "message": {
            "message_id": 90,
            "date": 1700000011,
            "chat": {"id": 808, "type": "private"},
            "from": {"id": 444, "is_bot": False, "first_name": "Test"},
            "text": "America/Los_Angeles",
        },
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert "timezone saved" in telegram_client.messages[-1][1].lower()


def test_webhook_week_command_returns_daily_totals(
    container, telegram_client: FakeTelegramClient
) -> None:
    app = create_app(container)
    client = TestClient(app)

    payload = {
        "update_id": 13,
        "message": {
            "message_id": 100,
            "date": 1700000012,
            "chat": {"id": 909, "type": "private"},
            "from": {"id": 5555, "is_bot": False, "first_name": "Test"},
            "text": "/week",
        },
    }
    response = client.post("/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert "daily totals" in telegram_client.messages[-1][1].lower()
