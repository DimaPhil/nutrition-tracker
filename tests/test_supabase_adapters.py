"""Tests for Supabase adapter implementations."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

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
from nutrition_tracker.domain.meals import MealItemSnapshot
from nutrition_tracker.domain.nutrition import MacroProfile


@dataclass
class FakeResponse:
    data: list[dict[str, object]] | None


@dataclass
class FakeTable:
    name: str
    response_queue: dict[str, list[list[dict[str, object]]]] = field(
        default_factory=lambda: {"select": [], "insert": [], "update": [], "delete": []}
    )
    last_payload: object | None = None
    last_filters: list[tuple[str, object]] = field(default_factory=list)

    def queue(self, action: str, data: list[dict[str, object]]) -> None:
        self.response_queue[action].append(data)

    def select(self, *_args) -> "FakeTable":
        self._action = "select"
        return self

    def insert(self, payload) -> "FakeTable":  # type: ignore[no-untyped-def]
        self._action = "insert"
        self.last_payload = payload
        return self

    def update(self, payload) -> "FakeTable":  # type: ignore[no-untyped-def]
        self._action = "update"
        self.last_payload = payload
        return self

    def delete(self) -> "FakeTable":
        self._action = "delete"
        return self

    def eq(self, column: str, value) -> "FakeTable":  # type: ignore[no-untyped-def]
        self.last_filters.append((column, value))
        return self

    def in_(self, column: str, value) -> "FakeTable":  # type: ignore[no-untyped-def]
        self.last_filters.append((column, value))
        return self

    def ilike(self, column: str, value) -> "FakeTable":  # type: ignore[no-untyped-def]
        self.last_filters.append((column, value))
        return self

    def limit(self, _count: int) -> "FakeTable":
        return self

    def order(self, _column: str, desc: bool = False) -> "FakeTable":
        return self

    def gte(self, _column: str, _value) -> "FakeTable":  # type: ignore[no-untyped-def]
        return self

    def lt(self, _column: str, _value) -> "FakeTable":  # type: ignore[no-untyped-def]
        return self

    def execute(self) -> FakeResponse:
        action = getattr(self, "_action", "select")
        queue = self.response_queue.get(action, [])
        data = queue.pop(0) if queue else []
        return FakeResponse(data=data)


@dataclass
class FakeSupabaseClient:
    tables: dict[str, FakeTable] = field(default_factory=dict)

    def table(self, name: str) -> FakeTable:
        if name not in self.tables:
            self.tables[name] = FakeTable(name=name)
        return self.tables[name]


def test_supabase_user_repository_roundtrip() -> None:
    client = FakeSupabaseClient()
    users_table = client.table("users")
    user_id = str(uuid4())
    users_table.queue("insert", [{"id": user_id, "telegram_user_id": 123}])
    users_table.queue("select", [{"id": user_id, "telegram_user_id": 123}])

    repository = SupabaseUserRepository(client)
    created = repository.create_user(123)
    fetched = repository.get_by_telegram_id(123)

    assert str(created.id) == user_id
    assert fetched is not None
    assert fetched.telegram_user_id == 123


def test_supabase_user_settings_repository() -> None:
    client = FakeSupabaseClient()
    settings_table = client.table("user_settings")
    settings_table.queue("select", [{"timezone": "UTC"}])

    repository = SupabaseUserSettingsRepository(client)
    assert repository.get_timezone(uuid4()) == "UTC"

    repository.set_timezone(uuid4(), "America/Los_Angeles")
    assert isinstance(settings_table.last_payload, dict)


def test_supabase_photo_repository() -> None:
    client = FakeSupabaseClient()
    photos_table = client.table("photos")
    photo_id = str(uuid4())
    photos_table.queue("insert", [{"id": photo_id}])

    repository = SupabasePhotoRepository(client)
    created_id = repository.create_photo(
        user_id=uuid4(),
        telegram_chat_id=1,
        telegram_message_id=2,
        telegram_file_id="file",
        telegram_file_unique_id="unique",
    )
    repository.delete_photo(created_id)
    assert str(created_id) == photo_id


def test_supabase_session_repository() -> None:
    client = FakeSupabaseClient()
    sessions_table = client.table("photo_sessions")
    session_id = str(uuid4())
    photo_id = str(uuid4())
    sessions_table.queue(
        "insert",
        [
            {
                "id": session_id,
                "user_id": str(uuid4()),
                "photo_id": photo_id,
                "status": "AWAITING_CONFIRMATION",
                "context_json": {"items": []},
            }
        ],
    )
    sessions_table.queue(
        "select",
        [
            {
                "id": session_id,
                "user_id": str(uuid4()),
                "photo_id": photo_id,
                "status": "ACTIVE",
                "context_json": {},
            }
        ],
    )

    repository = SupabaseSessionRepository(client)
    created = repository.create_session(
        user_id=uuid4(),
        photo_id=UUID(photo_id),
        status="AWAITING_CONFIRMATION",
        context={},
    )
    fetched = repository.get_session(created.id)

    assert created.photo_id is not None
    assert fetched is not None


def test_supabase_stats_repository() -> None:
    client = FakeSupabaseClient()
    table = client.table("meal_logs")
    table.queue(
        "select",
        [
            {
                "logged_at": datetime.now(tz=UTC).isoformat(),
                "total_calories": 100,
                "total_protein_g": 10,
                "total_fat_g": 5,
                "total_carbs_g": 20,
            }
        ],
    )
    table.queue(
        "select",
        [
            {
                "logged_at": datetime.now(tz=UTC).isoformat(),
                "total_calories": 200,
                "total_protein_g": 20,
                "total_fat_g": 10,
                "total_carbs_g": 40,
            }
        ],
    )

    repository = SupabaseStatsRepository(client)
    logs = repository.list_meal_logs(uuid4(), datetime.now(), datetime.now())
    recent = repository.list_recent_meal_logs(uuid4(), limit=1)

    assert logs
    assert recent


def test_supabase_meal_log_repository() -> None:
    client = FakeSupabaseClient()
    logs_table = client.table("meal_logs")
    items_table = client.table("meal_items")
    meal_id = str(uuid4())
    logs_table.queue("insert", [{"id": meal_id}])

    repository = SupabaseMealLogRepository(client)
    created_id = repository.create_meal_log(
        user_id=uuid4(),
        logged_at=datetime.now(tz=UTC),
        totals=MacroProfile(100, 10, 5, 20),
    )
    repository.create_meal_items(
        created_id,
        [MealItemSnapshot("rice", 100, 130, 3, 1, 28)],
    )

    assert str(created_id) == meal_id
    assert isinstance(items_table.last_payload, list)


def test_supabase_library_repository() -> None:
    client = FakeSupabaseClient()
    foods_table = client.table("foods_user_library")
    aliases_table = client.table("food_aliases")
    food_id = str(uuid4())

    foods_table.queue(
        "insert",
        [
            {
                "id": food_id,
                "user_id": str(uuid4()),
                "name": "Rice",
                "source_type": "manual",
                "basis": "per100g",
                "calories": 100,
                "protein_g": 2,
                "fat_g": 1,
                "carbs_g": 22,
                "use_count": 0,
            }
        ],
    )
    foods_table.queue("select", [])
    aliases_table.queue("select", [{"food_id": food_id}])
    foods_table.queue(
        "select",
        [
            {
                "id": food_id,
                "user_id": str(uuid4()),
                "name": "Rice",
                "source_type": "manual",
                "basis": "per100g",
                "calories": 100,
                "protein_g": 2,
                "fat_g": 1,
                "carbs_g": 22,
                "use_count": 1,
            }
        ],
    )
    foods_table.queue(
        "select",
        [
            {
                "id": food_id,
                "user_id": str(uuid4()),
                "name": "Rice",
                "source_type": "manual",
                "basis": "per100g",
                "calories": 100,
                "protein_g": 2,
                "fat_g": 1,
                "carbs_g": 22,
                "use_count": 1,
            }
        ],
    )

    repository = SupabaseLibraryRepository(client)
    created = repository.create_food(uuid4(), {"name": "Rice"})
    results = repository.search_foods(uuid4(), "Rice", limit=5)
    top = repository.list_top_foods(uuid4(), limit=5)
    repository.add_alias(uuid4(), UUID(food_id), "Rice")
    foods_table.queue("select", [{"use_count": 1}])
    repository.increment_usage(UUID(food_id), datetime.now(tz=UTC))

    assert created.name == "Rice"
    assert results
    assert top


def test_supabase_admin_repository() -> None:
    client = FakeSupabaseClient()
    users_table = client.table("users")
    sessions_table = client.table("photo_sessions")
    costs_table = client.table("model_usage_daily")
    audits_table = client.table("audit_events")

    user_id = str(uuid4())
    users_table.queue(
        "select",
        [
            {
                "id": user_id,
                "telegram_user_id": 999,
                "last_active_at": datetime.now(tz=UTC).isoformat(),
            }
        ],
    )
    sessions_table.queue("select", [{"id": "session"}])
    costs_table.queue("select", [{"day": "2024-01-01"}])
    audits_table.queue("select", [{"id": "audit"}])

    repository = SupabaseAdminRepository(client)
    users = repository.list_users()
    sessions = repository.list_sessions(limit=5)
    costs = repository.list_costs(limit=5)
    audits = repository.list_audit_events(UUID(user_id), limit=5)

    assert users
    assert sessions
    assert costs
    assert audits
