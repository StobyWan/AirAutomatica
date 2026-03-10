"""Tests for dashboard route."""

import pytest
from fastapi.testclient import TestClient

from airautomatica.api.server import create_app
from airautomatica.services.state_store import StateStore


@pytest.fixture
def store() -> StateStore:
    return StateStore()


@pytest.fixture
def client(store: StateStore) -> TestClient:
    return TestClient(create_app(store))


def test_dashboard_route_exists(client: TestClient) -> None:
    """GET /dashboard returns 200 and HTML containing AIRAUTOMATICA."""
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "AIRAUTOMATICA" in r.text
    assert "dashboard" in r.text.lower()
