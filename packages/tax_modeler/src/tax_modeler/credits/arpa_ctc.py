"""
ARPA 2021 Expanded Child Tax Credit

American Rescue Plan Act of 2021 (ARPA):
- Increased CTC to $3,600/child under 6, $3,000/child 6-17
- Made fully refundable (no earned-income floor)
- Advance monthly payments July-Dec 2021

For poverty-impact analysis: use as a counterfactual / reference scenario.
Take-up: 82% (Treasury monthly CTC data for Hawaii, 2021).
Source: US Treasury, 'Monthly Advance Child Tax Credit Payments by State', 2021.

Income phaseout:
  - First phaseout: $3,600/$3,000 -> $2,000 per child
    Threshold: $75,000 (single/HOH), $150,000 (MFJ)
    Rate: 5% of income above threshold ($50 per $1,000)
  - Second phaseout: $2,000/child
    Threshold: $200,000 (single/HOH), $400,000 (MFJ)
    Rate: 5% of income above threshold

Note: The ARPA CTC was enacted for tax year 2021 only; it was not extended.
"""

from __future__ import annotations

from typing import Dict, List

# ---------------------------------------------------------------------------
# ARPA CTC parameters (TY 2021)
# ---------------------------------------------------------------------------

ARPA_CTC_UNDER_6: int = 3_600       # Per qualifying child under age 6
ARPA_CTC_6_TO_17: int = 3_000       # Per qualifying child age 6-17

# First phaseout (reduces enhanced amounts to $2,000/child)
_PHASEOUT1_SINGLE: int = 75_000
_PHASEOUT1_JOINT: int = 150_000
_PHASEOUT1_RATE: float = 0.05       # 5% = $50 per $1,000

# Second phaseout (reduces from $2,000/child to $0)
_PHASEOUT2_SINGLE: int = 200_000
_PHASEOUT2_JOINT: int = 400_000
_PHASEOUT2_RATE: float = 0.05       # 5% = $50 per $1,000

_BASE_CTC_PER_CHILD: int = 2_000    # Pre-ARPA base credit

# Qualifying age for ARPA CTC: under 18 (i.e., age <= 17)
_QUALIFYING_AGE_LIMIT: int = 18

# Qualifying relationship codes (PUMS RELSHIPP / relationship codes)
_QUALIFYING_RELATIONSHIPS = {22, 23, 24, 25, 26, 35}  # child, stepchild, grandchild, sibling, foster


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------


def calculate_arpa_ctc(tax_unit: Dict) -> Dict[str, float]:
    """
    Calculate ARPA 2021 Expanded Child Tax Credit for a single tax unit.

    The ARPA CTC is fully refundable (no earned-income floor for refundability).

    Args:
        tax_unit: Dictionary with keys:
            - filing_status: str  ('single', 'married_filing_jointly',
                                   'head_of_household', etc.)
            - income: float  (MAGI)
            - dependents: list of dicts with keys 'age', 'relationship',
                          'citizenship' (optional)
            - dependents_details: alias for 'dependents' (optional)

    Returns:
        Dictionary with:
            - arpa_ctc_total: float        (total credit after phaseout)
            - arpa_ctc_refundable: float   (= arpa_ctc_total; fully refundable)
            - qualifying_children: int     (number of qualifying children)
            - arpa_ctc_under_6: int        (qualifying children under 6)
            - arpa_ctc_6_to_17: int        (qualifying children age 6-17)
    """
    result: Dict[str, float] = {
        "arpa_ctc_total": 0.0,
        "arpa_ctc_refundable": 0.0,
        "qualifying_children": 0,
        "arpa_ctc_under_6": 0,
        "arpa_ctc_6_to_17": 0,
    }

    # Resolve dependents list (support both 'dependents' and 'dependents_details')
    dependents: List[Dict] = tax_unit.get("dependents") or tax_unit.get("dependents_details") or []

    # Count qualifying children by age group
    under_6 = 0
    age_6_to_17 = 0
    for dep in dependents:
        if not _is_qualifying_child_arpa(dep):
            continue
        age = int(dep.get("age", 0))
        if age < 6:
            under_6 += 1
        else:
            age_6_to_17 += 1

    total_children = under_6 + age_6_to_17
    if total_children == 0:
        return result

    result["qualifying_children"] = total_children
    result["arpa_ctc_under_6"] = under_6
    result["arpa_ctc_6_to_17"] = age_6_to_17

    # Compute enhanced ARPA credit (before phaseout)
    enhanced_credit = (under_6 * ARPA_CTC_UNDER_6) + (age_6_to_17 * ARPA_CTC_6_TO_17)

    filing_status = str(tax_unit.get("filing_status", "single")).lower()
    income = float(tax_unit.get("income", 0) or 0)
    is_joint = "joint" in filing_status

    # --- First phaseout: enhanced amounts reduced toward $2,000/child ---
    po1_threshold = _PHASEOUT1_JOINT if is_joint else _PHASEOUT1_SINGLE
    base_credit = total_children * _BASE_CTC_PER_CHILD  # floor for first phaseout

    if income > po1_threshold:
        excess = income - po1_threshold
        # $50 per $1,000 (or fraction thereof) over threshold
        import math
        phaseout1_reduction = math.ceil(excess / 1_000) * 50
        # Can only reduce down to the $2,000/child base
        credit_after_po1 = max(base_credit, enhanced_credit - phaseout1_reduction)
    else:
        credit_after_po1 = enhanced_credit

    # --- Second phaseout: $2,000/child reduced toward $0 ---
    po2_threshold = _PHASEOUT2_JOINT if is_joint else _PHASEOUT2_SINGLE

    if income > po2_threshold:
        excess2 = income - po2_threshold
        import math
        phaseout2_reduction = math.ceil(excess2 / 1_000) * 50
        credit_final = max(0.0, credit_after_po1 - phaseout2_reduction)
    else:
        credit_final = credit_after_po1

    # ARPA CTC is fully refundable
    result["arpa_ctc_total"] = round(credit_final, 2)
    result["arpa_ctc_refundable"] = round(credit_final, 2)

    return result


def _is_qualifying_child_arpa(dep: Dict) -> bool:
    """Return True if the dependent qualifies for ARPA CTC."""
    age = int(dep.get("age", 0))
    if age >= _QUALIFYING_AGE_LIMIT:
        return False

    relationship = dep.get("relationship", 0)
    try:
        rel_int = int(relationship)
    except (ValueError, TypeError):
        rel_int = 0
    if rel_int not in _QUALIFYING_RELATIONSHIPS:
        return False

    # Citizenship test (CIT 1-4 = US person; 5 = not citizen)
    citizenship = dep.get("citizenship", 1)
    try:
        cit = int(citizenship)
    except (ValueError, TypeError):
        cit = 1
    if cit > 4:
        return False

    return True
