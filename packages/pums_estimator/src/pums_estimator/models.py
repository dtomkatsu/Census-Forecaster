"""Data models for pums_estimator.

Three frozen dataclasses form the core contract:

  PumsRecord          — one housing-unit (or person) row from the ACS PUMS file.
  CountyControls      — county-level marginal totals used as raking targets.
  SyntheticEstimatePoint — output of the estimator; analogous to ForecastPoint
                           in census_forecaster but keyed by (geoid, variable, category).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PumsRecord:
    """One person or housing-unit record from the ACS PUMS file.

    Fields
    ------
    serial : str
        Housing-unit serial number (SERIALNO from the PUMS API).
    puma : str
        7-character PUMA code: 2-digit state FIPS + 5-digit PUMA
        (e.g. "1500100" for PUMA 00100 in Hawaii).
    weight : float
        Housing-unit weight (WGTP) or person weight (PWGTP).
    variables : dict[str, float]
        Survey variables keyed by PUMS variable name.
        E.g. {"VEH": 2.0, "HINCP": 75000.0}.
    """
    serial: str
    puma: str
    weight: float
    variables: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class CountyControls:
    """Census / ACS control totals for one county.

    Used as margin constraints in the IPF raking step.  Each key in
    ``margins`` is a PUMS variable name; its value is a
    ``{category_label: count}`` distribution.

    Typical usage: populate from ``census_forecaster.project_ensemble_multi``
    outputs for the relevant indicator (e.g. household count, income bands)
    so that PUMS weights align with forecasted demographics.

    Fields
    ------
    geoid : str
        5-digit county FIPS code (2-digit state + 3-digit county).
    population : int
        Total county population control (persons, not housing units).
    margins : dict[str, dict[str, float]]
        E.g. {"VEH": {"0": 4500, "1": 12000, "2+": 8000}}.
    """
    geoid: str
    population: int
    margins: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass(frozen=True)
class SyntheticEstimatePoint:
    """Estimated distribution for one (geoid, variable, category) cell.

    Output of ``estimation.synthetic.estimate_county_distribution``.
    Carries both a point estimate and a standard error, analogous to
    ``ForecastPoint`` in census_forecaster, but represents a
    model-based / synthetic statistic rather than a forecast of a
    published ACS series.

    Fields
    ------
    geoid : str
        Target county FIPS code.
    variable : str
        PUMS variable name (e.g. "VEH").
    category : str
        Category label within the variable (e.g. "0", "1", "2+").
    estimate : float
        Estimated count (output_mode="count") or proportion
        (output_mode="proportion").
    se : float
        Standard error of the estimate (Kish effective-sample-size
        approximation).
    n_pums_records : int
        Number of PUMS records used after geographic filtering and
        reweighting (for audit and credibility assessment).
    method : str
        Method label (e.g. "ipf_raking").
    notes : str
        Free-form audit trail string.
    """
    geoid: str
    variable: str
    category: str
    estimate: float
    se: float
    n_pums_records: int
    method: str
    notes: str = ""
