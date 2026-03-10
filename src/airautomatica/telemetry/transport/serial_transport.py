"""Serial transport for MAVLink over USB/UART."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SerialTransport:
    """Serial MAVLink transport. Wraps pymavlink mavutil.mavlink_connection."""

    def __init__(self, port: str, baud: int) -> None:
        self._port = port
        self._baud = baud
        self._conn: Any = None

    def connect(self) -> None:
        """Open serial connection."""
        import os

        os.environ.setdefault("MAVLINK20", "1")

        from pymavlink import mavutil

        self._conn = mavutil.mavlink_connection(self._port, baud=self._baud)
        logger.debug(
            "Serial transport connected: port=%s baud=%s", self._port, self._baud
        )

    def close(self) -> None:
        """Close serial connection."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception as e:
                logger.debug("Close serial transport: %s", e)
            finally:
                self._conn = None

    def read_message(self, timeout: float = 2.0) -> Any | None:
        """Read next MAVLink message. Returns None on timeout."""
        if self._conn is None:
            return None
        msg = self._conn.recv_match(blocking=True, timeout=timeout)
        if msg is not None and msg.get_type() == "BAD_DATA":
            return self.read_message(timeout)
        return msg

    def send(self, data: bytes) -> None:
        """Send raw bytes. Serial transport uses connection write."""
        if self._conn is None:
            raise RuntimeError("Transport not connected")
        self._conn.file.write(data)
        self._conn.file.flush()

    @property
    def is_connected(self) -> bool:
        """True if connection is open."""
        return self._conn is not None

    @property
    def connection(self) -> Any:
        """Underlying pymavlink connection for adapter-specific sends (e.g. command_long)."""
        return self._conn
