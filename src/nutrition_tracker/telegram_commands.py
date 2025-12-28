"""Telegram bot command configuration."""

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class TelegramCommand:
    """Declarative bot command definition."""

    command: str
    description: str


class BotCommand(Enum):
    """Enum of bot commands (single source of truth)."""

    START = TelegramCommand("start", "Onboarding and timezone setup")
    LOG = TelegramCommand("log", "Send a photo to log a meal")
    TODAY = TelegramCommand("today", "Daily totals")
    WEEK = TelegramCommand("week", "Weekly averages and daily totals")
    MONTH = TelegramCommand("month", "Monthly averages and daily totals")
    HISTORY = TelegramCommand("history", "Last 10 logs with edit")
    LIBRARY = TelegramCommand("library", "Your food library and add new items")
    CANCEL = TelegramCommand("cancel", "Cancel the active session")
    HELP = TelegramCommand("help", "Quick guide and tips")


def telegram_commands() -> list[dict[str, str]]:
    """Return commands formatted for Telegram API."""
    return [
        {"command": entry.value.command, "description": entry.value.description}
        for entry in BotCommand
    ]


CHAT_MENU_BUTTON: dict[str, object] = {"type": "commands"}
