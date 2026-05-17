"""Federal income tax liability for Hawaii tax units.

A lightweight, year-aware federal income-tax estimator. The full
federal tax code is out of scope for this Hawaii-focused package; the
estimator here is a *closer-than-flat-rate* approximation built to
remove the largest bias in the SPM resource calculation.

The bias being removed: ``poverty/spm.py`` previously used a flat 10%
effective rate × money_income as the federal tax estimate. For Hawaii
SPM-eligible (low-income) filers, the true effective rate after the
standard deduction and nonrefundable credits is typically 0%. The
flat 10% therefore subtracted $0–$2,000+ of phantom federal tax from
SPM resources at the bottom of the income distribution, biasing the
modeled Hawaii poverty rate ~4–6 pp above the Census-published rate.

What this module computes:

    taxable_income = max(0, money_income - federal_standard_deduction)
    tax_before_credits = bracket_schedule(taxable_income, filing_status)
    federal_tax_liability = max(0, tax_before_credits - ctc_nonrefundable)

Refundable credits (EITC, ACTC) are NOT subtracted here — they are
counted as positive SPM resources upstream. This keeps the formula
consistent with Census SPM accounting:

    resources = money_income + EITC + refundable_CTC + ...
              - state_tax - federal_tax_liability - payroll_tax - ...

Year-keyed parameters: standard deduction and bracket schedules for
TY 2022, 2023, 2024, 2025 sourced from IRS Rev. Procs. Inflation
indexing for the SD and bracket thresholds is statutory.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


# Federal standard deduction by tax year and filing status (IRS Rev. Procs.).
# Used as the principal driver: filers with income < SD owe $0 in federal tax
# regardless of brackets.
_STANDARD_DEDUCTION = {
    2022: {
        "single": 12_950, "married_filing_jointly": 25_900,
        "head_of_household": 19_400, "married_filing_separately": 12_950,
    },
    2023: {
        "single": 13_850, "married_filing_jointly": 27_700,
        "head_of_household": 20_800, "married_filing_separately": 13_850,
    },
    2024: {
        "single": 14_600, "married_filing_jointly": 29_200,
        "head_of_household": 21_900, "married_filing_separately": 14_600,
    },
    2025: {
        "single": 15_000, "married_filing_jointly": 30_000,
        "head_of_household": 22_500, "married_filing_separately": 15_000,
    },
}

# Federal income-tax brackets by year and filing status, as
# (upper_threshold, marginal_rate) pairs sorted ascending. The last entry
# uses np.inf to capture the top bracket.
_BRACKETS = {
    2022: {
        "single": [
            (10_275, 0.10), (41_775, 0.12), (89_075, 0.22),
            (170_050, 0.24), (215_950, 0.32), (539_900, 0.35),
            (np.inf, 0.37),
        ],
        "married_filing_jointly": [
            (20_550, 0.10), (83_550, 0.12), (178_150, 0.22),
            (340_100, 0.24), (431_900, 0.32), (647_850, 0.35),
            (np.inf, 0.37),
        ],
        "head_of_household": [
            (14_650, 0.10), (55_900, 0.12), (89_050, 0.22),
            (170_050, 0.24), (215_950, 0.32), (539_900, 0.35),
            (np.inf, 0.37),
        ],
    },
    2023: {
        "single": [
            (11_000, 0.10), (44_725, 0.12), (95_375, 0.22),
            (182_100, 0.24), (231_250, 0.32), (578_125, 0.35),
            (np.inf, 0.37),
        ],
        "married_filing_jointly": [
            (22_000, 0.10), (89_450, 0.12), (190_750, 0.22),
            (364_200, 0.24), (462_500, 0.32), (693_750, 0.35),
            (np.inf, 0.37),
        ],
        "head_of_household": [
            (15_700, 0.10), (59_850, 0.12), (95_350, 0.22),
            (182_100, 0.24), (231_250, 0.32), (578_100, 0.35),
            (np.inf, 0.37),
        ],
    },
    2024: {
        "single": [
            (11_600, 0.10), (47_150, 0.12), (100_525, 0.22),
            (191_950, 0.24), (243_725, 0.32), (609_350, 0.35),
            (np.inf, 0.37),
        ],
        "married_filing_jointly": [
            (23_200, 0.10), (94_300, 0.12), (201_050, 0.22),
            (383_900, 0.24), (487_450, 0.32), (731_200, 0.35),
            (np.inf, 0.37),
        ],
        "head_of_household": [
            (16_550, 0.10), (63_100, 0.12), (100_500, 0.22),
            (191_950, 0.24), (243_700, 0.32), (609_350, 0.35),
            (np.inf, 0.37),
        ],
    },
    2025: {
        "single": [
            (11_925, 0.10), (48_475, 0.12), (103_350, 0.22),
            (197_300, 0.24), (250_525, 0.32), (626_350, 0.35),
            (np.inf, 0.37),
        ],
        "married_filing_jointly": [
            (23_850, 0.10), (96_950, 0.12), (206_700, 0.22),
            (394_600, 0.24), (501_050, 0.32), (751_600, 0.35),
            (np.inf, 0.37),
        ],
        "head_of_household": [
            (17_000, 0.10), (64_850, 0.12), (103_350, 0.22),
            (197_300, 0.24), (250_500, 0.32), (626_350, 0.35),
            (np.inf, 0.37),
        ],
    },
}


def _tax_from_brackets(taxable: np.ndarray, brackets: list) -> np.ndarray:
    """Compute federal tax by walking through the marginal brackets."""
    tax = np.zeros_like(taxable, dtype=float)
    prev_threshold = 0.0
    for upper, rate in brackets:
        slice_lo = prev_threshold
        slice_hi = upper
        in_slice = np.clip(taxable - slice_lo, 0.0, slice_hi - slice_lo)
        tax += in_slice * rate
        prev_threshold = upper
        if np.isinf(upper):
            break
    return tax


def compute_federal_income_tax_for_units(
    units: pd.DataFrame,
    *,
    tax_year: int,
    out_col: str = "federal_tax_liability",
    income_col: str = "total_cash_income",
    filing_status_col: str = "filing_status",
    ctc_nonrefundable_col: str = "ctc_nonrefundable",
) -> pd.DataFrame:
    """Add a ``federal_tax_liability`` column to ``units``.

    Liability is computed as::

        taxable_income     = max(0, money_income - federal_standard_deduction)
        tax_before_credits = federal_brackets(taxable_income, filing_status)
        federal_tax        = max(0, tax_before_credits - ctc_nonrefundable)

    The bracket schedule (10/12/22/24/32/35/37%) and standard deductions
    follow IRS Rev. Procs. for the requested tax year. MFS is mapped to
    the single brackets / SD for filers who file separately on their own.

    Refundable credits (EITC, ACTC) are NOT subtracted here. They are
    counted as positive SPM resources upstream. ``ctc_nonrefundable`` is
    the part of CTC that can offset tax but is not paid out as a refund.
    If the column is missing, it is treated as zero (an overstatement
    of tax for filers with kids, since their CTC will be entirely
    refundable up to the bracket-implied limit). The TY-aware federal
    pipeline (``_recalculate_ctc``) populates this column.

    Parameters
    ----------
    tax_year:
        Must be one of {2022, 2023, 2024, 2025}.

    Returns
    -------
    pd.DataFrame
        Copy of ``units`` with a new ``federal_tax_liability`` column
        (non-negative annual dollars).
    """
    if tax_year not in _STANDARD_DEDUCTION:
        raise KeyError(
            f"Federal tax parameters not defined for tax year {tax_year}. "
            f"Supported years: {sorted(_STANDARD_DEDUCTION)}"
        )
    sd_by_status = _STANDARD_DEDUCTION[tax_year]
    brackets_by_status = _BRACKETS[tax_year]

    out = units.copy()
    income = out[income_col].fillna(0).astype(float).to_numpy()
    status = out[filing_status_col].astype(str).to_numpy()

    # Per-row standard deduction lookup.
    sd = np.array(
        [sd_by_status.get(s, sd_by_status["single"]) for s in status],
        dtype=float,
    )
    taxable = np.maximum(income - sd, 0.0)

    # Per-row bracket lookup. MFS maps to single brackets (the IRS publishes
    # MFS thresholds as half of MFJ; the difference vs. single is small at
    # SPM-relevant incomes and either is closer than the previous 10% flat
    # fallback).
    tax = np.zeros(len(out), dtype=float)
    for s in np.unique(status):
        key = s if s in brackets_by_status else "single"
        mask = status == s
        if not mask.any():
            continue
        tax[mask] = _tax_from_brackets(taxable[mask], brackets_by_status[key])

    # Nonrefundable CTC offsets bracket tax, but cannot push it below zero.
    if ctc_nonrefundable_col in out.columns:
        ctc_nonref = out[ctc_nonrefundable_col].fillna(0).astype(float).to_numpy()
        tax = np.maximum(tax - ctc_nonref, 0.0)

    out[out_col] = tax
    return out


__all__ = ["compute_federal_income_tax_for_units"]
