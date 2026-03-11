"""Minimal scheduler for Ollama inference. One queue, one worker, one job at a time."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from airautomatica.ai.models import AiResult
from airautomatica.ai.ollama_service import OllamaAiService
from airautomatica.ai.service import AiService
from airautomatica.models.state import AircraftState

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Fixed cooldown between completed jobs (seconds). Kept in code for Phase 1.
_COOLDOWN_SEC = 2.0


class AiInferenceScheduler:
    """Serializes Ollama inference: one job at a time with cooldown between jobs."""

    def __init__(self, cooldown_sec: float = _COOLDOWN_SEC) -> None:
        self._cooldown_sec = cooldown_sec
        self._queue: asyncio.Queue[
            tuple[Callable[[], Awaitable[T]], asyncio.Future[T]]
        ] = asyncio.Queue()

    async def submit(self, job: Callable[[], Awaitable[T]]) -> T:
        """Submit a job. Returns when the job completes. Jobs run one at a time."""
        future: asyncio.Future[T] = asyncio.get_running_loop().create_future()
        await self._queue.put((job, future))
        return await future

    async def run(self) -> None:
        """Worker loop: run jobs one at a time with cooldown. Run as asyncio task."""
        while True:
            try:
                job, future = await self._queue.get()
                try:
                    result = await job()
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
                await asyncio.sleep(self._cooldown_sec)
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
            lambda: self._transport._infer_from_prompt(prompt)
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
            lambda: self._transport.generate_raw(prompt, format=format)
        )
