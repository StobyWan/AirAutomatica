"""Telemetry backends."""

from airautomatica.telemetry.base import TelemetrySource
from airautomatica.telemetry.mock import MockTelemetry
from airautomatica.telemetry.serial_mavlink import SerialMavlinkTelemetry

__all__ = ["TelemetrySource", "MockTelemetry", "SerialMavlinkTelemetry"]
