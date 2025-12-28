"""Pydantic models for Telegram webhook payloads."""

from pydantic import BaseModel, Field


class TelegramUser(BaseModel):
    """Telegram user payload."""

    id: int
    is_bot: bool | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None


class TelegramChat(BaseModel):
    """Telegram chat payload."""

    id: int
    type: str
    title: str | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class TelegramPhotoSize(BaseModel):
    """Telegram photo size payload."""

    file_id: str
    file_unique_id: str
    width: int
    height: int
    file_size: int | None = None


class TelegramMessage(BaseModel):
    """Telegram message payload."""

    message_id: int
    date: int
    chat: TelegramChat
    from_user: TelegramUser = Field(alias="from")
    text: str | None = None
    photo: list[TelegramPhotoSize] | None = None


class TelegramCallbackQuery(BaseModel):
    """Telegram callback query payload."""

    id: str
    from_user: TelegramUser = Field(alias="from")
    message: TelegramMessage | None = None
    data: str | None = None


class TelegramUpdate(BaseModel):
    """Telegram update payload."""

    update_id: int
    message: TelegramMessage | None = None
    callback_query: TelegramCallbackQuery | None = None
