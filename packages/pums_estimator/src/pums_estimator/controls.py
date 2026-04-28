"""Utility functions for building CountyControls from ACS table data.

Typical workflow
----------------
    from pums_estimator import (
        controls_from_acs_table, scale_margins,
        load_crosswalk, estimate_county_distribution,
    )

    # 1. Pull ACS control counts from a published ACS table (e.g. B08201
    #    for vehicle availability, B25003 for tenure, B11001 for household type).
    margins = {
        "VEH": {"0": 2100, "1": 11500, "2": 14200, "3+": 5100},
        "TEN": {"1": 18000, "2": 14900},
    }
    controls = controls_from_acs_table("15009", population=164000, margins=margins)

    # 2. Optionally scale to a projected future year.
    future_controls = scale_margins(controls, factor=1.08)  # 8% HH growth

    # 3. Estimate distribution.
    crosswalk = load_crosswalk(vintage_year=2022)
    estimates = estimate_county_distribution(records, future_controls, "VEH", crosswalk)
"""
from __future__ import annotations

from .models import CountyControls


def controls_from_acs_table(
    geoid: str,
    population: int,
    margins: dict[str, dict[str, float]],
) -> CountyControls:
    """Construct a CountyControls from ACS table data.

    Parameters
    ----------
    geoid : str
        5-digit county FIPS code (e.g. "15009" for Maui County).
    population : int
        Total county population control (from B01003 or a forecast).
    margins : dict[str, dict[str, float]]
        Variable-to-category-to-count mapping.  Category labels must
        match the PUMS variable encoding (e.g. VEH: {"0": ..., "1": ...,
        "2+": ...}).  All count values must be non-negative.

    Returns
    -------
    CountyControls

    Raises
    ------
    ValueError
        If geoid is not a 5-digit string, population is negative, or any
        margin count is negative.
    """
    if len(geoid) != 5 or not geoid.isdigit():
        raise ValueError(
            f"geoid must be a 5-digit county FIPS string, got {geoid!r}"
        )
    if population < 0:
        raise ValueError(f"population must be non-negative, got {population}")
    for var, cats in margins.items():
        for cat, count in cats.items():
            if count < 0:
                raise ValueError(
                    f"margin count for {var!r}/{cat!r} is negative: {count}"
                )
    return CountyControls(geoid=geoid, population=population, margins=margins)


def scale_margins(controls: CountyControls, factor: float) -> CountyControls:
    """Return a new CountyControls with all margin counts scaled by *factor*.

    Useful for adjusting ACS baseline controls to a projected future year
    (e.g. multiply by 1.08 for 8% household growth from a census_forecaster
    population or household-count forecast).

    Parameters
    ----------
    controls : CountyControls
        Source controls to scale.  Not mutated.
    factor : float
        Multiplicative scaling factor.  Must be positive.

    Returns
    -------
    CountyControls
        New frozen instance with all margin counts and population scaled.

    Raises
    ------
    ValueError
        If factor is not positive.
    """
    if factor <= 0:
        raise ValueError(f"factor must be positive, got {factor}")
    scaled_margins = {
        var: {cat: count * factor for cat, count in cats.items()}
        for var, cats in controls.margins.items()
    }
    return CountyControls(
        geoid=controls.geoid,
        population=round(controls.population * factor),
        margins=scaled_margins,
    )
