"""Tests for HTTP-based adapters."""

import asyncio
import json

import httpx

from nutrition_tracker.adapters.fdc_client import HttpxFdcClient
from nutrition_tracker.adapters.openai_vision_client import OpenAIVisionClient
from nutrition_tracker.adapters.telegram_client import HttpxTelegramClient
from nutrition_tracker.adapters.telegram_file_client import HttpxTelegramFileClient


class _FakeResponses:
    def __init__(self) -> None:
        self.last_payload: dict[str, object] | None = None

    async def create(self, **kwargs):  # type: ignore[no-untyped-def]
        self.last_payload = kwargs
        return type("Resp", (), {"output_text": json.dumps({"items": []})})()


class _FakeOpenAI:
    def __init__(self) -> None:
        self.responses = _FakeResponses()


def test_openai_vision_client_parses_output() -> None:
    client = OpenAIVisionClient(client=_FakeOpenAI())

    result = asyncio.run(
        client.extract(
            model="gpt-5.2",
            reasoning_effort="high",
            store=False,
            image_data_url="data:image/jpeg;base64,ZmFrZQ==",
            schema={"type": "object"},
            prompt="Detect foods",
        )
    )

    assert result == {"items": []}


def test_telegram_client_send_and_callback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/sendMessage") or request.url.path.endswith(
            "/answerCallbackQuery"
        )
        return httpx.Response(200, json={"ok": True, "result": {}})

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport)
    client = HttpxTelegramClient(bot_token="token", http_client=async_client)

    asyncio.run(client.send_message(chat_id=1, text="Hi"))
    asyncio.run(client.answer_callback_query(callback_query_id="cbq-1"))


def test_telegram_client_commands_and_menu_button() -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        payload = json.loads(request.content.decode())
        if request.url.path.endswith("/setMyCommands"):
            assert payload["commands"][0]["command"] == "start"
        if request.url.path.endswith("/setChatMenuButton"):
            assert payload["menu_button"]["type"] == "commands"
        return httpx.Response(200, json={"ok": True, "result": True})

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport)
    client = HttpxTelegramClient(bot_token="token", http_client=async_client)

    asyncio.run(
        client.set_my_commands(
            [{"command": "start", "description": "Onboarding and timezone setup"}]
        )
    )
    asyncio.run(client.set_chat_menu_button({"type": "commands"}))

    assert any(path.endswith("/setMyCommands") for path in seen_paths)
    assert any(path.endswith("/setChatMenuButton") for path in seen_paths)


def test_telegram_file_client_downloads_bytes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/getFile"):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {"file_path": "photos/file.jpg"},
                },
            )
        return httpx.Response(200, content=b"image-bytes")

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport)
    client = HttpxTelegramFileClient(bot_token="token", http_client=async_client)

    data = asyncio.run(client.download_file_bytes("file-id"))

    assert data == b"image-bytes"


def test_fdc_client_search_and_get() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/foods/search"):
            return httpx.Response(200, json={"foods": []})
        return httpx.Response(200, json={"fdcId": 1, "foodNutrients": []})

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport)
    client = HttpxFdcClient(
        api_key="key",
        base_url="https://api.test",
        http_client=async_client,
    )

    search = asyncio.run(client.search_foods("rice"))
    food = asyncio.run(client.get_food(1))

    assert search == {"foods": []}
    assert food["fdcId"] == 1
