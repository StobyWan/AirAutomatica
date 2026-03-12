"""Tests for telemetry subsystem controller and reconnect."""

import asyncio

import pytest

from airautomatica.runtime.telemetry_subsystem import (
    TelemetryController,
    TelemetryReconnectResult,
)
from airautomatica.telemetry.mock import MockTelemetry


async def _dummy_loop(source) -> None:
    """Consume stream until cancelled."""
    async for _ in source.stream():
        pass


def _create_mock_source() -> MockTelemetry:
    return MockTelemetry()


def _get_backend() -> str:
    return "mock"


def _start_task(source) -> asyncio.Task:
    return asyncio.create_task(_dummy_loop(source))


@pytest.mark.asyncio
async def test_controller_start_starts_task() -> None:
    """TelemetryController.start() creates and returns the loop task."""
    source = _create_mock_source()
    controller = TelemetryController(
        source=source,
        create_source_fn=_create_mock_source,
        get_backend_fn=_get_backend,
        start_task_fn=_start_task,
    )
    task = controller.start()
    assert task is not None
    assert not task.done()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_controller_reconnect_success() -> None:
    """TelemetryController.reconnect() swaps source and restarts task."""
    source = _create_mock_source()
    controller = TelemetryController(
        source=source,
        create_source_fn=_create_mock_source,
        get_backend_fn=_get_backend,
        start_task_fn=_start_task,
    )
    controller.start()
    result = await controller.reconnect()
    assert result.success is True
    assert result.backend_after == "mock"
    assert controller.get_task() is not None
    controller.get_task().cancel()
    try:
        await controller.get_task()
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_controller_reconnect_before_start_returns_failure() -> None:
    """TelemetryController.reconnect() before start() returns failure."""
    source = _create_mock_source()
    controller = TelemetryController(
        source=source,
        create_source_fn=_create_mock_source,
        get_backend_fn=_get_backend,
        start_task_fn=_start_task,
    )
    result = await controller.reconnect()
    assert result.success is False
    assert "not started" in (result.error or "").lower()
