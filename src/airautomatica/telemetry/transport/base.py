"""Transport abstraction for MAVLink connections."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TransportProtocol(Protocol):
    """Protocol for MAVLink transport (serial, UDP, etc.)."""

    def connect(self) -> None:
        """Open the transport connection."""
        ...

    def close(self) -> None:
        """Close the transport connection."""
        ...

    def read_message(self, timeout: float = 2.0) -> Any | None:
        """Read next MAVLink message. Returns parsed message or None on timeout."""
        ...

    def send(self, data: bytes) -> None:
        """Send raw bytes over the transport."""
        ...

    @property
    def is_connected(self) -> bool:
        """True if transport is open and ready."""
        ...
