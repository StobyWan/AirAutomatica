"""INAV adapter: telemetry-first, conservative command support."""

import logging
from typing import Any

from airautomatica.telemetry.capabilities import CapabilityProfile, inav_profile
from airautomatica.telemetry.mavlink_parser import MavlinkNormalizer

logger = logging.getLogger(__name__)

# MAV_AUTOPILOT_INAV (mavlink.io/common)
MAV_AUTOPILOT_INAV = 13

# INAV MAVLink emits ArduPilot-style custom_mode values in HEARTBEAT for GCS
# compatibility (see inav mavlink.c inavToArduCopterMap/inavToArduPlaneMap).
# Use default APM mapping; do NOT override with INAV-specific mapping.


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
        """Delegate to normalizer. INAV sends ArduPilot custom_mode; use default APM mapping."""
        normalizer.apply(msg)

    def request_initial_state(self, transport: Any) -> None:
        """No SET_MESSAGE_INTERVAL. INAV uses configured rates."""
        pass

    def safe_probe(self, transport: Any) -> list[str]:
        """No probes. INAV capabilities assumed conservative."""
        return []
