"""Dashboard routes: HTML pages."""

from fastapi import APIRouter
from fastapi.responses import Response

from airautomatica.ui.dashboard import get_dashboard_html, get_session_detail_html


def create_dashboard_router() -> APIRouter:
    """Create dashboard router."""
    router = APIRouter(tags=["dashboard"])

    @router.get("/dashboard")
    def dashboard() -> Response:
        """Serve the real-time flight dashboard. No-cache to ensure upgrades show new UI."""
        return Response(
            content=get_dashboard_html(),
            media_type="text/html",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
            },
        )

    @router.get("/dashboard/sessions/{sid:int}")
    def session_detail(sid: int) -> Response:
        """Serve session detail page with lat/lon path. No-cache for upgrade consistency."""
        return Response(
            content=get_session_detail_html(),
            media_type="text/html",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
            },
        )

    return router
