"""
Hawaii State Earned Income Tax Credit (HI EITC)

Act 209 (2017) / HRS § 235-55.85
Hawaii's state EITC equals a fixed percentage of the federal EITC.
Current law: 40% of federal EITC (Act 209 rate, effective TY 2018).

The rate is a policy parameter (law) — do NOT replace with an empirical value.

Source: Hawaii Revised Statutes § 235-55.85; Act 209, Session Laws of Hawaii 2017.
"""

from __future__ import annotations

from typing import Dict

# ---------------------------------------------------------------------------
# Policy parameter
# ---------------------------------------------------------------------------

HI_EITC_RATE: float = 0.40
"""Act 209: 40% of federal EITC. Policy parameter — NOT a placeholder."""


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------


def calculate_hi_eitc(
    tax_unit: Dict,
    federal_eitc_amount: float = 0.0,
) -> Dict[str, float]:
    """
    Calculate Hawaii state EITC for a single tax unit.

    The HI EITC is simply HI_EITC_RATE (40%) of the federal EITC amount.
    Eligibility mirrors federal EITC eligibility.

    Args:
        tax_unit: Dictionary representing one tax filing unit. Relevant keys:
            - eitc_amount: float  (federal EITC already computed; takes priority
                                   over the federal_eitc_amount parameter)
            - eitc_eligible: bool (federal EITC eligibility flag)
        federal_eitc_amount: float
            Fallback federal EITC amount if 'eitc_amount' is not in tax_unit.

    Returns:
        Dictionary with:
            - hi_eitc_amount: float  (Hawaii EITC credit amount, ≥ 0)
            - hi_eitc_eligible: bool  (True if eligible for HI EITC)
    """
    result: Dict[str, float] = {
        "hi_eitc_amount": 0.0,
        "hi_eitc_eligible": False,
    }

    # Determine federal EITC amount
    fed_eitc = float(tax_unit.get("eitc_amount", federal_eitc_amount) or 0.0)

    # Eligibility: must have positive federal EITC (HI EITC piggybacks federal)
    fed_eligible = bool(tax_unit.get("eitc_eligible", fed_eitc > 0))

    if not fed_eligible or fed_eitc <= 0:
        return result

    hi_eitc = round(fed_eitc * HI_EITC_RATE, 2)

    result["hi_eitc_amount"] = hi_eitc
    result["hi_eitc_eligible"] = True

    return result
