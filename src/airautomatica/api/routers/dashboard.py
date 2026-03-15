"""Dashboard routes: HTML pages or Vue SPA."""

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

from airautomatica.config import get_spa_index_path, get_use_spa_dashboard
from airautomatica.ui.dashboard import get_dashboard_html, get_session_detail_html

_no_cache = {
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
}


def create_dashboard_router() -> APIRouter:
    """Create dashboard router. Serves Vue SPA when USE_SPA_DASHBOARD and dist exists."""
    router = APIRouter(tags=["dashboard"])

    @router.get("/dashboard")
    def dashboard() -> Response:
        """Serve the real-time flight dashboard. SPA when enabled, else legacy HTML."""
        if get_use_spa_dashboard():
            spa_path = get_spa_index_path()
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
            spa_path = get_spa_index_path()
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
            spa_path = get_spa_index_path()
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
