"""Thin adapter for preprocessing. Uses AircraftState directly (Option A)."""

from airautomatica.models.state import AircraftState


def prepare_for_preprocessing(state: AircraftState) -> AircraftState:
    """Pass-through: AircraftState is used directly. No duplicate model."""
    return state
