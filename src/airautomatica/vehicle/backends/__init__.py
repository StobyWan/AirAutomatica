"""Vehicle control backends: mock, MAVLink, Arduino serial."""

from airautomatica.vehicle.backends.arduino_serial import ArduinoSerialVehicleBackend
from airautomatica.vehicle.backends.base import VehicleBackendBase
from airautomatica.vehicle.backends.mavlink import MavlinkVehicleBackend
from airautomatica.vehicle.backends.mock import MockVehicleBackend

__all__ = [
    "VehicleBackendBase",
    "MockVehicleBackend",
    "MavlinkVehicleBackend",
    "ArduinoSerialVehicleBackend",
]
