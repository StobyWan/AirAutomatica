"""Capability profile for MAVLink autopilots.

Controls UI/backend feature availability. Never expose unsupported actions
as if they are guaranteed to work.
"""

from dataclasses import dataclass

# Standard downgrade reason constants for probe failures
DOWNGRADE_PARAM_READ_TIMEOUT = "parameter read probe timeout"
DOWNGRADE_CMD_ACK_MISSING = "command ack missing"
DOWNGRADE_MESSAGE_INTERVAL_UNSUPPORTED = "message interval request unsupported"


@dataclass(frozen=True)
class CapabilityProfile:
    """Capability flags for an autopilot. Gate unsupported features at runtime."""

    supports_params_read: bool
    supports_params_write: bool
    supports_command_long: bool
    supports_message_interval: bool
    supports_missions: bool
    supports_guided_actions: bool
    supports_rc_over_mavlink: bool
    notes: str

    def to_dict(self) -> dict:
        """Serialize for API/JSON."""
        return {
            "supports_params_read": self.supports_params_read,
            "supports_params_write": self.supports_params_write,
            "supports_command_long": self.supports_command_long,
            "supports_message_interval": self.supports_message_interval,
            "supports_missions": self.supports_missions,
            "supports_guided_actions": self.supports_guided_actions,
            "supports_rc_over_mavlink": self.supports_rc_over_mavlink,
            "notes": self.notes,
        }


def ardupilot_profile() -> CapabilityProfile:
    """Full-featured ArduPilot capability set."""
    return CapabilityProfile(
        supports_params_read=True,
        supports_params_write=True,
        supports_command_long=True,
        supports_message_interval=True,
        supports_missions=True,
        supports_guided_actions=True,
        supports_rc_over_mavlink=True,
        notes="",
    )


def inav_profile() -> CapabilityProfile:
    """INAV: telemetry-first, conservative command support."""
    return CapabilityProfile(
        supports_params_read=True,
        supports_params_write=False,
        supports_command_long=True,
        supports_message_interval=False,
        supports_missions=True,
        supports_guided_actions=False,
        supports_rc_over_mavlink=False,
        notes="INAV: telemetry-first",
    )


def generic_readonly_profile() -> CapabilityProfile:
    """Unknown MAVLink device: read-only telemetry."""
    return CapabilityProfile(
        supports_params_read=False,
        supports_params_write=False,
        supports_command_long=False,
        supports_message_interval=False,
        supports_missions=False,
        supports_guided_actions=False,
        supports_rc_over_mavlink=False,
        notes="Unknown MAVLink device",
    )


@dataclass(frozen=True)
class CapabilityInfo:
    """Capability metadata for API/dashboard: firmware, profile, downgrade reasons."""

    firmware_name: str
    profile_id: str
    profile: CapabilityProfile
    downgrade_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        """Serialize for API/JSON."""
        d = self.profile.to_dict()
        d["firmware_name"] = self.firmware_name
        d["profile_id"] = self.profile_id
        d["downgrade_reasons"] = list(self.downgrade_reasons)
        return d


def capability_info(
    firmware_name: str,
    profile_id: str,
    profile: CapabilityProfile,
    downgrade_reasons: tuple[str, ...] = (),
) -> CapabilityInfo:
    """Build CapabilityInfo from profile and metadata."""
    return CapabilityInfo(
        firmware_name=firmware_name,
        profile_id=profile_id,
        profile=profile,
        downgrade_reasons=downgrade_reasons,
    )
