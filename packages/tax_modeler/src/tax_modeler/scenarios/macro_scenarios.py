"""Macro scenario income shocks for SB 3125 CD1 recession analysis.

Shocks are multiplicative adjustments applied AFTER project_tax_units_forward()
and apply_top_income_growth_premium(), and BEFORE behavioral response. They
represent deviations from the county B19013 baseline trajectory.

Usage in forecast loop:
    projected = project_tax_units_forward(units, target_year=year)
    projected = apply_top_income_growth_premium(projected, ...)
    if macro_shock is not None:
        projected = apply_macro_recession_shock(projected, target_year=year,
                                                scenario=macro_shock)
    # ... rest of behavioral chain unchanged

NOTE: Update SB3125_CD1_FORECAST.md whenever these parameters change.
"""
from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Moderate recession: onset 2027, partial rebound 2028, normal from 2029
# ---------------------------------------------------------------------------

# All-filer shock — applied to every income unit.
# Interpretation: nominal income growth is 2.0pp below the B19013 baseline
# in 2027 (recession year), 1.5pp above in 2028 (rebound), then back to baseline.
_MODERATE_BASE_SHOCKS: dict[int, float] = {
    2027: -0.020,   # −2.0pp: nominal income contraction in recession year
    2028: +0.015,   # +1.5pp: partial recovery
    2029:  0.000,   # back to B19013 baseline trajectory
    2030:  0.000,
    2031:  0.000,
}

# Top-income extra shock — additional hit for filers above TOP_INCOME_RECESSION_THRESHOLD.
# Rationale: capital gains realizations and pass-through business income are
# highly cyclical (historical −40–60% CG collapse in 2001, 2008 recessions).
# The extra −1.5pp in 2027 brings the total top-income shock to −3.5pp.
_MODERATE_TOP_EXTRA_SHOCKS: dict[int, float] = {
    2027: -0.015,   # −1.5pp additional for CG/business income cyclicality
    2028: +0.010,   # +1.0pp additional CG partial rebound
    2029:  0.000,
    2030:  0.000,
    2031:  0.000,
}

TOP_INCOME_RECESSION_THRESHOLD = 200_000  # income ≥ $200K receives extra shock

MACRO_SCENARIOS: dict[str, dict] = {
    "moderate": {
        "base_shocks":      _MODERATE_BASE_SHOCKS,
        "top_extra_shocks": _MODERATE_TOP_EXTRA_SHOCKS,
        "top_threshold":    TOP_INCOME_RECESSION_THRESHOLD,
        "description":      "Moderate recession onset 2027, partial rebound 2028",
    },
}


def apply_macro_recession_shock(
    df: pd.DataFrame,
    target_year: int,
    scenario: str = "moderate",
    income_col: str = "income",
) -> pd.DataFrame:
    """Apply a macro recession income shock to projected tax units.

    Applies a base shock to ALL filers (nominal income contraction) plus an
    additional top-income shock for filers above the income threshold (capturing
    capital-gains and business-income cyclicality).

    Call AFTER project_tax_units_forward() and apply_top_income_growth_premium(),
    BEFORE apply_behavioral_response(). Returns a modified copy; does not mutate
    the input DataFrame.

    Args:
        df:          Projected tax units for the target year.
        target_year: The tax year being modeled (2027–2031).
        scenario:    Key into MACRO_SCENARIOS dict (currently only "moderate").
        income_col:  Income column to scale (default "income").

    Returns:
        Modified DataFrame with income scaled by macro shock factors.
        Years with zero shock (2029–2031 for "moderate") are returned as a
        copy with no income changes (no-op but avoids mutating original).

    Example:
        >>> projected = apply_macro_recession_shock(projected, target_year=2027)
        # All filers: income × 0.980
        # Filers ≥ $200K: income × 0.980 × 0.985  (total: × 0.9653)
    """
    params = MACRO_SCENARIOS[scenario]
    base_delta = params["base_shocks"].get(target_year, 0.0)
    top_delta  = params["top_extra_shocks"].get(target_year, 0.0)
    top_thresh = params["top_threshold"]

    out = df.copy()
    out[income_col] = out[income_col].astype(float)

    # Apply base shock to ALL filers
    if base_delta != 0.0:
        out[income_col] = out[income_col] * (1.0 + base_delta)

    # Apply extra shock to top-income filers
    if top_delta != 0.0:
        mask = out[income_col] >= top_thresh
        out.loc[mask, income_col] = out.loc[mask, income_col] * (1.0 + top_delta)

    return out
