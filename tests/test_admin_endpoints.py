"""Tests for admin endpoints."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from nutrition_tracker.api.app import create_app
from nutrition_tracker.domain.admin import AdminUser
from tests.conftest import InMemoryAdminRepository


def test_admin_users_endpoint(container) -> None:
    app = create_app(container)
    client = TestClient(app)

    admin_repo = container.admin_service.admin_repository
    assert isinstance(admin_repo, InMemoryAdminRepository)
    admin_repo.users.append(
        AdminUser(
            id=uuid4(),
            telegram_user_id=111,
            last_active_at=datetime.now(tz=UTC),
        )
    )

    response = client.get("/admin/users", headers={"X-Admin-Token": "admin-token"})

    assert response.status_code == 200
    data = response.json()
    assert "users" in data
    assert data["users"][0]["telegram_user_id"] == 111


def test_admin_sessions_endpoint(container) -> None:
    app = create_app(container)
    client = TestClient(app)

    admin_repo = container.admin_service.admin_repository
    assert isinstance(admin_repo, InMemoryAdminRepository)
    admin_repo.sessions.append({"id": "session-1", "status": "ACTIVE"})

    response = client.get("/admin/sessions", headers={"X-Admin-Token": "admin-token"})

    assert response.status_code == 200
    data = response.json()
    assert data["sessions"][0]["id"] == "session-1"
