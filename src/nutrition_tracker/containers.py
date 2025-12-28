"""Dependency container wiring for the application."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from supabase import create_client

from nutrition_tracker.adapters.fdc_client import HttpxFdcClient
from nutrition_tracker.adapters.openai_vision_client import OpenAIVisionClient
from nutrition_tracker.adapters.supabase_admin_repository import SupabaseAdminRepository
from nutrition_tracker.adapters.supabase_library_repository import (
    SupabaseLibraryRepository,
)
from nutrition_tracker.adapters.supabase_meal_log_repository import (
    SupabaseMealLogRepository,
)
from nutrition_tracker.adapters.supabase_photo_repository import SupabasePhotoRepository
from nutrition_tracker.adapters.supabase_session_repository import (
    SupabaseSessionRepository,
)
from nutrition_tracker.adapters.supabase_stats_repository import SupabaseStatsRepository
from nutrition_tracker.adapters.supabase_user_repository import SupabaseUserRepository
from nutrition_tracker.adapters.supabase_user_settings_repository import (
    SupabaseUserSettingsRepository,
)
from nutrition_tracker.adapters.telegram_client import (
    HttpxTelegramClient,
    TelegramClient,
)
from nutrition_tracker.adapters.telegram_file_client import (
    HttpxTelegramFileClient,
    TelegramFileClient,
)
from nutrition_tracker.config import Settings
from nutrition_tracker.services.admin import AdminService
from nutrition_tracker.services.cache import InMemoryCache
from nutrition_tracker.services.commands import StartCommandHandler
from nutrition_tracker.services.library import LibraryService
from nutrition_tracker.services.meals import MealLogService
from nutrition_tracker.services.nutrition import NutritionService
from nutrition_tracker.services.sessions import SessionService
from nutrition_tracker.services.stats import StatsService
from nutrition_tracker.services.user_settings import UserSettingsService
from nutrition_tracker.services.users import UserService
from nutrition_tracker.services.vision import VisionService


@dataclass
class AppContainer:
    """Holds application-wide dependencies."""

    settings: Settings
    telegram_client: TelegramClient
    telegram_file_client: TelegramFileClient
    user_service: UserService
    start_command_handler: StartCommandHandler
    session_service: SessionService
    vision_service: VisionService
    nutrition_service: NutritionService
    library_service: LibraryService
    meal_log_service: MealLogService
    stats_service: StatsService
    user_settings_service: UserSettingsService
    admin_service: AdminService
    close_resources: Callable[[], Awaitable[None]]


def build_container(settings: Settings | None = None) -> AppContainer:
    """Create the default dependency container."""
    resolved_settings = settings or Settings()
    supabase_client = create_client(
        resolved_settings.supabase_url, resolved_settings.supabase_service_key
    )
    user_repository = SupabaseUserRepository(supabase_client)
    photo_repository = SupabasePhotoRepository(supabase_client)
    session_repository = SupabaseSessionRepository(supabase_client)
    library_repository = SupabaseLibraryRepository(supabase_client)
    meal_log_repository = SupabaseMealLogRepository(supabase_client)
    stats_repository = SupabaseStatsRepository(supabase_client)
    user_settings_repository = SupabaseUserSettingsRepository(supabase_client)
    admin_repository = SupabaseAdminRepository(supabase_client)
    user_service = UserService(user_repository)
    session_service = SessionService(photo_repository, session_repository)
    telegram_client = HttpxTelegramClient.create(resolved_settings.telegram_bot_token)
    telegram_file_client = HttpxTelegramFileClient.create(
        resolved_settings.telegram_bot_token
    )
    openai_client = OpenAIVisionClient.create(resolved_settings.openai_api_key)
    vision_service = VisionService(
        client=openai_client,
        model=resolved_settings.openai_model,
        reasoning_effort=resolved_settings.openai_reasoning_effort,
        store=resolved_settings.openai_store,
    )
    fdc_client = HttpxFdcClient.create(
        api_key=resolved_settings.fdc_api_key,
        base_url=resolved_settings.fdc_base_url,
    )
    nutrition_service = NutritionService(
        fdc_client=fdc_client,
        cache=InMemoryCache(),
    )
    library_service = LibraryService(library_repository)
    meal_log_service = MealLogService(
        nutrition_service=nutrition_service,
        repository=meal_log_repository,
    )
    stats_service = StatsService(stats_repository)
    user_settings_service = UserSettingsService(user_settings_repository)
    admin_service = AdminService(
        admin_repository=admin_repository,
        stats_repository=stats_repository,
        library_repository=library_repository,
    )
    start_handler = StartCommandHandler(user_service, telegram_client)

    async def close_resources() -> None:
        await telegram_client.close()
        await telegram_file_client.close()
        await fdc_client.close()

    return AppContainer(
        settings=resolved_settings,
        telegram_client=telegram_client,
        telegram_file_client=telegram_file_client,
        user_service=user_service,
        start_command_handler=start_handler,
        session_service=session_service,
        vision_service=vision_service,
        nutrition_service=nutrition_service,
        library_service=library_service,
        meal_log_service=meal_log_service,
        stats_service=stats_service,
        user_settings_service=user_settings_service,
        admin_service=admin_service,
        close_resources=close_resources,
    )
