"""Tests for Ollama readiness check."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from airautomatica.ai.ollama_readiness import (
    OllamaReadinessResult,
    check_ollama_ready,
    wait_for_ollama_ready,
)


def test_check_ollama_ready_reachable() -> None:
    """check_ollama_ready returns ready when API responds with models."""
    with patch("httpx.Client") as mock_client_cls:
        mock_resp = mock_client_cls.return_value.__enter__.return_value.get.return_value
        mock_resp.raise_for_status = lambda: None
        mock_resp.json.return_value = {"models": [{"name": "gemma3:1b"}]}
        mock_resp.status_code = 200

        result = check_ollama_ready("http://127.0.0.1:11434", model="gemma3:1b")
        assert result.ready is True
        assert result.reason == "ready"


def test_check_ollama_ready_model_missing() -> None:
    """check_ollama_ready returns model_missing when model not in tags."""
    with patch("httpx.Client") as mock_client_cls:
        mock_resp = mock_client_cls.return_value.__enter__.return_value.get.return_value
        mock_resp.raise_for_status = lambda: None
        mock_resp.json.return_value = {"models": [{"name": "other:1b"}]}
        mock_resp.status_code = 200

        result = check_ollama_ready("http://127.0.0.1:11434", model="gemma3:1b")
        assert result.ready is False
        assert result.reason == "model_missing"


def test_check_ollama_ready_no_model_check() -> None:
    """check_ollama_ready returns ready when model=None (no verification)."""
    with patch("httpx.Client") as mock_client_cls:
        mock_resp = mock_client_cls.return_value.__enter__.return_value.get.return_value
        mock_resp.raise_for_status = lambda: None
        mock_resp.json.return_value = {"models": []}
        mock_resp.status_code = 200

        result = check_ollama_ready("http://127.0.0.1:11434", model=None)
        assert result.ready is True
        assert result.reason == "ready"


def test_check_ollama_ready_unreachable() -> None:
    """check_ollama_ready returns unreachable on connection error."""
    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.side_effect = (
            httpx.ConnectError("Connection refused")
        )

        result = check_ollama_ready("http://127.0.0.1:11434")
        assert result.ready is False
        assert result.reason == "unreachable"


def test_check_ollama_ready_http_error() -> None:
    """check_ollama_ready returns http_error on HTTP status error."""
    with patch("httpx.Client") as mock_client_cls:
        mock_resp = mock_client_cls.return_value.__enter__.return_value.get.return_value
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )

        result = check_ollama_ready("http://127.0.0.1:11434")
        assert result.ready is False
        assert result.reason == "http_error"


@pytest.mark.asyncio
async def test_wait_for_ollama_ready_succeeds_first_try() -> None:
    """wait_for_ollama_ready returns ready when API responds immediately."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json.return_value = {"models": [{"name": "gemma3:1b"}]}
    mock_resp.status_code = 200

    mock_get = AsyncMock(return_value=mock_resp)
    mock_client = MagicMock()
    mock_client.get = mock_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await wait_for_ollama_ready(
            "http://127.0.0.1:11434",
            model="gemma3:1b",
            max_attempts=3,
            interval_sec=0.01,
        )
        assert result.ready is True
        assert result.reason == "ready"


@pytest.mark.asyncio
async def test_wait_for_ollama_ready_fails_after_retries() -> None:
    """wait_for_ollama_ready returns unreachable when all attempts fail."""
    mock_get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client = MagicMock()
    mock_client.get = mock_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await wait_for_ollama_ready(
            "http://127.0.0.1:11434",
            model="gemma3:1b",
            max_attempts=2,
            interval_sec=0.01,
        )
        assert result.ready is False
        assert result.reason == "unreachable"
