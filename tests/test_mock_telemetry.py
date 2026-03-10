"""Tests for mock telemetry and state store."""

import math
from datetime import datetime, timezone

import pytest

from airautomatica.models.state import AircraftState
from airautomatica.services.state_store import StateStore
from airautomatica.telemetry.mock import MockTelemetry


@pytest.mark.asyncio
async def test_mock_heartbeat_age_increases() -> None:
    """Mock telemetry heartbeat_age_s increases between simulated heartbeats."""
    source = MockTelemetry(interval_sec=0.05, heartbeat_interval_sec=0.2)
    states: list[AircraftState] = []
    async for state in source.stream():
        states.append(state)
        if len(states) >= 6:
            break
    # First state: heartbeat just received, age ~0
    assert states[0].heartbeat_age_s < 0.1
    # Subsequent states: age should increase until next heartbeat at ~0.2s
    ages = [s.heartbeat_age_s for s in states]
    assert all(not math.isnan(a) for a in ages)
    # Age should generally increase (or reset after heartbeat)
    assert max(ages) > 0.05


@pytest.mark.asyncio
async def test_mock_telemetry_yields_states() -> None:
    """Mock telemetry should yield valid AircraftState updates."""
    source = MockTelemetry(interval_sec=0.01)
    states: list[AircraftState] = []
    async for state in source.stream():
        states.append(state)
        if len(states) >= 3:
            break
    assert len(states) == 3
    for s in states:
        assert isinstance(s, AircraftState)
        assert s.connected is True
        assert s.heartbeat >= 1
        assert -90 <= s.lat <= 90
        assert -180 <= s.lon <= 180
        assert s.rel_alt_m >= 0
        assert 0 <= s.heading_deg < 360
        assert s.voltage_v > 0
        assert isinstance(s.timestamp, datetime)


@pytest.mark.asyncio
async def test_state_store_update_and_get() -> None:
    """StateStore should store and return the latest state."""
    store = StateStore()
    assert store.get() is None

    state = AircraftState(
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
        groundspeed_m_s=10.0,
        airspeed_m_s=12.0,
        timestamp=datetime.now(timezone.utc),
    )
    store.update(state)
    got = store.get()
    assert got is state
    assert got is not None and got.lat == 37.0
