"""Tests for AI subsystem holder and reload."""

import pytest

from airautomatica.ai.mock_service import MockAiService
from airautomatica.ai.ollama_task_service import OllamaTaskService
from airautomatica.runtime.ai_subsystem import AiSubsystemHolder, ReloadResult
from airautomatica.services.mission_logic import MissionLogic
from airautomatica.services.state_store import StateStore


def test_holder_swap_services() -> None:
    """AiSubsystemHolder.swap replaces services atomically."""
    ai1 = MockAiService()
    task1 = OllamaTaskService(provider="mock", ollama_service=None)
    holder = AiSubsystemHolder(ai1, task1)
    assert holder.get_ai_service() is ai1
    assert holder.get_task_service() is task1

    ai2 = MockAiService()
    task2 = OllamaTaskService(provider="mock", ollama_service=None)
    holder.swap(ai2, task2)
    assert holder.get_ai_service() is ai2
    assert holder.get_task_service() is task2


def test_reload_provider_change_returns_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_reload_ai_subsystem returns failure when provider changes."""
    from airautomatica.main import _reload_ai_subsystem

    monkeypatch.setenv("LOCAL_LLM_PROVIDER", "ollama")
    holder = AiSubsystemHolder(MockAiService(), OllamaTaskService(provider="mock"))
    mission_logic = MissionLogic(StateStore(), ai_service=MockAiService())

    result = _reload_ai_subsystem(holder, mission_logic, None, provider_before="mock")
    assert result.success is False
    assert "restart" in (result.error or "").lower()


def test_reload_same_provider_mock_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_reload_ai_subsystem succeeds when provider stays mock."""
    from airautomatica.main import _reload_ai_subsystem

    monkeypatch.setenv("LOCAL_LLM_PROVIDER", "mock")
    monkeypatch.delenv("AI_MODE", raising=False)
    monkeypatch.delenv("AI_BACKEND", raising=False)

    store = StateStore()
    ai = MockAiService()
    task = OllamaTaskService(provider="mock", ollama_service=None)
    holder = AiSubsystemHolder(ai, task)
    mission_logic = MissionLogic(store, ai_service=ai)

    result = _reload_ai_subsystem(holder, mission_logic, None, provider_before="mock")
    assert result.success is True
    assert holder.get_ai_service() is not ai
    assert mission_logic._ai_service is holder.get_ai_service()
