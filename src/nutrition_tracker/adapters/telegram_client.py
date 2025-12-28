"""Telegram API client adapter."""

from dataclasses import dataclass
from typing import Protocol

import httpx


class TelegramClient(Protocol):
    """Interface for Telegram API interactions."""

    async def send_message(
        self, chat_id: int, text: str, reply_markup: dict | None = None
    ) -> None:
        """Send a text message to a Telegram chat."""

    async def answer_callback_query(
        self, callback_query_id: str, text: str | None = None
    ) -> None:
        """Answer a Telegram callback query."""

    async def set_my_commands(self, commands: list[dict[str, str]]) -> None:
        """Set the bot command list."""

    async def set_chat_menu_button(
        self, menu_button: dict[str, object] | None = None
    ) -> None:
        """Set the chat menu button."""


@dataclass
class HttpxTelegramClient:
    """Telegram client implemented with httpx."""

    bot_token: str
    http_client: httpx.AsyncClient

    @classmethod
    def create(cls, bot_token: str) -> "HttpxTelegramClient":
        """Create a Telegram client with a managed httpx session."""
        return cls(bot_token=bot_token, http_client=httpx.AsyncClient())

    async def send_message(
        self, chat_id: int, text: str, reply_markup: dict | None = None
    ) -> None:
        """Send a message using Telegram's sendMessage API."""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload: dict[str, object] = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        response = await self.http_client.post(url, json=payload, timeout=10)
        response.raise_for_status()

    async def answer_callback_query(
        self, callback_query_id: str, text: str | None = None
    ) -> None:
        """Answer a callback query using Telegram's API."""
        url = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"
        payload: dict[str, object] = {"callback_query_id": callback_query_id}
        if text is not None:
            payload["text"] = text
        response = await self.http_client.post(url, json=payload, timeout=10)
        response.raise_for_status()

    async def close(self) -> None:
        """Close the underlying HTTP client session."""
        await self.http_client.aclose()

    async def set_my_commands(self, commands: list[dict[str, str]]) -> None:
        """Set the bot command list."""
        url = f"https://api.telegram.org/bot{self.bot_token}/setMyCommands"
        payload: dict[str, object] = {"commands": commands}
        response = await self.http_client.post(url, json=payload, timeout=10)
        response.raise_for_status()

    async def set_chat_menu_button(
        self, menu_button: dict[str, object] | None = None
    ) -> None:
        """Set the chat menu button."""
        url = f"https://api.telegram.org/bot{self.bot_token}/setChatMenuButton"
        payload: dict[str, object] = {
            "menu_button": menu_button or {"type": "commands"}
        }
        response = await self.http_client.post(url, json=payload, timeout=10)
        response.raise_for_status()
