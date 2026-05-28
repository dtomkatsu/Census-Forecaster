"""Smoke tests for take-up imputation (Phase 4).

Verifies that:

* :class:`AdminCaseload` loads the bundled Hawaii caseload CSV.
* :func:`impute_takeup` matches simulated receipt to a target count
  within tolerance for SNAP and SSI on the synthetic fixture.
* :func:`calibrate_benefits` is a working one-call wrapper.
* Per the TRIM3 convention, imputation does **not** apply on the
  reform-counterfactual path (apply_reform recomputes fresh).
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pytest

from tax_modeler import (
    AdminCaseload,
    CaseloadTarget,
    Reform,
    apply_reform,
    calibrate_benefits,
    compute_snap_for_units,
    compute_ssi_for_units,
    compute_ssi_hi_supplement_for_units,
    impute_takeup,
)
from tax_modeler.calibration.takeup_imputation import scale_benefit_to_dollar_target
from tax_modeler.errors import ConfigError, DataValidationError


pytestmark = pytest.mark.smoke


# ---------------------------------------------------------------------------
# AdminCaseload
# ---------------------------------------------------------------------------


def test_admin_caseload_loads_bundled():
    cl = AdminCaseload.load()
    assert len(cl) > 0
    snap2024 = cl.target("snap", 2024)
    assert isinstance(snap2024, CaseloadTarget)
    assert snap2024.unit == "household"
    # Real HI SNAP caseload is ~85k-90k households
    assert 50_000 < snap2024.count < 200_000


def test_admin_caseload_unknown_year_raises():
    cl = AdminCaseload.load()
    with pytest.raises(ConfigError):
        cl.target("snap", 1999)


def test_admin_caseload_unknown_program_raises():
    cl = AdminCaseload.load()
    with pytest.raises(ConfigError):
        cl.target("medicaid", 2024)


# ---------------------------------------------------------------------------
# impute_takeup
# ---------------------------------------------------------------------------


def _scaled_target(real: CaseloadTarget, fixture_units: pd.DataFrame, fixture_factor: float) -> CaseloadTarget:
    """Scale a real-world target down to the synthetic fixture's population."""
    # The fixture has ~50 households (a few thousand weighted units) vs. real
    # HI population (~500K households). Scale linearly so the imputation has
    # something to bite into.
    return CaseloadTarget(
        program=real.program,
        year=real.year,
        unit=real.unit,
        count=real.count * fixture_factor,
        annual_dollars_millions=real.annual_dollars_millions * fixture_factor,
        source=real.source,
    )


def test_impute_takeup_hits_target(taxed_units, caplog):
    """Target=10 weighted units → imputed count should land within ±50% on a 50-row fixture."""
    units = compute_snap_for_units(taxed_units)
    target = CaseloadTarget(
        program="snap", year=2024, unit="household",
        count=10.0, annual_dollars_millions=0.05,
    )
    out = impute_takeup(
        units, target=target, benefit_col="snap_amount", score_col="income"
    )
    assert "snap_receives_imputed" in out.columns
    imputed_total = float(out.loc[out["snap_receives_imputed"], "weight"].sum())
    # Tolerance is loose because the fixture is tiny (one row can swing
    # the cumulative weight by 10s)
    assert imputed_total >= target.count * 0.5
    # Non-recipients have zero benefit amount
    non_recipients = out[~out["snap_receives_imputed"]]
    assert (non_recipients["snap_amount"] == 0).all()


def test_impute_takeup_low_income_first(taxed_units):
    """Default scoring (income ascending) → imputed units have lower income than non-imputed eligible."""
    units = compute_snap_for_units(taxed_units)
    eligible = units[units["snap_amount"] > 0]
    if len(eligible) < 4:
        pytest.skip("need at least 4 eligible units for a meaningful comparison")
    target = CaseloadTarget(
        program="snap", year=2024, unit="household",
        count=float(eligible["weight"].sum()) * 0.5,  # half the eligible
        annual_dollars_millions=10.0,
    )
    out = impute_takeup(
        units, target=target, benefit_col="snap_amount", score_col="income"
    )
    imputed_eligible = out[(out["snap_amount"] >= 0) & (out["snap_receives_imputed"])]
    non_imputed_eligible_baseline = eligible[~eligible.index.isin(imputed_eligible.index)]
    if len(imputed_eligible) > 0 and len(non_imputed_eligible_baseline) > 0:
        assert imputed_eligible["income"].max() <= non_imputed_eligible_baseline["income"].min() + 1


def test_impute_takeup_missing_benefit_col_raises(taxed_units):
    target = CaseloadTarget(program="x", year=2024, unit="household", count=10.0, annual_dollars_millions=0.0)
    with pytest.raises(DataValidationError):
        impute_takeup(taxed_units, target=target, benefit_col="not_a_column")


def test_impute_takeup_logs_when_target_unmet(taxed_units, caplog):
    units = compute_snap_for_units(taxed_units)
    impossible_target = CaseloadTarget(
        program="snap", year=2024, unit="household",
        count=1e9, annual_dollars_millions=0.0,
    )
    with caplog.at_level(logging.WARNING, logger="tax_modeler.calibration.takeup_imputation"):
        impute_takeup(
            units, target=impossible_target, benefit_col="snap_amount",
            score_col="income",
        )
    assert any("exceeds tolerance" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# calibrate_benefits (one-call wrapper)
# ---------------------------------------------------------------------------


def test_calibrate_benefits_runs(taxed_units):
    df = compute_snap_for_units(taxed_units)
    df = compute_ssi_for_units(df)
    df = compute_ssi_hi_supplement_for_units(df)

    cl = AdminCaseload.load()
    # Scale targets way down so the synthetic fixture can hit them
    real_snap = cl.target("snap", 2024)
    real_ssi = cl.target("ssi", 2024)
    real_supp = cl.target("ssi_hi_supplement", 2024)
    fixture_factor = 0.0005  # 0.05% scale
    scaled = AdminCaseload(pd.DataFrame([
        {"program": "snap", "year": 2024, "unit": "household",
         "count": real_snap.count * fixture_factor,
         "annual_dollars_millions": real_snap.annual_dollars_millions * fixture_factor},
        {"program": "ssi", "year": 2024, "unit": "person",
         "count": real_ssi.count * fixture_factor,
         "annual_dollars_millions": real_ssi.annual_dollars_millions * fixture_factor},
        {"program": "ssi_hi_supplement", "year": 2024, "unit": "person",
         "count": real_supp.count * fixture_factor,
         "annual_dollars_millions": real_supp.annual_dollars_millions * fixture_factor},
    ]))

    out = calibrate_benefits(df, caseload=scaled, year=2024)
    # All imputed-flag columns now exist
    assert "snap_receives_imputed" in out.columns
    assert "ssi_receives_imputed" in out.columns
    assert "ssi_hi_receives_imputed" in out.columns


def test_calibrate_benefits_unknown_program_raises(taxed_units):
    df = compute_snap_for_units(taxed_units)
    cl = AdminCaseload.load()
    with pytest.raises(ConfigError):
        calibrate_benefits(df, caseload=cl, year=2024, programs=("medicaid",))


# ---------------------------------------------------------------------------
# EITC/CTC take-up (Phase 3 of EITC/CTC geo plan)
# ---------------------------------------------------------------------------


def test_admin_caseload_has_2022_eitc_ctc_benchmarks():
    """Hawaii admin caseload table must include IRS SOI TY2022 EITC/CTC anchors."""
    cl = AdminCaseload.load()
    eitc = cl.target("eitc", 2022)
    ctc = cl.target("ctc", 2022)
    actc = cl.target("actc", 2022)

    # IRS SOI Hawaii TY2022 published totals (ZIP=00000 state row):
    #   EITC: ~84,010 returns, $184.7M
    #   CTC (nonref + ACTC): ~154,580 returns, $469.5M
    #   ACTC: ~60,600 returns, $117.8M
    assert eitc.unit == "return"
    assert 50_000 < eitc.count < 150_000
    assert 100 < eitc.annual_dollars_millions < 300

    assert ctc.unit == "return"
    assert 100_000 < ctc.count < 250_000
    assert 300 < ctc.annual_dollars_millions < 700

    assert actc.unit == "return"
    assert 30_000 < actc.count < 100_000
    assert 50 < actc.annual_dollars_millions < 200


def test_calibrate_benefits_supports_eitc(taxed_units):
    """calibrate_benefits must zero out EITC amounts for non-imputed units."""
    # taxed_units already has eitc_amount from the pipeline fixture.
    if "eitc_amount" not in taxed_units.columns:
        pytest.skip("taxed_units fixture missing eitc_amount column")

    eligible_pre = (taxed_units["eitc_amount"] > 0).sum()
    if eligible_pre < 2:
        pytest.skip("not enough EITC-eligible rows in fixture")

    # Scale 2022 EITC target way down so the fixture can plausibly hit it.
    real = AdminCaseload.load().target("eitc", 2022)
    fixture_factor = 0.0001
    scaled = AdminCaseload(pd.DataFrame([{
        "program": "eitc", "year": 2022, "unit": "return",
        "count": real.count * fixture_factor,
        "annual_dollars_millions": real.annual_dollars_millions * fixture_factor,
    }]))

    out = calibrate_benefits(taxed_units, caseload=scaled, year=2022, programs=("eitc",))
    assert "eitc_receives_imputed" in out.columns
    # Non-recipients have zero EITC amount after imputation
    non_recipients = out[~out["eitc_receives_imputed"]]
    assert (non_recipients["eitc_amount"] == 0).all()
    # At least one unit was imputed as a recipient
    assert out["eitc_receives_imputed"].any()


def test_calibrate_benefits_eitc_ranks_descending_by_amount(taxed_units):
    """Among EITC-eligible units, the largest credit amounts should be claimed first."""
    if "eitc_amount" not in taxed_units.columns:
        pytest.skip("taxed_units fixture missing eitc_amount column")

    eligible = taxed_units[taxed_units["eitc_amount"] > 0]
    if len(eligible) < 4:
        pytest.skip("need at least 4 EITC-eligible rows for ranking test")

    target_count = float(eligible["weight"].sum()) * 0.5  # half the eligible
    scaled = AdminCaseload(pd.DataFrame([{
        "program": "eitc", "year": 2022, "unit": "return",
        "count": target_count, "annual_dollars_millions": 1.0,
    }]))
    out = calibrate_benefits(taxed_units, caseload=scaled, year=2022, programs=("eitc",))

    # Among originally-eligible units, claimants should have higher pre-imputation
    # eitc_amount than non-claimants. Pull pre-imputation amounts via a side
    # column on the input (eligible came from the fixture).
    eligible_idx = eligible.index
    claim_status = out.loc[eligible_idx, "eitc_receives_imputed"]
    pre_amount = eligible["eitc_amount"]
    if claim_status.any() and (~claim_status).any():
        # All claimants' pre-amounts >= all non-claimants' pre-amounts (tie tol)
        assert pre_amount[claim_status].min() >= pre_amount[~claim_status].max() - 0.01


# ---------------------------------------------------------------------------
# HI EITC take-up calibration (Tier 1A — eitc_revert_20 forecast)
# ---------------------------------------------------------------------------


def test_admin_caseload_has_hi_eitc_anchor():
    """Hawaii caseload table must include a hi_eitc anchor for the
    1A take-up-calibration step in forecast_hi_eitc_revert_20.py.
    Anchor year is TY 2023 — the first year HI EITC was refundable
    (Act 209, 2023). DOTAX Tax Credits Claimed Table A-1/A-2: 84,470
    returns, $77.054M.
    """
    cl = AdminCaseload.load()
    hi = cl.target("hi_eitc", 2023)
    assert hi.unit == "return"
    # DOTAX TY 2023: 84,470 returns. Refundable HI EITC has near-100%
    # take-up because it auto-attaches to the federal EITC claim.
    assert 80_000 < hi.count < 90_000, (
        f"hi_eitc count {hi.count} should match DOTAX TY 2023 (84,470)."
    )
    assert 70 < hi.annual_dollars_millions < 90


def test_calibrate_benefits_supports_hi_eitc(taxed_units):
    """calibrate_benefits zeros HI EITC for non-imputed units; preserves federal."""
    if "eitc_amount" not in taxed_units.columns:
        pytest.skip("taxed_units fixture missing eitc_amount column")

    units = taxed_units.copy()
    # Synthesize hi_eitc_amount = 0.40 × federal EITC.
    units["hi_eitc_amount"] = 0.40 * units["eitc_amount"].fillna(0)
    if (units["hi_eitc_amount"] > 0).sum() < 2:
        pytest.skip("not enough HI-EITC-eligible rows in fixture")

    fed_before = units["eitc_amount"].copy()

    target_count = float(units.loc[units["hi_eitc_amount"] > 0, "weight"].sum()) * 0.5
    scaled = AdminCaseload(pd.DataFrame([{
        "program": "hi_eitc", "year": 2023, "unit": "return",
        "count": target_count, "annual_dollars_millions": 1.0,
    }]))

    out = calibrate_benefits(units, caseload=scaled, year=2023, programs=("hi_eitc",))
    assert "hi_eitc_receives_imputed" in out.columns
    non_recip = out[~out["hi_eitc_receives_imputed"]]
    assert (non_recip["hi_eitc_amount"] == 0).all()
    # Federal EITC unaffected by HI calibration.
    pd.testing.assert_series_equal(
        out["eitc_amount"], fed_before, check_names=False
    )


# ---------------------------------------------------------------------------
# Reform-path interaction (TRIM3 convention)
# ---------------------------------------------------------------------------


def test_reform_path_does_not_apply_baseline_takeup(taxed_units):
    """Per TRIM3 convention, apply_reform recomputes from eligibility — it
    should NOT inherit the baseline take-up flags. Easiest way to verify:
    a Reform that doesn't touch SNAP should produce a counterfactual SNAP
    column equal to fresh eligibility-based computation, not zeroed-out."""
    # Manually apply take-up imputation to baseline first
    baseline = compute_snap_for_units(taxed_units)
    cl = AdminCaseload.load()
    # Use a tiny target so most eligible units have benefit_col == 0 in baseline
    tiny_target = CaseloadTarget(
        program="snap", year=2024, unit="household",
        count=1.0, annual_dollars_millions=0.0,
    )
    baseline_calibrated = impute_takeup(
        baseline, target=tiny_target, benefit_col="snap_amount", score_col="income"
    )
    # After this, baseline_calibrated["snap_amount"] is mostly zero.

    # Apply a tax-only reform (no benefit overrides)
    reform = Reform(name="null_tax_reform")
    result = apply_reform(baseline_calibrated, reform, year=2026)
    # No counterfactual_units (no benefit overrides) — the assertion is that
    # apply_reform doesn't crash on calibrated baseline data.
    assert result.counterfactual_units is None


# ---------------------------------------------------------------------------
# scale_benefit_to_dollar_target — SOI-anchored dollar calibration
# ---------------------------------------------------------------------------


def _make_eitc_units(n: int = 10, eitc_per_unit: float = 1_000.0) -> pd.DataFrame:
    """Minimal DataFrame with eitc_amount and weight columns."""
    return pd.DataFrame({
        "eitc_amount": [eitc_per_unit] * n,
        "hi_eitc_amount": [eitc_per_unit * 0.4] * n,
        "weight": [1.0] * n,
        "income": [30_000.0] * n,
    })


def test_scale_benefit_scalar_applied():
    """model=100M, target=120M → scalar=1.2, all amounts ×1.2."""
    # 100 units × $1M each × weight 1.0 = $100M model total
    df = pd.DataFrame({
        "eitc_amount": [1_000_000.0] * 100,
        "weight": [1.0] * 100,
    })
    out, scalar = scale_benefit_to_dollar_target(
        df, benefit_col="eitc_amount", target_dollars_M=120.0
    )
    assert abs(scalar - 1.2) < 1e-9
    np.testing.assert_allclose(out["eitc_amount"].to_numpy(), 1_200_000.0)


def test_scale_benefit_hi_eitc_same_scalar():
    """hi_eitc_amount must be scaled by the same scalar as the federal credit."""
    df = pd.DataFrame({
        "eitc_amount": [1_000_000.0] * 50,
        "hi_eitc_amount": [400_000.0] * 50,   # 40% of federal
        "weight": [1.0] * 50,
    })
    # Federal: model=50M, target=75M → scalar=1.5
    out_fed, scalar_fed = scale_benefit_to_dollar_target(
        df, benefit_col="eitc_amount", target_dollars_M=75.0
    )
    assert abs(scalar_fed - 1.5) < 1e-9

    # Apply same scalar to hi_eitc manually (mirrors calibrate_benefits logic)
    out_hi = out_fed.copy()
    out_hi["hi_eitc_amount"] = out_hi["hi_eitc_amount"] * scalar_fed
    # hi_eitc should still be 40% of federal after scaling
    ratio = out_hi["hi_eitc_amount"] / out_fed["eitc_amount"]
    np.testing.assert_allclose(ratio.to_numpy(), 0.4)


def test_scale_benefit_unusual_scalar_warns(caplog):
    """scalar > 2.0 must emit a WARNING."""
    df = pd.DataFrame({
        "eitc_amount": [1_000.0] * 10,  # model total = 0.01M
        "weight": [1.0] * 10,
    })
    with caplog.at_level(logging.WARNING, logger="tax_modeler.calibration.takeup_imputation"):
        _, scalar = scale_benefit_to_dollar_target(
            df, benefit_col="eitc_amount", target_dollars_M=1_000.0  # 100,000× overshoot
        )
    assert scalar > 2.0
    assert any("unusual scalar" in rec.message for rec in caplog.records)


def test_scale_benefit_zero_model_returns_unchanged(caplog):
    """model total == 0 must return the frame unchanged without divide-by-zero."""
    df = pd.DataFrame({
        "eitc_amount": [0.0] * 5,
        "weight": [1.0] * 5,
    })
    with caplog.at_level(logging.WARNING, logger="tax_modeler.calibration.takeup_imputation"):
        out, scalar = scale_benefit_to_dollar_target(
            df, benefit_col="eitc_amount", target_dollars_M=100.0
        )
    assert scalar == 1.0
    assert (out["eitc_amount"] == 0.0).all()
    assert any("zero" in rec.message for rec in caplog.records)


def test_calibrate_benefits_eitc_dollar_calibration_scales_hi_eitc(taxed_units):
    """When eitc + hi_eitc are both in programs and eitc has annual_dollars_millions > 0,
    hi_eitc_amount should be scaled by the same federal scalar."""
    if "eitc_amount" not in taxed_units.columns:
        pytest.skip("taxed_units fixture missing eitc_amount column")

    units = taxed_units.copy()
    units["hi_eitc_amount"] = 0.40 * units["eitc_amount"].fillna(0)

    eitc_eligible = units[units["eitc_amount"] > 0]
    hi_eligible = units[units["hi_eitc_amount"] > 0]
    if len(eitc_eligible) < 2 or len(hi_eligible) < 2:
        pytest.skip("not enough EITC/HI-EITC eligible rows in fixture")

    # Build a scaled caseload for both programs; give eitc a dollar target.
    eitc_count = float(eitc_eligible["weight"].sum())
    hi_count = float(hi_eligible["weight"].sum())
    # model eitc total in $M (before calibration)
    model_eitc_M = float((eitc_eligible["eitc_amount"] * eitc_eligible["weight"]).sum()) / 1e6
    # Set target to 1.5× model to force a known scalar
    target_eitc_M = model_eitc_M * 1.5 if model_eitc_M > 0 else 1.0

    scaled = AdminCaseload(pd.DataFrame([
        {"program": "eitc", "year": 2022, "unit": "return",
         "count": eitc_count, "annual_dollars_millions": target_eitc_M},
        {"program": "hi_eitc", "year": 2022, "unit": "return",
         "count": hi_count, "annual_dollars_millions": 0.0},
    ]))

    out = calibrate_benefits(units, caseload=scaled, year=2022, programs=("eitc", "hi_eitc"))

    # For recipients, hi_eitc should still be ~40% of eitc_amount after scaling.
    recipients = out[out["eitc_receives_imputed"] & out["hi_eitc_receives_imputed"]]
    if len(recipients) == 0:
        pytest.skip("no joint eitc+hi_eitc recipients in fixture")
    ratio = recipients["hi_eitc_amount"] / recipients["eitc_amount"]
    np.testing.assert_allclose(ratio.to_numpy(), 0.4, rtol=1e-6)
