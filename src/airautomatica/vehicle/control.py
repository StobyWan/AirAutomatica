"""Normalized control message handling for rover teleoperation.

Receives control messages from Socket.IO/REST, validates, applies deadband
and clamping, and emits to the vehicle bridge. Does not drive hardware directly.
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

DEADBAND = 0.05
STEERING_CLAMP = 1.0
THROTTLE_CLAMP = 1.0
PAN_TILT_CLAMP = 1.0


@dataclass
class RoverControlMessage:
    """Normalized rover control message."""

    timestamp: str
    seq: int
    steering: float
    throttle: float
    pan: float
    tilt: float
    source: str
    mode: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "seq": self.seq,
            "steering": self.steering,
            "throttle": self.throttle,
            "pan": self.pan,
            "tilt": self.tilt,
            "source": self.source,
            "mode": self.mode,
        }


def _apply_deadband(val: float, deadband: float = DEADBAND) -> float:
    """Apply deadband near zero."""
    if -deadband <= val <= deadband:
        return 0.0
    return val


def _clamp(val: float, low: float, high: float) -> float:
    """Clamp value to [low, high]."""
    return max(low, min(high, val))


def validate_and_normalize(raw: dict[str, Any]) -> RoverControlMessage | None:
    """Validate and normalize a raw control message. Returns None if invalid."""
    try:
        timestamp = str(raw.get("timestamp", ""))
        seq = int(raw.get("seq", 0))
        steering = float(raw.get("steering", 0.0))
        throttle = float(raw.get("throttle", 0.0))
        pan = float(raw.get("pan", 0.0))
        tilt = float(raw.get("tilt", 0.0))
        source = str(raw.get("source", "unknown"))
        mode = str(raw.get("mode", "rover"))

        steering = _apply_deadband(_clamp(steering, -STEERING_CLAMP, STEERING_CLAMP))
        throttle = _apply_deadband(_clamp(throttle, -THROTTLE_CLAMP, THROTTLE_CLAMP))
        pan = _apply_deadband(_clamp(pan, -PAN_TILT_CLAMP, PAN_TILT_CLAMP))
        tilt = _apply_deadband(_clamp(tilt, -PAN_TILT_CLAMP, PAN_TILT_CLAMP))

        if mode not in ("rover", "bench"):
            mode = "rover"

        return RoverControlMessage(
            timestamp=timestamp,
            seq=seq,
            steering=steering,
            throttle=throttle,
            pan=pan,
            tilt=tilt,
            source=source,
            mode=mode,
        )
    except (TypeError, ValueError) as e:
        logger.debug("Invalid control message: %s", e)
        return None
