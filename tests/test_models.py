"""Tests for AI models and shared helpers."""

import pytest

from airautomatica.ai.models import AiResult, create_error_fallback


def test_create_error_fallback_basic() -> None:
    """Error fallback returns AiResult with label=error, confidence=0."""
    r = create_error_fallback("Something failed", {"error": True}, "ollama")
    assert r.label == "error"
    assert r.confidence == 0.0
    assert r.summary == "Something failed"
    assert r.source_backend == "ollama"
    assert r.metadata == {"error": True}


def test_create_error_fallback_filters_metadata() -> None:
    """Only allowed metadata keys are kept."""
    r = create_error_fallback(
        "Parse error",
        {"parse_error": "json", "error_type": "timeout", "extra": "ignored"},
        "lmstudio",
    )
    assert r.metadata == {"parse_error": "json", "error_type": "timeout"}
    assert "extra" not in (r.metadata or {})


def test_create_error_fallback_empty_metadata() -> None:
    """Empty metadata produces None."""
    r = create_error_fallback("Err", {}, "mock")
    assert r.metadata is None


def test_create_error_fallback_all_filtered() -> None:
    """When all metadata keys are disallowed, metadata is None."""
    r = create_error_fallback("Err", {"extra": 1, "other": 2}, "ollama")
    assert r.metadata is None
