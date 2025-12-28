"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request

from nutrition_tracker.api.admin import router as admin_router
from nutrition_tracker.api.telegram_models import TelegramPhotoSize, TelegramUpdate
from nutrition_tracker.app_logging import configure_logging
from nutrition_tracker.config import parse_allowed_user_ids
from nutrition_tracker.containers import AppContainer
from nutrition_tracker.domain.library import LibraryFood
from nutrition_tracker.domain.meals import MealLogDetail, MealLogSummary
from nutrition_tracker.domain.stats import DailyTotals, MealLogRow
from nutrition_tracker.services.stats import PeriodSummary
from nutrition_tracker.telegram_commands import CHAT_MENU_BUTTON, telegram_commands


def create_app(container: AppContainer) -> FastAPI:  # noqa: PLR0915
    """Create a FastAPI app configured with dependencies."""
    configure_logging()
    logger = logging.getLogger(__name__)
    allowed_user_ids = parse_allowed_user_ids(
        container.settings.telegram_allowed_user_ids
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            await app.state.container.telegram_client.set_my_commands(
                telegram_commands()
            )
            await app.state.container.telegram_client.set_chat_menu_button(
                CHAT_MENU_BUTTON
            )
        except Exception:
            logger.exception("Failed to sync Telegram bot commands")
        yield
        await app.state.container.close_resources()

    app = FastAPI(lifespan=lifespan)
    app.state.container = container

    app.include_router(admin_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Simple health check endpoint."""
        return {"status": "ok"}

    @app.post("/telegram/webhook")
    async def telegram_webhook(  # noqa: PLR0911, PLR0912, PLR0915
        update: TelegramUpdate, request: Request
    ) -> dict[str, str]:
        """Handle Telegram webhook updates."""
        state_container: AppContainer = request.app.state.container
        user_id = _extract_user_id(update)
        if user_id is not None and not _is_user_allowed(user_id, allowed_user_ids):
            if update.callback_query:
                await state_container.telegram_client.answer_callback_query(
                    update.callback_query.id,
                    text="Not authorized.",
                )
                return {"status": "ok"}
            if update.message:
                await state_container.telegram_client.send_message(
                    chat_id=update.message.chat.id,
                    text="This bot is private.",
                )
                return {"status": "ok"}
        if update.callback_query:
            callback = update.callback_query
            await state_container.telegram_client.answer_callback_query(callback.id)
            if callback.data:
                session_callback = _parse_session_callback(callback.data)
                if session_callback:
                    session_id, action, payload = session_callback
                    if action == "save":
                        session_repository = (
                            state_container.session_service.session_repository
                        )
                        session = session_repository.get_session(session_id)
                        if session and callback.message:
                            resolved_items = session.context.get("resolved_items", [])
                            summary = await state_container.meal_log_service.save_meal(
                                user_id=session.user_id,
                                items=(
                                    resolved_items
                                    if isinstance(resolved_items, list)
                                    else []
                                ),
                            )
                            if session.photo_id:
                                state_container.session_service.photo_repository.delete_photo(
                                    session.photo_id
                                )
                            state_container.session_service.session_repository.update_session(
                                session_id,
                                status="COMPLETED",
                                context=session.context,
                            )
                            await state_container.telegram_client.send_message(
                                chat_id=callback.message.chat.id,
                                text=_format_meal_summary(summary),
                            )
                    else:
                        prompt = await state_container.session_service.handle_callback(
                            session_id, action, payload
                        )
                        if prompt and callback.message:
                            await state_container.telegram_client.send_message(
                                chat_id=callback.message.chat.id,
                                text=prompt.text,
                                reply_markup=prompt.reply_markup,
                            )
                history_id = _parse_history_callback(callback.data)
                if history_id and callback.message:
                    detail = state_container.meal_log_service.get_meal_detail(
                        history_id
                    )
                    if detail:
                        await state_container.telegram_client.send_message(
                            chat_id=callback.message.chat.id,
                            text=_format_meal_detail(detail),
                            reply_markup=_history_detail_keyboard(history_id),
                        )
                edit_id = _parse_edit_callback(callback.data)
                if edit_id and callback.message:
                    user = state_container.user_service.ensure_user(
                        callback.from_user.id
                    )
                    session_repo = state_container.session_service.session_repository
                    active = session_repo.get_active_session(user.id)
                    if active and active.status not in {"COMPLETED", "CANCELLED"}:
                        await state_container.telegram_client.send_message(
                            chat_id=callback.message.chat.id,
                            text=(
                                "You already have an active session. "
                                "Send /cancel to stop it."
                            ),
                        )
                        return {"status": "ok"}
                    prompt = state_container.session_service.start_edit_session(
                        user.id, edit_id
                    )
                    if prompt:
                        await state_container.telegram_client.send_message(
                            chat_id=callback.message.chat.id,
                            text=prompt.text,
                            reply_markup=prompt.reply_markup,
                        )
                library_action = _parse_library_callback(callback.data)
                if library_action == "add" and callback.message:
                    user = state_container.user_service.ensure_user(
                        callback.from_user.id
                    )
                    session_repo = state_container.session_service.session_repository
                    active = session_repo.get_active_session(user.id)
                    if active and active.status not in {"COMPLETED", "CANCELLED"}:
                        await state_container.telegram_client.send_message(
                            chat_id=callback.message.chat.id,
                            text=(
                                "You already have an active session. "
                                "Send /cancel to stop it."
                            ),
                        )
                        return {"status": "ok"}
                    prompt = state_container.session_service.start_library_add_session(
                        user.id
                    )
                    await state_container.telegram_client.send_message(
                        chat_id=callback.message.chat.id, text=prompt.text
                    )
            return {"status": "ok"}

        message = update.message
        if message and message.text and message.text.startswith("/start"):
            await state_container.start_command_handler.handle(
                telegram_user_id=message.from_user.id,
                chat_id=message.chat.id,
            )
            return {"status": "ok"}

        if message and message.text in {"/today", "/week", "/month", "/history"}:
            user = state_container.user_service.ensure_user(message.from_user.id)
            timezone = state_container.user_settings_service.get_timezone(user.id)
            if message.text == "/today":
                daily, logs = state_container.stats_service.get_today_with_logs(
                    user.id, timezone
                )
                await state_container.telegram_client.send_message(
                    chat_id=message.chat.id,
                    text=_format_daily_with_logs("Today", daily, logs),
                )
            elif message.text == "/week":
                summary = state_container.stats_service.get_week(user.id, timezone)
                await state_container.telegram_client.send_message(
                    chat_id=message.chat.id,
                    text=_format_period_summary("This week", summary),
                )
            elif message.text == "/month":
                summary = state_container.stats_service.get_month(user.id, timezone)
                await state_container.telegram_client.send_message(
                    chat_id=message.chat.id,
                    text=_format_period_summary("This month", summary),
                )
            else:
                history = state_container.stats_service.get_history(user.id, limit=10)
                await state_container.telegram_client.send_message(
                    chat_id=message.chat.id,
                    text=_format_history(history),
                    reply_markup=_history_keyboard(history),
                )
            return {"status": "ok"}

        if message and message.text == "/library":
            user = state_container.user_service.ensure_user(message.from_user.id)
            session_repo = state_container.session_service.session_repository
            active = session_repo.get_active_session(user.id)
            if active and active.status not in {"COMPLETED", "CANCELLED"}:
                await state_container.telegram_client.send_message(
                    chat_id=message.chat.id,
                    text="You already have an active session. Send /cancel to stop it.",
                )
                return {"status": "ok"}
            foods = state_container.library_service.search(user.id, None, limit=5)
            await state_container.telegram_client.send_message(
                chat_id=message.chat.id,
                text=_format_library(foods),
                reply_markup=_library_keyboard(),
            )
            return {"status": "ok"}

        if message and message.text == "/cancel":
            user = state_container.user_service.ensure_user(message.from_user.id)
            prompt = state_container.session_service.cancel_active_session(user.id)
            if prompt:
                await state_container.telegram_client.send_message(
                    chat_id=message.chat.id, text=prompt.text
                )
            else:
                await state_container.telegram_client.send_message(
                    chat_id=message.chat.id, text="No active session to cancel."
                )
            return {"status": "ok"}

        if message and message.photo:
            user = state_container.user_service.ensure_user(message.from_user.id)
            session_repo = state_container.session_service.session_repository
            active = session_repo.get_active_session(user.id)
            if active and active.status not in {"COMPLETED", "CANCELLED"}:
                await state_container.telegram_client.send_message(
                    chat_id=message.chat.id,
                    text="You already have an active session. Send /cancel to stop it.",
                )
                return {"status": "ok"}
            photo = _select_largest_photo(message.photo)
            try:
                image_bytes = (
                    await state_container.telegram_file_client.download_file_bytes(
                        photo.file_id
                    )
                )
            except Exception as exc:
                logger.exception(
                    "Failed to download Telegram photo",
                    extra={"file_id": photo.file_id},
                )
                await state_container.telegram_client.send_message(
                    chat_id=message.chat.id,
                    text=_format_photo_error(
                        state_container, exc, "Couldn't download that photo."
                    ),
                )
                return {"status": "ok"}

            try:
                vision_result = await state_container.vision_service.extract(
                    image_bytes
                )
            except Exception as exc:
                logger.exception(
                    "Vision extraction failed",
                    extra={"file_id": photo.file_id},
                )
                await state_container.telegram_client.send_message(
                    chat_id=message.chat.id,
                    text=_format_photo_error(
                        state_container,
                        exc,
                        (
                            "Sorry, I couldn't analyze that photo. "
                            "Please try a clearer shot."
                        ),
                    ),
                )
                return {"status": "ok"}

            try:
                vision_items = [item.model_dump() for item in vision_result.items]
                _, prompt = await state_container.session_service.start_session(
                    user_id=user.id,
                    telegram_chat_id=message.chat.id,
                    telegram_message_id=message.message_id,
                    telegram_file_id=photo.file_id,
                    telegram_file_unique_id=photo.file_unique_id,
                    vision_items=vision_items,
                )
                await state_container.telegram_client.send_message(
                    chat_id=message.chat.id,
                    text=prompt.text,
                    reply_markup=prompt.reply_markup,
                )
            except Exception as exc:
                logger.exception("Failed to start session", extra={"user_id": user.id})
                await state_container.telegram_client.send_message(
                    chat_id=message.chat.id,
                    text=_format_photo_error(
                        state_container,
                        exc,
                        ("Sorry, I couldn't start a meal session. Please try again."),
                    ),
                )
            return {"status": "ok"}

        if message and message.text:
            user = state_container.user_service.ensure_user(message.from_user.id)
            prompt = await state_container.session_service.handle_text(
                user.id, message.text
            )
            if prompt:
                await state_container.telegram_client.send_message(
                    chat_id=message.chat.id,
                    text=prompt.text,
                    reply_markup=prompt.reply_markup,
                )
                return {"status": "ok"}
            if not state_container.user_settings_service.is_timezone_set(user.id):
                timezone = message.text.strip()
                if _is_valid_timezone(timezone):
                    state_container.user_settings_service.set_timezone(
                        user.id, timezone
                    )
                    await state_container.telegram_client.send_message(
                        chat_id=message.chat.id,
                        text=f"Timezone saved: {timezone}.",
                    )
                else:
                    await state_container.telegram_client.send_message(
                        chat_id=message.chat.id,
                        text=("Please send a valid timezone like America/Los_Angeles."),
                    )
        return {"status": "ok"}

    return app


def _select_largest_photo(photos: list[TelegramPhotoSize]) -> TelegramPhotoSize:
    """Select the largest photo size from the Telegram payload."""
    return max(photos, key=lambda photo: (photo.width * photo.height))


def _extract_user_id(update: TelegramUpdate) -> int | None:
    """Extract Telegram user id from update, if present."""
    if update.callback_query:
        return update.callback_query.from_user.id
    if update.message:
        return update.message.from_user.id
    return None


def _is_user_allowed(user_id: int, allowed: set[int] | None) -> bool:
    """Return true when the user is allowed to interact with the bot."""
    return allowed is None or user_id in allowed


def _format_photo_error(
    state_container: AppContainer, exc: Exception, fallback: str
) -> str:
    """Return a user-facing photo error message with local debug info."""
    if state_container.settings.environment == "local":
        detail = f"{type(exc).__name__}: {exc}".strip()
        if detail:
            return f"{fallback} (debug: {detail})"
    return fallback


def _parse_session_callback(data: str) -> tuple[UUID, str, str | None] | None:
    """Parse callback data in the format s:<uuid>:<action>[:payload]."""
    if not data.startswith("s:"):
        return None
    parts = data.split(":", maxsplit=3)
    if len(parts) not in {3, 4}:
        return None
    _, session_id, action, *rest = parts
    payload = rest[0] if rest else None
    try:
        return UUID(session_id), action, payload
    except ValueError:
        return None


def _parse_history_callback(data: str) -> UUID | None:
    if not data.startswith("h:"):
        return None
    _, raw_id = data.split(":", maxsplit=1)
    try:
        return UUID(raw_id)
    except ValueError:
        return None


def _parse_edit_callback(data: str) -> UUID | None:
    if not data.startswith("e:"):
        return None
    _, raw_id = data.split(":", maxsplit=1)
    try:
        return UUID(raw_id)
    except ValueError:
        return None


def _parse_library_callback(data: str) -> str | None:
    if not data.startswith("lib:"):
        return None
    _, action = data.split(":", maxsplit=1)
    return action


def _format_meal_summary(summary: MealLogSummary) -> str:
    """Format a meal summary for Telegram messages."""
    lines = [
        "Meal saved!",
        f"Total: {summary.total_calories:.0f} kcal, "
        f"{summary.total_protein_g:.1f}P / "
        f"{summary.total_fat_g:.1f}F / "
        f"{summary.total_carbs_g:.1f}C",
        "Items:",
    ]
    for item in summary.items:
        lines.append(
            f"- {item.name}: {item.grams:.0f}g — {item.calories:.0f} kcal "
            f"({item.protein_g:.1f}P/{item.fat_g:.1f}F/{item.carbs_g:.1f}C)"
        )
    return "\n".join(lines)


def _format_daily_totals(label: str, totals: DailyTotals) -> str:
    """Format daily totals for Telegram."""
    return (
        f"{label} totals:\\n"
        f"Calories: {totals.calories:.0f}\\n"
        f"Protein: {totals.protein_g:.1f} g\\n"
        f"Fat: {totals.fat_g:.1f} g\\n"
        f"Carbs: {totals.carbs_g:.1f} g"
    )


def _format_daily_with_logs(
    label: str, totals: DailyTotals, logs: list[MealLogRow]
) -> str:
    """Format daily totals with per-meal list."""
    lines = [
        _format_daily_totals(label, totals),
    ]
    if logs:
        lines.append("Meals:")
        for log in logs:
            lines.append(
                f"- {log.logged_at.time().strftime('%H:%M')}: "
                f"{log.total_calories:.0f} kcal"
            )
    return "\n".join(lines)


def _format_period_summary(label: str, summary: PeriodSummary) -> str:
    """Format weekly or monthly totals."""
    lines = [
        f"{label} averages:",
        f"Calories: {summary.avg_calories:.0f}",
        f"Protein: {summary.avg_protein_g:.1f} g",
        f"Fat: {summary.avg_fat_g:.1f} g",
        f"Carbs: {summary.avg_carbs_g:.1f} g",
        "Daily totals:",
    ]
    for day in summary.daily:
        lines.append(f"- {day.day}: {day.calories:.0f} kcal")
    return "\n".join(lines)


def _format_history(history: list[MealLogRow]) -> str:
    """Format recent meal history for Telegram."""
    if not history:
        return "No recent meals logged."
    lines = ["Recent meals:"]
    for entry in history:
        lines.append(f"- {entry.logged_at.date()}: {entry.total_calories:.0f} kcal")
    return "\n".join(lines)


def _format_library(foods: list[LibraryFood]) -> str:
    if not foods:
        return "Your library is empty. Add a manual entry to get started."
    lines = ["Your top foods:"]
    for food in foods:
        lines.append(f"- {food.name} ({food.calories:.0f} kcal per 100g)")
    return "\n".join(lines)


def _history_keyboard(history: list[MealLogRow]) -> dict | None:
    if not history:
        return None
    return {
        "inline_keyboard": [
            [
                {
                    "text": _history_button_label(entry),
                    "callback_data": f"h:{entry.meal_id}",
                }
            ]
            for entry in history
        ]
    }


def _history_detail_keyboard(meal_id: UUID) -> dict:
    return {
        "inline_keyboard": [[{"text": "Edit grams", "callback_data": f"e:{meal_id}"}]]
    }


def _library_keyboard() -> dict:
    return {
        "inline_keyboard": [[{"text": "Add manual entry", "callback_data": "lib:add"}]]
    }


def _format_meal_detail(detail: MealLogDetail) -> str:
    lines = [
        f"Meal: {detail.total_calories:.0f} kcal",
        "Items:",
    ]
    for item in detail.items:
        lines.append(f"- {item.name}: {item.grams:.0f}g — {item.calories:.0f} kcal")
    return "\n".join(lines)


def _history_button_label(entry: MealLogRow) -> str:
    return f"{entry.logged_at.date()} — {entry.total_calories:.0f} kcal"


def _is_valid_timezone(value: str) -> bool:
    try:
        ZoneInfo(value)
    except Exception:
        return False
    return True
