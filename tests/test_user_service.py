"""Tests for user service."""

from nutrition_tracker.services.users import UserService
from tests.conftest import InMemoryUserRepository


def test_ensure_user_creates_user_and_settings() -> None:
    repository = InMemoryUserRepository()
    service = UserService(repository)

    user = service.ensure_user(telegram_user_id=123)

    assert user.telegram_user_id == 123
    assert user.id in repository.settings


def test_ensure_user_touches_existing_user() -> None:
    repository = InMemoryUserRepository()
    service = UserService(repository)

    user = repository.create_user(telegram_user_id=456)
    service.ensure_user(telegram_user_id=456)

    assert repository.touched == [user.id]
