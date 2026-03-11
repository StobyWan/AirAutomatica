"""Derived AI observability values. Shared helpers for rate computation."""

from typing import Any


def perception_acceptance_rate(counts: dict[str, int]) -> float | None:
    """Accepted / total perception outcomes. Returns None when denominator is 0."""
    total = sum(
        counts.get(k, 0)
        for k in (
            "accepted",
            "suppressed",
            "no_detection",
            "non_perception_label",
            "unknown_label",
            "parse_error",
        )
    )
    if total == 0:
        return None
    return counts.get("accepted", 0) / total


def telemetry_meaningful_rate(counts: dict[str, int]) -> float | None:
    """Accepted meaningful / total telemetry summary outcomes. Returns None when denominator is 0."""
    total = sum(
        counts.get(k, 0)
        for k in (
            "accepted_meaningful",
            "normalized_to_nominal",
            "parse_error",
        )
    )
    if total == 0:
        return None
    return counts.get("accepted_meaningful", 0) / total


def get_ai_observability_rates(
    perception_counts: dict[str, int],
    telemetry_summary_counts: dict[str, int],
) -> dict[str, Any]:
    """Return perception_acceptance_rate and telemetry_meaningful_rate for health payloads."""
    return {
        "perception_acceptance_rate": perception_acceptance_rate(perception_counts),
        "telemetry_meaningful_rate": telemetry_meaningful_rate(
            telemetry_summary_counts
        ),
    }
