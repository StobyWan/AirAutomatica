"""Tests for telemetry preprocessing pipeline scaffolding."""

from datetime import datetime, timezone

import pytest

from airautomatica.models.state import AircraftState
from airautomatica.telemetry.preprocessing import (
    FlightPhase,
    LlmContextPayload,
    PreprocessingSummary,
    TelemetryPreprocessor,
)
from airautomatica.telemetry.preprocessing.llm_policy import should_invoke_llm
from airautomatica.telemetry.preprocessing.models import TelemetryEvent
from airautomatica.telemetry.preprocessing.rolling_buffer import (
    RollingWindowBuffer,
    create_buffers,
)


def _make_state(
    mode: str = "GUIDED",
    armed: bool = True,
    climb_rate: float = 0.0,
    groundspeed: float = 5.0,
    voltage: float = 12.5,
    rel_alt: float = 100.0,
) -> AircraftState:
    return AircraftState(
        connected=True,
        heartbeat=1,
        mode=mode,
        lat=37.0,
        lon=-122.0,
        rel_alt_m=rel_alt,
        heading_deg=45.0,
        roll_rad=0.0,
        pitch_rad=0.0,
        yaw_rad=0.0,
        voltage_v=voltage,
        current_a=2.0,
        groundspeed_m_s=groundspeed,
        airspeed_m_s=6.0,
        timestamp=datetime.now(timezone.utc),
        armed=armed,
        climb_rate_m_s=climb_rate,
    )


def test_rolling_buffer_append_and_get() -> None:
    """RollingWindowBuffer appends and returns samples."""
    buf: RollingWindowBuffer[AircraftState] = RollingWindowBuffer(maxlen=5)
    assert len(buf) == 0
    assert not buf.is_ready()

    state = _make_state()
    buf.append(state)
    buf.append(state)
    assert len(buf) == 2
    assert buf.is_ready()
    samples = buf.get_samples()
    assert len(samples) == 2
    assert samples[0] is state


def test_rolling_buffer_maxlen() -> None:
    """RollingWindowBuffer respects maxlen."""
    buf: RollingWindowBuffer[AircraftState] = RollingWindowBuffer(maxlen=3)
    for _ in range(5):
        buf.append(_make_state())
    assert len(buf) == 3


def test_rolling_buffer_trim_by_age() -> None:
    """RollingWindowBuffer trims by max_age_sec when items have timestamp."""
    from datetime import timedelta

    buf: RollingWindowBuffer[AircraftState] = RollingWindowBuffer(
        maxlen=10, max_age_sec=1.0
    )
    old_ts = datetime.now(timezone.utc) - timedelta(seconds=2)
    old_state = AircraftState(
        connected=True,
        heartbeat=1,
        mode="GUIDED",
        lat=37.0,
        lon=-122.0,
        rel_alt_m=100.0,
        heading_deg=45.0,
        roll_rad=0.0,
        pitch_rad=0.0,
        yaw_rad=0.0,
        voltage_v=12.5,
        current_a=2.0,
        groundspeed_m_s=5.0,
        airspeed_m_s=6.0,
        timestamp=old_ts,
        armed=True,
        climb_rate_m_s=0.0,
    )
    buf.append(old_state)
    buf.append(_make_state())
    samples = buf.get_samples()
    assert len(samples) >= 1


def test_create_buffers() -> None:
    """create_buffers returns short/medium/long buffers."""
    bufs = create_buffers(short_maxlen=5, medium_maxlen=10, long_maxlen=15)
    assert "short" in bufs
    assert "medium" in bufs
    assert "long" in bufs
    for _ in range(10):
        bufs["short"].append(_make_state())
    assert len(bufs["short"]) == 5


def test_preprocessor_accepts_states() -> None:
    """TelemetryPreprocessor.on_state does not crash."""
    preprocessor = TelemetryPreprocessor()
    for _ in range(5):
        preprocessor.on_state(_make_state())
    summary = preprocessor.get_summary()
    assert isinstance(summary, PreprocessingSummary)
    assert summary.phase in (p.value for p in FlightPhase)
    assert summary.mode == "GUIDED"
    assert summary.buffer_sample_count == 5


def test_preprocessor_summary_deterministic() -> None:
    """get_summary returns structured output with expected fields."""
    preprocessor = TelemetryPreprocessor()
    for _ in range(5):
        preprocessor.on_state(_make_state(mode="RTL", armed=True))
    for _ in range(4):
        summary = preprocessor.get_summary()
    assert summary.phase == FlightPhase.RTL.value
    assert summary.mode == "RTL"
    assert hasattr(summary, "buffer_sample_count")
    assert hasattr(summary, "last_timestamp")


def test_preprocessor_llm_context_deterministic() -> None:
    """get_llm_context returns capped, structured payload."""
    preprocessor = TelemetryPreprocessor()
    preprocessor.on_state(_make_state())
    ctx = preprocessor.get_llm_context()
    assert isinstance(ctx, LlmContextPayload)
    assert ctx.phase in (p.value for p in FlightPhase)
    assert ctx.mode == "GUIDED"
    assert len(ctx.top_events) == 3
    assert len(ctx.top_metrics) == 5
    assert "voltage_v" in ctx.top_metrics or "rel_alt_m" in ctx.top_metrics
    assert ctx.trend_summary


def test_preprocessor_recent_events_with_good_state() -> None:
    """get_recent_events returns empty list when no events triggered."""
    preprocessor = TelemetryPreprocessor()
    preprocessor.on_state(_make_state())
    events = preprocessor.get_recent_events()
    assert isinstance(events, list)


def test_llm_policy_user_requested() -> None:
    """should_invoke_llm returns True when user_requested."""
    assert should_invoke_llm(user_requested=True) is True


def test_llm_policy_nontrivial_event() -> None:
    """should_invoke_llm returns True when nontrivial event present."""
    event = TelemetryEvent(
        name="battery_sag",
        severity="warn",
        started_at=datetime.now(timezone.utc),
        ended_at=None,
        evidence={"voltage_v": 11.0},
        operator_hint=None,
    )
    assert should_invoke_llm(events=[event]) is True


def test_llm_policy_interval_blocks() -> None:
    """should_invoke_llm returns False when within min_interval."""
    from datetime import timedelta

    last = datetime.now(timezone.utc) - timedelta(seconds=5)
    assert (
        should_invoke_llm(
            user_requested=False,
            events=[],
            last_invoke_at=last,
            min_interval_sec=20.0,
        )
        is False
    )


def test_preprocessor_empty_state() -> None:
    """get_summary and get_llm_context work with no state (empty buffers)."""
    preprocessor = TelemetryPreprocessor()
    summary = preprocessor.get_summary()
    assert summary.phase == FlightPhase.UNKNOWN.value
    assert summary.mode == "UNKNOWN"
    assert summary.buffer_sample_count == 0
    ctx = preprocessor.get_llm_context()
    assert ctx.phase == FlightPhase.UNKNOWN.value
    assert len(ctx.top_metrics) == 5


def test_feature_engine_computes_features() -> None:
    """FeatureEngine computes roll_var, pitch_var, distance_to_home when data exists."""
    from airautomatica.telemetry.preprocessing.feature_engine import FeatureEngine
    from airautomatica.telemetry.preprocessing.rolling_buffer import create_buffers

    engine = FeatureEngine()
    bufs = create_buffers(short_maxlen=10, medium_maxlen=20, long_maxlen=30)
    state = _make_state(voltage=12.5, rel_alt=100)
    for _ in range(5):
        bufs["short"].append(state)
        bufs["medium"].append(state)
    features = engine.compute(bufs, state)
    assert features.roll_var is not None or features.pitch_var is not None
    assert features.watts is not None
    assert features.watts == 12.5 * 2.0


def test_feature_engine_distance_to_home() -> None:
    """FeatureEngine computes distance_to_home when home_lat/lon present."""
    from airautomatica.telemetry.preprocessing.feature_engine import FeatureEngine
    from airautomatica.telemetry.preprocessing.rolling_buffer import create_buffers

    engine = FeatureEngine()
    bufs = create_buffers(short_maxlen=5)
    state = _make_state()
    state_with_home = AircraftState(
        **{
            k: getattr(state, k)
            for k in [
                "connected",
                "heartbeat",
                "mode",
                "lat",
                "lon",
                "rel_alt_m",
                "heading_deg",
                "roll_rad",
                "pitch_rad",
                "yaw_rad",
                "voltage_v",
                "current_a",
                "groundspeed_m_s",
                "airspeed_m_s",
                "timestamp",
                "armed",
                "climb_rate_m_s",
            ]
        },
        home_lat=37.001,
        home_lon=-122.001,
    )
    bufs["short"].append(state_with_home)
    features = engine.compute(bufs, state_with_home)
    assert features.distance_to_home_m is not None
    assert features.distance_to_home_m > 0


def test_event_engine_hysteresis_opens_after_n_samples() -> None:
    """EventEngine opens gps_degraded after open_samples consecutive evaluate calls."""
    from airautomatica.telemetry.preprocessing.event_engine import EventEngine
    from airautomatica.telemetry.preprocessing.feature_engine import FeatureEngine
    from airautomatica.telemetry.preprocessing.rolling_buffer import create_buffers

    engine = EventEngine(open_samples=3, clear_samples=2)
    fe = FeatureEngine()
    bufs = create_buffers(short_maxlen=10, medium_maxlen=10)
    base = _make_state()
    state_low_sats = AircraftState(
        connected=base.connected,
        heartbeat=base.heartbeat,
        mode=base.mode,
        lat=base.lat,
        lon=base.lon,
        rel_alt_m=base.rel_alt_m,
        heading_deg=base.heading_deg,
        roll_rad=base.roll_rad,
        pitch_rad=base.pitch_rad,
        yaw_rad=base.yaw_rad,
        voltage_v=base.voltage_v,
        current_a=base.current_a,
        groundspeed_m_s=base.groundspeed_m_s,
        airspeed_m_s=base.airspeed_m_s,
        timestamp=base.timestamp,
        armed=base.armed,
        climb_rate_m_s=base.climb_rate_m_s,
        satellites_visible=4,
        gps_fix_type=2,
    )
    for _ in range(5):
        bufs["short"].append(state_low_sats)
        bufs["medium"].append(state_low_sats)
    features = fe.compute(bufs, state_low_sats)
    events_after_3 = []
    for _ in range(4):
        events_after_3 = engine.evaluate(features, state_low_sats)
    assert any(e.name == "gps_degraded" for e in events_after_3)


def test_llm_context_payload_shape() -> None:
    """get_llm_context returns exactly 3 events, 5 metrics, 1 trend."""
    preprocessor = TelemetryPreprocessor()
    for _ in range(5):
        preprocessor.on_state(_make_state())
    ctx = preprocessor.get_llm_context()
    assert len(ctx.top_events) == 3
    assert len(ctx.top_metrics) == 5
    assert ctx.trend_summary
    assert "phase" in ctx.to_dict()
    assert "mode" in ctx.to_dict()
    assert "top_events" in ctx.to_dict()
    assert "top_metrics" in ctx.to_dict()
    assert "trend_summary" in ctx.to_dict()


def test_flight_phase_engine_mode_first() -> None:
    """FlightPhaseEngine returns RTL when mode is RTL."""
    from airautomatica.telemetry.preprocessing.feature_engine import FeatureEngine
    from airautomatica.telemetry.preprocessing.flight_phase_engine import (
        FlightPhaseEngine,
    )
    from airautomatica.telemetry.preprocessing.rolling_buffer import create_buffers

    engine = FlightPhaseEngine(hold_samples=2)
    fe = FeatureEngine()
    bufs = create_buffers(short_maxlen=5, medium_maxlen=10)
    state = _make_state(mode="RTL", armed=True)
    bufs["short"].append(state)
    bufs["medium"].append(state)
    features = fe.compute(bufs, state)
    for _ in range(3):
        phase = engine.classify(state, features)
    assert phase == FlightPhase.RTL.value


def test_flight_phase_engine_hysteresis() -> None:
    """FlightPhaseEngine holds phase for hold_samples before transitioning."""
    from airautomatica.telemetry.preprocessing.feature_engine import FeatureEngine
    from airautomatica.telemetry.preprocessing.flight_phase_engine import (
        FlightPhaseEngine,
    )
    from airautomatica.telemetry.preprocessing.rolling_buffer import create_buffers

    engine = FlightPhaseEngine(hold_samples=3)
    fe = FeatureEngine()
    bufs = create_buffers(short_maxlen=5, medium_maxlen=10)
    state_rtl = _make_state(mode="RTL", armed=True)
    bufs["short"].append(state_rtl)
    bufs["medium"].append(state_rtl)
    features = fe.compute(bufs, state_rtl)
    p1 = engine.classify(state_rtl, features)
    p2 = engine.classify(state_rtl, features)
    p3 = engine.classify(state_rtl, features)
    assert p1 == FlightPhase.UNKNOWN.value
    assert p2 == FlightPhase.UNKNOWN.value
    assert p3 == FlightPhase.RTL.value


def test_heading_drift_event() -> None:
    """heading_drift opens when heading_change_rate exceeds threshold."""
    from airautomatica.telemetry.preprocessing.event_engine import EventEngine
    from airautomatica.telemetry.preprocessing.feature_engine import FeatureSet

    engine = EventEngine(open_samples=3, clear_samples=2)
    features = FeatureSet(
        roll_var=0.01,
        pitch_var=0.01,
        heading_change_rate_deg_s=20.0,
        altitude_rate_m_s=0.0,
        voltage_trend=0.0,
        current_trend=0.0,
        watts=50.0,
        distance_to_home_m=1000.0,
        home_bearing_deg=90.0,
        relative_bearing_deg=0.0,
        estimated_endurance_s=3600.0,
        endurance_confidence="medium",
        return_margin_s=3000.0,
        groundspeed_mean_medium=5.0,
    )
    events = []
    for _ in range(4):
        events = engine.evaluate(features, _make_state())
    assert any(e.name == "heading_drift" for e in events)


def test_mission_progress_stall_event() -> None:
    """mission_progress_stall opens when AUTO mode with low groundspeed."""
    from airautomatica.telemetry.preprocessing.event_engine import EventEngine
    from airautomatica.telemetry.preprocessing.feature_engine import FeatureSet

    engine = EventEngine(open_samples=3, clear_samples=2)
    features = FeatureSet(
        roll_var=0.01,
        pitch_var=0.01,
        heading_change_rate_deg_s=0.0,
        altitude_rate_m_s=0.0,
        voltage_trend=0.0,
        current_trend=0.0,
        watts=50.0,
        distance_to_home_m=1000.0,
        home_bearing_deg=90.0,
        relative_bearing_deg=0.0,
        estimated_endurance_s=3600.0,
        endurance_confidence="medium",
        return_margin_s=3000.0,
        groundspeed_mean_medium=0.3,
    )
    state = _make_state(mode="AUTO", armed=True, groundspeed=0.3)
    events = []
    for _ in range(4):
        events = engine.evaluate(features, state)
    assert any(e.name == "mission_progress_stall" for e in events)


def test_trend_summary_phase_aware() -> None:
    """Trend summary includes phase and key metrics."""
    preprocessor = TelemetryPreprocessor()
    for _ in range(5):
        preprocessor.on_state(_make_state(mode="RTL", armed=True))
    for _ in range(4):
        summary = preprocessor.get_summary()
    ctx = preprocessor.get_llm_context()
    assert (
        "RTL" in ctx.trend_summary
        or "rtl" in ctx.trend_summary
        or "Rtl" in ctx.trend_summary
    )


def test_config_preprocessing_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_preprocessing_enabled respects env."""
    from airautomatica.config import get_preprocessing_enabled

    monkeypatch.setenv("AIRAUTOMATICA_PREPROCESSING_ENABLED", "0")
    assert get_preprocessing_enabled() is False
    monkeypatch.setenv("AIRAUTOMATICA_PREPROCESSING_ENABLED", "1")
    assert get_preprocessing_enabled() is True
    monkeypatch.setenv("AIRAUTOMATICA_PREPROCESSING_ENABLED", "true")
    assert get_preprocessing_enabled() is True
    monkeypatch.delenv("AIRAUTOMATICA_PREPROCESSING_ENABLED", raising=False)
    assert get_preprocessing_enabled() is True  # default is 1
