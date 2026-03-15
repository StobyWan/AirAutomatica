"""Dashboard routes: Vue SPA only."""

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, Response

from airautomatica.config import get_spa_index_path

_no_cache = {
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
}


def _spa_fallback_html() -> str:
    """Minimal HTML when SPA is not built."""
    return """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Dashboard — AIRAUTOMATICA</title></head>
<body style="font-family:system-ui;max-width:32rem;margin:4rem auto;padding:1rem;color:#334155">
  <h1 style="font-size:1.25rem;margin:0 0 1rem 0">Dashboard not built</h1>
  <p>Build the Vue frontend:</p>
  <pre style="background:#f1f5f9;padding:1rem;border-radius:6px;overflow-x:auto">cd frontend && npm install && npm run build</pre>
  <p style="color:#64748b;font-size:0.875rem">Then restart the server.</p>
</body>
</html>"""


def create_dashboard_router() -> APIRouter:
    """Create dashboard router. Serves Vue SPA from frontend/dist."""
    router = APIRouter(tags=["dashboard"])
    spa_path = get_spa_index_path()

    def _dashboard_response() -> Response:
        if spa_path is not None:
            return FileResponse(
                spa_path,
                media_type="text/html",
                headers=_no_cache,
            )
        return HTMLResponse(
            content=_spa_fallback_html(),
            status_code=503,
            headers=_no_cache,
        )

    @router.get("/dashboard")
    def dashboard() -> Response:
        """Serve the Vue SPA dashboard."""
        return _dashboard_response()

    @router.get("/dashboard/history")
    @router.get("/dashboard/settings")
    def dashboard_subroutes() -> Response:
        """Serve SPA index for client-side routes (history, settings)."""
        return _dashboard_response()

    @router.get("/dashboard/sessions/{sid:int}")
    def session_detail(sid: int) -> Response:
        """Serve SPA index for session detail (Vue Router handles /sessions/:id)."""
        return _dashboard_response()

    return router
