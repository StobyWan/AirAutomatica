"""Minimal scheduler for Ollama inference. One queue, one worker, one job at a time."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from airautomatica.ai.models import AiResult
from airautomatica.ai.ollama_service import OllamaAiService
from airautomatica.ai.service import AiService
from airautomatica.config import get_ai_scheduler_cooldown_sec
from airautomatica.models.state import AircraftState
from airautomatica.system.thermal import ThermalState, get_thermal_state

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Thermal backoff: extra delay when HOT, pause duration for background when THROTTLED.
_COOLDOWN_WARM_MULT = 2.0
_COOLDOWN_HOT_MULT = 3.0
_COOLDOWN_THROTTLED_USER_EXTRA_SEC = 10.0
_BACKGROUND_PAUSE_WHEN_THROTTLED_SEC = 30.0
_BACKGROUND_PAUSE_WHEN_HOT_SEC = 15.0


class AiInferenceScheduler:
    """Serializes Ollama inference: one job at a time with cooldown and thermal backoff."""

    def __init__(self, cooldown_sec: float | None = None) -> None:
        self._cooldown_sec = cooldown_sec
        self._use_config_cooldown = cooldown_sec is None
        self._queue: asyncio.Queue[
            tuple[Callable[[], Awaitable[Any]], asyncio.Future[Any], bool]
        ] = asyncio.Queue()

    async def submit(
        self, job: Callable[[], Awaitable[T]], *, user_triggered: bool = False
    ) -> T:
        """Submit a job. user_triggered=True for dashboard tasks; False for mission."""
        future: asyncio.Future[T] = asyncio.get_running_loop().create_future()
        await self._queue.put((job, future, user_triggered))
        return await future

    def _get_cooldown_sec(self, thermal: ThermalState) -> float:
        """Cooldown after job completion, scaled by thermal state."""
        if self._use_config_cooldown:
            base = get_ai_scheduler_cooldown_sec()
        else:
            base = self._cooldown_sec if self._cooldown_sec is not None else 0.0
        if thermal == ThermalState.NORMAL:
            return base
        if thermal == ThermalState.WARM:
            return base * _COOLDOWN_WARM_MULT
        if thermal == ThermalState.HOT:
            return base * _COOLDOWN_HOT_MULT
        return base * _COOLDOWN_HOT_MULT  # THROTTLED: same as hot for post-job

    async def run(self) -> None:
        """Worker loop: run jobs one at a time with thermal-aware cooldown."""
        while True:
            try:
                job, future, user_triggered = await self._queue.get()
                thermal = get_thermal_state()

                # THROTTLED: pause background jobs; user jobs run with extra delay
                if thermal == ThermalState.THROTTLED and not user_triggered:
                    logger.info(
                        "Thermal throttled: pausing background job for %ds",
                        _BACKGROUND_PAUSE_WHEN_THROTTLED_SEC,
                    )
                    await self._queue.put((job, future, user_triggered))
                    await asyncio.sleep(_BACKGROUND_PAUSE_WHEN_THROTTLED_SEC)
                    continue

                # HOT: defer background jobs briefly
                if thermal == ThermalState.HOT and not user_triggered:
                    logger.debug(
                        "Thermal hot: deferring background job for %ds",
                        _BACKGROUND_PAUSE_WHEN_HOT_SEC,
                    )
                    await self._queue.put((job, future, user_triggered))
                    await asyncio.sleep(_BACKGROUND_PAUSE_WHEN_HOT_SEC)
                    continue

                # THROTTLED + user job: extra delay before running
                if thermal == ThermalState.THROTTLED and user_triggered:
                    logger.info(
                        "Thermal throttled: adding %.0fs delay for user-triggered job",
                        _COOLDOWN_THROTTLED_USER_EXTRA_SEC,
                    )
                    await asyncio.sleep(_COOLDOWN_THROTTLED_USER_EXTRA_SEC)

                try:
                    result: Any = await job()
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)

                cooldown = self._get_cooldown_sec(get_thermal_state())
                await asyncio.sleep(cooldown)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Scheduler worker error: %s", e)
                if not future.done():
                    future.set_exception(e)


class ScheduledOllamaAiService(AiService):
    """AiService that routes mission inference through the scheduler."""

    def __init__(
        self, transport: OllamaAiService, scheduler: AiInferenceScheduler
    ) -> None:
        self._transport = transport
        self._scheduler = scheduler

    async def infer(self, state: AircraftState | None) -> AiResult:
        prompt = self._transport._build_prompt(state)
        return await self._scheduler.submit(
            lambda: self._transport._infer_from_prompt(prompt),
            user_triggered=False,
        )


class ScheduledOllamaExecutor:
    """Facade for generate_raw that routes through the scheduler. Used by OllamaTaskService."""

    def __init__(
        self, transport: OllamaAiService, scheduler: AiInferenceScheduler
    ) -> None:
        self._transport = transport
        self._scheduler = scheduler

    async def generate_raw(
        self, prompt: str, *, format: str | dict[str, Any] | None = None
    ) -> str:
        return await self._scheduler.submit(
            lambda: self._transport.generate_raw(prompt, format=format),
            user_triggered=True,
        )
