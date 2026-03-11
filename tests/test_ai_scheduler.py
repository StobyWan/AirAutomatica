"""Tests for AiInferenceScheduler Phase 1: serialization and cooldown."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from airautomatica.ai.ollama_task_service import OllamaTaskService
from airautomatica.ai.ollama_tasks import OllamaTaskType
from airautomatica.ai.scheduler import AiInferenceScheduler, ScheduledOllamaAiService


@pytest.mark.asyncio
async def test_one_job_at_a_time() -> None:
    """Only one job runs at a time; concurrent submits are serialized."""
    running = 0
    max_concurrent = 0

    async def job(i: int) -> int:
        nonlocal running, max_concurrent
        running += 1
        max_concurrent = max(max_concurrent, running)
        await asyncio.sleep(0.02)
        running -= 1
        return i

    scheduler = AiInferenceScheduler(cooldown_sec=0.0)
    worker = asyncio.create_task(scheduler.run())
    try:
        r0, r1, r2 = await asyncio.gather(
            scheduler.submit(lambda: job(0)),
            scheduler.submit(lambda: job(1)),
            scheduler.submit(lambda: job(2)),
        )
        assert r0 == 0 and r1 == 1 and r2 == 2
        assert max_concurrent == 1
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_jobs_serialized_fifo() -> None:
    """Jobs run in submission order."""
    order: list[int] = []

    async def job(i: int) -> int:
        order.append(i)
        return i

    scheduler = AiInferenceScheduler(cooldown_sec=0.0)
    worker = asyncio.create_task(scheduler.run())
    try:
        results = await asyncio.gather(
            scheduler.submit(lambda: job(0)),
            scheduler.submit(lambda: job(1)),
            scheduler.submit(lambda: job(2)),
        )
        assert results == [0, 1, 2]
        assert order == [0, 1, 2]
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_cooldown_respected() -> None:
    """Cooldown delay occurs between job completions."""
    scheduler = AiInferenceScheduler(cooldown_sec=0.05)
    worker = asyncio.create_task(scheduler.run())
    t0 = asyncio.get_event_loop().time()
    try:
        await scheduler.submit(lambda: asyncio.sleep(0) or 1)
        await scheduler.submit(lambda: asyncio.sleep(0) or 2)
        t1 = asyncio.get_event_loop().time()
        elapsed = t1 - t0
        assert elapsed >= 0.05
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_exception_propagates_to_caller() -> None:
    """Job exceptions are propagated to submit() caller."""

    async def failing_job() -> None:
        raise ValueError("job failed")

    scheduler = AiInferenceScheduler(cooldown_sec=0.0)
    worker = asyncio.create_task(scheduler.run())
    try:
        with pytest.raises(ValueError, match="job failed"):
            await scheduler.submit(failing_job)
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_scheduled_ollama_ai_service_routes_through_scheduler() -> None:
    """ScheduledOllamaAiService submits infer_from_prompt to scheduler."""
    transport = MagicMock()
    transport._build_prompt = MagicMock(return_value="test prompt")
    transport._infer_from_prompt = AsyncMock(
        return_value=MagicMock(label="ok", confidence=0.9, summary="test")
    )
    scheduler = AiInferenceScheduler(cooldown_sec=0.0)
    worker = asyncio.create_task(scheduler.run())
    try:
        svc = ScheduledOllamaAiService(transport, scheduler)
        result = await svc.infer(None)
        assert result.label == "ok"
        transport._build_prompt.assert_called_once_with(None)
        transport._infer_from_prompt.assert_called_once_with("test prompt")
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_mock_mode_bypasses_scheduler() -> None:
    """Mock provider returns immediately; no scheduler or Ollama calls."""
    task_service = OllamaTaskService(provider="mock", ollama_service=None)
    result = await task_service.infer_task(
        OllamaTaskType.TELEMETRY_SUMMARY,
        {"state": None, "telemetry_samples": []},
    )
    assert result.status == "ok"
    assert result.summary == "Mock telemetry summary"
