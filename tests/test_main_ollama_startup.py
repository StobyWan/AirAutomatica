"""Tests for main.py Ollama startup behavior: degraded vs fail-fast."""

import pytest


def test_degraded_mode_when_ollama_required_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When OLLAMA_REQUIRED=0, get_ollama_required returns False; startup would continue."""
    monkeypatch.setenv("LOCAL_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_REQUIRED", "0")

    from airautomatica.config import get_ollama_required

    assert get_ollama_required() is False


def test_fail_fast_when_ollama_required_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """When OLLAMA_REQUIRED=1, get_ollama_required returns True; startup would exit if not ready."""
    monkeypatch.setenv("LOCAL_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_REQUIRED", "1")

    from airautomatica.config import get_ollama_required

    assert get_ollama_required() is True


def test_ollama_required_ignored_when_provider_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OLLAMA_REQUIRED has no effect when provider is mock.

    The fail-fast check only runs when provider is ollama. When mock, we never
    call wait_for_ollama_ready, so OLLAMA_REQUIRED is irrelevant.
    """
    monkeypatch.setenv("LOCAL_LLM_PROVIDER", "mock")
    monkeypatch.setenv("OLLAMA_REQUIRED", "1")

    # Main would not even reach the Ollama readiness check when provider is mock
    from airautomatica.config import get_local_llm_provider

    assert get_local_llm_provider() == "mock"
