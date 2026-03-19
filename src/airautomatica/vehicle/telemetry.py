"""Rover telemetry aggregation: battery, WiFi RSSI, FC status."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_rover_telemetry() -> dict[str, Any]:
    """Return rover telemetry. Placeholder for battery, WiFi RSSI, FC status."""
    return {
        "battery_v": None,
        "wifi_rssi": None,
        "fc_connected": False,
    }
