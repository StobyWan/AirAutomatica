"""Socket.IO ASGI app and server instance."""

import logging
from typing import Any

import socketio
from fastapi import FastAPI

logger = logging.getLogger(__name__)

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")


@sio.event
async def connect(
    sid: str, environ: dict[str, Any], auth: dict[str, Any] | None
) -> None:
    """Log client connection."""
    logger.debug("Dashboard client connected: sid=%s", sid)


@sio.event
async def disconnect(sid: str) -> None:
    """Log client disconnection."""
    logger.debug("Dashboard client disconnected: sid=%s", sid)


@sio.event
async def vehicle_control(sid: str, data: dict) -> None:
    """Receive normalized rover control from browser. Validates and stores for bridge."""
    from airautomatica.vehicle.control_store import update_control

    update_control(data)


def wrap_app(app: FastAPI) -> socketio.ASGIApp:
    """Wrap FastAPI app with Socket.IO. Returns combined ASGI app."""
    return socketio.ASGIApp(sio, app)
