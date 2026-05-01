"""
Forward micro-simulation projector for tax units.

Scales each tax unit's income to a target year using county-specific
census_forecaster B19013 nominal income growth rates, then recalculates
Hawaii tax liability and federal credits on the scaled incomes.

The projected DataFrame has the same schema as the input and is ready
for consumption by RevenueEstimator:

    from tax_modeler.projection.tax_unit_projector import project_tax_units_forward
    from tax_modeler.revenue.estimator import RevenueEstimator

    projected = project_tax_units_forward(base_year_units, target_year=2026)
    est = RevenueEstimator(projected)
    est.by_county()             # county-level 2026 projections, differentiated
    est.by_district(...)        # district-level 2026 projections
    est.by_income_quintile()    # distributional breakdown at 2026

Growth methodology
------------------
For each county, the nominal income growth ratio is:

    factor = projected_B19013(target_year, county) / anchor_B19013(base_year, county)

sourced from census_forecaster's ensemble projector on the bundled ACS panel
(same projector used by project_revenue_per_filer). Counties not present in the
panel fall back to the Honolulu (15003) B19013 as a Hawaii-wide proxy.

Tax recalculation uses the 2023 Hawaii bracket schedule
(calculate_hawaii_tax_for_units). CTC and EITC are recalculated on the scaled
incomes using the 2023 federal parameters.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, NamedTuple, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# County → ACS FIPS geoid mapping
# ---------------------------------------------------------------------------

_HAWAII_COUNTY_GEOIDS: Dict[str, str] = {
    "Hawaii":   "15001",
    "Honolulu": "15003",
    "Kalawao":  "15005",
    "Kauai":    "15007",
    "Maui":     "15009",
}

# Kalawao County (~90 residents) is not in the ACS 1-year panel.
# Fall back to Maui (geographically adjacent on Molokai).
_KALAWAO_GEOID = "15005"
_KALAWAO_FALLBACK = "15009"

# Honolulu used as Hawaii-wide proxy when a county is not in the panel.
_STATE_PROXY_GEOID = "15003"

# Default anchor year when base_year is not supplied
_DEFAULT_BASE_YEAR = 2022

# 90% Gaussian multiplier — used to translate income_se into factor CI bounds.
_Z90 = 1.645


class _GrowthFactorResult(NamedTuple):
    """Point estimate and 90% CI bounds for a county income growth factor.

    All three values are ratios relative to ``anchor_income``
    (i.e. ``projected_income / anchor_income``).  ``factor_ci90_low``
    may be less than 1.0 even when nominal growth is positive if the
    forecast SE is large relative to the projected level.
    """
    factor: float          # point estimate: projected_income / anchor_income
    factor_ci90_low: float  # lower 90% CI bound on the growth factor
    factor_ci90_high: float  # upper 90% CI bound on the growth factor


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _resolve_geoid(county: str, geoid_map: Dict[str, str]) -> Optional[str]:
    """Return the FIPS geoid for a county name using a case-insensitive match."""
    county_lower = county.lower()
    for key, geoid in geoid_map.items():
        if key.lower() in county_lower or county_lower in key.lower():
            # Kalawao is not in the ACS panel; redirect to Maui
            if geoid == _KALAWAO_GEOID:
                return _KALAWAO_FALLBACK
            return geoid
    return None


def _fetch_growth_factor(
    geoid: str,
    anchor_year: Optional[int],
    target_year: int,
    method: str,
) -> Optional[_GrowthFactorResult]:
    """
    Return the nominal B19013 income growth factor and 90% CI for a geoid.

    The point factor is ``projected_income / anchor_income`` (both in nominal
    ACS dollars).  CI bounds are derived from ``income_se`` via
    ``factor ± Z90 × income_se / anchor_income``.

    Returns None if the geoid is absent from the census_forecaster panel or
    the projector fails.
    """
    from tax_modeler.projection.revenue_projection import project_revenue_per_filer

    proj = project_revenue_per_filer(
        target_year=target_year,
        geoid=geoid,
        method=method,
        anchor_year=anchor_year,
    )
    if proj is None or proj.anchor_income <= 0:
        return None

    factor = proj.projected_income / proj.anchor_income
    half_se = _Z90 * proj.income_se / proj.anchor_income
    return _GrowthFactorResult(
        factor=factor,
        factor_ci90_low=max(0.0, factor - half_se),
        factor_ci90_high=factor + half_se,
    )


def _state_fallback_growth(base_year: int, target_year: int, method: str) -> _GrowthFactorResult:
    """Honolulu-proxy growth factor (with CI) for counties not in the ACS panel."""
    gfr = _fetch_growth_factor(_STATE_PROXY_GEOID, base_year, target_year, method)
    if gfr is None:
        logger.warning(
            "State fallback (Honolulu proxy) also failed for %d→%d; using 1.0",
            base_year, target_year,
        )
        return _GrowthFactorResult(factor=1.0, factor_ci90_low=1.0, factor_ci90_high=1.0)
    return gfr


def _apply_bls_income_projection(
    df: pd.DataFrame,
    pums_persons_df: pd.DataFrame,
    bls_oes_data: pd.DataFrame,
    acs_timeseries_dir: Optional[Path],
    target_year: int,
    ep_base_year: int,
    acs_weight: float,
    bls_weight: float,
) -> pd.DataFrame:
    """Scale incomes using EnsembleProjector (BLS OES occupation-specific growth).

    Called when the caller provides PUMS person data with SOCP codes.  The
    EnsembleProjector blends county-level ACS aggregate growth with BLS OES
    occupation-specific wage-growth rates using confidence-weighted blending.

    ``df["income_base_year"]`` must already be set before this call.
    EnsembleProjector's ``income_original`` column is dropped on return (it
    duplicates ``income_base_year``). Metadata columns added by the projector
    that conflict with ``project_tax_units_forward``'s own metadata
    (``projection_year``, ``base_year``, ``years_projected``) are also dropped.
    """
    from tax_modeler.projection.ensemble import EnsembleProjector

    ep_dir = acs_timeseries_dir if acs_timeseries_dir is not None else Path("/dev/null")
    ep = EnsembleProjector(
        acs_timeseries_dir=ep_dir,
        bls_oes_data=bls_oes_data,
        base_year=ep_base_year,
        acs_weight=acs_weight,
        bls_weight=bls_weight,
    )
    df = ep.project_income(df, pums_persons_df, target_year, income_column="income")

    # Clean up EP-specific columns that are either redundant or would
    # conflict with the metadata added by project_tax_units_forward.
    drop_cols = ["income_original", "base_year", "projection_year", "years_projected"]
    df.drop(columns=[c for c in drop_cols if c in df.columns], inplace=True)

    return df


def _recalculate_ctc(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recalculate CTC on scaled incomes.

    Calls calculate_ctc() per row and merges results directly (unit.update
    pattern), producing ctc_total / ctc_refundable / ctc_nonrefundable columns
    as RevenueEstimator expects.  The DataFrame-level calculate_ctc_for_tax_units
    adds a redundant 'ctc_' prefix (producing ctc_ctc_total), so we bypass it.
    """
    from tax_modeler.credits.ctc import calculate_ctc

    results = []
    for _, row in df.iterrows():
        unit = row.to_dict()
        unit.update(calculate_ctc(unit))
        results.append(unit)
    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def project_tax_units_forward(
    tax_units_df: pd.DataFrame,
    target_year: int,
    base_year: Optional[int] = None,
    method: str = "ensemble",
    geoid_map: Optional[Dict[str, str]] = None,
    pums_persons_df: Optional[pd.DataFrame] = None,
    acs_timeseries_dir: Optional[Path] = None,
    bls_oes_data: Optional[pd.DataFrame] = None,
    acs_weight: float = 0.4,
    bls_weight: float = 0.6,
) -> pd.DataFrame:
    """
    Project tax units to ``target_year`` using county-specific income growth.

    Steps
    -----
    1. For each unique county in ``tax_units_df``, fetch the nominal B19013
       growth ratio from census_forecaster (projected / anchor).  Counties
       absent from the ACS panel fall back to the Honolulu proxy.
    2. Scale each tax unit's ``income`` column by its county's growth factor.
    3. Recalculate ``hi_*`` columns via ``calculate_hawaii_tax_for_units``
       (2023 Hawaii bracket schedule).
    4. Recalculate ``ctc_*`` and ``eitc_*`` columns on the scaled incomes.
    5. Return the projected DataFrame with the same schema as the input.

    Parameters
    ----------
    tax_units_df:
        Base-year tax units.  Required columns: ``weight``, ``filing_status``,
        ``income``, ``num_dependents``.  An optional ``county`` column enables
        per-county differentiated growth; without it, the Honolulu proxy is
        applied uniformly.
    target_year:
        Year to project forward to (e.g. 2026).
    base_year:
        ACS anchor year used as the denominator of the growth ratio.
        Defaults to ``None``, in which case census_forecaster uses its most
        recent 1-year ACS vintage as the anchor automatically.
    method:
        census_forecaster projector: ``"ensemble"`` (default),
        ``"damped_log_trend"``, ``"ar1_log_diff"``, ``"carry_forward"``, or
        ``"linear_log"``.
    geoid_map:
        Optional override for the county → FIPS geoid mapping.  Keys should
        match values in the ``county`` column.  Merged with (and takes
        precedence over) the built-in Hawaii mapping.
    pums_persons_df:
        Optional PUMS person-level DataFrame with columns ``SERIALNO``,
        ``SPORDER``, and ``SOCP`` (occupation codes).  When provided together
        with ``bls_oes_data``, activates the **BLS OES path**: income is
        projected via :class:`EnsembleProjector` (occupation-specific BLS wage
        growth blended with ACS aggregate growth) instead of the county-scalar
        B19013 path.  ``income_ci90_low`` / ``income_ci90_high`` are set to NaN
        in this path since the uncertainty model differs.
    acs_timeseries_dir:
        Directory containing ACS time-series parquet files consumed by
        :class:`EnsembleProjector`.  If ``None`` (default), the projector
        falls back to a 2% annual ACS aggregate growth rate.  Only used when
        ``pums_persons_df`` and ``bls_oes_data`` are both non-``None``.
    bls_oes_data:
        DataFrame with BLS OES occupation wage data.  Required columns depend
        on whether summary or time-series data is passed; see
        :class:`OccupationMatcher` for details.  When ``None``, the BLS OES
        path is skipped regardless of ``pums_persons_df``.
    acs_weight:
        Weight assigned to the ACS aggregate growth component in
        :class:`EnsembleProjector` (default 0.4).
    bls_weight:
        Weight assigned to the BLS occupation-specific component (default 0.6).
        Effective BLS weight is scaled by per-row match confidence; low-quality
        matches fall back toward the ACS aggregate.

    Returns
    -------
    pd.DataFrame
        Projected tax units.  Added columns:

        * ``income_base_year`` — original income before scaling
        * ``income_ci90_low`` / ``income_ci90_high`` — 90% CI bounds on
          projected income (NaN when using the BLS OES path)
        * ``projection_year`` — ``target_year``
        * ``projection_base_year`` — the anchor year used (or default)
        * ``projection_method`` — the projector name used
    """
    if tax_units_df.empty:
        return tax_units_df.copy()

    # Merge caller-supplied overrides into the built-in geoid map
    geoid_lookup = {**_HAWAII_COUNTY_GEOIDS, **(geoid_map or {})}
    anchor_year = base_year  # may be None → panel picks latest vintage

    # BLS OES path is active when the caller provides person-level PUMS data
    # with occupation codes AND BLS wage-growth data.
    use_bls_path = pums_persons_df is not None and bls_oes_data is not None

    # --- Auto-assign geography if PUMA is present but county is absent ------
    # TaxUnitConstructor preserves the PUMA column from PUMS records; use the
    # crosswalk to derive county (and legislative districts) before we try to
    # resolve per-county growth factors below.
    if "PUMA" in tax_units_df.columns and "county" not in tax_units_df.columns:
        from tax_modeler.analysis.puma_crosswalk import assign_geography
        logger.info(
            "project_tax_units_forward: PUMA column detected without county — "
            "auto-assigning geography via assign_geography()"
        )
        tax_units_df = assign_geography(tax_units_df)

    # --- Per-county growth factors (with CI) — scalar path only -------------
    county_growth: Dict[str, _GrowthFactorResult] = {}
    has_county = "county" in tax_units_df.columns

    if not use_bls_path and has_county:
        for county in tax_units_df["county"].dropna().unique():
            geoid = _resolve_geoid(str(county), geoid_lookup)
            if geoid is None:
                logger.warning(
                    "County %r has no geoid mapping; will apply state fallback", county
                )
                continue
            gfr = _fetch_growth_factor(geoid, anchor_year, target_year, method)
            if gfr is None:
                logger.warning(
                    "census_forecaster returned None for county=%r (geoid %s); "
                    "will apply state fallback",
                    county, geoid,
                )
            else:
                county_growth[county] = gfr
                logger.debug(
                    "County %r (geoid %s) growth factor: %.4f  90%% CI [%.4f, %.4f]",
                    county, geoid, gfr.factor, gfr.factor_ci90_low, gfr.factor_ci90_high,
                )

    # Compute fallback lazily (only if needed)
    _fallback: Optional[_GrowthFactorResult] = None

    def fallback() -> _GrowthFactorResult:
        nonlocal _fallback
        if _fallback is None:
            by = anchor_year if anchor_year is not None else _DEFAULT_BASE_YEAR
            _fallback = _state_fallback_growth(by, target_year, method)
            logger.info(
                "State fallback growth factor (Honolulu proxy): %.4f  "
                "90%% CI [%.4f, %.4f]",
                _fallback.factor, _fallback.factor_ci90_low, _fallback.factor_ci90_high,
            )
        return _fallback

    # --- Scale incomes -------------------------------------------------------
    df = tax_units_df.copy()
    df["income_base_year"] = df["income"].copy()

    if use_bls_path:
        # BLS OES path: occupation-specific growth via EnsembleProjector.
        # CI columns are left NaN — per-row occupation growth provides no
        # aggregate CI analogous to the county B19013 SE.
        ep_base_year = anchor_year if anchor_year is not None else _DEFAULT_BASE_YEAR
        df = _apply_bls_income_projection(
            df, pums_persons_df, bls_oes_data, acs_timeseries_dir,
            target_year, ep_base_year, acs_weight, bls_weight,
        )
        df["income_ci90_low"] = float("nan")
        df["income_ci90_high"] = float("nan")
        logger.info(
            "BLS OES path: %d units, median %.0f → %.0f",
            len(df), df["income_base_year"].median(), df["income"].median(),
        )
    else:
        # County B19013 scalar path: uniform factor per county + 90% CI.
        df["income_ci90_low"] = float("nan")
        df["income_ci90_high"] = float("nan")

    if not use_bls_path and has_county:
        for county, gfr in county_growth.items():
            mask = df["county"] == county
            df.loc[mask, "income"] *= gfr.factor
            df.loc[mask, "income_ci90_low"] = (
                df.loc[mask, "income_base_year"] * gfr.factor_ci90_low
            )
            df.loc[mask, "income_ci90_high"] = (
                df.loc[mask, "income_base_year"] * gfr.factor_ci90_high
            )

        # Rows whose county was not resolved → state fallback
        unresolved = ~df["county"].isin(county_growth) & df["county"].notna()
        if unresolved.any():
            fb = fallback()
            df.loc[unresolved, "income"] *= fb.factor
            df.loc[unresolved, "income_ci90_low"] = (
                df.loc[unresolved, "income_base_year"] * fb.factor_ci90_low
            )
            df.loc[unresolved, "income_ci90_high"] = (
                df.loc[unresolved, "income_base_year"] * fb.factor_ci90_high
            )

        # Rows with a null county → state fallback
        null_county = df["county"].isna()
        if null_county.any():
            fb = fallback()
            df.loc[null_county, "income"] *= fb.factor
            df.loc[null_county, "income_ci90_low"] = (
                df.loc[null_county, "income_base_year"] * fb.factor_ci90_low
            )
            df.loc[null_county, "income_ci90_high"] = (
                df.loc[null_county, "income_base_year"] * fb.factor_ci90_high
            )

    elif not use_bls_path:
        # No county column → apply state-wide fallback to all rows
        fb = fallback()
        df["income"] *= fb.factor
        df["income_ci90_low"] = df["income_base_year"] * fb.factor_ci90_low
        df["income_ci90_high"] = df["income_base_year"] * fb.factor_ci90_high

    if not use_bls_path:
        logger.info(
            "Income scaled: %d units, median %.0f → %.0f  "
            "90%% CI median [%.0f, %.0f]",
            len(df),
            df["income_base_year"].median(),
            df["income"].median(),
            df["income_ci90_low"].median(),
            df["income_ci90_high"].median(),
        )

    # --- Recalculate Hawaii tax on scaled incomes (with scaled deductions) ---
    from tax_modeler.liability.hawaii import calculate_hawaii_tax_for_units
    from tax_modeler.adjustments.itemized_deductions import scale_deduction_params_for_target_year

    if has_county:
        # Compute per-county scaled deduction params and recalculate each group.
        county_ded_params: Dict[str, dict] = {}
        for county in df["county"].dropna().unique():
            geoid = _resolve_geoid(str(county), geoid_lookup)
            if geoid is None:
                geoid = _STATE_PROXY_GEOID
            county_ded_params[county] = scale_deduction_params_for_target_year(
                target_year, geoid=geoid
            )
        # Fallback params for null-county rows
        fallback_ded = scale_deduction_params_for_target_year(
            target_year, geoid=_STATE_PROXY_GEOID
        )

        groups = []
        # Named county groups
        for county, ded_params in county_ded_params.items():
            mask = df["county"] == county
            groups.append(
                calculate_hawaii_tax_for_units(
                    df[mask], tax_year=target_year, deduction_params=ded_params
                )
            )
        # Null-county rows
        null_mask = df["county"].isna()
        if null_mask.any():
            groups.append(
                calculate_hawaii_tax_for_units(
                    df[null_mask], tax_year=target_year, deduction_params=fallback_ded
                )
            )
        df = pd.concat(groups).sort_index()
    else:
        state_ded = scale_deduction_params_for_target_year(
            target_year, geoid=_STATE_PROXY_GEOID
        )
        df = calculate_hawaii_tax_for_units(df, tax_year=target_year, deduction_params=state_ded)

    # --- Recalculate CTC and EITC on scaled incomes --------------------------
    df = _recalculate_ctc(df)

    from tax_modeler.credits.eitc import calculate_eitc_for_tax_units
    df = calculate_eitc_for_tax_units(df)

    # --- Metadata columns ----------------------------------------------------
    df["projection_year"] = target_year
    df["projection_base_year"] = anchor_year if anchor_year is not None else _DEFAULT_BASE_YEAR
    df["projection_method"] = method

    return df
