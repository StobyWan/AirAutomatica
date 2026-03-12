"""Tests for MAVLink parser and MavlinkNormalizer."""

import math
import time
from types import SimpleNamespace

import pytest

from airautomatica.models.state import AircraftState
from airautomatica.telemetry.mavlink_parser import (
    UINT16_MAX,
    MavlinkNormalizer,
)


def make_msg(msg_type: str, **kwargs: object) -> SimpleNamespace:
    """Create MAVLink-like message for testing."""
    m = SimpleNamespace()
    m.get_type = lambda: msg_type
    for k, v in kwargs.items():
        setattr(m, k, v)
    return m


def test_heartbeat_mode_auto() -> None:
    """HEARTBEAT custom_mode=10 -> mode=AUTO."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("HEARTBEAT", custom_mode=10))
    s = n.build_state()
    assert s.mode == "AUTO"
    assert s.heartbeat == 1
    assert s.connected is True


def test_heartbeat_mode_guided() -> None:
    """HEARTBEAT custom_mode=15 -> mode=GUIDED."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("HEARTBEAT", custom_mode=15))
    s = n.build_state()
    assert s.mode == "GUIDED"


def test_heartbeat_mode_unknown() -> None:
    """HEARTBEAT custom_mode=99 -> mode=UNKNOWN."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("HEARTBEAT", custom_mode=99))
    s = n.build_state()
    assert s.mode == "UNKNOWN"


def test_global_position_int() -> None:
    """GLOBAL_POSITION_INT: lat, lon, rel_alt conversion."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("HEARTBEAT", custom_mode=0))
    n.apply(
        make_msg(
            "GLOBAL_POSITION_INT",
            lat=376213000,
            lon=-1223790000,
            relative_alt=50000,
            hdg=9000,
        )
    )
    s = n.build_state()
    assert abs(s.lat - 37.6213) < 1e-4
    assert abs(s.lon - (-122.379)) < 1e-4
    assert s.rel_alt_m == 50.0
    assert s.heading_deg == 90.0


def test_global_position_int_hdg_invalid() -> None:
    """GLOBAL_POSITION_INT hdg=65535 -> heading unchanged (stays NaN)."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("HEARTBEAT", custom_mode=0))
    n.apply(
        make_msg(
            "GLOBAL_POSITION_INT",
            lat=0,
            lon=0,
            relative_alt=0,
            hdg=UINT16_MAX,
        )
    )
    s = n.build_state()
    assert math.isnan(s.heading_deg)


def test_attitude() -> None:
    """ATTITUDE: roll, pitch, yaw in radians."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("HEARTBEAT", custom_mode=0))
    n.apply(make_msg("ATTITUDE", roll=0.1, pitch=-0.2, yaw=1.57))
    s = n.build_state()
    assert s.roll_rad == 0.1
    assert s.pitch_rad == -0.2
    assert s.yaw_rad == 1.57


def test_sys_status_voltage() -> None:
    """SYS_STATUS voltage_battery=12400 -> 12.4V."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("HEARTBEAT", custom_mode=0))
    n.apply(make_msg("SYS_STATUS", voltage_battery=12400, current_battery=-1))
    s = n.build_state()
    assert s.voltage_v == 12.4


def test_sys_status_voltage_invalid() -> None:
    """SYS_STATUS voltage_battery=65535 -> no update (stays NaN)."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("HEARTBEAT", custom_mode=0))
    n.apply(make_msg("SYS_STATUS", voltage_battery=65535, current_battery=-1))
    s = n.build_state()
    assert math.isnan(s.voltage_v)


def test_sys_status_current() -> None:
    """SYS_STATUS current_battery=500 -> 5.0A."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("HEARTBEAT", custom_mode=0))
    n.apply(make_msg("SYS_STATUS", voltage_battery=65535, current_battery=500))
    s = n.build_state()
    assert s.current_a == 5.0


def test_sys_status_current_invalid() -> None:
    """SYS_STATUS current_battery=-1 -> no update (stays NaN)."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("HEARTBEAT", custom_mode=0))
    n.apply(make_msg("SYS_STATUS", voltage_battery=65535, current_battery=-1))
    s = n.build_state()
    assert math.isnan(s.current_a)


def test_vfr_hud() -> None:
    """VFR_HUD: heading, groundspeed, airspeed."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("HEARTBEAT", custom_mode=0))
    n.apply(
        make_msg(
            "VFR_HUD",
            heading=180,
            groundspeed=25.5,
            airspeed=28.0,
        )
    )
    s = n.build_state()
    assert s.heading_deg == 180
    assert s.groundspeed_m_s == 25.5
    assert s.airspeed_m_s == 28.0


def test_stale_heartbeat() -> None:
    """No HEARTBEAT for 5s -> connected=False."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=0.1)
    n.apply(make_msg("HEARTBEAT", custom_mode=0))
    s = n.build_state()
    assert s.connected is True
    time.sleep(0.15)
    s = n.build_state()
    assert s.connected is False


def test_initial_state_no_heartbeat() -> None:
    """Before any HEARTBEAT, connected=False."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("GLOBAL_POSITION_INT", lat=0, lon=0, relative_alt=0, hdg=0))
    s = n.build_state()
    assert s.connected is False
    assert s.heartbeat == 0


def test_heartbeat_count_increments() -> None:
    """Each HEARTBEAT increments heartbeat count."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("HEARTBEAT", custom_mode=0))
    n.apply(make_msg("HEARTBEAT", custom_mode=0))
    n.apply(make_msg("HEARTBEAT", custom_mode=10))
    s = n.build_state()
    assert s.heartbeat == 3


def test_last_heartbeat_at_and_age() -> None:
    """HEARTBEAT sets last_heartbeat_at and heartbeat_age_s."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("HEARTBEAT", custom_mode=0))
    s = n.build_state()
    assert s.last_heartbeat_at is not None
    assert s.heartbeat_age_s >= 0
    assert s.heartbeat_age_s < 1.0


def test_to_dict_serializes_nan_as_none() -> None:
    """AircraftState.to_dict() serializes NaN as None for JSON."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("HEARTBEAT", custom_mode=0))
    s = n.build_state()
    d = s.to_dict()
    assert d["lat"] is None
    assert d["voltage_v"] is None
    assert d["connected"] is True
    assert d["mode"] == "MANUAL"


def test_home_position() -> None:
    """HOME_POSITION: latitude, longitude -> home_lat, home_lon (ArduPilot)."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("HEARTBEAT", custom_mode=0))
    n.apply(make_msg("HOME_POSITION", latitude=376213000, longitude=-1223790000))
    s = n.build_state()
    assert s.home_lat == pytest.approx(37.6213, abs=1e-4)
    assert s.home_lon == pytest.approx(-122.379, abs=1e-4)


def test_gps_global_origin() -> None:
    """GPS_GLOBAL_ORIGIN: latitude, longitude -> home_lat, home_lon (INAV)."""
    n = MavlinkNormalizer(heartbeat_timeout_sec=10.0)
    n.apply(make_msg("HEARTBEAT", custom_mode=0))
    n.apply(make_msg("GPS_GLOBAL_ORIGIN", latitude=376213000, longitude=-1223790000))
    s = n.build_state()
    assert s.home_lat == pytest.approx(37.6213, abs=1e-4)
    assert s.home_lon == pytest.approx(-122.379, abs=1e-4)
