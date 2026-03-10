"""Tests for shared JSON extraction helper."""

import pytest

from airautomatica.ai.json_utils import extract_json


def test_extract_json_raw_valid() -> None:
    """Raw valid JSON returns dict."""
    assert extract_json('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_extract_json_raw_invalid() -> None:
    """Invalid JSON returns None."""
    assert extract_json("{invalid") is None
    assert extract_json("not json") is None


def test_extract_json_empty() -> None:
    """Empty or whitespace returns None."""
    assert extract_json("") is None
    assert extract_json("   ") is None


def test_extract_json_non_dict() -> None:
    """Valid JSON that is not a dict returns None."""
    assert extract_json("[1, 2, 3]") is None
    assert extract_json('"string"') is None
    assert extract_json("42") is None


def test_extract_json_markdown_block() -> None:
    """JSON inside markdown code block is extracted."""
    content = 'Text before\n```json\n{"x": 1}\n```\ntext after'
    assert extract_json(content) == {"x": 1}


def test_extract_json_markdown_block_no_lang() -> None:
    """Code block without json lang tag still works."""
    content = '```\n{"y": 2}\n```'
    assert extract_json(content) == {"y": 2}


def test_extract_json_markdown_block_invalid() -> None:
    """Invalid JSON inside block returns None."""
    content = "```json\n{invalid}\n```"
    assert extract_json(content) is None
