"""Census-Forecaster-driven Hawaii / national income growth factors.

Two public entry points:

  - :func:`get_hawaii_real_growth_factor` — Hawaii residents. Uses
    Honolulu B19013 (geoid 15003) deflated by Honolulu CPI All-Items.
  - :func:`get_national_real_growth_factor` — Hawaii nonresidents.
    Inverse-variance-weighted geometric mean of B19013 forecasts across
    a representative basket of large mainland counties (see
    :data:`_NATIONAL_GEOIDS`), deflated by the BEA national PCE chain
    price index.

Both delegate to a shared private helper, :func:`_compute_real_growth_factor`,
which implements the multi-county aggregation + CPI deflation. The
single-county case (Hawaii) is the degenerate aggregation of N=1 county.

Opt-out switch
--------------
Set the environment variable ``TAX_MODELER_USE_ENSEMBLE_GROWTH=0`` (or
``false`` / ``no``) to bypass this module entirely and force callers to
use the hardcoded ``RESIDENT_GROWTH`` / ``NONRESIDENT_GROWTH`` constants.
Useful for diagnosing whether a regression is caused by the ensemble path
or by the underlying tax math. The env var is checked at every call site
so it can be flipped without restarting a long-running process.

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

Why an 8-county basket for the national proxy
---------------------------------------------
Hawaii nonresidents earn income from outside Hawaii, so Honolulu B19013 +
Honolulu CPI is the wrong proxy. We use the 8 largest mainland counties
in census_forecaster's bundled panel (LA, Cook, Harris, Maricopa,
San Diego, Orange, Miami-Dade, Dallas — all xlarge population bucket
with full 14-obs B19013 series) deflated by the national PCE deflator.

Aggregation across the basket uses **inverse-variance weighting** on the
log-growth-rate via the delta method
(``var(log(point/base)) ≈ (se_total/point)^2``). This dominates over
population-weighting (which would over-weight LA + Cook + Harris) because
it gives more weight to forecasts with tighter standard errors regardless
of which county they came from. Population weighting is offered as a
sensitivity-analysis fallback (``weighting="population"``).

Why explicit CPI deflation
--------------------------
``project_ensemble_multi`` produces a NOMINAL forecast (e.g., median
income $114,204 in 2026). tax_modeler's ``apply_income_growth`` is
documented as applying REAL growth (purchasing-power-adjusted). To
convert nominal → real we deflate by the price-index ratio
``cpi_target_year / cpi_base_year``. CPI past the bundled 2024 endpoint
is projected forward with :func:`census_forecaster.project_damped_trend`
— the same methodology census_forecaster uses internally for indicator
trends, so income and CPI projections are mutually consistent. The
damped-trend model dampens the COVID-era inflation spike and converges
toward the long-run rate (~2.5%/yr Honolulu CPI, ~2%/yr national PCE),
avoiding the bias that a naive recent-window extrapolation would
introduce.

Note: PCE is one of the input anchors to ``project_ensemble_multi`` for
B19013 *level* calibration, not as a deflator. Explicit deflation of the
nominal forecast by the PCE projection therefore is not double-counting.

Graceful degradation
--------------------
If 1 of N county forecasts in the basket fails (panel missing the geoid,
ensemble returning None), it is logged at WARNING and skipped; the
remaining counties are aggregated. The public wrappers return ``None``
only if **all** counties fail, in which case ``apply_income_growth``
falls back to the hardcoded constant.
"""
from __future__ import annotations

import functools
import json
import logging
import math
import os
from importlib.resources import files
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# Hawaii state FIPS = "15"; Honolulu county = "15003".
DEFAULT_HAWAII_GEOID: str = "15003"
DEFAULT_INCOME_INDICATOR: str = "B19013_001E"

# 8 largest mainland US counties (excluding Hawaii / Alaska) by 2020 pop.
# Each has a full 14-obs B19013_001E series in the bundled panel.
_NATIONAL_GEOIDS: tuple[str, ...] = (
    "06037",  # Los Angeles, CA
    "17031",  # Cook, IL
    "48201",  # Harris, TX
    "04013",  # Maricopa, AZ
    "06073",  # San Diego, CA
    "06059",  # Orange, CA
    "12086",  # Miami-Dade, FL
    "48113",  # Dallas, TX
)

# 2020 populations for the national basket (used only when
# ``weighting="population"``; not the default).
_COUNTY_POP_2020: dict[str, int] = {
    "06037": 10_040_682,
    "17031":  5_169_517,
    "48201":  4_680_609,
    "04013":  4_412_779,
    "06073":  3_323_970,
    "06059":  3_170_345,
    "12086":  2_705_528,
    "48113":  2_622_634,
}

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


# -----------------------------------------------------------------------------
# Series + price-index loaders (memoised)
# -----------------------------------------------------------------------------


@functools.lru_cache(maxsize=16)
def _load_b19013_series(geoid: str) -> tuple:
    """Load and cache the B19013 series for ``geoid`` from the bundled panel.

    Returns an empty tuple if the geoid isn't represented in the panel.
    """
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


@functools.lru_cache(maxsize=1)
def _load_pce_deflator_series() -> dict[int, float]:
    """Load and cache the BEA national PCE chain price index (2010-2024 in bundle).

    BEA NIPA Table 2.3.4, line 1 (Personal consumption expenditures price index).
    Annual, 2017=100. The national PCE price index is the appropriate deflator
    for nonresident income forecasts (national-level cost of living).
    """
    pce_path = files("census_forecaster") / "data" / "anchors" / "pce_deflator.json"
    with pce_path.open() as f:
        d = json.load(f)
    return {int(k): float(v) for k, v in d["values_by_year"].items()}


# -----------------------------------------------------------------------------
# Damped-trend price-index projection
# -----------------------------------------------------------------------------


def _project_cpi(cpi_by_year: dict[int, float], target_year: int) -> float:
    """Return the price index for ``target_year`` (projecting past observed range).

    Within the observed range, returns the bundled value (or linearly
    interpolates a gap year). Past the latest observation, projects
    forward with :func:`census_forecaster.project_damped_trend` —
    matching the methodology census_forecaster uses for indicator
    trends, so the deflated income figure is internally consistent.

    Parameters
    ----------
    cpi_by_year:
        Year → index value mapping (CPI, PCE, etc. — any annual series).
    target_year:
        Year to return the index for.

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
        raise KeyError(
            f"CPI extrapolation backwards not supported: {target_year} < {years[0]}"
        )

    last_year = years[-1]
    if target_year <= last_year:
        # Gap year inside the observed range — interpolate linearly.
        prev = max(y for y in years if y < target_year)
        nxt = min(y for y in years if y > target_year)
        frac = (target_year - prev) / (nxt - prev)
        return cpi_by_year[prev] + frac * (cpi_by_year[nxt] - cpi_by_year[prev])

    # Forward projection: damped-trend over the entire history.
    from common.models import AcsObservation
    from census_forecaster import project_damped_trend

    obs = [
        AcsObservation(
            estimate=cpi_by_year[y],
            moe=0.0,
            year=y,
            vintage="1y",
            geoid="00000",  # placeholder; not consumed by trend math
            indicator="PRICE_INDEX",
        )
        for y in years
    ]
    forecast = project_damped_trend(obs, target_year=target_year)
    if forecast is None:
        raise RuntimeError(
            f"project_damped_trend returned None for price-index target_year={target_year}"
        )
    return float(forecast.point)


# -----------------------------------------------------------------------------
# Multi-county forecast aggregation (the workhorse)
# -----------------------------------------------------------------------------


def _forecast_one_county(
    geoid: str,
    base_year: int,
    target_year: int,
    calibration: Optional[dict],
) -> Optional[tuple[float, float]]:
    """Run :func:`project_ensemble_multi` for one county and return
    ``(nominal_growth_ratio, log_variance_estimate)``.

    Returns ``None`` if the panel lacks data for this county or the
    ensemble can't produce a forecast. ``log_variance_estimate`` is
    ``(se_total / point)**2`` per the delta method; falls back to a
    sentinel ``float('nan')`` if ``se_total`` is unavailable, so the
    caller can decide how to weight the result.
    """
    from census_forecaster.acs.ensemble import project_ensemble_multi

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

    forecast = project_ensemble_multi(
        series_observations=list(series),
        target_year=target_year,
        calibration=calibration,
        use_ml=False,
    )
    if forecast is None:
        logger.warning(
            "project_ensemble_multi returned None for %s/%s→%s",
            geoid, base_year, target_year,
        )
        return None

    nominal_ratio = forecast.point / base_obs.estimate

    # Delta-method log-variance: var(log(X/c)) ≈ (sd(X)/X)^2 for X>0.
    se_total = getattr(forecast, "se_total", None)
    if se_total is None or not math.isfinite(se_total) or forecast.point <= 0:
        log_var = float("nan")
    else:
        log_var = (float(se_total) / float(forecast.point)) ** 2
        if not math.isfinite(log_var) or log_var <= 0:
            log_var = float("nan")

    return nominal_ratio, log_var


def _compute_real_growth_factor(
    geoids: tuple[str, ...],
    base_year: int,
    target_year: int,
    cpi_loader: Callable[[], dict[int, float]],
    weighting: str = "inverse_variance",
) -> Optional[float]:
    """Aggregate per-geoid B19013 forecasts into one real growth factor.

    For each ``geoid`` in ``geoids``:

    1. Load B19013 series, find ``base_year`` observation.
    2. Run ``project_ensemble_multi`` → ``forecast.point`` and
       ``forecast.se_total``.
    3. Compute ``nominal_ratio = point / base_obs.estimate``.
    4. Compute weight per ``weighting``:

       - ``"inverse_variance"`` (default): ``1 / (se_total / point)**2``
         (delta-method log-variance). Counties with missing/invalid
         ``se_total`` get equal weight.
       - ``"population"``: ``_COUNTY_POP_2020[geoid]``. Counties with no
         population entry get weight 1.

    Aggregate in log space:

        log_ratio_combined = sum(w_i * log(nominal_ratio_i)) / sum(w_i)
        nominal_growth = exp(log_ratio_combined)

    Then deflate by ``_project_cpi(cpi_loader(), target_year) / cpi_loader()[base_year]``.

    Parameters
    ----------
    geoids:
        Tuple of county GEOIDs to forecast and aggregate. Single-geoid is
        the degenerate case for the Hawaii path.
    base_year:
        Base year of the income value.
    target_year:
        Year to project to. Must be > ``base_year``.
    cpi_loader:
        Zero-arg callable returning a year→index dict (CPI Honolulu, PCE
        national, etc.).
    weighting:
        ``"inverse_variance"`` (default) or ``"population"``.

    Returns
    -------
    float or None
        Real growth factor, or ``None`` if all geoids fail or the CPI
        projection fails. Reasons logged at WARNING level.

    Raises
    ------
    ValueError
        If ``weighting`` is not one of the recognised values.
    """
    if weighting not in {"inverse_variance", "population"}:
        raise ValueError(
            f"weighting must be 'inverse_variance' or 'population', got {weighting!r}"
        )

    if target_year <= base_year:
        return 1.0

    if not _ensemble_enabled():
        logger.info("%s set to a falsy value; bypassing ensemble path.", _ENV_VAR)
        return None

    try:
        from census_forecaster.acs.anchors import load_calibration
    except ImportError as e:
        logger.warning(
            "census_forecaster import failed (%s); will fall back to hardcoded growth.", e,
        )
        return None

    try:
        calibration = load_calibration()
    except Exception as e:  # pragma: no cover - load_calibration is robust
        logger.warning("load_calibration failed: %s", e)
        calibration = None

    # Per-county forecasts.
    per_county: list[tuple[str, float, float]] = []  # (geoid, ratio, log_var)
    for geoid in geoids:
        result = _forecast_one_county(geoid, base_year, target_year, calibration)
        if result is None:
            continue
        ratio, log_var = result
        per_county.append((geoid, ratio, log_var))

    if not per_county:
        logger.warning(
            "All %d county forecast(s) failed for base_year=%s, target_year=%s",
            len(geoids), base_year, target_year,
        )
        return None

    # Compute weights.
    if weighting == "inverse_variance":
        # 1/log_var; equal weights for missing-SE counties (NaN log_var).
        finite_vars = [lv for _, _, lv in per_county if math.isfinite(lv) and lv > 0]
        # Use a sentinel "equal" weight equal to the median finite weight,
        # so missing-SE counties don't get pathologically high or low weight.
        if finite_vars:
            sentinel_weight = 1.0 / (sum(finite_vars) / len(finite_vars))
        else:
            sentinel_weight = 1.0
        weights = [
            (1.0 / lv) if (math.isfinite(lv) and lv > 0) else sentinel_weight
            for _, _, lv in per_county
        ]
    else:  # population
        weights = [
            float(_COUNTY_POP_2020.get(geoid, 1))
            for geoid, _, _ in per_county
        ]

    # Weighted geometric mean of ratios = exp(weighted arithmetic mean of logs).
    total_w = sum(weights)
    if total_w <= 0:
        logger.warning("Non-positive total weight for aggregation: %s", total_w)
        return None
    log_ratio_combined = sum(
        w * math.log(ratio) for w, (_, ratio, _) in zip(weights, per_county)
    ) / total_w
    nominal_growth = math.exp(log_ratio_combined)

    # Deflate by price-index ratio.
    cpi_by_year = cpi_loader()
    cpi_base = cpi_by_year.get(base_year)
    if cpi_base is None:
        logger.warning(
            "No price-index data for base_year=%s (have %s..%s)",
            base_year, min(cpi_by_year), max(cpi_by_year),
        )
        return None
    try:
        cpi_target = _project_cpi(cpi_by_year, target_year)
    except (KeyError, RuntimeError) as e:
        logger.warning("Price-index projection failed: %s", e)
        return None

    inflation_factor = cpi_target / cpi_base
    if inflation_factor <= 0:
        logger.warning("Non-positive inflation factor %.4f", inflation_factor)
        return None

    real_growth = nominal_growth / inflation_factor

    # One-line summary, plus per-county breakdown at DEBUG.
    logger.info(
        "Real income growth %s→%s (n=%d geoids, weighting=%s): "
        "nominal=%.4f (%.2f%%), inflation=%.4f (%.2f%%), real=%.4f (%.2f%%)",
        base_year, target_year, len(per_county), weighting,
        nominal_growth, (nominal_growth - 1) * 100,
        inflation_factor, (inflation_factor - 1) * 100,
        real_growth, (real_growth - 1) * 100,
    )
    if logger.isEnabledFor(logging.DEBUG):
        for geoid, ratio, log_var in per_county:
            logger.debug(
                "  %s: ratio=%.4f, log_var=%s",
                geoid, ratio, f"{log_var:.4e}" if math.isfinite(log_var) else "nan",
            )

    return real_growth


# -----------------------------------------------------------------------------
# Public wrappers
# -----------------------------------------------------------------------------


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
        in the bundled panel and a Honolulu CPI observation.
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
    Result is memoised via ``@lru_cache``. Delegates to
    :func:`_compute_real_growth_factor` with N=1 geoid and the Honolulu
    CPI loader.
    """
    return _compute_real_growth_factor(
        geoids=(geoid,),
        base_year=base_year,
        target_year=target_year,
        cpi_loader=_load_cpi_honolulu_series,
    )


@functools.lru_cache(maxsize=8)
def get_national_real_growth_factor(
    base_year: int,
    target_year: int,
    geoids: tuple[str, ...] = _NATIONAL_GEOIDS,
) -> Optional[float]:
    """Return national median-income real growth factor from base→target year.

    "Real" means PCE-deflated (purchasing-power-adjusted). The factor
    applied to a base-year income gives the equivalent target-year income
    in constant base-year dollars.

    Used by :func:`tax_modeler.config.income_growth.apply_income_growth`
    for **nonresident** filers, whose income is earned outside Hawaii and
    therefore tracks national rather than local trends.

    Parameters
    ----------
    base_year:
        Base year of the income value. Must have a B19013 observation in
        the bundled panel for at least one of ``geoids``, and a PCE
        deflator observation.
    target_year:
        The year to project to. Must be > ``base_year``.
    geoids:
        Tuple of county GEOIDs to use as the national basket. Defaults to
        :data:`_NATIONAL_GEOIDS` (8 largest mainland US counties by 2020
        population). Per-county forecasts are aggregated via inverse-
        variance-weighted geometric mean of nominal growth ratios.

    Returns
    -------
    float or None
        Real growth factor (e.g. 1.05 for 5% real growth), or ``None``
        if all county forecasts fail or the PCE projection fails.
        Reasons logged at WARNING level.

    Notes
    -----
    Result is memoised via ``@lru_cache``. Delegates to
    :func:`_compute_real_growth_factor` with the national basket and the
    PCE deflator loader.
    """
    return _compute_real_growth_factor(
        geoids=geoids,
        base_year=base_year,
        target_year=target_year,
        cpi_loader=_load_pce_deflator_series,
    )
