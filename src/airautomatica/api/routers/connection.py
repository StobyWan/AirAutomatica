"""Connection routes: state, detect, mode, disconnect."""

import logging
from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter, Body

from airautomatica.config import get_serial_baud, get_serial_port
from airautomatica.models.connection_state import (
    ConnectionMode,
    ConnectionState,
)
from airautomatica.services.connection_state_store import (
    ConnectionStateStore,
)
from airautomatica.services.connection_state_store import (
    DetectionResult as StoreDetectionResult,
)
from airautomatica.settings import save_settings
from airautomatica.telemetry.detector import scan_and_detect

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def create_connection_router(
    session_ref: list[int | None],
    connection_store: Optional[ConnectionStateStore],
) -> APIRouter:
    """Create connection router with injected dependencies."""
    router = APIRouter(prefix="/connection", tags=["connection"])

    @router.get("/state")
    def get_connection_state() -> dict:
        """Return connection/session state for frontend. Primary source of truth for v1."""
        session_id = session_ref[0]
        if connection_store is None:
            return {
                "connection_state": "setup",
                "session_state": "none",
                "mode": None,
                "session_id": session_id,
                "detection_result": None,
            }
        conn = connection_store.get_connection_state()
        sess = connection_store.get_session_state()
        mode = connection_store.get_mode()
        det = connection_store.get_detection_result()
        return {
            "connection_state": conn.value if hasattr(conn, "value") else conn,
            "session_state": sess.value if hasattr(sess, "value") else sess,
            "mode": mode.value if mode is not None and hasattr(mode, "value") else mode,
            "session_id": session_id,
            "detection_result": (
                {
                    "detected": det.detected,
                    "port": det.port,
                    "baud": det.baud,
                    "autopilot": det.autopilot,
                    "message": det.message,
                    "heartbeat_age_ms": det.heartbeat_age_ms,
                }
                if det is not None
                else None
            ),
        }

    @router.post("/detect")
    def post_connection_detect() -> dict:
        """Scan serial ports for MAVLink HEARTBEAT. Updates connection_store state."""
        if connection_store is not None:
            connection_store.set_connection_state(ConnectionState.DETECTING)
        try:
            r = scan_and_detect()
            if connection_store is not None:
                store_result = StoreDetectionResult(
                    detected=r.detected,
                    port=r.port,
                    baud=r.baud,
                    autopilot=r.autopilot,
                    message=r.message,
                    heartbeat_age_ms=r.heartbeat_age_ms,
                )
                connection_store.set_detection_result(store_result)
                if r.detected:
                    if r.autopilot == "ardupilot":
                        connection_store.set_connection_state(
                            ConnectionState.CONNECTED_ARDUPILOT
                        )
                    else:
                        connection_store.set_connection_state(
                            ConnectionState.CONNECTED_INAV
                        )
                else:
                    connection_store.set_connection_state(ConnectionState.NOT_DETECTED)
            mode = r.autopilot if r.autopilot else "inav"
            if r.autopilot == "generic":
                mode = "inav"
            conn_state = (
                "not_detected"
                if not r.detected
                else (
                    "connected_ardupilot"
                    if r.autopilot == "ardupilot"
                    else "connected_inav"
                )
            )
            return {
                "connection_state": conn_state,
                "detected": r.detected,
                "mode": mode,
                "port": r.port,
                "baud": r.baud,
                "autopilot": r.autopilot,
                "message": r.message,
                "heartbeat_age_ms": r.heartbeat_age_ms,
            }
        except Exception as e:
            logger.exception("Detection failed: %s", e)
            if connection_store is not None:
                connection_store.set_connection_state(ConnectionState.NOT_DETECTED)
                connection_store.set_detection_result(
                    StoreDetectionResult(
                        detected=False,
                        port=None,
                        baud=None,
                        autopilot=None,
                        message=str(e),
                        heartbeat_age_ms=None,
                    )
                )
            return {
                "connection_state": "not_detected",
                "detected": False,
                "mode": "inav",
                "port": None,
                "baud": None,
                "autopilot": None,
                "message": str(e),
                "heartbeat_age_ms": None,
            }

    @router.post("/mode")
    def post_connection_mode(body: dict = Body(...)) -> dict:
        """Set connection mode. Persists to settings. Serial modes require restart."""
        mode = (body.get("mode") or "").lower()
        port = body.get("port") or get_serial_port()
        baud = body.get("baud") or get_serial_baud()
        if mode not in ("mock", "ardupilot", "inav"):
            return {"ok": False, "error": "Invalid mode. Use mock, ardupilot, or inav."}
        updates = {
            "TELEMETRY_BACKEND": "mock" if mode == "mock" else "serial",
            "SERIAL_PORT": str(port),
            "SERIAL_BAUD": str(int(baud)),
        }
        save_settings(updates)
        restart_required = mode in ("ardupilot", "inav")
        if connection_store is not None:
            if mode == "mock":
                connection_store.set_connection_state(ConnectionState.MOCK_IDLE)
                connection_store.set_mode(ConnectionMode.MOCK)
            elif mode == "ardupilot":
                connection_store.set_connection_state(
                    ConnectionState.CONNECTED_ARDUPILOT
                )
                connection_store.set_mode(ConnectionMode.ARDUPILOT)
            else:
                connection_store.set_connection_state(ConnectionState.CONNECTED_INAV)
                connection_store.set_mode(ConnectionMode.INAV)
        return {"ok": True, "restart_required": restart_required}

    @router.post("/disconnect")
    def post_connection_disconnect() -> dict:
        """Return to setup. Clear mode. Preserve detection_result for diagnostics."""
        if connection_store is not None:
            connection_store.set_connection_state(ConnectionState.SETUP)
            connection_store.set_mode(None)
        return {"ok": True}

    return router
