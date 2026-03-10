"""MAVLink utilities for autopilot detection and message handling."""

from airautomatica.telemetry.mavlink.detection import (
    MAV_AUTOPILOT_ARDUPILOTMEGA,
    MAV_AUTOPILOT_INAV,
    detect_autopilot_from_heartbeat,
)

__all__ = [
    "MAV_AUTOPILOT_ARDUPILOTMEGA",
    "MAV_AUTOPILOT_INAV",
    "detect_autopilot_from_heartbeat",
]
