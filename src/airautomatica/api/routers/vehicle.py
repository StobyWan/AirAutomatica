"""Vehicle control routes: REST fallback for rover control."""

from fastapi import APIRouter, Body

from airautomatica.config import get_vehicle_mode
from airautomatica.vehicle.control_store import clear_control, update_control
from airautomatica.vehicle.failsafe import reset

router = APIRouter(prefix="/vehicle", tags=["vehicle"])


@router.post("/stop")
def post_vehicle_stop() -> dict:
    """Manual stop: clear control store and reset failsafe."""
    mode = get_vehicle_mode()
    if mode not in ("rover", "bench"):
        return {
            "ok": False,
            "error": "Vehicle control only available in rover or bench mode",
        }
    clear_control()
    reset()
    return {"ok": True}


@router.post("/control")
def post_vehicle_control(body: dict = Body(...)) -> dict:
    """Accept normalized rover control. Validates and stores for bridge.
    Body: { timestamp, seq, steering, throttle, pan?, tilt?, source, mode }"""
    mode = get_vehicle_mode()
    if mode not in ("rover", "bench"):
        return {
            "ok": False,
            "error": "Vehicle control only available in rover or bench mode",
        }
    update_control(body)
    return {"ok": True}


@router.get("/status")
def get_vehicle_status() -> dict:
    """Return current vehicle mode and control status."""
    from airautomatica.vehicle.control_store import get_last_control

    mode = get_vehicle_mode()
    last = get_last_control()
    return {
        "vehicle_mode": mode,
        "last_control": last.to_dict() if last else None,
    }
