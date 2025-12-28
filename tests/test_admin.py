"""Tests for admin authentication."""

from fastapi.testclient import TestClient

from nutrition_tracker.api.app import create_app
from nutrition_tracker.containers import AppContainer


def test_admin_health_requires_token(container: AppContainer) -> None:
    app = create_app(container)
    client = TestClient(app)

    response = client.get("/admin/health")

    assert response.status_code == 401


def test_admin_health_accepts_valid_token(container: AppContainer) -> None:
    app = create_app(container)
    client = TestClient(app)

    response = client.get("/admin/health", headers={"X-Admin-Token": "admin-token"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
