"""Tests for ``tax_modeler.liability.federal.compute_federal_income_tax_for_units``."""
from __future__ import annotations

import pandas as pd
import pytest

from tax_modeler.liability.federal import compute_federal_income_tax_for_units


def _frame(rows):
    return pd.DataFrame(rows)


def test_low_income_owes_zero_federal_tax_after_sd():
    """A single filer below the federal SD owes $0 federal income tax."""
    df = _frame([{"filing_status": "single", "total_cash_income": 10_000}])
    out = compute_federal_income_tax_for_units(df, tax_year=2024)
    assert out["federal_tax_liability"].iloc[0] == pytest.approx(0.0, abs=1e-6)


def test_mfj_at_standard_deduction_owes_zero():
    """An MFJ household exactly at the SD owes $0."""
    df = _frame([{"filing_status": "married_filing_jointly",
                  "total_cash_income": 29_200}])
    out = compute_federal_income_tax_for_units(df, tax_year=2024)
    assert out["federal_tax_liability"].iloc[0] == pytest.approx(0.0, abs=1e-6)


def test_mfj_inside_10pct_bracket():
    """TY2024 MFJ at $40k income: SD=$29,200 → taxable $10,800 × 10% = $1,080."""
    df = _frame([{"filing_status": "married_filing_jointly",
                  "total_cash_income": 40_000}])
    out = compute_federal_income_tax_for_units(df, tax_year=2024)
    assert out["federal_tax_liability"].iloc[0] == pytest.approx(1_080.0, abs=1.0)


def test_single_into_12pct_bracket():
    """TY2024 single at $50k: SD=$14,600 → taxable $35,400.
    Bracket walk: $11,600 × 10% + ($35,400-$11,600) × 12% = $1,160 + $2,856 = $4,016."""
    df = _frame([{"filing_status": "single", "total_cash_income": 50_000}])
    out = compute_federal_income_tax_for_units(df, tax_year=2024)
    assert out["federal_tax_liability"].iloc[0] == pytest.approx(4_016.0, abs=1.0)


def test_nonrefundable_ctc_offsets_tax():
    """A filer with $4,000 bracket tax and $2,000 nonref CTC pays $2,000."""
    df = _frame([{
        "filing_status": "single",
        "total_cash_income": 50_000,
        "ctc_nonrefundable": 2_000.0,
    }])
    out = compute_federal_income_tax_for_units(df, tax_year=2024)
    # bracket tax = $4,016, minus $2,000 nonref CTC = $2,016
    assert out["federal_tax_liability"].iloc[0] == pytest.approx(2_016.0, abs=1.0)


def test_ctc_cannot_push_liability_below_zero():
    """Nonrefundable CTC offsets bracket tax to zero floor, not negative."""
    df = _frame([{
        "filing_status": "married_filing_jointly",
        "total_cash_income": 35_000,
        "ctc_nonrefundable": 10_000.0,
    }])
    out = compute_federal_income_tax_for_units(df, tax_year=2024)
    assert out["federal_tax_liability"].iloc[0] >= 0.0
    # bracket tax = $580; nonref CTC $10k caps liability at $0
    assert out["federal_tax_liability"].iloc[0] == pytest.approx(0.0, abs=1e-6)


def test_year_specific_brackets_2022():
    """TY2022 MFJ SD=$25,900. At $40k income: taxable $14,100 × 10% = $1,410."""
    df = _frame([{"filing_status": "married_filing_jointly",
                  "total_cash_income": 40_000}])
    out = compute_federal_income_tax_for_units(df, tax_year=2022)
    assert out["federal_tax_liability"].iloc[0] == pytest.approx(1_410.0, abs=1.0)


def test_hoh_uses_head_of_household_brackets():
    """HoH brackets differ from single — confirm $20k MFJ-equivalent uses HoH SD."""
    df = _frame([{"filing_status": "head_of_household",
                  "total_cash_income": 25_000}])
    out = compute_federal_income_tax_for_units(df, tax_year=2024)
    # HoH SD 2024 = $21,900 → taxable $3,100 × 10% = $310
    assert out["federal_tax_liability"].iloc[0] == pytest.approx(310.0, abs=1.0)


def test_unsupported_year_raises():
    df = _frame([{"filing_status": "single", "total_cash_income": 50_000}])
    with pytest.raises(KeyError):
        compute_federal_income_tax_for_units(df, tax_year=2030)
