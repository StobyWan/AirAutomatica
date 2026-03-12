"""Session routes: start, stop, live/home."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Optional

from fastapi import APIRouter, Body, HTTPException

from airautomatica.models.connection_state import SessionState
from airautomatica.models.state import nan_to_none
from airautomatica.services.app_home_store import AppHomeStore
from airautomatica.services.connection_state_store import ConnectionStateStore
from airautomatica.services.persistence import (
    PersistenceService,
    build_session_start_params,
)
from airautomatica.services.state_store import StateStore

if TYPE_CHECKING:
    pass


def create_session_router(
    store: StateStore,
    session_ref: list[int | None],
    connection_store: Optional[ConnectionStateStore],
    persistence: Optional[PersistenceService],
    app_home_store: Optional[AppHomeStore],
) -> APIRouter:
    """Create session router with injected dependencies."""
    router = APIRouter(tags=["session"])

    @router.post("/session/start")
    def post_session_start(body: dict = Body(...)) -> dict:
        """Start a session. Requires connection_state in mock_idle or connected_*."""
        if session_ref[0] is not None:
            return {
                "ok": True,
                "already_active": True,
                "session_id": session_ref[0],
            }
        if persistence is None:
            return {"ok": False, "error": "Persistence not available"}
        params = build_session_start_params(connection_store)
        sid = persistence.start_session(**params)
        if sid is None:
            return {"ok": False, "error": "Failed to start session"}
        session_ref[0] = sid
        if connection_store is not None:
            connection_store.set_session_state(SessionState.ACTIVE)
        return {
            "ok": True,
            "session_id": sid,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

    @router.post("/session/stop")
    def post_session_stop() -> dict:
        """End current session. Idempotent when no session active."""
        sid = session_ref[0]
        if sid is not None and persistence is not None:
            persistence.end_session(sid)
        session_ref[0] = None
        if app_home_store is not None:
            app_home_store.clear_app_home()
        if connection_store is not None:
            connection_store.set_session_state(SessionState.NONE)
        return {"ok": True}

    @router.post("/live/home")
    def post_live_home(
        lat: Optional[float] = Body(None),
        lon: Optional[float] = Body(None),
        use_current: Optional[bool] = Body(None),
        clear: Optional[bool] = Body(None),
    ) -> dict:
        """Set or clear live app home override. Does not change flight controller RTL home."""
        if app_home_store is None:
            raise HTTPException(status_code=503, detail="App home store not available")
        if clear is True:
            app_home_store.clear_app_home()
            return {"ok": True}
        if use_current is True:
            state = store.get()
            if state is None:
                raise HTTPException(
                    status_code=400,
                    detail="No telemetry state; cannot use current position",
                )
            lat_val = nan_to_none(state.lat)
            lon_val = nan_to_none(state.lon)
            if lat_val is None or lon_val is None:
                raise HTTPException(
                    status_code=400,
                    detail="Current position unavailable",
                )
            if not (-90 <= lat_val <= 90) or not (-180 <= lon_val <= 180):
                raise HTTPException(status_code=400, detail="Invalid position")
            app_home_store.set_app_home(lat_val, lon_val)
            return {"ok": True}
        if lat is not None and lon is not None:
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                raise HTTPException(status_code=400, detail="Invalid lat/lon")
            app_home_store.set_app_home(lat, lon)
            return {"ok": True}
        raise HTTPException(
            status_code=400,
            detail="Provide lat and lon, use_current=true, or clear=true",
        )

    return router
