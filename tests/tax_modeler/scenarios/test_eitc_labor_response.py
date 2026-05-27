"""Tests for tax_modeler.scenarios.eitc_labor_response."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from tax_modeler.poverty.spm import _EMPLOYEE_FICA_RATE
from tax_modeler.scenarios.eitc_labor_response import (
    LFP_EXIT_PROB_COLUMN,
    LFP_LOSS_COLUMN,
    apply_hi_eitc_lfp_response,
)


def _make(rows: list[dict]) -> pd.DataFrame:
    defaults = {
        "filing_status": "head_of_household",
        "earned_income": 25_000.0,
        "eitc_amount": 4_000.0,
        "hi_eitc_amount": 1_600.0,  # 40% × $4k federal
        "federal_tax_liability": 0.0,
        "weight": 100.0,
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


def test_non_hoh_filers_unchanged():
    df = _make([
        {"filing_status": "single"},
        {"filing_status": "married_filing_jointly"},
        {"filing_status": "married_filing_separately"},
    ])
    out, _ = apply_hi_eitc_lfp_response(df)
    np.testing.assert_array_equal(out[LFP_LOSS_COLUMN].to_numpy(), np.zeros(3))
    np.testing.assert_array_equal(out[LFP_EXIT_PROB_COLUMN].to_numpy(), np.zeros(3))


def test_hoh_with_zero_earnings_unaffected():
    df = _make([{"earned_income": 0.0}])
    out, _ = apply_hi_eitc_lfp_response(df)
    assert out[LFP_LOSS_COLUMN].iloc[0] == 0.0
    assert out[LFP_EXIT_PROB_COLUMN].iloc[0] == 0.0


def test_hoh_with_zero_hi_eitc_unaffected():
    df = _make([{"hi_eitc_amount": 0.0}])
    out, _ = apply_hi_eitc_lfp_response(df)
    assert out[LFP_LOSS_COLUMN].iloc[0] == 0.0


def test_exit_prob_matches_elasticity_formula():
    df = _make([{}])
    out, diag = apply_hi_eitc_lfp_response(df, elasticity=0.5)
    expected = 0.5 * abs(math.log(1.20 / 1.40))
    assert out[LFP_EXIT_PROB_COLUMN].iloc[0] == pytest.approx(expected, rel=1e-9)
    assert diag["p_exit"] == pytest.approx(expected, rel=1e-9)


def test_resource_loss_formula_components():
    """Verify loss_if_exit = earnings + fed_eitc + 0.5*hi_eitc - FICA - fed_tax."""
    earned = 30_000.0
    fed_eitc = 5_000.0
    hi_eitc = 2_000.0
    fed_tax = 0.0
    df = _make([{
        "earned_income": earned,
        "eitc_amount": fed_eitc,
        "hi_eitc_amount": hi_eitc,
        "federal_tax_liability": fed_tax,
    }])
    out, _ = apply_hi_eitc_lfp_response(df, elasticity=0.5)
    p = 0.5 * abs(math.log(1.20 / 1.40))
    expected_loss_if_exit = (
        earned + fed_eitc + 0.5 * hi_eitc - _EMPLOYEE_FICA_RATE * earned - fed_tax
    )
    expected = p * expected_loss_if_exit
    assert out[LFP_LOSS_COLUMN].iloc[0] == pytest.approx(expected, rel=1e-9)


def test_zero_elasticity_disables_response():
    df = _make([{}])
    out, diag = apply_hi_eitc_lfp_response(df, elasticity=0.0)
    assert out[LFP_LOSS_COLUMN].iloc[0] == 0.0
    assert diag["affected_filers_weighted"] == 0.0
    assert diag["expected_lfp_exits_weighted"] == 0.0


def test_elasticity_scales_loss_linearly():
    df = _make([{}])
    out_low, _ = apply_hi_eitc_lfp_response(df, elasticity=0.3)
    out_high, _ = apply_hi_eitc_lfp_response(df, elasticity=0.6)
    # 0.6 / 0.3 = 2.0 scaling on the loss
    assert out_high[LFP_LOSS_COLUMN].iloc[0] == pytest.approx(
        2.0 * out_low[LFP_LOSS_COLUMN].iloc[0], rel=1e-9
    )


def test_inplace_modifies_input():
    df = _make([{}])
    out, _ = apply_hi_eitc_lfp_response(df, inplace=True)
    assert out is df
    assert LFP_LOSS_COLUMN in df.columns


def test_copy_default_does_not_mutate_input():
    df = _make([{}])
    df_before = df.copy()
    out, _ = apply_hi_eitc_lfp_response(df, inplace=False)
    assert out is not df
    assert LFP_LOSS_COLUMN not in df.columns
    pd.testing.assert_frame_equal(df, df_before)


def test_missing_required_column_raises():
    df = _make([{}]).drop(columns=["hi_eitc_amount"])
    with pytest.raises(KeyError, match="hi_eitc_amount"):
        apply_hi_eitc_lfp_response(df)


def test_missing_federal_tax_column_treated_as_zero():
    df = _make([{}]).drop(columns=["federal_tax_liability"])
    out, _ = apply_hi_eitc_lfp_response(df)
    # Should still produce a non-zero loss for the HoH filer
    assert out[LFP_LOSS_COLUMN].iloc[0] > 0


def test_loss_clamped_non_negative():
    """If baseline federal tax somehow exceeds earnings + credits, clamp at 0."""
    df = _make([{
        "earned_income": 1_000.0,
        "eitc_amount": 100.0,
        "hi_eitc_amount": 40.0,
        "federal_tax_liability": 100_000.0,  # absurd, but tests the clamp
    }])
    out, _ = apply_hi_eitc_lfp_response(df)
    assert out[LFP_LOSS_COLUMN].iloc[0] == 0.0


def test_diagnostics_keys():
    df = _make([{}, {"filing_status": "single"}])
    _, diag = apply_hi_eitc_lfp_response(df)
    expected_keys = {
        "elasticity", "delta_log_eitc", "p_exit",
        "affected_filers_weighted", "avg_exit_prob",
        "expected_lfp_exits_weighted",
        "aggregate_lost_earnings_$M", "aggregate_resource_loss_$M",
    }
    assert set(diag.keys()) >= expected_keys


def test_aggregate_diagnostics_match_per_filer_loss():
    """Aggregate resource loss equals weight-sum of per-filer loss."""
    df = _make([
        {"weight": 100.0},
        {"weight": 200.0, "earned_income": 15_000.0,
         "eitc_amount": 2_500.0, "hi_eitc_amount": 1_000.0},
        {"filing_status": "single"},  # unaffected
    ])
    out, diag = apply_hi_eitc_lfp_response(df)
    expected_agg_m = float(
        (out[LFP_LOSS_COLUMN].to_numpy() * df["weight"].to_numpy()).sum() / 1e6
    )
    assert diag["aggregate_resource_loss_$M"] == pytest.approx(expected_agg_m, rel=1e-9)
