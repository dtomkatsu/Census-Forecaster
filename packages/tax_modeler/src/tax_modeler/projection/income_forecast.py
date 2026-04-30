"""Census-Forecaster-driven Hawaii income growth factors.

Opt-out switch
--------------
Set the environment variable ``TAX_MODELER_USE_ENSEMBLE_GROWTH=0`` (or
``false`` / ``no``) to bypass this module entirely and force callers to
use the hardcoded ``RESIDENT_GROWTH`` constant. Useful for diagnosing
whether a regression is caused by the ensemble path or by the
underlying tax math. The env var is checked at every call site so it
can be flipped without restarting a long-running process.


Replaces the hardcoded ``RESIDENT_GROWTH`` constant in
:mod:`tax_modeler.config.income_growth` with a calibrated forecast from
:mod:`census_forecaster`. The forecast uses the same multi-anchor
ensemble (CPI + PCE + QCEW + FMR + FHFA HPI) that produces the
calibrated ACS predictions in census_forecaster's bundled
``calibration.json`` (schema_version=4 with conformal quantiles).

Why a single Hawaii proxy (Honolulu, geoid 15003)
--------------------------------------------------
Median household income (B19013) is forecast at the county level. Hawaii
has 4 counties; Honolulu carries 70% of state population and has the
smallest MOE in the panel. For tax_modeler's purpose — applying a
SCALAR growth factor to PUMS-level individual incomes — a state-aggregate
factor is what we need. We use Honolulu as the proxy because:

  - Population-weighted averaging of MEDIANS across counties is
    statistically incorrect (you can't average medians).
  - Population-weighted averaging of GROWTH RATES is defensible (rates
    are approximately log-additive) — but the smallest-MOE county
    dominates the variance-weighted average anyway.
  - For Hawaii, that's Honolulu.

A future enhancement (Phase A.5) could compute per-county factors and
apply them by PUMA.

Why explicit CPI deflation
--------------------------
``project_ensemble_multi`` produces a NOMINAL forecast (e.g., median
income $114,204 in 2026). tax_modeler's ``apply_income_growth`` is
documented as applying REAL growth (purchasing-power-adjusted). To
convert nominal → real we deflate by the Honolulu CPI ratio
``cpi_target_year / cpi_base_year``. CPI past the bundled 2024 endpoint
is projected forward with :func:`census_forecaster.project_damped_trend`
— the same methodology census_forecaster uses internally for indicator
trends, so income and CPI projections are mutually consistent. The
damped-trend model dampens the COVID-era inflation spike and converges
toward the long-run Hawaii CPI rate (~2.5%/yr), avoiding the bias
that a naive recent-window extrapolation would introduce.

Fallback behaviour
------------------
Any failure (missing panel data, missing CPI, ensemble returning None)
returns ``None`` so the caller can fall back to the hardcoded constant.
The reason is logged at WARNING level for diagnostics.
"""
from __future__ import annotations

import functools
import json
import logging
import os
from importlib.resources import files
from typing import Optional

logger = logging.getLogger(__name__)


# Hawaii state FIPS = "15"; Honolulu county = "15003".
DEFAULT_HAWAII_GEOID: str = "15003"
DEFAULT_INCOME_INDICATOR: str = "B19013_001E"

# Env var to disable the ensemble path. Truthy values: "1", "true", "yes",
# "on" (case-insensitive). Anything else (including the var being unset)
# leaves the ensemble enabled.
_ENV_VAR = "TAX_MODELER_USE_ENSEMBLE_GROWTH"


def _ensemble_enabled() -> bool:
    """Return False if ``TAX_MODELER_USE_ENSEMBLE_GROWTH`` is set to a
    falsy value, True otherwise."""
    val = os.environ.get(_ENV_VAR)
    if val is None:
        return True  # default: enabled
    return val.strip().lower() in {"1", "true", "yes", "on"}


@functools.lru_cache(maxsize=8)
def _load_b19013_series(geoid: str) -> tuple:
    """Load and cache the B19013 series for ``geoid`` from the bundled panel."""
    from common.models import AcsObservation

    panel_path = files("census_forecaster") / "data" / "calibration_panel" / "acs_panel.json"
    with panel_path.open() as f:
        panel = json.load(f)

    obs = [
        AcsObservation(
            estimate=o["estimate"],
            moe=o["moe"],
            year=o["year"],
            vintage=o["vintage"],
            geoid=o["geoid"],
            indicator=o["indicator"],
        )
        for o in panel["observations"]
        if o["geoid"] == geoid and o["indicator"] == DEFAULT_INCOME_INDICATOR
    ]
    return tuple(sorted(obs, key=lambda o: o.year))


@functools.lru_cache(maxsize=1)
def _load_cpi_honolulu_series() -> dict[int, float]:
    """Load and cache the Honolulu CPI All-Items series (2010-2024 in bundle)."""
    cpi_path = files("census_forecaster") / "data" / "anchors" / "cpi_honolulu_allitems.json"
    with cpi_path.open() as f:
        d = json.load(f)
    return {int(k): float(v) for k, v in d["values_by_year"].items()}


def _project_cpi(cpi_by_year: dict[int, float], target_year: int) -> float:
    """Return CPI for ``target_year`` (projecting past observed range if needed).

    Within the observed range, returns the bundled value (or linearly
    interpolates a gap year). Past the latest observation, projects
    forward with :func:`census_forecaster.project_damped_trend` —
    matching the methodology census_forecaster uses for indicator
    trends, so the deflated income figure is internally consistent.

    Raises
    ------
    KeyError
        If ``target_year`` < min(observed). No backward extrapolation.
    RuntimeError
        If the damped-trend projection fails for any reason.
    """
    years = sorted(cpi_by_year.keys())
    if target_year in cpi_by_year:
        return cpi_by_year[target_year]
    if target_year < years[0]:
        raise KeyError(f"CPI extrapolation backwards not supported: {target_year} < {years[0]}")

    last_year = years[-1]
    if target_year <= last_year:
        # Gap year inside the observed range — interpolate linearly.
        prev = max(y for y in years if y < target_year)
        nxt = min(y for y in years if y > target_year)
        frac = (target_year - prev) / (nxt - prev)
        return cpi_by_year[prev] + frac * (cpi_by_year[nxt] - cpi_by_year[prev])

    # Forward projection: damped-trend over the entire CPI history.
    # This mirrors census_forecaster's internal trend handling for ACS
    # indicators, so income+CPI projections are mutually consistent.
    from common.models import AcsObservation
    from census_forecaster import project_damped_trend

    obs = [
        AcsObservation(
            estimate=cpi_by_year[y],
            moe=0.0,
            year=y,
            vintage="1y",
            geoid="15003",  # placeholder; not consumed by trend math
            indicator="CPI_HONOLULU_AI",
        )
        for y in years
    ]
    forecast = project_damped_trend(obs, target_year=target_year)
    if forecast is None:
        raise RuntimeError(
            f"project_damped_trend returned None for CPI target_year={target_year}"
        )
    return float(forecast.point)


@functools.lru_cache(maxsize=16)
def get_hawaii_real_growth_factor(
    base_year: int,
    target_year: int,
    geoid: str = DEFAULT_HAWAII_GEOID,
) -> Optional[float]:
    """Return Hawaii median-income real growth factor from base→target year.

    "Real" means CPI-deflated (purchasing-power-adjusted). The factor
    applied to a base-year income gives the equivalent target-year
    income in constant base-year dollars.

    Parameters
    ----------
    base_year:
        The base year of the income value. Must have a B19013 observation
        in the bundled panel and a CPI observation.
    target_year:
        The year to project to. Must be > ``base_year``.
    geoid:
        County GEOID to use as the Hawaii proxy. Defaults to Honolulu
        (15003).

    Returns
    -------
    float or None
        Real growth factor (e.g. 1.05 for 5% real growth), or ``None``
        if the forecast can't be produced. The reason for ``None`` is
        logged at WARNING level.

    Notes
    -----
    Result is memoised via ``@lru_cache``, so repeated calls with the
    same arguments are O(1).
    """
    if target_year <= base_year:
        return 1.0

    if not _ensemble_enabled():
        logger.info(
            "%s set to a falsy value; bypassing ensemble path.", _ENV_VAR,
        )
        return None

    try:
        from census_forecaster.acs.anchors import load_calibration
        from census_forecaster.acs.ensemble import project_ensemble_multi
    except ImportError as e:
        logger.warning(
            "census_forecaster import failed (%s); will fall back to hardcoded growth.", e
        )
        return None

    series = _load_b19013_series(geoid)
    if not series:
        logger.warning("No B19013 series for geoid=%s in bundled panel", geoid)
        return None

    base_obs = next((o for o in series if o.year == base_year), None)
    if base_obs is None:
        logger.warning(
            "No B19013 obs for geoid=%s in base_year=%s (have %s)",
            geoid, base_year, [o.year for o in series],
        )
        return None
    if base_obs.estimate <= 0:
        logger.warning("Invalid B19013 base value at %s/%s: %s", geoid, base_year, base_obs.estimate)
        return None

    try:
        calibration = load_calibration()
    except Exception as e:  # pragma: no cover - load_calibration is robust
        logger.warning("load_calibration failed: %s", e)
        calibration = None

    forecast = project_ensemble_multi(
        series_observations=list(series),
        target_year=target_year,
        calibration=calibration,
        use_ml=False,
    )
    if forecast is None:
        logger.warning("project_ensemble_multi returned None for %s/%s→%s", geoid, base_year, target_year)
        return None

    nominal_growth = forecast.point / base_obs.estimate

    cpi_by_year = _load_cpi_honolulu_series()
    cpi_base = cpi_by_year.get(base_year)
    if cpi_base is None:
        logger.warning("No CPI Honolulu data for base_year=%s (have %s..%s)",
                       base_year, min(cpi_by_year), max(cpi_by_year))
        return None
    try:
        cpi_target = _project_cpi(cpi_by_year, target_year)
    except (KeyError, RuntimeError) as e:
        logger.warning("CPI projection failed: %s", e)
        return None

    inflation_factor = cpi_target / cpi_base
    if inflation_factor <= 0:
        logger.warning("Non-positive inflation factor %.4f", inflation_factor)
        return None

    real_growth = nominal_growth / inflation_factor

    logger.info(
        "Hawaii real income growth %s→%s (proxy=%s): "
        "nominal=%.4f (%.2f%%), inflation=%.4f (%.2f%%), real=%.4f (%.2f%%)",
        base_year, target_year, geoid,
        nominal_growth, (nominal_growth - 1) * 100,
        inflation_factor, (inflation_factor - 1) * 100,
        real_growth, (real_growth - 1) * 100,
    )

    return real_growth
