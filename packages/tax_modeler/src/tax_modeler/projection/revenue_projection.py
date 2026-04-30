"""End-to-end forward revenue projection entry point (Phase G).

Ties together the full pipeline:

* **Phase A/A.5** — census_forecaster ensemble income forecast (B19013 → 2026)
* **Phase E** — DOTAX-calibrated concentration model (per-filer revenue)
* **Phase F** — concentration_marginal_fn for delta-method SE propagation
* **Phase C** — optional split-conformal CI floor
* **Phase H** — B19082_005E top-quintile share projection (when in panel)

Usage
-----
::

    from tax_modeler.projection.revenue_projection import (
        project_revenue_per_filer,
        project_revenue_2026,
        RevenueProjection,
    )

    # Quick 2026 projection for Honolulu (15003):
    proj = project_revenue_2026()
    print(f"2026 per-filer revenue: ${proj.per_filer_revenue:,.0f}")
    print(f"90% CI: ${proj.ci90_low:,.0f} – ${proj.ci90_high:,.0f}")
    print(f"Income growth: {(proj.income_growth_factor - 1)*100:.1f}% over 2022 base")

    # With conformal floor (from Phase C calibration):
    from tax_modeler.projection.revenue_conformal import calibrate_revenue_conformal
    quantiles = calibrate_revenue_conformal(series_by_key, [2016, 2017, 2018])
    proj = project_revenue_2026(conformal_quantiles=quantiles)

    # Any target year and geoid:
    proj = project_revenue_per_filer(
        target_year=2028, geoid="15003", method="ensemble"
    )

Numeric snapshot (Honolulu, 2026, full panel through 2024)
-----------------------------------------------------------
* Base: $4,770/filer (DOTAX 2022 calibration)
* Projected income: ~$112k (ensemble, 6 years from $84k 2022 median)
* Projected per-filer revenue: ~$6,757
* Revenue growth: ~41.7% over 4 years (2022→2026)
* 90% CI half-width: ~$720 (delta-method, no conformal floor)

Module layout
-------------
``RevenueProjection``
    Frozen dataclass: income forecast + per-filer revenue + CI + derived metrics.
``project_revenue_per_filer(target_year, geoid, ...)``
    Core projection function.  Loads bundled ACS panel, runs ensemble
    projector, applies Phase E concentration model, builds CI.
    Returns ``None`` if the geoid is not in the panel or the projector fails.
``project_revenue_2026(geoid, ...)``
    Convenience wrapper: ``project_revenue_per_filer(target_year=2026, ...)``.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_Z_90 = 1.645  # 90% Gaussian CI multiplier

# Default geoid: Honolulu County (FIPS 15003), which drives the DOTAX calibration
DEFAULT_GEOID: str = "15003"

# Default projection method
DEFAULT_METHOD: str = "ensemble"


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RevenueProjection:
    """Per-filer revenue forecast from the ACS + concentration model pipeline.

    All revenue figures are *per-return averages* calibrated to the DOTAX 2022
    bracket distribution (635,117 resident returns, $4,770 average).  To
    convert to an aggregate dollar total, multiply ``per_filer_revenue`` by an
    appropriate projected filer count.

    Attributes
    ----------
    target_year:
        The year being projected.
    geoid:
        ACS FIPS code of the geography whose B19013 series was used.
    method:
        census_forecaster projector name (e.g. ``"ensemble"``).
    anchor_year:
        Last ACS vintage year used for training (typically the last available
        year in the bundled panel).
    anchor_income:
        Observed B19013 estimate at ``anchor_year`` (nominal $).
    projected_income:
        Ensemble-projected B19013 for ``target_year`` (nominal $).
    income_se:
        Total SE of the income projection (sample + forecast components).
    per_filer_revenue:
        Phase E bracket-weighted per-filer revenue at ``projected_income``.
        At the 2022 calibration income ($83,737) this equals $4,769.80.
    revenue_se:
        Delta-method SE: ``concentration_marginal_fn(projected_income) × income_se``.
    ci90_low, ci90_high:
        90% prediction interval half-width = ``conformal_multiplier × revenue_se``.
    conformal_multiplier:
        Actual half-width multiplier.  Equals ``Z₉₀`` (1.645) when no
        conformal quantiles are provided; may be larger if conformal floor
        binds.
    base_per_filer_revenue:
        Concentration model output at the DOTAX 2022 calibration income —
        always $4,769.80 regardless of ``anchor_year``.
    income_growth_factor:
        ``projected_income / DOTAX_2022_MEDIAN_INCOME``.  Measures how far
        incomes have moved from the 2022 calibration point.
    revenue_growth_pct:
        ``(per_filer_revenue / base_per_filer_revenue − 1) × 100``.
        Revenue grows faster than income due to bracket creep.
    top_income_scale:
        B19082-derived scale factor applied to top-quintile brackets
        (``projected_share / base_share``).  ``None`` when B19082_005E is
        not in the bundled panel or ``use_b19082=False``.  When not ``None``
        the top brackets (AGI ≥ $75k) grow by this ratio beyond the uniform
        income growth — models top/median income divergence.
    b19082_top_share_projected:
        Projected B19082_005E top-quintile income share (fraction 0–1).
        ``None`` when B19082 data is unavailable.
    """
    target_year: int
    geoid: str
    method: str
    # Income forecast
    anchor_year: int
    anchor_income: float
    projected_income: float
    income_se: float
    # Revenue forecast
    per_filer_revenue: float
    revenue_se: float
    ci90_low: float
    ci90_high: float
    conformal_multiplier: float
    # Base year anchor
    base_per_filer_revenue: float
    # Derived
    income_growth_factor: float
    revenue_growth_pct: float
    # B19082 top-quintile divergence (Phase H)
    top_income_scale: Optional[float]
    b19082_top_share_projected: Optional[float]


# ---------------------------------------------------------------------------
# Core projection function
# ---------------------------------------------------------------------------

def project_revenue_per_filer(
    target_year: int = 2026,
    geoid: str = DEFAULT_GEOID,
    method: str = DEFAULT_METHOD,
    tax_fn: Optional[Callable[[float], float]] = None,
    marginal_fn: Optional[Callable[[float], float]] = None,
    conformal_quantiles: Optional[Sequence] = None,
    anchor_year: Optional[int] = None,
    use_b19082: bool = True,
) -> Optional[RevenueProjection]:
    """Project per-filer revenue to ``target_year`` using the bundled ACS panel.

    Steps
    -----
    1. Load the B19013 series for ``geoid`` from the bundled census_forecaster
       panel.
    2. Identify ``anchor_year`` (defaults to the last 1-year ACS vintage in
       the panel).
    3. Run the specified census_forecaster projector on the training series
       (all observations through ``anchor_year``) to get
       ``(projected_income, income_se)``.
    4. Apply the Phase E concentration model:
       ``per_filer_revenue = tax_fn(projected_income)``
       Default: ``make_concentration_adjusted_fn()`` (DOTAX-calibrated).
    5. Propagate SE via delta method:
       ``revenue_se = marginal_fn(projected_income) × income_se``
       Default: ``concentration_marginal_fn``.
    6. Build 90% CI, optionally floored by conformal quantiles (Phase C).

    Parameters
    ----------
    target_year:
        Year to project to.  Default 2026 (the tax model target year).
    geoid:
        ACS FIPS code.  Must be present in the bundled calibration panel
        (``census_forecaster/data/calibration_panel/acs_panel.json``).
        Default "15003" (Honolulu County).
    method:
        census_forecaster projector name.  One of ``"ensemble"``,
        ``"carry_forward"``, ``"linear_log"``, ``"damped_log_trend"``,
        ``"ar1_log_diff"``.  Default ``"ensemble"``.
    tax_fn:
        Income → per-filer revenue function.  Default: the Phase E
        concentration model (``make_concentration_adjusted_fn()``),
        which reproduces the DOTAX 2022 average of $4,770 within 0.004%.
    marginal_fn:
        Income → effective marginal callable.  Default:
        ``concentration_marginal_fn`` (numerical derivative of ``tax_fn``).
    conformal_quantiles:
        Optional list of ``RevenueConformalRecord`` from Phase C.  When
        provided, the CI half-width is floored at ``q × revenue_se``
        (in addition to the Gaussian ``Z₉₀`` floor).
    anchor_year:
        Last ACS year to include in the training series.  Default: the
        latest 1-year ACS vintage in the panel for this geoid.  Set
        explicitly to reproduce a historical forecast.
    use_b19082:
        When ``True`` (default), attempt to load B19082_005E top-quintile
        income share from the bundled panel and compute ``top_income_scale``
        for the concentration model.  If B19082_005E is not yet in the
        panel, this degrades gracefully to uniform income growth.
        Set ``False`` to skip B19082 entirely and always use uniform growth.

    Returns
    -------
    RevenueProjection or None
        Returns ``None`` if:
        * ``geoid`` is not found in the bundled panel,
        * the projector returns ``None`` (insufficient training data),
        * the projected income is non-positive.
    """
    # --- lazy imports keep module importable without heavy deps at top-level ---
    from census_forecaster.backtest.acs import DEFAULT_METHODS
    from census_forecaster.acs.projection import effective_year
    from tax_modeler.projection.income_forecast import _load_b19013_series
    from tax_modeler.projection.revenue_backtest import _CONCENTRATION_TAX_FN
    from tax_modeler.projection.revenue_concentration import (
        concentration_marginal_fn,
        expected_revenue_per_filer,
        DOTAX_2022_MEDIAN_INCOME,
    )

    fn = tax_fn or _CONCENTRATION_TAX_FN
    mr_fn = marginal_fn or concentration_marginal_fn

    # 1. Load panel
    series = _load_b19013_series(geoid)
    if not series:
        logger.warning("No B19013 data for geoid %r; returning None", geoid)
        return None

    # 2. Resolve anchor year
    one_year_obs = [o for o in series if o.vintage == "1y"]
    if not one_year_obs:
        logger.warning("No 1-year ACS observations for geoid %r", geoid)
        return None

    if anchor_year is None:
        anchor_year = max(effective_year(o) for o in one_year_obs)

    train = sorted(
        [o for o in series if effective_year(o) <= anchor_year],
        key=lambda o: (effective_year(o), o.vintage),
    )
    if not train:
        logger.warning(
            "No observations for geoid %r through anchor_year=%d", geoid, anchor_year
        )
        return None

    # Find the anchor observation (best estimate at anchor_year)
    anchor_obs = next(
        (o for o in reversed(sorted(train, key=lambda o: effective_year(o)))
         if effective_year(o) == anchor_year and o.vintage == "1y"),
        None,
    )
    if anchor_obs is None:
        # Fallback: last observation overall
        anchor_obs = max(train, key=lambda o: (effective_year(o), o.vintage))
    anchor_income = anchor_obs.estimate

    # 3. Project income
    projector = DEFAULT_METHODS.get(method)
    if projector is None:
        logger.warning("Unknown projector method %r; returning None", method)
        return None

    fp = projector(train, target_year)
    if fp is None:
        logger.warning(
            "Projector %r returned None for geoid=%r target=%d",
            method, geoid, target_year,
        )
        return None

    projected_income = fp.point
    if projected_income <= 0:
        logger.warning(
            "Non-positive projected income %.0f for geoid=%r target=%d",
            projected_income, geoid, target_year,
        )
        return None

    income_se = fp.se_total

    # 4. B19082 top-quintile divergence (Phase H)
    top_income_scale: Optional[float] = None
    b19082_top_share_projected: Optional[float] = None
    if use_b19082 and tax_fn is None:
        # Only apply B19082 when using the default concentration model;
        # custom tax_fn callers opt out of the B19082 layer.
        try:
            from tax_modeler.projection.b19082_projection import (
                compute_top_income_scale,
                project_top_quintile_share,
            )
            top_income_scale = compute_top_income_scale(
                target_year=target_year,
                geoid=geoid,
                anchor_year=anchor_year,
            )
            if top_income_scale is not None:
                b19082_top_share_projected = project_top_quintile_share(
                    target_year=target_year,
                    geoid=geoid,
                    anchor_year=anchor_year,
                )
        except Exception as exc:
            logger.debug("B19082 computation failed (%s); using uniform growth", exc)
            top_income_scale = None

    # 5. Revenue + delta-method SE
    if top_income_scale is not None:
        # Use concentration model directly with top_income_scale
        from tax_modeler.projection.revenue_concentration import expected_revenue_per_filer
        per_filer_rev = expected_revenue_per_filer(
            projected_income, top_income_scale=top_income_scale
        )
    else:
        per_filer_rev = fn(projected_income)
    mr = mr_fn(projected_income)
    revenue_se = abs(mr) * income_se

    # 6. CI
    if conformal_quantiles:
        from tax_modeler.projection.revenue_conformal import apply_revenue_conformal_floor
        horizon = target_year - anchor_year
        ci_lo, ci_hi = apply_revenue_conformal_floor(
            per_filer_rev, revenue_se, conformal_quantiles, method, horizon
        )
    else:
        half = _Z_90 * revenue_se
        ci_lo = per_filer_rev - half
        ci_hi = per_filer_rev + half

    # Back-compute actual multiplier used
    if revenue_se > 0:
        conformal_mult = (ci_hi - ci_lo) / (2.0 * revenue_se)
    else:
        conformal_mult = _Z_90

    # Base year anchor (always DOTAX 2022 calibration)
    base_rev = fn(DOTAX_2022_MEDIAN_INCOME)

    income_growth_factor = projected_income / DOTAX_2022_MEDIAN_INCOME
    revenue_growth_pct = (per_filer_rev / base_rev - 1.0) * 100.0 if base_rev > 0 else 0.0

    proj = RevenueProjection(
        target_year=target_year,
        geoid=geoid,
        method=method,
        anchor_year=anchor_year,
        anchor_income=anchor_income,
        projected_income=projected_income,
        income_se=income_se,
        per_filer_revenue=per_filer_rev,
        revenue_se=revenue_se,
        ci90_low=ci_lo,
        ci90_high=ci_hi,
        conformal_multiplier=conformal_mult,
        base_per_filer_revenue=base_rev,
        income_growth_factor=income_growth_factor,
        revenue_growth_pct=revenue_growth_pct,
        top_income_scale=top_income_scale,
        b19082_top_share_projected=b19082_top_share_projected,
    )
    logger.info(
        "Revenue projection [%s/%s → %d]: income=%.0f (±%.0f) "
        "rev=%.0f CI=[%.0f, %.0f] growth=%.1f%%",
        geoid, method, target_year,
        projected_income, income_se,
        per_filer_rev, ci_lo, ci_hi,
        revenue_growth_pct,
    )
    return proj


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------

def project_revenue_2026(
    geoid: str = DEFAULT_GEOID,
    method: str = DEFAULT_METHOD,
    tax_fn: Optional[Callable[[float], float]] = None,
    marginal_fn: Optional[Callable[[float], float]] = None,
    conformal_quantiles: Optional[Sequence] = None,
    anchor_year: Optional[int] = None,
    use_b19082: bool = True,
) -> Optional[RevenueProjection]:
    """Project per-filer revenue to 2026 — the tax model primary target year.

    Convenience wrapper for :func:`project_revenue_per_filer` with
    ``target_year=2026``.  All parameters are forwarded unchanged.

    Parameters
    ----------
    geoid:
        Default ``"15003"`` (Honolulu County).
    method:
        Default ``"ensemble"``.
    tax_fn, marginal_fn, conformal_quantiles, anchor_year, use_b19082:
        Forwarded to :func:`project_revenue_per_filer`.

    Returns
    -------
    RevenueProjection or None
    """
    return project_revenue_per_filer(
        target_year=2026,
        geoid=geoid,
        method=method,
        tax_fn=tax_fn,
        marginal_fn=marginal_fn,
        conformal_quantiles=conformal_quantiles,
        anchor_year=anchor_year,
        use_b19082=use_b19082,
    )


def format_projection_report(proj: RevenueProjection) -> str:
    """Return a concise human-readable summary of a RevenueProjection.

    Suitable for logging, CLI output, or notebook display.

    Parameters
    ----------
    proj:
        A RevenueProjection from :func:`project_revenue_per_filer`.

    Returns
    -------
    str
        Multi-line formatted report.
    """
    lines = [
        f"Revenue Projection: {proj.geoid} → {proj.target_year} [{proj.method}]",
        f"  Anchor:            {proj.anchor_year}  income=${proj.anchor_income:,.0f}",
        f"  Projected income:  ${proj.projected_income:,.0f} (±${proj.income_se:,.0f} 1σ)",
        f"  Income growth:     {(proj.income_growth_factor - 1)*100:.1f}%"
        f" from DOTAX 2022 base (${proj.anchor_income:,.0f}→${proj.projected_income:,.0f})",
        f"  Per-filer revenue: ${proj.per_filer_revenue:,.0f}",
        f"  90% CI:            ${proj.ci90_low:,.0f} – ${proj.ci90_high:,.0f}"
        f"  (mult={proj.conformal_multiplier:.3f})",
        f"  Revenue growth:    {proj.revenue_growth_pct:.1f}%"
        f" from base ${proj.base_per_filer_revenue:,.0f}",
        f"  Revenue SE:        ${proj.revenue_se:,.0f}",
    ]
    return "\n".join(lines)
