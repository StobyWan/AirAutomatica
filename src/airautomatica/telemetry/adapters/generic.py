"""Generic MAVLink adapter: read-only fallback for unknown devices."""

from typing import Any

from airautomatica.telemetry.capabilities import (
    CapabilityProfile,
    generic_readonly_profile,
)
from airautomatica.telemetry.mavlink_parser import MavlinkNormalizer


class GenericMavlinkAdapter:
    """Generic adapter for unknown MAVLink devices. Read-only telemetry."""

    def detect(self, heartbeat_msg: Any) -> bool:
        """Always True. Fallback when no other adapter matches."""
        return True

    def get_capabilities(self) -> CapabilityProfile:
        """Read-only profile. No commands, no params, no missions."""
        return generic_readonly_profile()

    def handle_message(self, msg: Any, normalizer: MavlinkNormalizer) -> None:
        """Use generic mode mapping (custom_mode as string). Delegate to normalizer."""
        generic_mapping = {i: str(i) for i in range(50)}
        normalizer.set_mode_mapping(generic_mapping)
        normalizer.apply(msg)

    def request_initial_state(self, transport: Any) -> None:
        """No requests. Unknown device; avoid sending commands."""
        pass

    def safe_probe(self, transport: Any) -> list[str]:
        """No probes. Unknown device."""
        return []
