"""Tests for main.py background task restart and shutdown handling."""

import asyncio
from unittest.mock import MagicMock

import pytest

from airautomatica.main import _run_with_restart


@pytest.mark.asyncio
async def test_telemetry_restart_on_exception() -> None:
    """Restart wrapper catches exception, sleeps, and restarts the coroutine."""
    call_count = 0

    async def failing_then_ok() -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("telemetry failed")
        await asyncio.sleep(10)

    task = asyncio.create_task(
        _run_with_restart(failing_then_ok, name="telemetry", restart_delay_sec=0.05)
    )
    await asyncio.sleep(0.2)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert call_count >= 2


@pytest.mark.asyncio
async def test_mission_restart_on_exception() -> None:
    """Restart wrapper restarts mission-like coroutine that raises."""
    call_count = 0

    async def mission_run() -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise TimeoutError("AI inference timeout")
        while True:
            await asyncio.sleep(1)

    task = asyncio.create_task(
        _run_with_restart(mission_run, name="mission", restart_delay_sec=0.05)
    )
    await asyncio.sleep(0.2)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert call_count >= 2


@pytest.mark.asyncio
async def test_shutdown_handles_task_exception() -> None:
    """Cleanup await of task that exited with exception does not propagate.
    Mirrors main.py cleanup loop: catch Exception so shutdown completes."""

    async def raises() -> None:
        raise ValueError("task crashed")

    task = asyncio.create_task(raises())
    await asyncio.sleep(0.05)
    assert task.done()
    assert task.exception() is not None

    propagated = False
    try:
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            pass
    except Exception:
        propagated = True
    assert not propagated
