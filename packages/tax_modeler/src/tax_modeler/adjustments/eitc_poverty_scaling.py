"""EITC eligibility adjustment driven by projected S1701 poverty rate changes.

Economic rationale
------------------
``project_tax_units_forward`` scales every tax unit's income by the county's
B19013 (median household income) growth factor — a median-based signal.  The
S1701 poverty rate is an *independent* lower-tail signal: if poverty rises in a
county while the median also rises, it implies income inequality is widening and
low-income workers' earnings grew slower than the median would suggest.

After EITC is recalculated on B19013-scaled incomes, we apply a secondary
correction to EITC-eligible units using the S1701 poverty rate growth factor.
The correction is:

    eitc_amount_final = eitc_amount × poverty_rate_factor ** alpha

If poverty_rate_factor > 1 (poverty increased): EITC amounts grow — more
low-income households are struggling, and their average EITC need is higher.
If poverty_rate_factor < 1 (poverty decreased): EITC amounts shrink.

``alpha`` (default 0.5) dampens the response.  The poverty rate signal is
correlated with B19013 and noisier, so a half-elasticity is conservative and
avoids over-counting the distributional signal that B19013 partially captures.

Empirical calibration status
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The 0.5 default is currently a literature half-elasticity citation
(consistent with the half-elasticity convention used in similar
microsimulation projects: Tax Policy Center model, ITEP state model).
It has **not** been backtested against Hawaii-specific historical data.

TODO — empirical calibration (deferred to a separate sprint):

  Backtest specification:
    1. Pull historical ACS 5-year S1701 (county-level poverty rate) and
       B19013 (county median household income) for Hawaii counties
       2014→2022 via ``census_forecaster.acs.client.fetch_acs_5yr``.
    2. Pull IRS SOI EITC by Hawaii state-level (ZIP=00000 row) for the
       same years from ``data/raw/dotax_*`` or fetch from IRS SOI portal.
    3. For each year-pair (y, y+1), compute:
         B19013_factor   = B19013[y+1] / B19013[y]   (per county)
         poverty_factor  = S1701[y+1]  / S1701[y]    (per county)
         observed_eitc_change_factor = EITC[y+1] / EITC[y]  (state-level)
    4. Run a constrained regression:
         observed_eitc_change_factor ≈
             B19013_factor_weighted_average × (poverty_factor_weighted_average) ** α
       where the weighted averages are population-weighted across counties.
    5. Fit α by minimizing the residual sum of squares across year-pairs.
       Expected band: 0.3–0.7.

  Acceptance: replace the literature default with the fitted α, store the
  fit's RMSE in the docstring, and add a regression test in
  ``tests/tax_modeler/adjustments/test_eitc_poverty_scaling.py``.

  Why deferred: requires live Census API access + a multi-year IRS SOI
  panel build. Cross-package (tax_modeler ↔ census_forecaster) data
  pipeline. Estimated effort: 4-6 hours.

The Hawaii low-income tax credit (``hi_low_income_credit``) is also scaled by
the same factor, since it specifically targets filers below a poverty threshold.
``hi_tax_liability`` is updated consistently to preserve the post-credit total.

Public API
----------
scale_eitc_for_poverty(df, county_poverty_factors, default_factor, alpha) → df
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def scale_eitc_for_poverty(
    df: pd.DataFrame,
    county_poverty_factors: Dict[str, float],
    default_factor: Optional[float] = None,
    alpha: float = 0.5,
) -> pd.DataFrame:
    """Scale EITC and Hawaii LITC amounts using projected S1701 poverty rate factors.

    Parameters
    ----------
    df:
        Tax-unit DataFrame. Expected columns: ``eitc_eligible``, ``eitc_amount``,
        and optionally ``county``, ``hi_low_income_credit``, ``hi_tax_liability``.
    county_poverty_factors:
        Mapping of county name → ``poverty_rate_growth_factor`` from
        :func:`~tax_modeler.projection.acs_supplement_forecast.project_acs_supplement`.
        Factors are nominal ratios (``projected_poverty_rate / anchor_poverty_rate``).
    default_factor:
        Factor applied to rows whose county is absent from *county_poverty_factors*
        or when the DataFrame has no ``county`` column.  When ``None``, those rows
        are left unchanged.
    alpha:
        Elasticity exponent (default 0.5).  The effective multiplier per row is
        ``poverty_rate_factor ** alpha``.  Use 0.0 to disable the adjustment.

    Returns
    -------
    pd.DataFrame
        Copy of *df* with ``eitc_amount``, ``hi_low_income_credit``, and
        ``hi_tax_liability`` updated for EITC-eligible rows.
    """
    if alpha == 0.0:
        return df.copy()

    if "eitc_eligible" not in df.columns:
        logger.debug("scale_eitc_for_poverty: no eitc_eligible column; returning unchanged")
        return df.copy()

    df = df.copy()
    has_county = "county" in df.columns

    # Build a per-row multiplier series (default 1.0 = no change)
    multiplier = pd.Series(1.0, index=df.index)

    if has_county:
        for county, factor in county_poverty_factors.items():
            mask = df["county"] == county
            if mask.any():
                multiplier.loc[mask] = factor ** alpha
                logger.debug(
                    "County %r: poverty_rate_factor=%.4f → multiplier=%.4f",
                    county, factor, factor ** alpha,
                )

        # Rows whose county is not in county_poverty_factors
        unknown_mask = ~df["county"].isin(county_poverty_factors) & df["county"].notna()
        null_mask = df["county"].isna()
        fallback_mask = unknown_mask | null_mask
        if fallback_mask.any() and default_factor is not None:
            multiplier.loc[fallback_mask] = default_factor ** alpha
    else:
        # No county column: apply default factor to all rows if provided
        if default_factor is not None:
            multiplier[:] = default_factor ** alpha
        else:
            logger.debug(
                "scale_eitc_for_poverty: no county column and no default_factor; "
                "returning df unchanged"
            )
            return df

    # Only scale EITC-eligible units
    eligible = df["eitc_eligible"].astype(bool)
    if not eligible.any():
        return df

    eff_multiplier = multiplier[eligible]

    # --- Scale EITC amount --------------------------------------------------
    df.loc[eligible, "eitc_amount"] = (
        df.loc[eligible, "eitc_amount"] * eff_multiplier
    ).round(2)

    # --- Scale Hawaii low-income tax credit + keep hi_tax_liability in sync -
    if "hi_low_income_credit" in df.columns:
        old_credit = df.loc[eligible, "hi_low_income_credit"].copy()
        new_credit = (old_credit * eff_multiplier).round(2)
        df.loc[eligible, "hi_low_income_credit"] = new_credit

        # hi_tax_liability = hi_tax_before_credits - hi_low_income_credit
        # Update the net liability to reflect the changed credit.
        if "hi_tax_liability" in df.columns:
            delta = new_credit - old_credit
            df.loc[eligible, "hi_tax_liability"] = (
                df.loc[eligible, "hi_tax_liability"] - delta
            ).round(2)

    n_scaled = int(eligible.sum())
    logger.info(
        "scale_eitc_for_poverty: scaled %d eligible rows "
        "(counties: %s; alpha=%.2f)",
        n_scaled,
        list(county_poverty_factors.keys()) or ("default",),
        alpha,
    )

    return df
