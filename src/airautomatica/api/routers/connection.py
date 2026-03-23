"""Connection routes: state, detect, mode, disconnect."""

import logging
import os
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter, Body

from airautomatica.config import get_serial_baud, get_serial_port, get_telemetry_backend
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

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _serial_settings_already_match(port: str, baud: int) -> bool:
    """True if env-backed telemetry is already serial on this port and baud."""
    if get_telemetry_backend() != "serial":
        return False
    try:
        if os.path.realpath(str(port)) != os.path.realpath(get_serial_port()):
            return False
    except OSError:
        return False
    return int(baud) == int(get_serial_baud())


def create_connection_router(
    session_ref: list[int | None],
    connection_store: Optional[ConnectionStateStore],
    reload_telemetry_fn: Optional[Callable[[], Awaitable[object]]] = None,
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

    @router.get("/ports")
    def get_connection_ports() -> dict:
        """List detected ports with lightweight MAVLink status. Fast summary endpoint."""
        try:
            from airautomatica.telemetry.detector import list_ports_with_status

            ports = list_ports_with_status()
            return {
                "ports": [
                    {
                        "path": p.path,
                        "mavlink_active": p.mavlink_active,
                        "autopilot": p.autopilot,
                        "baud": p.baud,
                        "status": p.status,
                    }
                    for p in ports
                ]
            }
        except Exception as e:
            logger.exception("Ports list failed: %s", e)
            return {"ports": [], "error": str(e)}

    @router.post("/detect")
    async def post_connection_detect(body: dict = Body(default_factory=dict)) -> dict:
        """Scan serial ports for MAVLink HEARTBEAT. Updates connection_store state.
        Optional body: { port?, baud? } to probe a single port only."""
        # Lazy import: telemetry.detector pulls in pymavlink/pyserial, which can cause
        # SIGBUS on some Raspberry Pi setups when loaded at process startup.
        from airautomatica.telemetry.detector import (
            detect_on_port,
            detect_on_port_skips_open_if_live_link,
            scan_and_detect,
        )

        port = body.get("port")
        baud = body.get("baud")
        if port and baud is not None:
            baud = int(baud)
        else:
            port = None
            baud = None

        if connection_store is not None:
            connection_store.set_connection_state(ConnectionState.DETECTING)
        try:
            if port and baud is not None:
                fa: str | None = None
                fm: str | None = None
                if connection_store is not None:
                    d0 = connection_store.get_detection_result()
                    if d0 is not None:
                        fa = d0.autopilot
                        fm = d0.message
                r = detect_on_port_skips_open_if_live_link(
                    str(port),
                    baud,
                    fallback_autopilot=fa,
                    fallback_message=fm,
                )
                if r is None:
                    r = detect_on_port(str(port), baud)
            else:
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
            if r.detected and r.port and r.baud is not None:
                if not _serial_settings_already_match(str(r.port), int(r.baud)):
                    save_settings(
                        {
                            "TELEMETRY_BACKEND": "serial",
                            "SERIAL_PORT": str(r.port),
                            "SERIAL_BAUD": str(int(r.baud)),
                        }
                    )
                    if reload_telemetry_fn is not None:
                        await reload_telemetry_fn()
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
    async def post_connection_mode(body: dict = Body(...)) -> dict:
        """Set connection mode. Persists to settings. Serial/mock modes trigger telemetry reconnect."""
        mode = (body.get("mode") or "").lower()
        port = body.get("port") or get_serial_port()
        baud = body.get("baud") or get_serial_baud()
        valid_modes = ("mock", "mock_ardupilot", "mock_inav", "ardupilot", "inav")
        if mode not in valid_modes:
            return {
                "ok": False,
                "error": "Invalid mode. Use mock, mock_ardupilot, mock_inav, ardupilot, or inav.",
            }
        is_mock = mode in ("mock", "mock_ardupilot", "mock_inav")
        mock_type = "generic"
        if mode == "mock_ardupilot":
            mock_type = "ardupilot"
        elif mode == "mock_inav":
            mock_type = "inav"
        updates: dict[str, str] = {
            "TELEMETRY_BACKEND": "mock" if is_mock else "serial",
            "SERIAL_PORT": str(port),
            "SERIAL_BAUD": str(int(baud)),
        }
        if is_mock:
            updates["MOCK_TELEMETRY_TYPE"] = mock_type
        save_settings(updates)
        restart_required = mode in ("ardupilot", "inav")
        if connection_store is not None:
            if is_mock:
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
        if (
            mode in ("ardupilot", "inav") or is_mock
        ) and reload_telemetry_fn is not None:
            await reload_telemetry_fn()
        return {"ok": True, "restart_required": restart_required}

    @router.post("/disconnect")
    async def post_connection_disconnect() -> dict:
        """Return to setup. Clear mode. Switch to mock telemetry. Preserve detection_result for diagnostics."""
        save_settings({"TELEMETRY_BACKEND": "mock"})
        if connection_store is not None:
            connection_store.set_connection_state(ConnectionState.SETUP)
            connection_store.set_mode(None)
        if reload_telemetry_fn is not None:
            await reload_telemetry_fn()
        return {"ok": True}

    return router
