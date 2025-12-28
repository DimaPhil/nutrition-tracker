"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, Request

from nutrition_tracker.api.admin import router as admin_router
from nutrition_tracker.api.telegram_models import TelegramPhotoSize, TelegramUpdate
from nutrition_tracker.containers import AppContainer
from nutrition_tracker.domain.meals import MealLogSummary
from nutrition_tracker.domain.stats import DailyTotals, MealLogRow
from nutrition_tracker.services.stats import PeriodSummary


def create_app(container: AppContainer) -> FastAPI:  # noqa: PLR0915
    """Create a FastAPI app configured with dependencies."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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
    async def telegram_webhook(  # noqa: PLR0912, PLR0915
        update: TelegramUpdate, request: Request
    ) -> dict[str, str]:
        """Handle Telegram webhook updates."""
        state_container: AppContainer = request.app.state.container
        if update.callback_query:
            callback = update.callback_query
            await state_container.telegram_client.answer_callback_query(callback.id)
            if callback.data:
                parsed = _parse_callback(callback.data)
                if parsed:
                    session_id, action = parsed
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
                        prompt = state_container.session_service.handle_callback(
                            session_id, action
                        )
                        if prompt and callback.message:
                            await state_container.telegram_client.send_message(
                                chat_id=callback.message.chat.id,
                                text=prompt.text,
                                reply_markup=prompt.reply_markup,
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
                daily = state_container.stats_service.get_today(user.id, timezone)
                await state_container.telegram_client.send_message(
                    chat_id=message.chat.id,
                    text=_format_daily_totals("Today", daily),
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
                )
            return {"status": "ok"}

        if message and message.photo:
            user = state_container.user_service.ensure_user(message.from_user.id)
            photo = _select_largest_photo(message.photo)
            try:
                image_bytes = (
                    await state_container.telegram_file_client.download_file_bytes(
                        photo.file_id
                    )
                )
                vision_result = await state_container.vision_service.extract(
                    image_bytes
                )
                vision_items = [item.model_dump() for item in vision_result.items]
                _, prompt = state_container.session_service.start_session(
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
            except Exception:
                await state_container.telegram_client.send_message(
                    chat_id=message.chat.id,
                    text=(
                        "Sorry, I couldn't process that photo. "
                        "Please try sending it again."
                    ),
                )
            return {"status": "ok"}

        if message and message.text:
            user = state_container.user_service.ensure_user(message.from_user.id)
            prompt = state_container.session_service.handle_text(user.id, message.text)
            if prompt:
                await state_container.telegram_client.send_message(
                    chat_id=message.chat.id,
                    text=prompt.text,
                    reply_markup=prompt.reply_markup,
                )
        return {"status": "ok"}

    return app


def _select_largest_photo(photos: list[TelegramPhotoSize]) -> TelegramPhotoSize:
    """Select the largest photo size from the Telegram payload."""
    return max(photos, key=lambda photo: (photo.width * photo.height))


def _parse_callback(data: str) -> tuple[UUID, str] | None:
    """Parse callback data in the format s:<uuid>:<action>."""
    if not data.startswith("s:"):
        return None
    parts = data.split(":", maxsplit=2)
    if len(parts) != CALLBACK_PARTS:
        return None
    _, session_id, action = parts
    try:
        return UUID(session_id), action
    except ValueError:
        return None


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
        lines.append(f"- {item.name}: {item.grams:.0f}g ({item.calories:.0f} kcal)")
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


def _format_period_summary(label: str, summary: PeriodSummary) -> str:
    """Format weekly or monthly totals."""
    return (
        f"{label} averages:\\n"
        f"Calories: {summary.avg_calories:.0f}\\n"
        f"Protein: {summary.avg_protein_g:.1f} g\\n"
        f"Fat: {summary.avg_fat_g:.1f} g\\n"
        f"Carbs: {summary.avg_carbs_g:.1f} g"
    )


def _format_history(history: list[MealLogRow]) -> str:
    """Format recent meal history for Telegram."""
    if not history:
        return "No recent meals logged."
    lines = ["Recent meals:"]
    for entry in history:
        lines.append(f"- {entry.logged_at.date()}: {entry.total_calories:.0f} kcal")
    return "\n".join(lines)


CALLBACK_PARTS = 3
