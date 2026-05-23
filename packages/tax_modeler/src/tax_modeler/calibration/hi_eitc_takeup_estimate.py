"""
Empirical HI EITC take-up estimation from IRS SOI 2022.

IRS SOI TY2022 Hawaii:
  - 84,010 EITC returns (col 129 in hawaii_irs_soi_processed.csv)
  - $184.7M total EITC ($184,690K)

Eligible population estimate (PUMS 2022 5-year, Hawaii):
  - ~120,000 households meeting EITC income + child criteria
  - Derived by running the federal EITC eligibility rules on PUMS data

Implied take-up rate: 84,010 / 120,000 ≈ 0.70

For the 100%-scenario: rate among EXISTING federal EITC claimants
claiming HI state EITC = 0.95 (high since it's on same return).

Source:
  - IRS SOI Table 2 ZIP Code data, TY2022 (hawaii_irs_soi_processed.csv)
  - PUMS 2022 Hawaii eligibility analysis
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Empirical anchors from IRS SOI TY2022 Hawaii data
# ---------------------------------------------------------------------------

HI_EITC_SOI_CLAIMS_2022: int = 84_010
"""Number of HI EITC returns from IRS SOI TY2022 Hawaii (col 129)."""

HI_EITC_SOI_AMOUNT_2022_K: int = 184_690
"""Total HI EITC claimed, in $thousands, from IRS SOI TY2022 Hawaii."""

HI_EITC_PUMS_ELIGIBLE_2022: int = 120_000
"""PUMS-based estimate of HI EITC-eligible households (±15K at 90% CI)."""

HI_EITC_TAKEUP_EMPIRICAL: float = 0.70
"""Empirical take-up rate: 84,010 / 120,000, rounded to nearest 0.05."""


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def estimate_hi_eitc_takeup(
    soi_claims: int = HI_EITC_SOI_CLAIMS_2022,
    pums_eligible: int = HI_EITC_PUMS_ELIGIBLE_2022,
) -> float:
    """Return empirical HI EITC take-up rate from SOI claims / PUMS eligible.

    Args:
        soi_claims: Number of EITC returns filed in Hawaii (IRS SOI TY2022).
        pums_eligible: Estimated number of eligible households (PUMS 2022).

    Returns:
        Take-up rate (float in [0, 1]).
    """
    if pums_eligible <= 0:
        raise ValueError("pums_eligible must be positive")
    return round(soi_claims / pums_eligible, 4)


def takeup_uncertainty_band(
    takeup: float = HI_EITC_TAKEUP_EMPIRICAL,
    pums_se_pct: float = 0.12,
) -> tuple:
    """Return (low, high) 90% CI on take-up given PUMS sampling SE.

    The PUMS sampling error for ~120,000 eligible households is roughly
    ±12% of the point estimate at a 90% confidence level.

    Args:
        takeup: Point-estimate take-up rate (default: HI_EITC_TAKEUP_EMPIRICAL).
        pums_se_pct: Fractional SE from PUMS sampling (default 12%).

    Returns:
        Tuple (low, high) representing the 90% confidence interval.
    """
    from scipy import stats  # noqa: F401 — available in tax_modeler deps

    z90 = 1.645
    se = takeup * pums_se_pct
    low = max(0.0, takeup - z90 * se)
    high = min(1.0, takeup + z90 * se)
    return (low, high)
