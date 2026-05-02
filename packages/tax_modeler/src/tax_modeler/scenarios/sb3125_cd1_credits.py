"""Static-scoring overlay for SB 3125 CD1 credit changes.

Two credit changes in the bill have material fiscal impact but are not
captured by the individual-income-tax microsimulation:

  1. §235-12.5 Renewable Energy Technologies Income Tax Credit
     - Capped at $40M aggregate per year for TY 2027–2030
     - Set to $0 from TY 2031 onward
     - Adds AGI eligibility limits ($175K single / $350K joint)

  2. §235-110.7 Capital Goods Excise Tax Credit
     - Sunsets effective Dec 31, 2027 (applies TY 2028+)

Both credits are largely refundable and substantially corporate-side, so
they don't flow through the individual tax microsimulation. We score them
as a static overlay using DOTAX TY2023 actuals as the base, projected
forward by an assumed nominal growth rate.

Source: "Tax Credits Claimed by Hawai`i Taxpayers — Tax Year 2023"
(DOTAX, December 2025), pages 25-27 (renewable energy) and 31 (capital
goods excise).

This overlay does NOT model:
  - The new AGI eligibility limits (would further reduce demand)
  - Behavioral response to the cap (filers might shift timing or substitute)
  - Carryover dynamics (multi-year tax-credit carry-forwards)
"""
from __future__ import annotations

from typing import Dict


# DOTAX TY2023 actuals (in $ millions) — see module docstring for source.
RENEWABLE_ENERGY_CREDIT_2023_M = 99.6   # $50.7M refundable + $48.8M nonref + $0.4M carryover
CAPITAL_GOODS_EXCISE_CREDIT_2023_M = 34.6

# Bill provisions
RENEWABLE_CAP_2027_2030_M = 40.0   # Aggregate annual cap for TY 2027-2030
RENEWABLE_CAP_2031_PLUS_M = 0.0    # Credit fully zeroes out from TY 2031
CAPITAL_GOODS_SUNSET_YEAR = 2027   # Sunsets after Dec 31, 2027 (applies TY 2028+)

# Static-scoring growth assumption — applied to the DOTAX 2023 baseline
# to project forward to the target year. Hawaii nominal household income
# has averaged ~4% annual growth historically; corporate capital
# investment growth is similar. Set conservatively as a placeholder.
DEFAULT_NOMINAL_GROWTH_RATE = 0.04
BASE_YEAR = 2023


def compute_credit_overlay(
    target_year: int,
    nominal_growth_rate: float = DEFAULT_NOMINAL_GROWTH_RATE,
) -> Dict[str, float]:
    """Compute SB 3125 CD1 credit-cap fiscal impact for a target year.

    Returns positive values for revenue gains (taxes the State collects
    that it otherwise wouldn't, because the credit was capped/sunset).

    Parameters
    ----------
    target_year:
        The tax year to score, e.g. 2027.
    nominal_growth_rate:
        Annual nominal growth applied to the DOTAX TY2023 baseline.
        Default 4%/year.

    Returns
    -------
    dict with keys (all in $ millions):
        - reec_baseline_$M:     projected baseline §235-12.5 claims
        - reec_capped_$M:       projected claims after the bill's cap
        - reec_savings_$M:      revenue gain from the cap
        - cgec_baseline_$M:     projected baseline §235-110.7 claims
        - cgec_savings_$M:      revenue gain from the sunset
        - total_credit_savings_$M: sum of reec + cgec savings
    """
    if target_year < BASE_YEAR:
        raise ValueError(f"target_year must be >= {BASE_YEAR}, got {target_year}")

    years_forward = target_year - BASE_YEAR
    growth_factor = (1.0 + nominal_growth_rate) ** years_forward

    # Renewable energy credit (§235-12.5)
    reec_baseline = RENEWABLE_ENERGY_CREDIT_2023_M * growth_factor
    if 2027 <= target_year <= 2030:
        reec_capped = min(reec_baseline, RENEWABLE_CAP_2027_2030_M)
    elif target_year >= 2031:
        reec_capped = RENEWABLE_CAP_2031_PLUS_M
    else:
        # Pre-2027: bill not yet effective
        reec_capped = reec_baseline
    reec_savings = max(0.0, reec_baseline - reec_capped)

    # Capital goods excise credit (§235-110.7)
    cgec_baseline = CAPITAL_GOODS_EXCISE_CREDIT_2023_M * growth_factor
    if target_year > CAPITAL_GOODS_SUNSET_YEAR:
        cgec_savings = cgec_baseline   # full credit eliminated
    else:
        cgec_savings = 0.0

    return {
        "reec_baseline_$M":      round(reec_baseline, 2),
        "reec_capped_$M":        round(reec_capped, 2),
        "reec_savings_$M":       round(reec_savings, 2),
        "cgec_baseline_$M":      round(cgec_baseline, 2),
        "cgec_savings_$M":       round(cgec_savings, 2),
        "total_credit_savings_$M": round(reec_savings + cgec_savings, 2),
    }
