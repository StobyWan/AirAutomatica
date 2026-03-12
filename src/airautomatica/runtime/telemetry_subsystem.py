"""Runtime holder for telemetry subsystem. Supports hot-reconnect when settings change."""

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from airautomatica.telemetry.base import TelemetrySource

logger = logging.getLogger(__name__)


@dataclass
class TelemetryReconnectResult:
    """Result of telemetry subsystem reconnect."""

    success: bool
    error: Optional[str] = None
    backend_before: Optional[str] = None
    backend_after: Optional[str] = None


class TelemetryController:
    """Owns the active telemetry source and loop task. Supports reconnect."""

    def __init__(
        self,
        source: "TelemetrySource",
        create_source_fn: Callable[[], "TelemetrySource"],
        get_backend_fn: Callable[[], str],
        start_task_fn: Callable[["TelemetrySource"], asyncio.Task[None]],
    ) -> None:
        self._source = source
        self._create_source_fn = create_source_fn
        self._get_backend_fn = get_backend_fn
        self._start_task_fn = start_task_fn
        self._task: Optional[asyncio.Task[None]] = None

    def get_source(self) -> "TelemetrySource":
        return self._source

    def start(self) -> asyncio.Task[None]:
        """Start the telemetry loop. Returns the task."""
        self._task = self._start_task_fn(self._source)
        return self._task

    def get_task(self) -> Optional[asyncio.Task[None]]:
        return self._task

    async def reconnect(self) -> TelemetryReconnectResult:
        """Stop current source, create new one from config, restart loop.
        Returns result. On creation failure, restarts with old source."""
        if self._task is None:
            return TelemetryReconnectResult(
                success=False,
                error="Telemetry not started",
                backend_before=self._get_backend_fn(),
                backend_after=self._get_backend_fn(),
            )
        backend_before = self._get_backend_fn()

        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

        try:
            new_source = self._create_source_fn()
        except Exception as e:
            logger.exception("Telemetry source creation failed: %s", e)
            self._task = self._start_task_fn(self._source)
            return TelemetryReconnectResult(
                success=False,
                error=str(e),
                backend_before=backend_before,
                backend_after=self._get_backend_fn(),
            )

        self._source = new_source
        self._task = self._start_task_fn(self._source)
        backend_after = self._get_backend_fn()
        logger.info(
            "Telemetry reconnected: backend=%s",
            backend_after,
        )
        return TelemetryReconnectResult(
            success=True,
            backend_before=backend_before,
            backend_after=backend_after,
        )
