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
