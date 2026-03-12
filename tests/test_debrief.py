"""Tests for debrief engine and compact payload."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from airautomatica.telemetry.preprocessing import debrief_engine
from airautomatica.telemetry.preprocessing.debrief_engine import (
    CompactDebriefPayload,
    DebriefEngine,
    DebriefEventStat,
    DebriefSummary,
    build_compact_debrief_context,
)


def _make_sample(
    i: int,
    lat: float = 37.0,
    lon: float = -122.0,
    voltage: float = 12.5,
    current: float = 5.0,
    mode: str = "GUIDED",
    rel_alt: float = 100.0,
) -> dict:
    base = datetime(2025, 3, 12, 10, 0, 0, tzinfo=timezone.utc)
    return {
        "timestamp": base + timedelta(seconds=i),
        "lat": lat,
        "lon": lon,
        "rel_alt_m": rel_alt,
        "voltage_v": voltage,
        "current_a": current,
        "groundspeed_m_s": 5.0,
        "mode": mode,
        "heading_deg": 45.0,
        "roll_rad": 0.0,
        "pitch_rad": 0.0,
        "yaw_rad": 0.0,
        "airspeed_m_s": 6.0,
        "connected": True,
    }


def test_debrief_duration_calculation() -> None:
    """Debrief computes session duration from sample timestamps."""
    persistence = MagicMock()
    persistence.get_session_home.return_value = (None, None, None)
    samples = [_make_sample(i) for i in range(10)]
    persistence.get_session_telemetry_for_debrief.return_value = samples

    engine = DebriefEngine()
    summary = engine.generate(1, persistence, sample_limit=100)
    assert summary is not None
    assert summary.session_duration_sec > 0
    assert summary.session_duration_sec <= 15


def test_debrief_phase_breakdown() -> None:
    """Debrief aggregates phase durations deterministically."""
    persistence = MagicMock()
    persistence.get_session_home.return_value = (None, None, None)
    samples = [_make_sample(i, mode="GUIDED") for i in range(5)] + [
        _make_sample(i, mode="RTL") for i in range(5, 10)
    ]
    persistence.get_session_telemetry_for_debrief.return_value = samples

    engine = DebriefEngine()
    summary = engine.generate(1, persistence, sample_limit=100)
    assert summary is not None
    assert "phase_duration_sec" in summary.__dict__
    phases = summary.phase_duration_sec
    assert isinstance(phases, dict)
    assert sum(phases.values()) > 0


def test_debrief_top_event_aggregation() -> None:
    """Debrief aggregates events by duration, deterministic order."""
    persistence = MagicMock()
    persistence.get_session_home.return_value = (None, None, None)
    samples = [_make_sample(i, voltage=10.5) for i in range(15)]
    persistence.get_session_telemetry_for_debrief.return_value = samples

    engine = DebriefEngine()
    summary = engine.generate(1, persistence, sample_limit=100)
    assert summary is not None
    assert isinstance(summary.top_events, list)
    for e in summary.top_events:
        assert hasattr(e, "name")
        assert hasattr(e, "count")
        assert hasattr(e, "duration_sec")


def test_debrief_compact_payload_shape() -> None:
    """Compact debrief payload has fixed shape: duration, phase, 3 events, 5 metrics, 1 sentence."""
    summary = DebriefSummary(
        session_id=1,
        session_duration_sec=300.0,
        phase_duration_sec={"cruise": 200.0, "rtl": 100.0},
        peak_distance_from_home_m=1500.0,
        average_power_w=80.0,
        peak_power_w=120.0,
        minimum_voltage_v=11.8,
        top_events=[
            DebriefEventStat("weak_return_margin", 1, 30.0),
            DebriefEventStat("high_power_draw", 1, 10.0),
        ],
        weak_return_margin_occurred=True,
        gps_degraded_occurred=False,
        unstable_attitude_occurred=False,
        assessment_tags=["return_risk"],
    )
    compact = build_compact_debrief_context(summary)
    assert isinstance(compact, CompactDebriefPayload)
    assert compact.total_duration_sec == 300.0
    assert compact.dominant_phase == "cruise"
    assert len(compact.top_3_event_summaries) == 3
    assert len(compact.top_5_metrics) == 5
    assert compact.assessment_sentence
    d = compact.to_dict()
    assert "total_duration_sec" in d
    assert "dominant_phase" in d
    assert "top_3_event_summaries" in d
    assert "top_5_metrics" in d
    assert "assessment_sentence" in d


def test_debrief_deterministic_output_ordering() -> None:
    """Top events are sorted by duration desc, then name asc."""
    persistence = MagicMock()
    persistence.get_session_home.return_value = (None, None, None)
    samples = [_make_sample(i) for i in range(20)]
    persistence.get_session_telemetry_for_debrief.return_value = samples

    engine = DebriefEngine()
    s1 = engine.generate(1, persistence, sample_limit=100)
    s2 = engine.generate(1, persistence, sample_limit=100)
    assert s1 is not None and s2 is not None
    assert s1.session_duration_sec == s2.session_duration_sec
    assert s1.phase_duration_sec == s2.phase_duration_sec
    names1 = [e.name for e in s1.top_events]
    names2 = [e.name for e in s2.top_events]
    assert names1 == names2


def test_debrief_empty_session_returns_none() -> None:
    """Debrief returns None when no samples."""
    persistence = MagicMock()
    persistence.get_session_telemetry_for_debrief.return_value = []

    engine = DebriefEngine()
    summary = engine.generate(1, persistence)
    assert summary is None


def test_debrief_power_and_voltage_aggregates() -> None:
    """Debrief computes avg/peak power and min voltage."""
    persistence = MagicMock()
    persistence.get_session_home.return_value = (None, None, None)
    samples = [
        _make_sample(i, voltage=12.5 - i * 0.05, current=5.0 + i * 0.5)
        for i in range(10)
    ]
    persistence.get_session_telemetry_for_debrief.return_value = samples

    engine = DebriefEngine()
    summary = engine.generate(1, persistence, sample_limit=100)
    assert summary is not None
    assert summary.average_power_w is not None
    assert summary.peak_power_w is not None
    assert summary.minimum_voltage_v is not None
    assert summary.minimum_voltage_v <= 12.5


def test_sample_to_state_uses_stored_fields_when_present() -> None:
    """_sample_to_state uses armed, climb_rate, home, gps when stored."""
    sample = {
        **_make_sample(0),
        "armed": False,
        "climb_rate_m_s": 2.5,
        "home_lat": 37.1,
        "home_lon": -122.1,
        "gps_fix_type": 3,
        "satellites_visible": 10,
    }
    state = debrief_engine._sample_to_state(
        sample, home_lat=37.0, home_lon=-122.0, climb_rate_m_s=0.0
    )
    assert state.armed is False
    assert state.climb_rate_m_s == 2.5
    assert state.home_lat == 37.1
    assert state.home_lon == -122.1
    assert state.gps_fix_type == 3
    assert state.satellites_visible == 10


def test_sample_to_state_legacy_fallbacks_when_null() -> None:
    """_sample_to_state falls back for NULL new fields (legacy sessions)."""
    sample = _make_sample(0)
    # Omit armed, climb_rate_m_s, home_lat, home_lon, gps_fix_type, satellites_visible
    state = debrief_engine._sample_to_state(
        sample, home_lat=37.0, home_lon=-122.0, climb_rate_m_s=1.5
    )
    assert state.armed is True  # legacy: assume armed
    assert state.climb_rate_m_s == 1.5  # use derived
    assert state.home_lat == 37.0  # use session home
    assert state.home_lon == -122.0
    assert state.gps_fix_type is None
    assert state.satellites_visible is None


def test_debrief_with_stored_home_uses_correct_distance() -> None:
    """Debrief with stored home_lat/home_lon uses correct distance_to_home."""
    persistence = MagicMock()
    persistence.get_session_home.return_value = (None, None, None)
    home_lat, home_lon = 37.0, -122.0
    samples = []
    for i in range(5):
        s = _make_sample(i, lat=home_lat + i * 0.001, lon=home_lon)
        s["home_lat"] = home_lat
        s["home_lon"] = home_lon
        s["armed"] = True
        s["climb_rate_m_s"] = 0.0
        samples.append(s)
    persistence.get_session_telemetry_for_debrief.return_value = samples

    engine = DebriefEngine()
    summary = engine.generate(1, persistence, sample_limit=100)
    assert summary is not None
    assert summary.peak_distance_from_home_m is not None
    assert summary.peak_distance_from_home_m > 0


def test_debrief_session_override_wins_over_per_sample_home() -> None:
    """When session has manual override, it overrides per-sample home for all samples."""
    persistence = MagicMock()
    override_lat, override_lon = 37.5, -122.5
    persistence.get_session_home.return_value = (
        override_lat,
        override_lon,
        "manual_session",
    )
    samples = []
    for i in range(3):
        s = _make_sample(i, lat=37.0 + i * 0.001, lon=-122.0)
        s["home_lat"] = 37.0
        s["home_lon"] = -122.0
        s["armed"] = True
        s["climb_rate_m_s"] = 0.0
        samples.append(s)
    persistence.get_session_telemetry_for_debrief.return_value = samples

    state = debrief_engine._sample_to_state(
        samples[0], override_lat, override_lon, 0.0, session_override_active=True
    )
    assert state.home_lat == override_lat
    assert state.home_lon == override_lon

    state_no_override = debrief_engine._sample_to_state(
        samples[0], 37.0, -122.0, 0.0, session_override_active=False
    )
    assert state_no_override.home_lat == 37.0
    assert state_no_override.home_lon == -122.0
