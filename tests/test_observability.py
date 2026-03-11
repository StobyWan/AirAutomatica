"""Tests for derived AI observability rate helpers."""

import pytest

from airautomatica.system.observability import (
    get_ai_observability_rates,
    perception_acceptance_rate,
    telemetry_meaningful_rate,
)


def test_perception_acceptance_rate_null_when_denominator_zero() -> None:
    """Returns None when all counts are zero."""
    counts = {
        "accepted": 0,
        "suppressed": 0,
        "no_detection": 0,
        "non_perception_label": 0,
        "unknown_label": 0,
        "parse_error": 0,
    }
    assert perception_acceptance_rate(counts) is None


def test_perception_acceptance_rate_computed() -> None:
    """Returns accepted / total when denominator > 0."""
    counts = {
        "accepted": 5,
        "suppressed": 2,
        "no_detection": 1,
        "non_perception_label": 1,
        "unknown_label": 1,
        "parse_error": 0,
    }
    # 5 / (5+2+1+1+1+0) = 5/10 = 0.5
    assert perception_acceptance_rate(counts) == 0.5


def test_perception_acceptance_rate_all_accepted() -> None:
    """Returns 1.0 when all outcomes are accepted."""
    counts = {
        "accepted": 10,
        "suppressed": 0,
        "no_detection": 0,
        "non_perception_label": 0,
        "unknown_label": 0,
        "parse_error": 0,
    }
    assert perception_acceptance_rate(counts) == 1.0


def test_telemetry_meaningful_rate_null_when_denominator_zero() -> None:
    """Returns None when all counts are zero."""
    counts = {
        "accepted_meaningful": 0,
        "normalized_to_nominal": 0,
        "parse_error": 0,
    }
    assert telemetry_meaningful_rate(counts) is None


def test_telemetry_meaningful_rate_computed() -> None:
    """Returns accepted_meaningful / total when denominator > 0."""
    counts = {
        "accepted_meaningful": 3,
        "normalized_to_nominal": 5,
        "parse_error": 2,
    }
    # 3 / (3+5+2) = 3/10 = 0.3
    assert telemetry_meaningful_rate(counts) == 0.3


def test_get_ai_observability_rates() -> None:
    """Returns both rates from get_ai_observability_rates."""
    perception = {
        "accepted": 2,
        "suppressed": 2,
        "no_detection": 0,
        "non_perception_label": 0,
        "unknown_label": 0,
        "parse_error": 0,
    }
    telemetry = {"accepted_meaningful": 1, "normalized_to_nominal": 1, "parse_error": 0}
    rates = get_ai_observability_rates(perception, telemetry)
    assert rates["perception_acceptance_rate"] == 0.5  # 2/4
    assert rates["telemetry_meaningful_rate"] == 0.5  # 1/2
