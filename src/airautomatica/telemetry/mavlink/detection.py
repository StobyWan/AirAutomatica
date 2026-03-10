"""MAVLink autopilot detection from HEARTBEAT."""

from typing import Any

# MAV_AUTOPILOT enum values (mavlink.io/common)
MAV_AUTOPILOT_GENERIC = 0
MAV_AUTOPILOT_RESERVED = 1
MAV_AUTOPILOT_SLUGS = 2
MAV_AUTOPILOT_ARDUPILOTMEGA = 3
MAV_AUTOPILOT_OPENPILOT = 4
MAV_AUTOPILOT_GENERIC_WAYPOINTS_ONLY = 5
MAV_AUTOPILOT_GENERIC_WAYPOINTS_AND_SIMPLE_NAVIGATION_ONLY = 6
MAV_AUTOPILOT_GENERIC_MISSION_FULL = 7
MAV_AUTOPILOT_INVALID = 8
MAV_AUTOPILOT_PPZ = 9
MAV_AUTOPILOT_UDB = 10
MAV_AUTOPILOT_FP = 11
MAV_AUTOPILOT_PX4 = 12
MAV_AUTOPILOT_INAV = 13


def detect_autopilot_from_heartbeat(msg: Any) -> str:
    """Return autopilot type from HEARTBEAT for adapter selection.

    Returns "ardupilot", "inav", or "generic".
    """
    autopilot = getattr(msg, "autopilot", MAV_AUTOPILOT_GENERIC)
    if autopilot == MAV_AUTOPILOT_ARDUPILOTMEGA:
        return "ardupilot"
    if autopilot == MAV_AUTOPILOT_INAV:
        return "inav"
    return "generic"
