"""Tests for AppHomeStore."""

import pytest

from airautomatica.services.app_home_store import AppHomeStore


def test_app_home_store_set_get_clear() -> None:
    """AppHomeStore set_app_home, get_override, clear_app_home, has_override."""
    store = AppHomeStore()
    assert store.has_override() is False
    assert store.get_override() == (None, None)

    store.set_app_home(37.0, -122.0)
    assert store.has_override() is True
    assert store.get_override() == (37.0, -122.0)

    store.clear_app_home()
    assert store.has_override() is False
    assert store.get_override() == (None, None)


def test_app_home_store_overwrite() -> None:
    """Setting app home overwrites previous value."""
    store = AppHomeStore()
    store.set_app_home(37.0, -122.0)
    store.set_app_home(38.0, -123.0)
    assert store.get_override() == (38.0, -123.0)
