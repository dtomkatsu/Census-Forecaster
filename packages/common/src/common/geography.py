"""GEOID helpers and geography utilities shared across Census-Forecaster packages."""
from __future__ import annotations


def state_fips(geoid: str) -> str:
    """Return 2-digit state FIPS from a 5-digit county GEOID (e.g. '15003' → '15')."""
    return geoid[:2]


def county_fips(geoid: str) -> str:
    """Return 3-digit county FIPS from a 5-digit county GEOID (e.g. '15003' → '003')."""
    return geoid[2:]
