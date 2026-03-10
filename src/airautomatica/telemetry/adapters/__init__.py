"""Autopilot adapters for MAVLink capability detection and message handling."""

from airautomatica.telemetry.adapters.ardupilot import ArduPilotAdapter
from airautomatica.telemetry.adapters.base import AutopilotAdapterProtocol
from airautomatica.telemetry.adapters.generic import GenericMavlinkAdapter
from airautomatica.telemetry.adapters.inav import INAVAdapter

__all__ = [
    "AutopilotAdapterProtocol",
    "ArduPilotAdapter",
    "INAVAdapter",
    "GenericMavlinkAdapter",
]
