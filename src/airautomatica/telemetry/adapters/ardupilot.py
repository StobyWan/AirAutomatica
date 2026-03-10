"""ArduPilot adapter: full-featured capability set."""

import logging
from typing import Any

from airautomatica.telemetry.capabilities import (
    DOWNGRADE_PARAM_READ_TIMEOUT,
    CapabilityProfile,
    ardupilot_profile,
)
from airautomatica.telemetry.mavlink_parser import MavlinkNormalizer

logger = logging.getLogger(__name__)

# MAV_AUTOPILOT_ARDUPILOTMEGA (mavlink.io/common)
MAV_AUTOPILOT_ARDUPILOTMEGA = 3

# MAV_CMD_SET_MESSAGE_INTERVAL (ArduPilot 4.0+)
MAV_CMD_SET_MESSAGE_INTERVAL = 511
MESSAGE_INTERVAL_US_10HZ = 100000

MAVLINK_MSG_ID_GLOBAL_POSITION_INT = 33
MAVLINK_MSG_ID_ATTITUDE = 30
MAVLINK_MSG_ID_SYS_STATUS = 1
MAVLINK_MSG_ID_VFR_HUD = 74

# Param read probe
PARAM_PROBE_TIMEOUT_SEC = 2.0
PARAM_PROBE_POLL_INTERVAL_SEC = 0.2


class ArduPilotAdapter:
    """ArduPilot adapter with rich capability set and SET_MESSAGE_INTERVAL."""

    def detect(self, heartbeat_msg: Any) -> bool:
        """True if autopilot is ArduPilot (MAV_AUTOPILOT_ARDUPILOTMEGA)."""
        autopilot = getattr(heartbeat_msg, "autopilot", 0)
        return autopilot == MAV_AUTOPILOT_ARDUPILOTMEGA

    def get_capabilities(self) -> CapabilityProfile:
        """Full-featured ArduPilot profile."""
        return ardupilot_profile()

    def handle_message(self, msg: Any, normalizer: MavlinkNormalizer) -> None:
        """Delegate to normalizer. Uses default APM mode mapping."""
        normalizer.apply(msg)

    def request_initial_state(self, transport: Any) -> None:
        """Request 10 Hz message rates via SET_MESSAGE_INTERVAL."""
        conn = getattr(transport, "connection", None)
        if conn is None:
            logger.warning("ArduPilotAdapter: no connection for message rate request")
            return
        sysid = conn.target_system
        compid = conn.target_component
        mav = conn.mav
        messages = [
            (MAVLINK_MSG_ID_GLOBAL_POSITION_INT, MESSAGE_INTERVAL_US_10HZ),
            (MAVLINK_MSG_ID_ATTITUDE, MESSAGE_INTERVAL_US_10HZ),
            (MAVLINK_MSG_ID_SYS_STATUS, MESSAGE_INTERVAL_US_10HZ),
            (MAVLINK_MSG_ID_VFR_HUD, MESSAGE_INTERVAL_US_10HZ),
        ]
        for msg_id, interval_us in messages:
            mav.command_long_send(
                sysid,
                compid,
                MAV_CMD_SET_MESSAGE_INTERVAL,
                0,
                msg_id,
                interval_us,
                0,
                0,
                0,
                0,
                0,
            )
        logger.info(
            "Requested MAVLink message rates (10 Hz) for GLOBAL_POSITION_INT, ATTITUDE, SYS_STATUS, VFR_HUD"
        )

    def safe_probe(self, transport: Any) -> list[str]:
        """Probe param read. Return downgrade reasons on failure."""
        downgrades: list[str] = []
        conn = getattr(transport, "connection", None)
        if conn is None or not getattr(transport, "is_connected", True):
            return downgrades
        if not self.get_capabilities().supports_params_read:
            return downgrades
        try:
            sysid = conn.target_system
            compid = conn.target_component
            mav = conn.mav
            mav.param_request_read_send(sysid, compid, b"", 0)
            elapsed = 0.0
            while elapsed < PARAM_PROBE_TIMEOUT_SEC:
                msg = transport.read_message(timeout=PARAM_PROBE_POLL_INTERVAL_SEC)
                if msg is not None and msg.get_type() == "PARAM_VALUE":
                    return downgrades
                elapsed += PARAM_PROBE_POLL_INTERVAL_SEC
            downgrades.append(DOWNGRADE_PARAM_READ_TIMEOUT)
            logger.warning("Param read probe timeout; recording downgrade")
        except Exception as e:
            logger.warning("Param read probe failed: %s", e)
            downgrades.append(DOWNGRADE_PARAM_READ_TIMEOUT)
        return downgrades
