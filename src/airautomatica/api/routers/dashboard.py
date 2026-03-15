"""Dashboard routes: HTML pages or Vue SPA."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

from airautomatica.config import get_use_spa_dashboard
from airautomatica.ui.dashboard import get_dashboard_html, get_session_detail_html

_no_cache = {
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
}


def _get_spa_index_path() -> Path | None:
    """Return path to frontend/dist/index.html if it exists."""
    # Installed .deb: /opt/airautomatica/frontend/dist/index.html
    opt_path = Path("/opt/airautomatica/frontend/dist/index.html")
    if opt_path.is_file():
        return opt_path
    # Dev layout: project_root/frontend/dist/index.html
    # dashboard.py is at src/airautomatica/api/routers/; need 5 parents to reach project root
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    spa_index = project_root / "frontend" / "dist" / "index.html"
    return spa_index if spa_index.is_file() else None


def create_dashboard_router() -> APIRouter:
    """Create dashboard router. Serves Vue SPA when USE_SPA_DASHBOARD and dist exists."""
    router = APIRouter(tags=["dashboard"])

    @router.get("/dashboard")
    def dashboard() -> Response:
        """Serve the real-time flight dashboard. SPA when enabled, else legacy HTML."""
        if get_use_spa_dashboard():
            spa_path = _get_spa_index_path()
            if spa_path is not None:
                return FileResponse(
                    spa_path,
                    media_type="text/html",
                    headers=_no_cache,
                )
        return Response(
            content=get_dashboard_html(),
            media_type="text/html",
            headers=_no_cache,
        )

    @router.get("/dashboard/history")
    @router.get("/dashboard/settings")
    def dashboard_subroutes() -> Response:
        """Serve SPA index for client-side routes (history, settings)."""
        if get_use_spa_dashboard():
            spa_path = _get_spa_index_path()
            if spa_path is not None:
                return FileResponse(
                    spa_path,
                    media_type="text/html",
                    headers=_no_cache,
                )
        return Response(
            content=get_dashboard_html(),
            media_type="text/html",
            headers=_no_cache,
        )

    @router.get("/dashboard/sessions/{sid:int}")
    def session_detail(sid: int) -> Response:
        """Serve session detail page. SPA when enabled, else legacy HTML."""
        if get_use_spa_dashboard():
            spa_path = _get_spa_index_path()
            if spa_path is not None:
                return FileResponse(
                    spa_path,
                    media_type="text/html",
                    headers=_no_cache,
                )
        return Response(
            content=get_session_detail_html(),
            media_type="text/html",
            headers=_no_cache,
        )

    return router
