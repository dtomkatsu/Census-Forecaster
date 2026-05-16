"""Federal income tax liability (pre-credit) for SPM resource accounting.

The package is Hawaii-focused and historically has not computed federal
income tax. For SPM-poverty work that's a problem: the Supplemental
Poverty Measure subtracts net federal income tax (post-credit) from
resources, and the existing fallback inside
:func:`tax_modeler.poverty.spm.compute_spm_resources` is a flat
``10% × max(money_income, 0)`` proxy. That's too high at the bottom of
the distribution (where refundable credits + standard deduction usually
zero out liability) and too low at the top. The flat rate inflates
baseline poverty by depressing low-income SPM resources.

This module ships a graduated bracket calculator keyed off federal AGI
and filing status, mirroring the IRS Form 1040 calculation through the
standard-deduction step. It produces a *pre-credit* liability column —
``federal_tax_liability`` — that ``compute_spm_resources`` consumes in
the standard SPM accounting:

    resources = money_income
                + (refundable credits: EITC, ACTC, …)
                - federal_tax_liability_pre_credit
                - state_tax - payroll_tax
                - MOOP - childcare_expense - work_expense

Refundable credits (EITC, refundable CTC) are added back separately by
the SPM formula, so the federal liability column is left at its
pre-credit value to avoid double-counting.

Bracket vintage is year-keyed for TY 2022-2025 (Rev. Proc. inflation
adjustments). Itemized deductions are out of scope (rare for
low-to-mid-income filers where SPM accuracy matters most) — the standard
deduction is used unconditionally.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FederalBrackets:
    """Federal income-tax bracket schedule + standard deduction by status."""

    year: int
    # Brackets as list of (upper_bound, marginal_rate). The final
    # entry uses np.inf as upper_bound and carries the top marginal rate.
    single: tuple[tuple[float, float], ...]
    married_filing_jointly: tuple[tuple[float, float], ...]
    head_of_household: tuple[tuple[float, float], ...]
    standard_deduction: Mapping[str, float]


# IRS Rev. Proc. 2021-45 (TY2022), 2022-38 (TY2023), 2023-34 (TY2024),
# 2024-40 (TY2025). Brackets reflect post-inflation-adjustment values.
_FED_BRACKETS_2024 = FederalBrackets(
    year=2024,
    single=(
        (11_600.0, 0.10), (47_150.0, 0.12), (100_525.0, 0.22),
        (191_950.0, 0.24), (243_725.0, 0.32), (609_350.0, 0.35),
        (float("inf"), 0.37),
    ),
    married_filing_jointly=(
        (23_200.0, 0.10), (94_300.0, 0.12), (201_050.0, 0.22),
        (383_900.0, 0.24), (487_450.0, 0.32), (731_200.0, 0.35),
        (float("inf"), 0.37),
    ),
    head_of_household=(
        (16_550.0, 0.10), (63_100.0, 0.12), (100_500.0, 0.22),
        (191_950.0, 0.24), (243_700.0, 0.32), (609_350.0, 0.35),
        (float("inf"), 0.37),
    ),
    standard_deduction={
        "single": 14_600.0,
        "married_filing_jointly": 29_200.0,
        "head_of_household": 21_900.0,
        "married_filing_separately": 14_600.0,
        "qualifying_widow": 29_200.0,
    },
)
_FED_BRACKETS_2025 = FederalBrackets(
    year=2025,
    single=(
        (11_925.0, 0.10), (48_475.0, 0.12), (103_350.0, 0.22),
        (197_300.0, 0.24), (250_525.0, 0.32), (626_350.0, 0.35),
        (float("inf"), 0.37),
    ),
    married_filing_jointly=(
        (23_850.0, 0.10), (96_950.0, 0.12), (206_700.0, 0.22),
        (394_600.0, 0.24), (501_050.0, 0.32), (751_600.0, 0.35),
        (float("inf"), 0.37),
    ),
    head_of_household=(
        (17_000.0, 0.10), (64_850.0, 0.12), (103_350.0, 0.22),
        (197_300.0, 0.24), (250_500.0, 0.32), (626_350.0, 0.35),
        (float("inf"), 0.37),
    ),
    standard_deduction={
        "single": 15_000.0,
        "married_filing_jointly": 30_000.0,
        "head_of_household": 22_500.0,
        "married_filing_separately": 15_000.0,
        "qualifying_widow": 30_000.0,
    },
)
_FED_BRACKETS_2023 = FederalBrackets(
    year=2023,
    single=(
        (11_000.0, 0.10), (44_725.0, 0.12), (95_375.0, 0.22),
        (182_100.0, 0.24), (231_250.0, 0.32), (578_125.0, 0.35),
        (float("inf"), 0.37),
    ),
    married_filing_jointly=(
        (22_000.0, 0.10), (89_450.0, 0.12), (190_750.0, 0.22),
        (364_200.0, 0.24), (462_500.0, 0.32), (693_750.0, 0.35),
        (float("inf"), 0.37),
    ),
    head_of_household=(
        (15_700.0, 0.10), (59_850.0, 0.12), (95_350.0, 0.22),
        (182_100.0, 0.24), (231_250.0, 0.32), (578_100.0, 0.35),
        (float("inf"), 0.37),
    ),
    standard_deduction={
        "single": 13_850.0,
        "married_filing_jointly": 27_700.0,
        "head_of_household": 20_800.0,
        "married_filing_separately": 13_850.0,
        "qualifying_widow": 27_700.0,
    },
)
_FED_BRACKETS_2022 = FederalBrackets(
    year=2022,
    single=(
        (10_275.0, 0.10), (41_775.0, 0.12), (89_075.0, 0.22),
        (170_050.0, 0.24), (215_950.0, 0.32), (539_900.0, 0.35),
        (float("inf"), 0.37),
    ),
    married_filing_jointly=(
        (20_550.0, 0.10), (83_550.0, 0.12), (178_150.0, 0.22),
        (340_100.0, 0.24), (431_900.0, 0.32), (647_850.0, 0.35),
        (float("inf"), 0.37),
    ),
    head_of_household=(
        (14_650.0, 0.10), (55_900.0, 0.12), (89_050.0, 0.22),
        (170_050.0, 0.24), (215_950.0, 0.32), (539_900.0, 0.35),
        (float("inf"), 0.37),
    ),
    standard_deduction={
        "single": 12_950.0,
        "married_filing_jointly": 25_900.0,
        "head_of_household": 19_400.0,
        "married_filing_separately": 12_950.0,
        "qualifying_widow": 25_900.0,
    },
)
_BRACKETS_BY_YEAR: dict[int, FederalBrackets] = {
    2022: _FED_BRACKETS_2022,
    2023: _FED_BRACKETS_2023,
    2024: _FED_BRACKETS_2024,
    2025: _FED_BRACKETS_2025,
}


def _tax_on_taxable_income(
    taxable_income: np.ndarray, schedule: tuple[tuple[float, float], ...]
) -> np.ndarray:
    """Vectorized progressive-bracket tax calculation."""
    tax = np.zeros_like(taxable_income, dtype=float)
    prev_cap = 0.0
    for upper, rate in schedule:
        slab = np.clip(taxable_income, prev_cap, upper) - prev_cap
        tax = tax + np.maximum(slab, 0.0) * rate
        prev_cap = upper
        if not np.isfinite(upper):
            break
    return tax


def compute_federal_income_tax_for_units(
    units: pd.DataFrame,
    *,
    tax_year: int = 2024,
    agi_col: str = "income",
    filing_status_col: str = "filing_status",
    out_col: str = "federal_tax_liability",
) -> pd.DataFrame:
    """Add a pre-credit federal income tax liability column.

    Computation:
      taxable_income = max(0, AGI - standard_deduction[filing_status])
      federal_tax    = sum_brackets(taxable_income)

    Itemized deductions are NOT applied — for low-to-mid-income units
    (where SPM accuracy matters most) the standard deduction dominates.
    Above-the-line adjustments are likewise ignored; ``agi_col`` is used
    directly as AGI proxy. Refundable credits (EITC, refundable CTC) are
    added back separately by the SPM resource formula.

    Parameters
    ----------
    units:
        Tax-unit DataFrame. Must contain ``agi_col`` and ``filing_status_col``.
    tax_year:
        2022, 2023, 2024, or 2025. Year selects bracket vintage + std ded.
    agi_col:
        Column to treat as federal AGI. Default ``"income"`` is consistent
        with how :mod:`tax_modeler.liability.hawaii` uses it.
    filing_status_col:
        Column carrying ``"single"`` / ``"married_filing_jointly"`` /
        ``"head_of_household"`` / etc.
    out_col:
        Name for the output column. Default ``"federal_tax_liability"``.

    Returns
    -------
    pd.DataFrame
        Copy of ``units`` with the ``out_col`` added.
    """
    if tax_year not in _BRACKETS_BY_YEAR:
        # Fall back to closest available year; document loudly.
        nearest = min(_BRACKETS_BY_YEAR.keys(), key=lambda y: abs(y - tax_year))
        brackets = _BRACKETS_BY_YEAR[nearest]
    else:
        brackets = _BRACKETS_BY_YEAR[tax_year]

    df = units.copy()
    if agi_col not in df.columns:
        df[out_col] = 0.0
        return df

    agi = df[agi_col].fillna(0.0).to_numpy(dtype=float)
    statuses = df[filing_status_col].fillna("single").astype(str).to_numpy()

    # Build per-row standard deduction vector.
    std_ded = np.array([
        brackets.standard_deduction.get(s, brackets.standard_deduction["single"])
        for s in statuses
    ])
    taxable = np.maximum(agi - std_ded, 0.0)

    # Vectorized status partitioning — apply each schedule to its slice.
    tax = np.zeros_like(taxable, dtype=float)
    mfj_mask = statuses == "married_filing_jointly"
    hoh_mask = statuses == "head_of_household"
    single_mask = ~(mfj_mask | hoh_mask)

    if mfj_mask.any():
        tax[mfj_mask] = _tax_on_taxable_income(
            taxable[mfj_mask], brackets.married_filing_jointly
        )
    if hoh_mask.any():
        tax[hoh_mask] = _tax_on_taxable_income(
            taxable[hoh_mask], brackets.head_of_household
        )
    if single_mask.any():
        tax[single_mask] = _tax_on_taxable_income(
            taxable[single_mask], brackets.single
        )

    df[out_col] = tax
    return df


__all__ = [
    "FederalBrackets",
    "compute_federal_income_tax_for_units",
]
