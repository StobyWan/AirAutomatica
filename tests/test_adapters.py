"""Tests for autopilot adapter detection and capability assignment."""

from types import SimpleNamespace

import pytest

from airautomatica.telemetry.adapters import (
    ArduPilotAdapter,
    GenericMavlinkAdapter,
    INAVAdapter,
)
from airautomatica.telemetry.mavlink import detect_autopilot_from_heartbeat
from airautomatica.telemetry.mavlink_parser import MavlinkNormalizer


def make_heartbeat(autopilot: int = 0, custom_mode: int = 0) -> SimpleNamespace:
    """Create HEARTBEAT-like message for testing."""
    m = SimpleNamespace()
    m.get_type = lambda: "HEARTBEAT"
    m.autopilot = autopilot
    m.custom_mode = custom_mode
    return m


def test_detect_autopilot_ardupilot() -> None:
    """HEARTBEAT with autopilot=3 -> ardupilot."""
    hb = make_heartbeat(autopilot=3)
    assert detect_autopilot_from_heartbeat(hb) == "ardupilot"


def test_detect_autopilot_inav() -> None:
    """HEARTBEAT with autopilot=13 -> inav."""
    hb = make_heartbeat(autopilot=13)
    assert detect_autopilot_from_heartbeat(hb) == "inav"


def test_detect_autopilot_generic() -> None:
    """HEARTBEAT with unknown autopilot -> generic."""
    assert detect_autopilot_from_heartbeat(make_heartbeat(autopilot=0)) == "generic"
    assert detect_autopilot_from_heartbeat(make_heartbeat(autopilot=5)) == "generic"
    assert detect_autopilot_from_heartbeat(make_heartbeat(autopilot=12)) == "generic"


def test_ardupilot_adapter_detect() -> None:
    """ArduPilotAdapter detects autopilot=3."""
    adapter = ArduPilotAdapter()
    assert adapter.detect(make_heartbeat(autopilot=3)) is True
    assert adapter.detect(make_heartbeat(autopilot=13)) is False
    assert adapter.detect(make_heartbeat(autopilot=0)) is False


def test_inav_adapter_detect() -> None:
    """INAVAdapter detects autopilot=13."""
    adapter = INAVAdapter()
    assert adapter.detect(make_heartbeat(autopilot=13)) is True
    assert adapter.detect(make_heartbeat(autopilot=3)) is False
    assert adapter.detect(make_heartbeat(autopilot=0)) is False


def test_generic_adapter_detect() -> None:
    """GenericMavlinkAdapter always detects (fallback)."""
    adapter = GenericMavlinkAdapter()
    assert adapter.detect(make_heartbeat(autopilot=3)) is True
    assert adapter.detect(make_heartbeat(autopilot=13)) is True
    assert adapter.detect(make_heartbeat(autopilot=0)) is True


def test_ardupilot_capabilities() -> None:
    """ArduPilotAdapter returns ardupilot profile."""
    adapter = ArduPilotAdapter()
    cap = adapter.get_capabilities()
    assert cap.supports_message_interval is True
    assert cap.supports_guided_actions is True


def test_inav_capabilities() -> None:
    """INAVAdapter returns inav profile."""
    adapter = INAVAdapter()
    cap = adapter.get_capabilities()
    assert cap.supports_message_interval is False
    assert cap.supports_guided_actions is False
    assert cap.supports_params_read is True


def test_generic_capabilities() -> None:
    """GenericMavlinkAdapter returns generic readonly profile."""
    adapter = GenericMavlinkAdapter()
    cap = adapter.get_capabilities()
    assert cap.supports_command_long is False
    assert cap.supports_params_read is False
    assert "Unknown" in cap.notes


def test_ardupilot_handle_message_uses_apm_mapping() -> None:
    """ArduPilotAdapter handle_message sets mode via APM mapping."""
    adapter = ArduPilotAdapter()
    normalizer = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    hb = make_heartbeat(autopilot=3, custom_mode=15)
    adapter.handle_message(hb, normalizer)
    state = normalizer.build_state()
    assert state.mode == "GUIDED"


def test_inav_handle_message_uses_inav_mapping() -> None:
    """INAVAdapter handle_message uses INAV mode mapping."""
    adapter = INAVAdapter()
    normalizer = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    hb = make_heartbeat(autopilot=13, custom_mode=4)
    adapter.handle_message(hb, normalizer)
    state = normalizer.build_state()
    assert state.mode == "NAV_POSHOLD"


def test_generic_handle_message_uses_custom_mode_as_string() -> None:
    """GenericMavlinkAdapter uses custom_mode as string."""
    adapter = GenericMavlinkAdapter()
    normalizer = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    hb = make_heartbeat(autopilot=0, custom_mode=7)
    adapter.handle_message(hb, normalizer)
    state = normalizer.build_state()
    assert state.mode == "7"
