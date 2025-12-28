"""Admin API endpoints with simple token auth."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

if TYPE_CHECKING:
    from nutrition_tracker.containers import AppContainer

router = APIRouter(prefix="/admin", tags=["admin"])


def _get_admin_token(request: Request) -> str:
    container: AppContainer = request.app.state.container
    return container.settings.admin_token


async def require_admin(
    x_admin_token: str | None = Header(default=None),
    admin_token: str = Depends(_get_admin_token),
) -> None:
    """Ensure requests include a valid admin token."""
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@router.get("/health", dependencies=[Depends(require_admin)])
async def admin_health() -> dict[str, str]:
    """Admin health check endpoint."""
    return {"status": "ok"}


@router.get("/users", dependencies=[Depends(require_admin)])
async def list_users(request: Request) -> dict[str, object]:
    """Return a list of users with usage summaries."""
    container: AppContainer = request.app.state.container
    return {"users": container.admin_service.list_users()}


@router.get("/users/{user_id}", dependencies=[Depends(require_admin)])
async def user_detail(user_id: UUID, request: Request) -> dict[str, object]:
    """Return a detailed user summary."""
    container: AppContainer = request.app.state.container
    return container.admin_service.get_user_detail(user_id)


@router.get("/sessions", dependencies=[Depends(require_admin)])
async def list_sessions(request: Request, limit: int = 20) -> dict[str, object]:
    """Return recent photo sessions."""
    container: AppContainer = request.app.state.container
    return {"sessions": container.admin_service.list_sessions(limit)}


@router.get("/costs", dependencies=[Depends(require_admin)])
async def list_costs(request: Request, limit: int = 30) -> dict[str, object]:
    """Return recent model usage entries."""
    container: AppContainer = request.app.state.container
    return {"usage": container.admin_service.list_costs(limit)}
