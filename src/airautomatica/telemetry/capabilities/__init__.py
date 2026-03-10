"""Capability profiles for MAVLink autopilots."""

from airautomatica.telemetry.capabilities.profile import (
    DOWNGRADE_CMD_ACK_MISSING,
    DOWNGRADE_MESSAGE_INTERVAL_UNSUPPORTED,
    DOWNGRADE_PARAM_READ_TIMEOUT,
    CapabilityInfo,
    CapabilityProfile,
    ardupilot_profile,
    capability_info,
    generic_readonly_profile,
    inav_profile,
)

__all__ = [
    "CapabilityInfo",
    "CapabilityProfile",
    "DOWNGRADE_CMD_ACK_MISSING",
    "DOWNGRADE_MESSAGE_INTERVAL_UNSUPPORTED",
    "DOWNGRADE_PARAM_READ_TIMEOUT",
    "ardupilot_profile",
    "capability_info",
    "generic_readonly_profile",
    "inav_profile",
]
