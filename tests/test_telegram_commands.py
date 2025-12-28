"""Tests for Telegram command definitions."""

from nutrition_tracker.telegram_commands import BotCommand, telegram_commands


def test_telegram_commands_include_start() -> None:
    commands = telegram_commands()

    assert {"command": "start", "description": "Onboarding and timezone setup"} in (
        commands
    )
    assert len(commands) == len(list(BotCommand))
