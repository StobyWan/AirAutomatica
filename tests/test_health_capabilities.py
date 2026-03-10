"""Tests for /health capabilities exposure."""

import pytest
from fastapi.testclient import TestClient

from airautomatica.api.server import create_app
from airautomatica.services.state_store import StateStore
from airautomatica.telemetry.capabilities import (
    DOWNGRADE_PARAM_READ_TIMEOUT,
    ardupilot_profile,
    capability_info,
)


@pytest.fixture
def store() -> StateStore:
    return StateStore()


@pytest.fixture
def client(store: StateStore) -> TestClient:
    return TestClient(create_app(store))


def test_health_includes_capabilities_when_set(
    client: TestClient, store: StateStore
) -> None:
    """GET /health includes capabilities when StateStore has CapabilityInfo."""
    info = capability_info("ArduPilot", "ardupilot", ardupilot_profile())
    store.set_capabilities(info)
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "capabilities" in data
    caps = data["capabilities"]
    assert caps["firmware_name"] == "ArduPilot"
    assert caps["profile_id"] == "ardupilot"
    assert caps["supports_params_read"] is True
    assert caps["supports_message_interval"] is True
    assert caps["supports_guided_actions"] is True
    assert "notes" in caps
    assert "downgrade_reasons" in caps
    assert caps["downgrade_reasons"] == []


def test_health_capabilities_include_downgrade_reasons(
    client: TestClient, store: StateStore
) -> None:
    """GET /health capabilities include downgrade_reasons when present."""
    info = capability_info(
        "ArduPilot",
        "ardupilot",
        ardupilot_profile(),
        downgrade_reasons=(DOWNGRADE_PARAM_READ_TIMEOUT,),
    )
    store.set_capabilities(info)
    r = client.get("/health")
    assert r.status_code == 200
    caps = r.json()["capabilities"]
    assert caps["downgrade_reasons"] == ["parameter read probe timeout"]


def test_health_omits_capabilities_when_none(
    client: TestClient, store: StateStore
) -> None:
    """GET /health omits capabilities when mock mode (no profile)."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "capabilities" not in data


def test_health_capabilities_serialization_shape(
    client: TestClient, store: StateStore
) -> None:
    """Capabilities object has expected keys for dashboard (firmware_name, profile_id, supports_*, notes, downgrade_reasons)."""
    info = capability_info("ArduPilot", "ardupilot", ardupilot_profile())
    store.set_capabilities(info)
    r = client.get("/health")
    assert r.status_code == 200
    caps = r.json()["capabilities"]
    expected_keys = {
        "firmware_name",
        "profile_id",
        "supports_params_read",
        "supports_params_write",
        "supports_command_long",
        "supports_message_interval",
        "supports_missions",
        "supports_guided_actions",
        "supports_rc_over_mavlink",
        "notes",
        "downgrade_reasons",
    }
    assert set(caps.keys()) >= expected_keys
