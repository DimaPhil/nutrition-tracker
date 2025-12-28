"""Admin API endpoints with simple token auth."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse

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


@router.get("/ui", response_class=HTMLResponse)
async def admin_ui() -> HTMLResponse:
    """Minimal admin UI that consumes the admin API."""
    return HTMLResponse(_ADMIN_UI_HTML)


_ADMIN_UI_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Nutrition Tracker Admin</title>
    <style>
      body { font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem; }
      h1 { margin-bottom: 0.5rem; }
      .row { margin-bottom: 1rem; }
      input { padding: 0.4rem 0.6rem; width: 320px; }
      button { padding: 0.4rem 0.8rem; margin-right: 0.5rem; }
      pre { background: #f6f6f6; padding: 1rem; overflow: auto; }
    </style>
  </head>
  <body>
    <h1>Nutrition Tracker Admin</h1>
    <div class="row">
      <label>Admin token</label><br />
      <input id="token" type="password" placeholder="X-Admin-Token" />
    </div>
    <div class="row">
      <button onclick="loadEndpoint('/admin/users')">Users</button>
      <button onclick="loadEndpoint('/admin/sessions')">Sessions</button>
      <button onclick="loadEndpoint('/admin/costs')">Costs</button>
    </div>
    <pre id="output">Ready.</pre>
    <script>
      async function loadEndpoint(path) {
        const token = document.getElementById('token').value;
        const output = document.getElementById('output');
        output.textContent = 'Loading...';
        const res = await fetch(path, {
          headers: { 'X-Admin-Token': token }
        });
        if (!res.ok) {
          output.textContent = 'Error: ' + res.status;
          return;
        }
        const data = await res.json();
        output.textContent = JSON.stringify(data, null, 2);
      }
    </script>
  </body>
</html>
"""
