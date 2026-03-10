"""Autopilot adapter protocol for MAVLink capability detection and message handling."""

from typing import Any, Protocol, runtime_checkable

from airautomatica.telemetry.capabilities import CapabilityProfile


@runtime_checkable
class AutopilotAdapterProtocol(Protocol):
    """Protocol for autopilot-specific adapters (ArduPilot, INAV, Generic)."""

    def detect(self, heartbeat_msg: Any) -> bool:
        """Return True if this adapter handles the autopilot from HEARTBEAT."""
        ...

    def get_capabilities(self) -> CapabilityProfile:
        """Return capability profile for this autopilot."""
        ...

    def handle_message(self, msg: Any, normalizer: Any) -> None:
        """Process message and update state accumulator. Mutates normalizer."""
        ...

    def request_initial_state(self, transport: Any) -> None:
        """Request initial telemetry (e.g. message rates). Only if capability allows."""
        ...

    def safe_probe(self, transport: Any) -> list[str]:
        """Optional probes. Return downgrade reasons on failure (empty = no downgrades)."""
        ...
