"""
Child Tax Credit (CTC) Calculation Module

Implements the federal Child Tax Credit with year-specific statutory
parameters. The CTC provides up to $2,000 per qualifying child under
the Tax Cuts and Jobs Act (TCJA), with a refundable portion (ACTC) that
the IRS indexes for inflation per year.

Supported tax years: 2022, 2023, 2024, 2025.

Sources (IRS Revenue Procedures):
- TY 2022: IRS Rev. Proc. 2021-45  → refundable cap $1,500/child
- TY 2023: IRS Rev. Proc. 2022-38  → refundable cap $1,600/child
- TY 2024: IRS Rev. Proc. 2023-34  → refundable cap $1,700/child
- TY 2025: IRS Rev. Proc. 2024-40  → refundable cap $1,700/child

Phaseout thresholds ($200K single / $400K joint) and max $2,000/child
are statutory TCJA values that do not move with inflation through 2025.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass


@dataclass
class CTCParameters:
    """Parameters for CTC calculation.

    Defaults reflect TY 2023 to preserve historical call sites. Use
    ``ctc_parameters_for_year(year)`` to build a year-specific instance.
    """
    max_credit_per_child: int = 2000
    refundable_limit_per_child: int = 1600  # Additional Child Tax Credit (ACTC), TY 2023
    phaseout_threshold_single: int = 200000
    phaseout_threshold_joint: int = 400000
    phaseout_rate: float = 0.05  # $50 per $1,000 over threshold
    qualifying_age_limit: int = 17  # Must be under 17
    earned_income_threshold: int = 2500  # ACTC earned-income threshold (TCJA, IRC §24(d))
    actc_earned_income_rate: float = 0.15  # ACTC = 15% of earned income above threshold


# Refundable per-child cap (Additional CTC) is inflation-indexed under TCJA.
_CTC_REFUNDABLE_LIMIT_BY_YEAR = {
    2022: 1_500,  # IRS Rev. Proc. 2021-45
    2023: 1_600,  # IRS Rev. Proc. 2022-38
    2024: 1_700,  # IRS Rev. Proc. 2023-34
    2025: 1_700,  # IRS Rev. Proc. 2024-40
}


def ctc_parameters_for_year(tax_year: int, *, extrapolate: bool = False) -> CTCParameters:
    """Return CTC parameters for the requested tax year.

    With ``extrapolate=True``, years beyond the last published Rev. Proc. get
    a CPI-extrapolated ACTC refundable cap (chained CPI per IRC §24(d)(4),
    floored to the next-lowest $100 per §24(d)(4)(B)). The $2,000 max credit
    and $200K/$400K phaseout thresholds are NOT indexed under TCJA and stay
    fixed.

    Raises ``KeyError`` for unsupported years when not extrapolating.
    """
    if tax_year in _CTC_REFUNDABLE_LIMIT_BY_YEAR:
        return CTCParameters(
            refundable_limit_per_child=_CTC_REFUNDABLE_LIMIT_BY_YEAR[tax_year],
        )
    if extrapolate and tax_year > max(_CTC_REFUNDABLE_LIMIT_BY_YEAR):
        from tax_modeler.credits.eitc import CREDIT_PARAM_CPI_GROWTH

        base_year = max(_CTC_REFUNDABLE_LIMIT_BY_YEAR)
        base_cap = _CTC_REFUNDABLE_LIMIT_BY_YEAR[base_year]
        factor = (1.0 + CREDIT_PARAM_CPI_GROWTH) ** (tax_year - base_year)
        # §24(d)(4)(B): round DOWN to the nearest multiple of $100. Cap at the
        # statutory $2,000 max — the refundable portion cannot exceed it.
        cap = min(int(base_cap * factor // 100) * 100, 2_000)
        return CTCParameters(refundable_limit_per_child=cap)
    raise KeyError(
        f"CTC parameters not defined for tax year {tax_year}. "
        f"Supported years: {sorted(_CTC_REFUNDABLE_LIMIT_BY_YEAR)}"
        + ("" if extrapolate else " (pass extrapolate=True for later years)")
    )


def calculate_ctc(
    tax_unit: Dict,
    tax_year: int = 2023,
    *,
    extrapolate: bool = False,
) -> Dict[str, float]:
    """
    Calculate Child Tax Credit for a tax unit.

    Args:
        tax_unit: Dictionary containing tax unit information with keys:
            - filing_status: str ('single', 'married_filing_jointly', etc.)
            - income: float (Modified Adjusted Gross Income)
            - dependents: List of dependent dictionaries
            - num_dependents: int
        tax_year: Tax year for calculation (default 2023)
        extrapolate: CPI-extrapolate the ACTC cap for years beyond the last
            published Rev. Proc. instead of raising KeyError.

    Returns:
        Dictionary with:
            - ctc_total: Total CTC amount
            - ctc_nonrefundable: Non-refundable portion
            - ctc_refundable: Refundable portion (ACTC)
            - qualifying_children: Number of qualifying children
    """
    params = ctc_parameters_for_year(tax_year, extrapolate=extrapolate)

    # Initialize result
    result = {
        'ctc_total': 0.0,
        'ctc_nonrefundable': 0.0,
        'ctc_refundable': 0.0,
        'qualifying_children': 0
    }

    # Get qualifying children
    qualifying_children = _get_qualifying_children(tax_unit.get('dependents', []), params)
    result['qualifying_children'] = len(qualifying_children)

    if len(qualifying_children) == 0:
        return result

    # Calculate base credit amount
    base_credit = len(qualifying_children) * params.max_credit_per_child

    # Apply income phaseout
    filing_status = tax_unit.get('filing_status', 'single')
    income = tax_unit.get('income', 0)

    phased_out_credit = _apply_income_phaseout(
        base_credit, income, filing_status, params
    )

    # Calculate Additional Child Tax Credit (ACTC) - refundable portion
    earned_income = tax_unit.get('earned_income', tax_unit.get('income', 0))  # Fallback to total income if earned_income not available

    # ACTC is 15% of earned income above the EI threshold, up to refundable cap per child
    actc_per_child = min(
        max(0, earned_income - params.earned_income_threshold) * params.actc_earned_income_rate,
        params.refundable_limit_per_child
    )

    # Total potential ACTC is per-child amount * number of children
    max_actc = len(qualifying_children) * actc_per_child

    # The refundable portion is the lesser of:
    # 1. The total credit amount after phaseout
    # 2. The ACTC amount (15% of earned income above threshold, up to refundable cap/child)
    # 3. The refundable limit cap × number of children
    refundable_portion = min(
        phased_out_credit,
        max_actc,
        len(qualifying_children) * params.refundable_limit_per_child
    )

    # Non-refundable portion is the remaining credit
    nonrefundable_portion = max(0, phased_out_credit - refundable_portion)

    result.update({
        'ctc_total': phased_out_credit,
        'ctc_nonrefundable': nonrefundable_portion,
        'ctc_refundable': refundable_portion
    })

    return result


def _get_qualifying_children(dependents: List[Dict], params: CTCParameters) -> List[Dict]:
    """
    Identify qualifying children for CTC purposes.

    Args:
        dependents: List of dependent dictionaries
        params: CTC parameters

    Returns:
        List of qualifying children
    """
    qualifying = []

    for dependent in dependents:
        if _is_qualifying_child_ctc(dependent, params):
            qualifying.append(dependent)

    return qualifying


def _is_qualifying_child_ctc(dependent: Dict, params: CTCParameters) -> bool:
    """
    Check if a dependent qualifies for CTC.

    Args:
        dependent: Dependent information dictionary
        params: CTC parameters

    Returns:
        True if dependent qualifies for CTC
    """
    # Age test: Must be under 17 at end of tax year
    age = dependent.get('age', 0)
    if age >= params.qualifying_age_limit:
        return False

    # Relationship test: Must be a qualifying child relationship
    # For PUMS data, we'll use the relationship codes
    relationship = dependent.get('relationship', '')
    if not _is_qualifying_relationship(relationship):
        return False

    # SSN test: Must have valid SSN (simplified - assume all dependents have SSN)
    # In real implementation, would check SSN validity

    # Support test: Child must not provide more than half of own support
    # For PUMS data, we'll assume children under 17 don't provide own support

    # Citizenship test: Must be US citizen/national/resident alien
    # For PUMS data, we'll use citizenship status if available
    citizenship = dependent.get('citizenship', 'US')  # Default to US citizen
    if not _is_us_person(citizenship):
        return False

    return True


def _is_qualifying_relationship(relationship: str) -> bool:
    """
    Check if relationship qualifies for CTC.

    Args:
        relationship: PUMS relationship code or description

    Returns:
        True if relationship qualifies
    """
    # PUMS relationship codes that qualify:
    # 22 = Natural born child
    # 23 = Adopted child
    # 24 = Stepchild
    # 25 = Grandchild
    # 26 = Brother or sister
    # 27 = Father or mother
    # 28 = Grandparent
    # 29 = Parent-in-law
    # 30 = Son-in-law or daughter-in-law
    # 31 = Other relative
    # 32 = Roomer or boarder
    # 33 = Housemate or roommate
    # 34 = Unmarried partner
    # 35 = Foster child
    # 36 = Other nonrelative

    qualifying_codes = ['22', '23', '24', '25', '26', '35']  # Child, stepchild, grandchild, sibling, foster child

    # Handle both string and numeric relationship codes
    rel_str = str(relationship)
    return rel_str in qualifying_codes


def _is_us_person(citizenship: str) -> bool:
    """
    Check if person is US citizen, national, or resident alien.

    Args:
        citizenship: Citizenship status

    Returns:
        True if person qualifies as US person
    """
    # PUMS citizenship codes:
    # 1 = Born in the US
    # 2 = Born in Puerto Rico, Guam, the U.S. Virgin Islands, or the Northern Marianas
    # 3 = Born abroad of American parent(s)
    # 4 = U.S. citizen by naturalization
    # 5 = Not a citizen of the U.S.

    us_citizen_codes = ['1', '2', '3', '4', 'US']
    return str(citizenship) in us_citizen_codes


def _apply_income_phaseout(
    base_credit: float,
    income: float,
    filing_status: str,
    params: CTCParameters
) -> float:
    """
    Apply income-based phaseout to CTC.

    Args:
        base_credit: Base credit amount before phaseout
        income: Modified Adjusted Gross Income
        filing_status: Filing status
        params: CTC parameters

    Returns:
        Credit amount after phaseout
    """
    # Determine phaseout threshold based on filing status
    if filing_status in ['married_filing_jointly']:
        threshold = params.phaseout_threshold_joint
    else:
        threshold = params.phaseout_threshold_single

    # No phaseout if income is below threshold
    if income <= threshold:
        return base_credit

    # Calculate phaseout amount
    excess_income = income - threshold
    # Phaseout is $50 for every $1,000 (or fraction thereof) over threshold
    phaseout_amount = np.ceil(excess_income / 1000) * 50

    # Apply phaseout
    phased_out_credit = max(0, base_credit - phaseout_amount)

    return phased_out_credit


def calculate_ctc_for_tax_units(
    tax_units_df: pd.DataFrame,
    tax_year: int = 2023,
) -> pd.DataFrame:
    """
    Calculate CTC for all tax units in a DataFrame.

    Args:
        tax_units_df: DataFrame containing tax unit information
        tax_year: Tax year for parameter selection (default 2023).

    Returns:
        DataFrame with CTC calculations added (prefixed ``ctc_``).
    """
    results = []

    for _, tax_unit in tax_units_df.iterrows():
        tax_unit_dict = tax_unit.to_dict()
        ctc_result = calculate_ctc(tax_unit_dict, tax_year=tax_year)
        for key, value in ctc_result.items():
            tax_unit_dict[f'ctc_{key}'] = value
        results.append(tax_unit_dict)

    return pd.DataFrame(results)


def get_ctc_summary_stats(tax_units_df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate summary statistics for CTC across tax units.

    Args:
        tax_units_df: DataFrame with CTC calculations

    Returns:
        Dictionary with summary statistics
    """
    # Calculate CTC for all units if not already done
    if 'ctc_ctc_total' not in tax_units_df.columns:
        tax_units_df = calculate_ctc_for_tax_units(tax_units_df)

    stats = {
        'total_tax_units': len(tax_units_df),
        'units_with_ctc': len(tax_units_df[tax_units_df['ctc_ctc_total'] > 0]),
        'total_ctc_amount': tax_units_df['ctc_ctc_total'].sum(),
        'average_ctc_per_unit': tax_units_df['ctc_ctc_total'].mean(),
        'average_ctc_per_recipient': tax_units_df[tax_units_df['ctc_ctc_total'] > 0]['ctc_ctc_total'].mean(),
        'total_qualifying_children': tax_units_df['ctc_qualifying_children'].sum(),
        'total_refundable_ctc': tax_units_df['ctc_ctc_refundable'].sum(),
        'total_nonrefundable_ctc': tax_units_df['ctc_ctc_nonrefundable'].sum()
    }

    return stats
