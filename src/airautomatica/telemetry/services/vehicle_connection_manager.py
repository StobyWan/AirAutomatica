"""VehicleConnectionManager: connects transport, selects adapter, runs message loop."""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from airautomatica.models.state import AircraftState
from airautomatica.telemetry.adapters import (
    ArduPilotAdapter,
    AutopilotAdapterProtocol,
    GenericMavlinkAdapter,
    INAVAdapter,
)
from airautomatica.telemetry.capabilities import CapabilityInfo, capability_info
from airautomatica.telemetry.mavlink import detect_autopilot_from_heartbeat
from airautomatica.telemetry.mavlink_parser import MavlinkNormalizer

logger = logging.getLogger(__name__)

HEARTBEAT_WAIT_TIMEOUT = 10.0
READ_MESSAGE_TIMEOUT = 0.5


class VehicleConnectionManager:
    """Orchestrates transport connection, adapter selection, and telemetry stream."""

    def __init__(
        self,
        transport: Any,
        heartbeat_timeout_sec: float = 3.0,
        adapters: list[AutopilotAdapterProtocol] | None = None,
    ) -> None:
        self._transport = transport
        self._heartbeat_timeout = heartbeat_timeout_sec
        self._adapters = adapters or [
            ArduPilotAdapter(),
            INAVAdapter(),
            GenericMavlinkAdapter(),
        ]
        self._capability_info: CapabilityInfo | None = None
        self._selected_adapter: str | None = None
        self._adapter_instance: AutopilotAdapterProtocol | None = None

    @property
    def capability_info(self) -> CapabilityInfo | None:
        """Read-only. Set after adapter selection."""
        return self._capability_info

    @property
    def selected_adapter(self) -> str | None:
        """Adapter name: ardupilot, inav, or generic."""
        return self._selected_adapter

    def _firmware_name(self, profile_id: str) -> str:
        """Map profile_id to human-readable firmware name."""
        return {"ardupilot": "ArduPilot", "inav": "INAV", "generic": "Unknown"}.get(
            profile_id, "Unknown"
        )

    async def run_connection_cycle(
        self,
        reconnect_count: int = 0,
        last_disconnect_reason: str | None = None,
    ) -> AsyncIterator[tuple[AircraftState, CapabilityInfo | None]]:
        """Connect, wait heartbeat, select adapter, run reader loop. Yields (state, info)."""
        normalizer = MavlinkNormalizer(heartbeat_timeout_sec=self._heartbeat_timeout)
        loop = asyncio.get_running_loop()

        self._transport.connect()

        # Wait for heartbeat
        heartbeat_msg: Any = None
        for _ in range(int(HEARTBEAT_WAIT_TIMEOUT / READ_MESSAGE_TIMEOUT) + 1):
            msg = await loop.run_in_executor(
                None,
                lambda: self._transport.read_message(timeout=READ_MESSAGE_TIMEOUT),
            )
            if msg is not None and msg.get_type() == "HEARTBEAT":
                heartbeat_msg = msg
                break

        if heartbeat_msg is None:
            self._transport.close()
            raise RuntimeError("No HEARTBEAT within timeout")

        conn = getattr(self._transport, "connection", None)
        if conn is not None:
            logger.info(
                "Heartbeat from system %u component %u",
                conn.target_system,
                conn.target_component,
            )

        # Select adapter (first match; generic is fallback)
        autopilot_type = detect_autopilot_from_heartbeat(heartbeat_msg)
        adapter = None
        for a in self._adapters:
            if a.detect(heartbeat_msg):
                adapter = a
                self._selected_adapter = autopilot_type
                break

        if adapter is None:
            adapter = GenericMavlinkAdapter()
            self._selected_adapter = "generic"

        self._adapter_instance = adapter
        profile = adapter.get_capabilities()
        logger.info("Selected adapter: %s", self._selected_adapter)

        # Apply first heartbeat to normalizer so mode is set
        adapter.handle_message(heartbeat_msg, normalizer)

        # Request initial state (e.g. message rates) only if capability allows
        if profile.supports_message_interval:
            try:
                adapter.request_initial_state(self._transport)
            except Exception as e:
                logger.warning("request_initial_state failed: %s", e)

        # Safe probe (optional; may downgrade)
        downgrade_reasons: list[str] = []
        try:
            downgrade_reasons = adapter.safe_probe(self._transport)
        except Exception as e:
            logger.warning("safe_probe failed: %s", e)

        firmware_name = self._firmware_name(self._selected_adapter or "generic")
        self._capability_info = capability_info(
            firmware_name=firmware_name,
            profile_id=self._selected_adapter or "generic",
            profile=profile,
            downgrade_reasons=tuple(downgrade_reasons),
        )

        # Reader loop
        try:
            while self._transport.is_connected:
                try:
                    msg = await loop.run_in_executor(
                        None,
                        lambda: self._transport.read_message(
                            timeout=READ_MESSAGE_TIMEOUT
                        ),
                    )
                except Exception as e:
                    logger.exception("read_message failed: %s", e)
                    break

                if msg is None:
                    # Timeout; yield current state
                    state = normalizer.build_state(
                        reconnect_count=reconnect_count,
                        last_disconnect_reason=last_disconnect_reason,
                    )
                    yield state, self._capability_info
                    continue

                try:
                    adapter.handle_message(msg, normalizer)
                except Exception as e:
                    logger.warning("handle_message failed: %s", e)
                    continue

                state = normalizer.build_state(
                    reconnect_count=reconnect_count,
                    last_disconnect_reason=last_disconnect_reason,
                )
                yield state, self._capability_info
        finally:
            self._transport.close()
