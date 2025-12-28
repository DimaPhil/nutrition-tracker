"""Shared test fixtures."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from nutrition_tracker.adapters.fdc_client import FdcClient
from nutrition_tracker.adapters.telegram_client import TelegramClient
from nutrition_tracker.config import Settings
from nutrition_tracker.containers import AppContainer
from nutrition_tracker.domain.admin import AdminUser
from nutrition_tracker.domain.library import LibraryFood
from nutrition_tracker.domain.meals import MealItemRecord, MealItemSnapshot
from nutrition_tracker.domain.models import UserRecord
from nutrition_tracker.domain.sessions import SessionRecord
from nutrition_tracker.domain.stats import MealLogRow
from nutrition_tracker.services.admin import AdminRepository, AdminService
from nutrition_tracker.services.audit import AuditRepository, AuditService
from nutrition_tracker.services.cache import InMemoryCache
from nutrition_tracker.services.commands import StartCommandHandler
from nutrition_tracker.services.library import LibraryRepository, LibraryService
from nutrition_tracker.services.meals import MealLogRepository, MealLogService
from nutrition_tracker.services.nutrition import NutritionService
from nutrition_tracker.services.sessions import (
    PhotoRepository,
    SessionRepository,
    SessionService,
)
from nutrition_tracker.services.stats import StatsRepository, StatsService
from nutrition_tracker.services.user_settings import (
    UserSettingsRepository,
    UserSettingsService,
)
from nutrition_tracker.services.users import UserRepository, UserService
from nutrition_tracker.services.vision import VisionClient, VisionService


@dataclass
class InMemoryUserRepository(UserRepository):
    """In-memory user repository for tests."""

    users: dict[int, UserRecord] = field(default_factory=dict)
    settings: set[UUID] = field(default_factory=set)
    touched: list[UUID] = field(default_factory=list)

    def get_by_telegram_id(self, telegram_user_id: int) -> UserRecord | None:
        return self.users.get(telegram_user_id)

    def create_user(self, telegram_user_id: int) -> UserRecord:
        user = UserRecord(id=uuid4(), telegram_user_id=telegram_user_id)
        self.users[telegram_user_id] = user
        return user

    def create_settings(self, user_id: UUID, timezone: str | None) -> None:
        self.settings.add(user_id)

    def touch_last_active(self, user_id: UUID) -> None:
        self.touched.append(user_id)


@dataclass
class FakeTelegramClient(TelegramClient):
    """Fake Telegram client that records messages."""

    messages: list[tuple[int, str]] = field(default_factory=list)
    callbacks: list[tuple[str, str | None]] = field(default_factory=list)
    commands: list[dict[str, str]] | None = None
    menu_button: dict[str, object] | None = None

    async def send_message(
        self, chat_id: int, text: str, reply_markup: dict | None = None
    ) -> None:
        self.messages.append((chat_id, text))

    async def answer_callback_query(
        self, callback_query_id: str, text: str | None = None
    ) -> None:
        self.callbacks.append((callback_query_id, text))

    async def set_my_commands(self, commands: list[dict[str, str]]) -> None:
        self.commands = commands

    async def set_chat_menu_button(
        self, menu_button: dict[str, object] | None = None
    ) -> None:
        self.menu_button = menu_button


@dataclass
class FakeTelegramFileClient:
    """Fake Telegram file client that returns static bytes."""

    content: bytes = b"fake-image-bytes"

    async def download_file_bytes(self, file_id: str) -> bytes:
        return self.content


@dataclass
class FakeVisionClient(VisionClient):
    """Fake vision client returning a fixed payload."""

    payload: dict[str, object] = field(
        default_factory=lambda: {
            "items": [
                {
                    "label": "rice",
                    "confidence": 0.72,
                    "estimated_grams_low": 150,
                    "estimated_grams_high": 250,
                    "notes": "white rice",
                }
            ]
        }
    )

    async def extract(  # noqa: PLR0913
        self,
        *,
        model: str,
        reasoning_effort: str | None,
        store: bool,
        image_data_url: str,
        schema: dict[str, object],
        prompt: str,
    ) -> dict[str, object]:
        return self.payload


@dataclass
class FakeFdcClient(FdcClient):
    """Fake FDC client with in-memory responses."""

    search_payload: dict[str, object] = field(
        default_factory=lambda: {
            "foods": [
                {
                    "fdcId": 123456,
                    "description": "Kirkland Signature Chicken Breast",
                    "brandOwner": "Costco",
                    "brandName": "Kirkland",
                    "dataType": "Branded",
                }
            ]
        }
    )
    food_payload: dict[str, object] = field(
        default_factory=lambda: {
            "fdcId": 123456,
            "description": "Kirkland Signature Chicken Breast",
            "brandOwner": "Costco",
            "brandName": "Kirkland",
            "dataType": "Branded",
            "servingSize": 100,
            "foodNutrients": [
                {"nutrientId": 1008, "amount": 165},
                {"nutrientId": 1003, "amount": 31},
                {"nutrientId": 1004, "amount": 3.6},
                {"nutrientId": 1005, "amount": 0},
            ],
        }
    )

    async def search_foods(self, query: str, page_size: int = 10) -> dict[str, object]:
        return self.search_payload

    async def get_food(self, fdc_id: int) -> dict[str, object]:
        return self.food_payload


@dataclass
class InMemoryPhotoRepository(PhotoRepository):
    """In-memory photo repository for tests."""

    photos: dict[UUID, dict[str, object]] = field(default_factory=dict)

    def create_photo(
        self,
        user_id: UUID,
        telegram_chat_id: int,
        telegram_message_id: int,
        telegram_file_id: str,
        telegram_file_unique_id: str | None,
    ) -> UUID:
        photo_id = uuid4()
        self.photos[photo_id] = {
            "user_id": user_id,
            "telegram_chat_id": telegram_chat_id,
            "telegram_message_id": telegram_message_id,
            "telegram_file_id": telegram_file_id,
            "telegram_file_unique_id": telegram_file_unique_id,
        }
        return photo_id

    def delete_photo(self, photo_id: UUID) -> None:
        self.photos.pop(photo_id, None)


@dataclass
class InMemorySessionRepository(SessionRepository):
    """In-memory session repository for tests."""

    sessions: dict[UUID, SessionRecord] = field(default_factory=dict)

    def create_session(
        self,
        user_id: UUID,
        photo_id: UUID | None,
        status: str,
        context: dict[str, object],
    ) -> SessionRecord:
        session = SessionRecord(
            id=uuid4(),
            user_id=user_id,
            photo_id=photo_id,
            status=status,
            context=context,
        )
        self.sessions[session.id] = session
        return session

    def get_session(self, session_id: UUID) -> SessionRecord | None:
        return self.sessions.get(session_id)

    def get_active_session(self, user_id: UUID) -> SessionRecord | None:
        for session in self.sessions.values():
            if session.user_id == user_id and session.status not in {
                "COMPLETED",
                "CANCELLED",
            }:
                return session
        return None

    def update_session(
        self, session_id: UUID, status: str, context: dict[str, object]
    ) -> None:
        session = self.sessions[session_id]
        self.sessions[session_id] = SessionRecord(
            id=session.id,
            user_id=session.user_id,
            photo_id=session.photo_id,
            status=status,
            context=context,
        )


@dataclass
class InMemoryLibraryRepository(LibraryRepository):
    """In-memory library repository for tests."""

    foods: dict[UUID, LibraryFood] = field(default_factory=dict)
    aliases: dict[str, UUID] = field(default_factory=dict)

    def create_food(self, user_id: UUID, payload: dict[str, object]) -> LibraryFood:
        food_id = uuid4()
        food = LibraryFood(
            id=food_id,
            user_id=user_id,
            name=str(payload.get("name", "")),
            brand=payload.get("brand"),
            store=payload.get("store"),
            source_type=str(payload.get("source_type", "")),
            source_ref=payload.get("source_ref"),
            basis=str(payload.get("basis", "")),
            serving_size_g=payload.get("serving_size_g"),
            calories=float(payload.get("calories", 0.0)),
            protein_g=float(payload.get("protein_g", 0.0)),
            fat_g=float(payload.get("fat_g", 0.0)),
            carbs_g=float(payload.get("carbs_g", 0.0)),
            use_count=0,
            last_used_at=None,
        )
        self.foods[food_id] = food
        return food

    def update_food(self, food_id: UUID, payload: dict[str, object]) -> LibraryFood:
        current = self.foods[food_id]
        updated = LibraryFood(
            id=current.id,
            user_id=current.user_id,
            name=str(payload.get("name", current.name)),
            brand=payload.get("brand", current.brand),
            store=payload.get("store", current.store),
            source_type=str(payload.get("source_type", current.source_type)),
            source_ref=payload.get("source_ref", current.source_ref),
            basis=str(payload.get("basis", current.basis)),
            serving_size_g=payload.get("serving_size_g", current.serving_size_g),
            calories=float(payload.get("calories", current.calories)),
            protein_g=float(payload.get("protein_g", current.protein_g)),
            fat_g=float(payload.get("fat_g", current.fat_g)),
            carbs_g=float(payload.get("carbs_g", current.carbs_g)),
            use_count=current.use_count,
            last_used_at=current.last_used_at,
        )
        self.foods[food_id] = updated
        return updated

    def get_food(self, food_id: UUID) -> LibraryFood | None:
        return self.foods.get(food_id)

    def find_by_source_ref(
        self, user_id: UUID, source_type: str, source_ref: str
    ) -> LibraryFood | None:
        for food in self.foods.values():
            if (
                food.user_id == user_id
                and food.source_type == source_type
                and str(food.source_ref) == source_ref
            ):
                return food
        return None

    def search_foods(self, user_id: UUID, query: str, limit: int) -> list[LibraryFood]:
        query_lower = query.lower()
        results = [
            food
            for food in self.foods.values()
            if food.user_id == user_id and query_lower in food.name.lower()
        ]
        for alias, food_id in self.aliases.items():
            if query_lower in alias.lower() and food_id in self.foods:
                results.append(self.foods[food_id])
        return results[:limit]

    def list_top_foods(self, user_id: UUID, limit: int) -> list[LibraryFood]:
        return [food for food in self.foods.values() if food.user_id == user_id][:limit]

    def add_alias(self, user_id: UUID, food_id: UUID, alias_text: str) -> None:
        self.aliases[alias_text] = food_id

    def increment_usage(self, food_id: UUID, used_at) -> None:
        current = self.foods[food_id]
        self.foods[food_id] = LibraryFood(
            id=current.id,
            user_id=current.user_id,
            name=current.name,
            brand=current.brand,
            store=current.store,
            source_type=current.source_type,
            source_ref=current.source_ref,
            basis=current.basis,
            serving_size_g=current.serving_size_g,
            calories=current.calories,
            protein_g=current.protein_g,
            fat_g=current.fat_g,
            carbs_g=current.carbs_g,
            use_count=current.use_count + 1,
            last_used_at=used_at,
        )


@dataclass
class InMemoryMealLogRepository(MealLogRepository):
    """In-memory meal log repository for tests."""

    meals: dict[UUID, dict[str, object]] = field(default_factory=dict)
    items: dict[UUID, MealItemRecord] = field(default_factory=dict)

    def create_meal_log(self, user_id: UUID, logged_at, totals) -> UUID:
        meal_id = uuid4()
        self.meals[meal_id] = {
            "user_id": user_id,
            "logged_at": logged_at,
            "totals": totals,
        }
        return meal_id

    def create_meal_items(
        self, meal_log_id: UUID, items: list[MealItemSnapshot]
    ) -> None:
        for item in items:
            item_id = uuid4()
            self.items[item_id] = MealItemRecord(
                id=item_id,
                meal_log_id=meal_log_id,
                food_id=item.food_id,
                name=item.name,
                grams=item.grams,
                calories=item.calories,
                protein_g=item.protein_g,
                fat_g=item.fat_g,
                carbs_g=item.carbs_g,
                nutrition_snapshot=item.nutrition_snapshot or {},
            )

    def get_meal_log(self, meal_log_id: UUID):
        meal = self.meals.get(meal_log_id)
        if not meal:
            return None
        return MealLogRow(
            meal_id=meal_log_id,
            logged_at=meal["logged_at"],
            total_calories=meal["totals"].calories,
            total_protein_g=meal["totals"].protein_g,
            total_fat_g=meal["totals"].fat_g,
            total_carbs_g=meal["totals"].carbs_g,
        )

    def list_meal_items(self, meal_log_id: UUID) -> list[MealItemRecord]:
        return [item for item in self.items.values() if item.meal_log_id == meal_log_id]

    def get_meal_item(self, meal_item_id: UUID) -> MealItemRecord | None:
        return self.items.get(meal_item_id)

    def update_meal_item(self, meal_item_id: UUID, grams: float, macros) -> None:
        item = self.items[meal_item_id]
        self.items[meal_item_id] = MealItemRecord(
            id=item.id,
            meal_log_id=item.meal_log_id,
            food_id=item.food_id,
            name=item.name,
            grams=grams,
            calories=macros.calories,
            protein_g=macros.protein_g,
            fat_g=macros.fat_g,
            carbs_g=macros.carbs_g,
            nutrition_snapshot=item.nutrition_snapshot,
        )

    def update_meal_log_totals(self, meal_log_id: UUID, totals) -> None:
        meal = self.meals[meal_log_id]
        meal["totals"] = totals


@dataclass
class InMemoryStatsRepository(StatsRepository):
    """In-memory stats repository for tests."""

    logs: list[MealLogRow] = field(default_factory=list)

    def list_meal_logs(self, user_id: UUID, start, end) -> list[MealLogRow]:
        return [log for log in self.logs if start <= log.logged_at <= end]

    def list_recent_meal_logs(self, user_id: UUID, limit: int) -> list[MealLogRow]:
        return sorted(self.logs, key=lambda log: log.logged_at, reverse=True)[:limit]


@dataclass
class InMemoryUserSettingsRepository(UserSettingsRepository):
    """In-memory user settings repository for tests."""

    timezones: dict[UUID, str] = field(default_factory=dict)

    def get_timezone(self, user_id: UUID) -> str | None:
        return self.timezones.get(user_id)

    def set_timezone(self, user_id: UUID, timezone: str) -> None:
        self.timezones[user_id] = timezone


@dataclass
class InMemoryAdminRepository(AdminRepository):
    """In-memory admin repository for tests."""

    users: list[AdminUser] = field(default_factory=list)
    sessions: list[dict[str, object]] = field(default_factory=list)
    costs: list[dict[str, object]] = field(default_factory=list)
    audits: dict[UUID, list[dict[str, object]]] = field(default_factory=dict)

    def list_users(self) -> list[AdminUser]:
        return self.users

    def list_sessions(self, limit: int) -> list[dict[str, object]]:
        return self.sessions[:limit]

    def list_costs(self, limit: int) -> list[dict[str, object]]:
        return self.costs[:limit]

    def list_audit_events(self, user_id: UUID, limit: int) -> list[dict[str, object]]:
        return self.audits.get(user_id, [])[:limit]


@dataclass
class InMemoryAuditRepository(AuditRepository):
    """In-memory audit repository for tests."""

    events: list[dict[str, object]] = field(default_factory=list)

    def create_event(  # noqa: PLR0913
        self,
        user_id: UUID,
        entity_type: str,
        entity_id: UUID,
        event_type: str,
        before: dict[str, object] | None,
        after: dict[str, object] | None,
    ) -> None:
        self.events.append(
            {
                "user_id": user_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "event_type": event_type,
                "before": before,
                "after": after,
            }
        )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        telegram_bot_token="test-token",
        supabase_url="https://example.supabase.co",
        supabase_service_key="service-key",
        admin_token="admin-token",
        openai_api_key="openai-key",
        fdc_api_key="fdc-key",
    )


@pytest.fixture
def user_repository() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
def telegram_client() -> FakeTelegramClient:
    return FakeTelegramClient()


@pytest.fixture
def container(
    settings: Settings,
    user_repository: InMemoryUserRepository,
    telegram_client: FakeTelegramClient,
) -> AppContainer:
    user_service = UserService(user_repository)
    photo_repository = InMemoryPhotoRepository()
    session_repository = InMemorySessionRepository()
    telegram_file_client = FakeTelegramFileClient()
    vision_service = VisionService(
        client=FakeVisionClient(),
        model=settings.openai_model,
        reasoning_effort=settings.openai_reasoning_effort,
        store=settings.openai_store,
    )
    nutrition_service = NutritionService(
        fdc_client=FakeFdcClient(),
        cache=InMemoryCache(),
    )
    library_service = LibraryService(InMemoryLibraryRepository())
    meal_log_service = MealLogService(
        nutrition_service=nutrition_service,
        library_service=library_service,
        repository=InMemoryMealLogRepository(),
    )
    audit_service = AuditService(InMemoryAuditRepository())
    session_service = SessionService(
        photo_repository=photo_repository,
        session_repository=session_repository,
        library_service=library_service,
        nutrition_service=nutrition_service,
        meal_log_service=meal_log_service,
        audit_service=audit_service,
    )
    stats_service = StatsService(InMemoryStatsRepository())
    user_settings_service = UserSettingsService(InMemoryUserSettingsRepository())
    start_handler = StartCommandHandler(
        user_service=user_service,
        user_settings_service=user_settings_service,
        telegram_client=telegram_client,
    )
    admin_service = AdminService(
        admin_repository=InMemoryAdminRepository(),
        stats_repository=stats_service.repository,
        library_repository=library_service.repository,
    )

    async def close_resources() -> None:
        return None

    return AppContainer(
        settings=settings,
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
