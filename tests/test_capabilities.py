"""Tests for CapabilityProfile, CapabilityInfo, and factory functions."""

import pytest

from airautomatica.telemetry.capabilities import (
    DOWNGRADE_PARAM_READ_TIMEOUT,
    CapabilityInfo,
    CapabilityProfile,
    ardupilot_profile,
    capability_info,
    generic_readonly_profile,
    inav_profile,
)


def test_ardupilot_profile_full_capabilities() -> None:
    """ArduPilot has full capability set."""
    p = ardupilot_profile()
    assert p.supports_params_read is True
    assert p.supports_params_write is True
    assert p.supports_command_long is True
    assert p.supports_message_interval is True
    assert p.supports_missions is True
    assert p.supports_guided_actions is True
    assert p.supports_rc_over_mavlink is True
    assert p.notes == ""


def test_inav_profile_degraded() -> None:
    """INAV has telemetry-first, conservative command support."""
    p = inav_profile()
    assert p.supports_params_read is True
    assert p.supports_params_write is False
    assert p.supports_command_long is True
    assert p.supports_message_interval is False
    assert p.supports_missions is True
    assert p.supports_guided_actions is False
    assert p.supports_rc_over_mavlink is False
    assert "INAV" in p.notes


def test_generic_profile_readonly() -> None:
    """Generic unknown device is read-only."""
    p = generic_readonly_profile()
    assert p.supports_params_read is False
    assert p.supports_params_write is False
    assert p.supports_command_long is False
    assert p.supports_message_interval is False
    assert p.supports_missions is False
    assert p.supports_guided_actions is False
    assert p.supports_rc_over_mavlink is False
    assert "Unknown" in p.notes


def test_capability_profile_to_dict() -> None:
    """to_dict serializes all fields for API."""
    p = ardupilot_profile()
    d = p.to_dict()
    assert d["supports_params_read"] is True
    assert d["supports_message_interval"] is True
    assert d["notes"] == ""
    assert "supports_guided_actions" in d
    assert "supports_rc_over_mavlink" in d


def test_capability_info_to_dict() -> None:
    """CapabilityInfo.to_dict includes firmware_name, profile_id, downgrade_reasons."""
    info = capability_info(
        firmware_name="ArduPilot",
        profile_id="ardupilot",
        profile=ardupilot_profile(),
        downgrade_reasons=(DOWNGRADE_PARAM_READ_TIMEOUT,),
    )
    d = info.to_dict()
    assert d["firmware_name"] == "ArduPilot"
    assert d["profile_id"] == "ardupilot"
    assert d["downgrade_reasons"] == ["parameter read probe timeout"]
    assert d["supports_params_read"] is True
    assert d["supports_message_interval"] is True


def test_capability_info_to_dict_empty_downgrades() -> None:
    """CapabilityInfo.to_dict with no downgrades returns empty list."""
    info = capability_info("INAV", "inav", inav_profile())
    d = info.to_dict()
    assert d["firmware_name"] == "INAV"
    assert d["profile_id"] == "inav"
    assert d["downgrade_reasons"] == []
