"""Tests for config getters."""

import pytest

from airautomatica.config import get_ollama_num_thread, get_ollama_required


def test_get_ollama_num_thread_default() -> None:
    """Default is 4 when env not set."""
    with pytest.MonkeyPatch.context() as m:
        m.delenv("OLLAMA_NUM_THREAD", raising=False)
        m.delenv("AIRAUTOMATICA_OLLAMA_NUM_THREAD", raising=False)
        assert get_ollama_num_thread() == 4


def test_get_ollama_num_thread_env_override() -> None:
    """OLLAMA_NUM_THREAD env overrides default."""
    with pytest.MonkeyPatch.context() as m:
        m.setenv("OLLAMA_NUM_THREAD", "6")
        m.delenv("AIRAUTOMATICA_OLLAMA_NUM_THREAD", raising=False)
        assert get_ollama_num_thread() == 6


def test_get_ollama_num_thread_airautomatica_prefix() -> None:
    """AIRAUTOMATICA_OLLAMA_NUM_THREAD takes precedence over OLLAMA_NUM_THREAD."""
    with pytest.MonkeyPatch.context() as m:
        m.setenv("AIRAUTOMATICA_OLLAMA_NUM_THREAD", "2")
        m.setenv("OLLAMA_NUM_THREAD", "8")
        assert get_ollama_num_thread() == 2


def test_get_ollama_num_thread_clamped() -> None:
    """Values outside 1-8 are clamped."""
    with pytest.MonkeyPatch.context() as m:
        m.delenv("AIRAUTOMATICA_OLLAMA_NUM_THREAD", raising=False)
        m.setenv("OLLAMA_NUM_THREAD", "0")
        assert get_ollama_num_thread() == 1
        m.setenv("OLLAMA_NUM_THREAD", "99")
        assert get_ollama_num_thread() == 8


def test_get_ollama_num_thread_invalid_fallback() -> None:
    """Invalid string falls back to 4."""
    with pytest.MonkeyPatch.context() as m:
        m.setenv("OLLAMA_NUM_THREAD", "invalid")
        m.delenv("AIRAUTOMATICA_OLLAMA_NUM_THREAD", raising=False)
        assert get_ollama_num_thread() == 4


def test_get_ollama_required_default() -> None:
    """Default is False when env not set."""
    with pytest.MonkeyPatch.context() as m:
        m.delenv("OLLAMA_REQUIRED", raising=False)
        m.delenv("AIRAUTOMATICA_OLLAMA_REQUIRED", raising=False)
        assert get_ollama_required() is False


def test_get_ollama_required_env_true() -> None:
    """OLLAMA_REQUIRED=1 returns True."""
    with pytest.MonkeyPatch.context() as m:
        m.setenv("OLLAMA_REQUIRED", "1")
        m.delenv("AIRAUTOMATICA_OLLAMA_REQUIRED", raising=False)
        assert get_ollama_required() is True


def test_get_ollama_required_airautomatica_wins() -> None:
    """AIRAUTOMATICA_OLLAMA_REQUIRED takes precedence over OLLAMA_REQUIRED."""
    with pytest.MonkeyPatch.context() as m:
        m.setenv("AIRAUTOMATICA_OLLAMA_REQUIRED", "0")
        m.setenv("OLLAMA_REQUIRED", "1")
        assert get_ollama_required() is False
        m.setenv("AIRAUTOMATICA_OLLAMA_REQUIRED", "true")
        assert get_ollama_required() is True
