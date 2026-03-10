"""Transport layer for MAVLink connections."""

from airautomatica.telemetry.transport.base import TransportProtocol
from airautomatica.telemetry.transport.serial_transport import SerialTransport

__all__ = ["TransportProtocol", "SerialTransport"]
