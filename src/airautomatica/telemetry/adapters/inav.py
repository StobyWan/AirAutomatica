"""INAV adapter: telemetry-first, conservative command support."""

import logging
from typing import Any

from airautomatica.telemetry.capabilities import CapabilityProfile, inav_profile
from airautomatica.telemetry.mavlink_parser import MavlinkNormalizer

logger = logging.getLogger(__name__)

# MAV_AUTOPILOT_INAV (mavlink.io/common)
MAV_AUTOPILOT_INAV = 13

# INAV flight mode mapping (custom_mode). Minimal set; unknown -> UNKNOWN.
# Based on INAV NAV modes and common stabilization modes.
MODE_MAPPING_INAV: dict[int, str] = {
    0: "MANUAL",
    1: "ACRO",
    2: "ANGLE",
    3: "HORIZON",
    4: "NAV_POSHOLD",
    5: "NAV_ALTHOLD",
    6: "NAV_COURSEHOLD",
    7: "NAV_CRUISE",
    10: "NAV_RTH",
    11: "NAV_WP",
    12: "NAV_LAUNCH",
    13: "NAV_WP",
    14: "NAV_RTH",
    15: "GUIDED",
    16: "NAV_EMERGENCY_LANDING",
}


class INAVAdapter:
    """INAV adapter with degraded/read-mostly capability."""

    def detect(self, heartbeat_msg: Any) -> bool:
        """True if autopilot is INAV (MAV_AUTOPILOT_INAV)."""
        autopilot = getattr(heartbeat_msg, "autopilot", 0)
        return autopilot == MAV_AUTOPILOT_INAV

    def get_capabilities(self) -> CapabilityProfile:
        """Telemetry-first INAV profile. No message_interval, no guided_actions."""
        return inav_profile()

    def handle_message(self, msg: Any, normalizer: MavlinkNormalizer) -> None:
        """Use INAV mode mapping. Delegate telemetry parsing to normalizer."""
        normalizer.set_mode_mapping(MODE_MAPPING_INAV)
        normalizer.apply(msg)

    def request_initial_state(self, transport: Any) -> None:
        """No SET_MESSAGE_INTERVAL. INAV uses configured rates."""
        pass

    def safe_probe(self, transport: Any) -> list[str]:
        """No probes. INAV capabilities assumed conservative."""
        return []
