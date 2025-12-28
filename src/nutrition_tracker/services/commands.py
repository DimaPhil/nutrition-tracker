"""Command handlers for Telegram updates."""

from dataclasses import dataclass

from nutrition_tracker.adapters.telegram_client import TelegramClient
from nutrition_tracker.services.user_settings import UserSettingsService
from nutrition_tracker.services.users import UserService


@dataclass
class StartCommandHandler:
    """Handle the /start Telegram command."""

    user_service: UserService
    user_settings_service: UserSettingsService
    telegram_client: TelegramClient

    async def handle(self, telegram_user_id: int, chat_id: int) -> None:
        """Create the user if needed and send a welcome message."""
        user = self.user_service.ensure_user(telegram_user_id)
        if self.user_settings_service.is_timezone_set(user.id):
            await self.telegram_client.send_message(
                chat_id=chat_id,
                text="Welcome back! Your timezone is already set.",
            )
            return
        await self.telegram_client.send_message(
            chat_id=chat_id,
            text=(
                "Welcome to Nutrition Tracker! "
                "Please reply with your timezone (e.g., America/Los_Angeles)."
            ),
        )
