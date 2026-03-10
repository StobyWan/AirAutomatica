"""Serial MAVLink telemetry source with robust connection lifecycle."""

import asyncio
import logging
import os
import threading
from queue import Empty, Queue
from typing import Any, AsyncIterator

from airautomatica.models.state import AircraftState, TelemetryStatus
from airautomatica.telemetry.base import TelemetrySource
from airautomatica.telemetry.mavlink_parser import MavlinkNormalizer

logger = logging.getLogger(__name__)

# Sentinel for reader thread error; value is (READER_ERROR, reason: str)
READER_ERROR = "__error__"

# MAVLink message IDs (mavlink.io common dialect)
MAVLINK_MSG_ID_GLOBAL_POSITION_INT = 33
MAVLINK_MSG_ID_ATTITUDE = 30
MAVLINK_MSG_ID_SYS_STATUS = 1
MAVLINK_MSG_ID_VFR_HUD = 74

# MAV_CMD_SET_MESSAGE_INTERVAL (ArduPilot 4.0+)
MAV_CMD_SET_MESSAGE_INTERVAL = 511

# Request 10 Hz for telemetry messages (100000 us = 10 Hz)
MESSAGE_INTERVAL_US_10HZ = 100000

# Reconnect backoff
INITIAL_BACKOFF_SEC = 1.0
MAX_BACKOFF_SEC = 60.0

# Yield interval during backoff (keep stream alive)
BACKOFF_YIELD_INTERVAL_SEC = 0.5

# Minimal backoff when wait_heartbeat times out (avoids tight retry loop)
NO_HEARTBEAT_BACKOFF_SEC = 1.0


def _request_message_rates(conn: Any) -> None:
    """Request required MAVLink message rates via SET_MESSAGE_INTERVAL.
    Call after wait_heartbeat(). See ArduPilot mavlink-requesting-data."""
    sysid = conn.target_system
    compid = conn.target_component
    mav = conn.mav

    messages = [
        (MAVLINK_MSG_ID_GLOBAL_POSITION_INT, MESSAGE_INTERVAL_US_10HZ),
        (MAVLINK_MSG_ID_ATTITUDE, MESSAGE_INTERVAL_US_10HZ),
        (MAVLINK_MSG_ID_SYS_STATUS, MESSAGE_INTERVAL_US_10HZ),
        (MAVLINK_MSG_ID_VFR_HUD, MESSAGE_INTERVAL_US_10HZ),
    ]
    for msg_id, interval_us in messages:
        mav.command_long_send(
            sysid,
            compid,
            MAV_CMD_SET_MESSAGE_INTERVAL,
            0,
            msg_id,
            interval_us,
            0,
            0,
            0,
            0,
            0,
        )
    logger.info(
        "Requested MAVLink message rates (10 Hz) for GLOBAL_POSITION_INT, ATTITUDE, SYS_STATUS, VFR_HUD"
    )


class SerialMavlinkTelemetry(TelemetrySource):
    """Read MAVLink telemetry from serial/USB connection to flight controller.
    Tracks telemetry_status (starting, connecting, connected, stale, disconnected, backoff),
    auto-reconnects with backoff, and re-runs heartbeat wait and message rate requests.
    """

    def __init__(
        self,
        port: str,
        baud: int,
        heartbeat_timeout_sec: float = 3.0,
        initial_backoff_sec: float = INITIAL_BACKOFF_SEC,
        max_backoff_sec: float = MAX_BACKOFF_SEC,
    ) -> None:
        self._port = port
        self._baud = baud
        self._heartbeat_timeout = heartbeat_timeout_sec
        self._initial_backoff = initial_backoff_sec
        self._max_backoff = max_backoff_sec

    async def stream(self) -> AsyncIterator[AircraftState]:
        """Stream state from MAVLink messages. Auto-reconnects on disconnect."""
        os.environ.setdefault("MAVLINK20", "1")

        from pymavlink import mavutil

        normalizer = MavlinkNormalizer(heartbeat_timeout_sec=self._heartbeat_timeout)
        backoff = self._initial_backoff
        loop = asyncio.get_running_loop()
        reconnect_count = 0
        last_disconnect_reason: str | None = None

        yield normalizer.build_state(
            telemetry_status_override="starting",
            reconnect_count=reconnect_count,
            last_disconnect_reason=last_disconnect_reason,
        )

        while True:
            conn = None
            try:
                conn = mavutil.mavlink_connection(self._port, baud=self._baud)

                yield normalizer.build_state(
                    telemetry_status_override="connecting",
                    reconnect_count=reconnect_count,
                    last_disconnect_reason=last_disconnect_reason,
                )

                def wait_and_request() -> bool:
                    hb = conn.wait_heartbeat(blocking=True, timeout=10)
                    if hb is None:
                        logger.warning(
                            "No HEARTBEAT within 10s; continuing without rate request"
                        )
                        return False
                    logger.info(
                        "Heartbeat from system %u component %u",
                        conn.target_system,
                        conn.target_component,
                    )
                    _request_message_rates(conn)
                    return True

                ok = await loop.run_in_executor(None, wait_and_request)
                if not ok:
                    last_disconnect_reason = "no_heartbeat"
                    await asyncio.sleep(NO_HEARTBEAT_BACKOFF_SEC)
                    continue

                backoff = self._initial_backoff

                queue: Queue[Any] = Queue()

                def reader() -> None:
                    try:
                        while True:
                            msg = conn.recv_match(blocking=True, timeout=2.0)
                            if msg is not None:
                                if msg.get_type() == "BAD_DATA":
                                    continue
                                queue.put(msg)
                    except Exception as e:
                        reason = str(e)
                        logger.exception("Serial MAVLink reader failed: %s", reason)
                        queue.put((READER_ERROR, reason))
                    finally:
                        queue.put(None)

                t = threading.Thread(target=reader, daemon=True)
                t.start()

                while True:
                    try:
                        item = await loop.run_in_executor(
                            None, lambda: queue.get(timeout=0.5)
                        )
                    except Empty:
                        yield normalizer.build_state(
                            reconnect_count=reconnect_count,
                            last_disconnect_reason=last_disconnect_reason,
                        )
                        continue

                    if item is None:
                        last_disconnect_reason = "reader_exited"
                        logger.info("Reader exited normally; reconnecting")
                        break
                    if isinstance(item, tuple) and item[0] is READER_ERROR:
                        last_disconnect_reason = (
                            item[1] if len(item) > 1 else "reader_error"
                        )
                        logger.warning("Reader reported error; reconnecting")
                        break

                    try:
                        normalizer.apply(item)
                    except Exception as e:
                        logger.warning("Parser failed for message: %s", e)
                        continue

                    yield normalizer.build_state(
                        reconnect_count=reconnect_count,
                        last_disconnect_reason=last_disconnect_reason,
                    )

            except Exception as e:
                last_disconnect_reason = str(e)
                logger.exception("Connection failed: %s", e)
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception as e:
                        logger.debug("Close MAVLink connection: %s", e)

            reconnect_count += 1

            yield normalizer.build_state(
                telemetry_status_override="disconnected",
                reconnect_count=reconnect_count,
                last_disconnect_reason=last_disconnect_reason,
            )

            logger.info(
                "Reconnecting in %.1fs (attempt %d)...", backoff, reconnect_count
            )
            elapsed = 0.0
            while elapsed < backoff:
                await asyncio.sleep(min(BACKOFF_YIELD_INTERVAL_SEC, backoff - elapsed))
                elapsed += BACKOFF_YIELD_INTERVAL_SEC
                yield normalizer.build_state(
                    telemetry_status_override="backoff",
                    reconnect_count=reconnect_count,
                    last_disconnect_reason=last_disconnect_reason,
                )

            backoff = min(backoff * 2, self._max_backoff)
