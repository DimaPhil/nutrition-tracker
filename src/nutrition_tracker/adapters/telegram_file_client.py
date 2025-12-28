"""Telegram file download client."""

from dataclasses import dataclass
from typing import Protocol

import httpx


class TelegramFileClient(Protocol):
    """Interface for downloading Telegram files."""

    async def download_file_bytes(self, file_id: str) -> bytes:
        """Download a Telegram file and return its bytes."""


@dataclass
class HttpxTelegramFileClient(TelegramFileClient):
    """Telegram file client using httpx."""

    bot_token: str
    http_client: httpx.AsyncClient

    @classmethod
    def create(cls, bot_token: str) -> "HttpxTelegramFileClient":
        """Create a Telegram file client with a managed httpx session."""
        return cls(bot_token=bot_token, http_client=httpx.AsyncClient())

    async def download_file_bytes(self, file_id: str) -> bytes:
        """Download Telegram file bytes via getFile."""
        get_file_url = f"https://api.telegram.org/bot{self.bot_token}/getFile"
        response = await self.http_client.get(
            get_file_url, params={"file_id": file_id}, timeout=10
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError("Telegram getFile failed")
        file_path = payload["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
        file_response = await self.http_client.get(download_url, timeout=20)
        file_response.raise_for_status()
        return file_response.content

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        await self.http_client.aclose()
