"""Revenue walk-forward backtest.

Wraps census_forecaster's ACS walk-forward harness
(:mod:`census_forecaster.backtest.acs`) with a simplified Hawaii income-tax
function.  For each fold the projected income is passed through
``apply_hawaii_tax_brackets`` to produce a projected revenue, and the "actual"
revenue is derived by applying the same function to the observed ACS income at
the target year.

This gives a self-contained, DOTAX-data-free check that income-forecast
quality translates to revenue-forecast quality — the end-to-end validation
that Phases A and A.5 set up.

Why a surrogate tax function?
------------------------------
The full resident pipeline (PUMS → TaxUnitConstructor → HawaiiCalculator) is
too heavy to instantiate inside a unit-level backtest.  A surrogate that has
the right *shape* — piecewise-linear with marginal-rate jumps — is sufficient
to verify:

1. The revenue CI is correctly propagated via the delta method.
2. Ensemble income accuracy translates to better revenue accuracy than
   carry-forward (the key ship gate).
3. Revenue MAPE and CI coverage are finite and in a sane range.

The surrogate brackets are calibrated so that at Hawaii's current median HH
income (~$83k) the effective rate is approximately 5%, which is in line with
published DOTAX aggregate data.  They are NOT meant for tax planning.

Module layout
-------------
``apply_hawaii_tax_brackets(income)``
    Surrogate piecewise-linear tax function.

``run_revenue_backtest(series_by_key, anchors, ...)``
    Walk-forward driver.  Internally calls each method's projector, converts
    projected and actual income to revenue, and scores with
    ``_summarise_rows`` from the backtest harness.

``revenue_mape_vs_income_mape(series_by_key, anchors, ...)``
    Convenience diagnostic: returns a dict comparing revenue-level and
    income-level MAPE for each method so callers can see the amplification
    (or dampening) introduced by the tax function.
"""
from __future__ import annotations

import math
import logging
from typing import Callable, Sequence

from census_forecaster.backtest.acs import (
    BacktestRow,
    BacktestSummary,
    ProjectorFn,
    _summarise_rows,
    DEFAULT_METHODS,
    run_backtest,
)
from census_forecaster.acs.projection import effective_year

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Surrogate Hawaii income-tax function
# ---------------------------------------------------------------------------

# Standard deduction for single filer (2024 Hawaii schedule)
_STANDARD_DEDUCTION = 4_400.0

# Bracket thresholds (AGI after deduction, in $)
_BRACKET_LIMITS = (48_000.0, 100_000.0)  # two breakpoints → three bands
# Marginal rates per band
_BRACKET_RATES = (0.040, 0.080, 0.110)


def apply_hawaii_tax_brackets(income: float) -> float:
    """Simplified Hawaii income-tax surrogate (piecewise-linear, 3 bands).

    Uses a 3-bracket schedule calibrated to yield an effective rate of ~5%
    at the Hawaii median household income of ~$83k.  NOT for actual tax
    computation.

    Brackets (after standard deduction of $4,400):
        $0 – $48,000:     4.0 %
        $48,001 – $100,000: 8.0 %
        $100,001+:          11.0 %

    Parameters
    ----------
    income:
        Pre-deduction household income in nominal dollars.

    Returns
    -------
    float
        Estimated tax liability (≥ 0).
    """
    agi = max(income - _STANDARD_DEDUCTION, 0.0)
    if agi <= 0.0:
        return 0.0

    b0, b1 = _BRACKET_LIMITS
    r0, r1, r2 = _BRACKET_RATES

    if agi <= b0:
        return agi * r0

    if agi <= b1:
        return b0 * r0 + (agi - b0) * r1

    return b0 * r0 + (b1 - b0) * r1 + (agi - b1) * r2


def marginal_rate(income: float) -> float:
    """Marginal tax rate at ``income`` under the surrogate schedule.

    Used by the delta-method SE propagation in ``run_revenue_backtest``.
    Returns the derivative of ``apply_hawaii_tax_brackets`` with respect to
    income (piecewise constant).

    Parameters
    ----------
    income:
        Pre-deduction household income.

    Returns
    -------
    float
        Marginal rate in [0, 1].
    """
    agi = income - _STANDARD_DEDUCTION
    if agi <= 0.0:
        return 0.0
    b0, b1 = _BRACKET_LIMITS
    r0, r1, r2 = _BRACKET_RATES
    if agi <= b0:
        return r0
    if agi <= b1:
        return r1
    return r2


# ---------------------------------------------------------------------------
# Walk-forward revenue backtest driver
# ---------------------------------------------------------------------------

def run_revenue_backtest(
    series_by_key: dict[tuple[str, str], Sequence],
    anchors: Sequence[int],
    horizon: int | None = None,
    horizons: Sequence[int] | None = None,
    methods: dict[str, ProjectorFn] | None = None,
    tax_fn: Callable[[float], float] = apply_hawaii_tax_brackets,
    marginal_fn: Callable[[float], float] = marginal_rate,
    conformal_quantiles: Sequence | None = None,
) -> dict[str, BacktestSummary]:
    """Run a revenue-level walk-forward backtest.

    Each projector in ``methods`` produces an income forecast.  The forecast
    income and the observed actual income are both passed through ``tax_fn``
    to produce revenue estimates; prediction intervals are propagated via the
    delta method using ``marginal_fn``.

    Argument contract mirrors :func:`census_forecaster.backtest.acs.run_backtest`
    so callers can swap between income-level and revenue-level evaluation with
    a one-line change.

    Parameters
    ----------
    series_by_key:
        ``{(geoid, indicator): [AcsObservation, ...]}`` — full historical
        series; truncation happens internally per anchor.
    anchors:
        Integer anchor years.
    horizon / horizons:
        Forecast horizon(s) in years.  Mirrors ``run_backtest`` semantics:
        if ``horizons`` is given it wins; if neither is given, defaults to 2.
    methods:
        Dict mapping method name → :data:`ProjectorFn`.  Defaults to
        ``DEFAULT_METHODS`` from ``census_forecaster.backtest.acs``.
    tax_fn:
        Income → revenue function.  Default: ``apply_hawaii_tax_brackets``.
    marginal_fn:
        Income → marginal rate function (derivative of ``tax_fn``).
        Used for delta-method SE propagation.  Default: ``marginal_rate``.
    conformal_quantiles:
        Optional list of ``RevenueConformalRecord`` from Phase C.  When
        provided, the CI half-width is floored at ``q × se_revenue`` (in
        addition to the Gaussian ``Z₉₀ × se_revenue``), providing the
        marginal coverage guarantee.  Produced by
        :func:`tax_modeler.projection.revenue_conformal.calibrate_revenue_conformal`.

    Returns
    -------
    dict[str, BacktestSummary]
        One summary per method.  ``BacktestRow.actual`` / ``.projected`` hold
        revenue values; ``.ci90_low`` / ``.ci90_high`` are the
        delta-method-propagated (and optionally conformal-floored) revenue
        intervals.
    """
    if methods is None:
        methods = DEFAULT_METHODS

    if horizons is None:
        horizons_list: list[int] = [horizon if horizon is not None else 2]
    else:
        horizons_list = list(horizons)

    rows_by_method: dict[str, list[BacktestRow]] = {m: [] for m in methods}

    for (geoid, indicator), full_series in series_by_key.items():
        full_sorted = sorted(full_series, key=lambda o: (effective_year(o), o.vintage))

        for anchor in anchors:
            train = [o for o in full_sorted if effective_year(o) <= anchor]
            if not train:
                continue

            for h in horizons_list:
                target_year = anchor + h
                actual_obs = next(
                    (o for o in full_sorted
                     if effective_year(o) == target_year and o.vintage == "1y"),
                    None,
                )
                if actual_obs is None or actual_obs.estimate <= 0:
                    continue

                actual_revenue = tax_fn(actual_obs.estimate)
                if actual_revenue <= 0:
                    # Income below deduction threshold → skip (no revenue signal)
                    continue

                for name, projector in methods.items():
                    fp = projector(train, target_year)
                    if fp is None:
                        continue

                    # Convert projected income → projected revenue
                    income_est = fp.point
                    rev_est = tax_fn(income_est)

                    # Delta-method SE propagation: Var(tax(Y)) ≈ [tax'(Y)]² Var(Y)
                    mr = marginal_fn(income_est)
                    se_rev = abs(mr) * fp.se_total
                    se_sample_rev = abs(mr) * fp.se_sample
                    se_forecast_rev = abs(mr) * fp.se_forecast

                    # Revenue 90% CI: delta-method Gaussian, with optional
                    # conformal floor (Phase C) that widens CI when q > Z₉₀.
                    if conformal_quantiles:
                        from tax_modeler.projection.revenue_conformal import (
                            apply_revenue_conformal_floor,
                        )
                        ci_lo, ci_hi = apply_revenue_conformal_floor(
                            rev_est, se_rev, conformal_quantiles, name, h,
                        )
                    else:
                        from common.moe import ci_from_se
                        ci_lo, ci_hi = ci_from_se(rev_est, se_rev)

                    rows_by_method[name].append(BacktestRow(
                        geoid=geoid,
                        indicator=indicator,
                        anchor_year=anchor,
                        target_year=target_year,
                        horizon=h,
                        method=name,
                        actual=actual_revenue,
                        projected=rev_est,
                        ci90_low=ci_lo,
                        ci90_high=ci_hi,
                        sample_se=se_sample_rev,
                        forecast_se=se_forecast_rev,
                    ))

    result = {name: _summarise_rows(name, rows) for name, rows in rows_by_method.items()}

    # Log summary for diagnostics
    for name, summary in result.items():
        if summary.n > 0:
            logger.info(
                "Revenue backtest [%s]: n=%d  MAPE=%.2f%%  CI90cov=%.1f%%",
                name, summary.n,
                summary.mean_abs_pct_error * 100,
                summary.ci90_coverage * 100,
            )

    return result


# ---------------------------------------------------------------------------
# Diagnostic helper
# ---------------------------------------------------------------------------

def revenue_mape_vs_income_mape(
    series_by_key: dict[tuple[str, str], Sequence],
    anchors: Sequence[int],
    horizon: int | None = None,
    horizons: Sequence[int] | None = None,
    methods: dict[str, ProjectorFn] | None = None,
    tax_fn: Callable[[float], float] = apply_hawaii_tax_brackets,
    marginal_fn: Callable[[float], float] = marginal_rate,
) -> dict[str, dict[str, float]]:
    """Return per-method ``{"income_mape": ..., "revenue_mape": ..., "amplification": ...}``.

    Useful for checking that the tax function does not amplify income forecast
    errors unreasonably.  For a bracket schedule, the amplification is driven
    by the marginal rate at the projected income level — revenue MAPE ≈
    income MAPE × (effective_marginal_rate / effective_average_rate).

    In practice, for Hawaii median income (~$83k), the effective rate is ~5%
    and the marginal rate is ~8%, so we expect amplification of roughly 1.6×.
    The diagnostic makes this explicit and lets callers set an appropriate
    revenue MAPE threshold.
    """
    income_summaries = run_backtest(
        series_by_key, anchors,
        horizon=horizon, horizons=horizons,
        methods=methods,
    )
    revenue_summaries = run_revenue_backtest(
        series_by_key, anchors,
        horizon=horizon, horizons=horizons,
        methods=methods, tax_fn=tax_fn, marginal_fn=marginal_fn,
    )

    out: dict[str, dict[str, float]] = {}
    for name in income_summaries:
        im = income_summaries[name].mean_abs_pct_error
        rm = revenue_summaries[name].mean_abs_pct_error
        amp = (rm / im) if (math.isfinite(im) and im > 0 and math.isfinite(rm)) else math.nan
        out[name] = {
            "income_mape": im,
            "revenue_mape": rm,
            "amplification": amp,
        }
    return out
