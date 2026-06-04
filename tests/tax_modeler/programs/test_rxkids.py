"""Tests for tax_modeler.programs.rxkids_hi."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tax_modeler.credits.arpa_ctc import arpa_ctc_for_tax_units
from tax_modeler.errors import ConfigError
from tax_modeler.poverty.impact import compute_poverty_impact
from tax_modeler.poverty.spm import compute_spm_resources
from tax_modeler.programs import (
    RxKidsHIParams,
    compute_rxkids_for_units,
    hawaii_rxkids_parameters,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_units(rows: list[dict]) -> pd.DataFrame:
    """Minimal tax-unit DataFrame with the columns the impact module
    requires. Mirrors the helper in tests/tax_modeler/poverty/test_impact.py.
    """
    defaults = {
        "filing_status": "head_of_household",
        "num_dependents": 0,
        "num_qualifying_children": 0,
        "total_cash_income": 15_000.0,
        "earned_income": 15_000.0,
        "income": 15_000.0,
        "weight": 100.0,
        "hi_tax_liability": 0.0,
        "eitc_amount": 0.0,
        "ctc_total": 0.0,
        "ctc_refundable": 0.0,
        "hi_eitc_amount": 0.0,
        "tenure": "renter",
        "county": "Honolulu",
        "house_district": 1,
        "senate_district": 1,
        "PUMA": 301,
    }
    out = pd.DataFrame([{**defaults, **r} for r in rows])
    out = arpa_ctc_for_tax_units(out)
    return out


# ---------------------------------------------------------------------------
# Unit-level behavior of compute_rxkids_for_units
# ---------------------------------------------------------------------------


def test_rxkids_zero_for_high_income():
    """A unit with income > income_fpl_cap × FPL → rxkids_amount == 0."""
    # Universal default cap = 10.0 × FPL. HI 2024 FPL(3) = $28,590.
    # 10 × $28,590 = $285,900. Use $400k to safely clear universal cap.
    units = _make_units([
        {
            "filing_status": "head_of_household",
            "num_dependents": 2,
            "num_qualifying_children": 2,
            "income": 400_000.0,
            "total_cash_income": 400_000.0,
            "earned_income": 400_000.0,
        },
    ])
    out = compute_rxkids_for_units(units, tax_year=2024)
    assert out["rxkids_amount"].iloc[0] == pytest.approx(0.0)


def test_rxkids_postnatal_scales_with_children():
    """More dependents → larger postnatal rxkids_amount (linear)."""
    units = _make_units([
        {"num_dependents": 1, "num_qualifying_children": 1, "income": 15_000.0},
        {"num_dependents": 4, "num_qualifying_children": 4, "income": 15_000.0},
    ])
    out = compute_rxkids_for_units(units, tax_year=2024)
    one_kid = out["rxkids_amount"].iloc[0]
    four_kids = out["rxkids_amount"].iloc[1]
    assert four_kids > one_kid > 0
    # Postnatal is linear in n_kids (the FPL cap rises with hh_size so
    # both units remain eligible). Expect ~4× the lift.
    assert four_kids == pytest.approx(4.0 * one_kid, rel=1e-9)


def test_rxkids_is_nontaxable_in_spm():
    """With is_taxable=False, rxkids_amount lands in spm_resources but
    NOT in total_cash_income.
    """
    units = _make_units([
        {"num_dependents": 2, "num_qualifying_children": 2, "income": 12_000.0},
    ])
    out = compute_rxkids_for_units(units, tax_year=2024)
    rxk = float(out["rxkids_amount"].iloc[0])
    assert rxk > 0, "fixture should produce a non-zero RxKids amount"

    # total_cash_income unchanged
    assert out["total_cash_income"].iloc[0] == pytest.approx(
        units["total_cash_income"].iloc[0]
    )

    # SPM resources WITHOUT rxkids
    no_rxk, _ = compute_spm_resources(out, rxkids_col=None)
    # SPM resources WITH rxkids
    with_rxk, _ = compute_spm_resources(out, rxkids_col="rxkids_amount")
    delta = float(with_rxk["spm_resources"].iloc[0] - no_rxk["spm_resources"].iloc[0])
    assert delta == pytest.approx(rxk, rel=1e-9)


def test_rxkids_takeup_rate_monotone():
    """Higher takeup_rate → larger rxkids_amount (strictly, when > 0)."""
    units = _make_units([
        {"num_dependents": 2, "num_qualifying_children": 2, "income": 12_000.0},
    ])
    low = compute_rxkids_for_units(
        units, tax_year=2024,
        params=RxKidsHIParams(takeup_rate=0.50),
    )
    high = compute_rxkids_for_units(
        units, tax_year=2024,
        params=RxKidsHIParams(takeup_rate=1.00),
    )
    assert float(low["rxkids_amount"].iloc[0]) > 0
    assert float(high["rxkids_amount"].iloc[0]) == pytest.approx(
        2.0 * float(low["rxkids_amount"].iloc[0])
    )


# ---------------------------------------------------------------------------
# Integration: poverty impact + by_household_type
# ---------------------------------------------------------------------------


def test_rxkids_hoh_poverty_rate_lower_with_program():
    """HoH baseline poverty rate decreases when --apply-rxkids ON."""
    # Build a cohort of HoH filers near the 2024 HI renter SPM threshold.
    # 1A+2C Honolulu renter threshold ≈ $36.4k. Incomes ~$28k-$33k so SPM
    # resources + credits sit just below threshold.
    rng = np.random.default_rng(0)
    rows = []
    for _ in range(30):
        n_kids = int(rng.integers(2, 4))  # 2-3 kids
        income = float(rng.uniform(28_000, 33_000))
        rows.append({
            "filing_status": "head_of_household",
            "num_dependents": n_kids,
            "num_qualifying_children": n_kids,
            "income": income,
            "total_cash_income": income,
            "earned_income": income,
            "weight": 100.0,
            "eitc_amount": float(rng.uniform(2_000, 5_000)),
            "ctc_refundable": n_kids * 1_500.0,
            "ctc_total": n_kids * 2_000.0,
            "hi_eitc_amount": float(rng.uniform(800, 2_000)),
        })
    units = _make_units(rows)

    # Inflate the rxkids payment so it has a clear-the-threshold lift on
    # this synthetic cohort (the production defaults are calibrated to
    # cost ranges, not to lift this particular cohort).
    units = compute_rxkids_for_units(
        units, tax_year=2024,
        params=RxKidsHIParams(
            postnatal_monthly_per_child=600.0,
            child_under_age_share=1.0,
            takeup_rate=1.0,
        ),
    )

    result = compute_poverty_impact(
        units, tax_year=2024, scenarios=("rxkids_hi",),
    )
    s = result.by_state.iloc[0]
    # rxkids_hi reduces poverty rate among HoH filers.
    assert s["poverty_rate_rxkids_hi_hoh"] <= s["poverty_rate_hoh_baseline"] + 1e-9
    # Strict decrease on this synthetic cohort.
    assert s["poverty_rate_rxkids_hi_hoh"] < s["poverty_rate_hoh_baseline"]


def test_rxkids_lift_positive_for_synthetic_eligible_cohort():
    """At least some persons lifted for HoH families near the poverty threshold.

    TY2024 SPM threshold for 1A+2C Honolulu renter ≈ $36.4k. Units are set
    near the threshold so an $8k-$12k rxkids payment bridges the gap.
    """
    rng = np.random.default_rng(1)
    rows = []
    for _ in range(30):
        n_kids = int(rng.integers(1, 3))  # 1-2 kids
        income = float(rng.uniform(25_000, 32_000))
        rows.append({
            "filing_status": "head_of_household",
            "num_dependents": n_kids,
            "num_qualifying_children": n_kids,
            "income": income,
            "total_cash_income": income,
            "earned_income": income,
            "weight": 100.0,
            "eitc_amount": float(rng.uniform(1_500, 3_000)),
            "ctc_refundable": n_kids * 1_500.0,
            "ctc_total": n_kids * 2_000.0,
            "hi_eitc_amount": float(rng.uniform(500, 1_200)),
        })
    units = _make_units(rows)
    # postnatal $1k/mo × 6 mo × all-children age-share = $6k–$12k per unit,
    # enough to bridge the remaining gap for units near the threshold.
    units = compute_rxkids_for_units(
        units, tax_year=2024,
        params=RxKidsHIParams(
            postnatal_monthly_per_child=1_000.0,
            child_under_age_share=1.0,
            takeup_rate=1.0,
        ),
    )
    result = compute_poverty_impact(
        units, tax_year=2024, scenarios=("rxkids_hi",),
    )
    s = result.by_state.iloc[0]
    assert s["persons_lifted_rxkids_hi"] > 0
    # by_household_type frame populated.
    assert "filing_status" in result.by_household_type.columns
    assert "head_of_household" in set(result.by_household_type["filing_status"])


def test_rxkids_singletype_baseline_unchanged_without_scenario():
    """If 'rxkids_hi' is not in scenarios, baseline + other scenarios
    should be identical to a run that has no rxkids_amount column at all.
    """
    units = _make_units([
        {"num_dependents": 2, "num_qualifying_children": 2, "income": 12_000.0},
    ])
    units_with_rxk = compute_rxkids_for_units(units, tax_year=2024)

    r_no_col = compute_poverty_impact(
        units, tax_year=2024, scenarios=("no_eitc",),
    ).by_state.iloc[0]
    r_with_col = compute_poverty_impact(
        units_with_rxk, tax_year=2024, scenarios=("no_eitc",),
    ).by_state.iloc[0]
    assert r_no_col["poverty_rate_baseline"] == pytest.approx(
        r_with_col["poverty_rate_baseline"]
    )
    assert r_no_col["persons_lifted_no_eitc"] == pytest.approx(
        r_with_col["persons_lifted_no_eitc"]
    )


def test_rxkids_unknown_override_raises():
    units = _make_units([{"num_dependents": 1, "num_qualifying_children": 1}])
    with pytest.raises(ConfigError):
        compute_rxkids_for_units(units, overrides={"foo_bar": 1.0})


def test_rxkids_takeup_out_of_range_raises():
    units = _make_units([{"num_dependents": 1, "num_qualifying_children": 1}])
    with pytest.raises(ConfigError):
        compute_rxkids_for_units(units, params=RxKidsHIParams(takeup_rate=1.5))


def test_rxkids_defaults_match_hawaii_factory():
    """hawaii_rxkids_parameters() returns the canonical default set."""
    p = hawaii_rxkids_parameters()
    # Statutory eligibility variant: $1,500 one-time prenatal,
    # $500/mo × 6 months postnatal, 300% FPL income cap (+ Medicaid OR
    # clause), 196% FPL Medicaid pregnancy pathway for the prenatal arm.
    assert p.prenatal_monthly == pytest.approx(1500.0)
    assert p.prenatal_months == 1
    assert p.postnatal_monthly_per_child == pytest.approx(500.0)
    assert p.postnatal_months == 6
    assert p.income_fpl_cap == pytest.approx(3.00)
    assert p.pregnant_fpl_cap == pytest.approx(1.96)
    assert p.takeup_rate == pytest.approx(0.90)
    assert p.prenatal_takeup_rate is None  # library default: arms uniform
    assert p.is_taxable is False


def test_rxkids_arm_specific_takeup():
    """A lower prenatal_takeup_rate scales only the prenatal arm; the postnatal
    arm stays on takeup_rate. (Mothers enroll prenatally at a lower rate than
    newborns are enrolled — Flint ~90% vs ~98%.)"""
    units = _make_units([
        {"num_dependents": 2, "num_qualifying_children": 2, "income": 30_000.0,
         "medicaid_receives": False},
    ])
    uniform = compute_rxkids_for_units(units, tax_year=2024)  # both arms 0.90
    split = compute_rxkids_for_units(
        units, tax_year=2024,
        params=RxKidsHIParams(takeup_rate=0.90, prenatal_takeup_rate=0.828),
    )
    # Postnatal arm unchanged; prenatal arm scaled by 0.828/0.90 = 0.92.
    assert float(split["rxkids_postnatal_amount"].iloc[0]) == pytest.approx(
        float(uniform["rxkids_postnatal_amount"].iloc[0]))
    assert float(split["rxkids_prenatal_amount"].iloc[0]) == pytest.approx(
        float(uniform["rxkids_prenatal_amount"].iloc[0]) * (0.828 / 0.90))


# ---------------------------------------------------------------------------
# Statutory eligibility: Medicaid (clause 1) OR 300% FPL incl. unborn (clause 2)
# ---------------------------------------------------------------------------
#
# 2024 HI HHS FPL anchors used below:
#   FPL(1)=16,770  FPL(2)=22,680  FPL(3)=28,590


def test_rxkids_clause2_income_under_300pct_eligible():
    """Clause 2: a postnatal unit at ~220% FPL (no Medicaid) is eligible;
    the same unit at ~350% FPL is not."""
    # HoH + 1 dependent → postnatal family size 2, FPL(2)=22,680.
    eligible = _make_units([
        {"num_dependents": 1, "num_qualifying_children": 1,
         "income": 50_000.0, "medicaid_receives": False},  # 50k/22.68k ≈ 2.20
    ])
    ineligible = _make_units([
        {"num_dependents": 1, "num_qualifying_children": 1,
         "income": 80_000.0, "medicaid_receives": False},  # 80k/22.68k ≈ 3.53
    ])
    out_e = compute_rxkids_for_units(eligible, tax_year=2024)
    out_i = compute_rxkids_for_units(ineligible, tax_year=2024)
    assert float(out_e["rxkids_amount"].iloc[0]) > 0
    assert float(out_i["rxkids_amount"].iloc[0]) == pytest.approx(0.0)


def test_rxkids_clause1_medicaid_overrides_income_test():
    """Clause 1: a unit above 300% FPL still qualifies if medicaid_receives
    is True; the identical unit without Medicaid does not (proves the OR)."""
    base_row = {"num_dependents": 1, "num_qualifying_children": 1,
                "income": 80_000.0}  # ≈ 353% of FPL(2) — fails clause 2
    on_medicaid = _make_units([{**base_row, "medicaid_receives": True}])
    off_medicaid = _make_units([{**base_row, "medicaid_receives": False}])
    out_on = compute_rxkids_for_units(on_medicaid, tax_year=2024)
    out_off = compute_rxkids_for_units(off_medicaid, tax_year=2024)
    assert float(out_on["rxkids_amount"].iloc[0]) > 0
    assert float(out_off["rxkids_amount"].iloc[0]) == pytest.approx(0.0)


def test_rxkids_married_and_repeat_births_covered():
    """Both arms are birth-driven, so a MARRIED family (MFJ) with a child —
    previously excluded from the prenatal arm — now draws a prenatal payment
    too. A childless filer (no birth event) draws nothing."""
    units = _make_units([
        # Married couple with their (first) newborn dependent, income-eligible.
        {"filing_status": "married_filing_jointly", "num_dependents": 1,
         "num_qualifying_children": 1, "income": 50_000.0,
         "medicaid_receives": False},
        # Childless single filer → no birth event → no payment.
        {"filing_status": "single", "num_dependents": 0,
         "num_qualifying_children": 0, "income": 30_000.0,
         "medicaid_receives": False},
    ])
    out = compute_rxkids_for_units(units, tax_year=2024)
    mfj = out.iloc[0]
    assert float(mfj["rxkids_prenatal_amount"]) > 0   # married first birth covered
    assert float(mfj["rxkids_postnatal_amount"]) > 0
    assert float(out.iloc[1]["rxkids_amount"]) == pytest.approx(0.0)


def test_rxkids_prenatal_is_half_postnatal_per_birth():
    """Each eligible birth draws one prenatal ($1,500) and one postnatal
    ($3,000) payment, so the prenatal arm is exactly half the postnatal arm."""
    units = _make_units([
        {"num_dependents": 2, "num_qualifying_children": 2, "income": 30_000.0,
         "medicaid_receives": False},
    ])
    out = compute_rxkids_for_units(units, tax_year=2024)
    pre = float(out["rxkids_prenatal_amount"].iloc[0])
    post = float(out["rxkids_postnatal_amount"].iloc[0])
    assert pre > 0 and post > 0
    assert pre == pytest.approx(0.5 * post)


def test_rxkids_medicaid_pregnancy_pathway_binds_below_196():
    """Clause 1 pregnancy pathway (196% FPL): with the income cap set below
    196%, a family at ~150% FPL still qualifies for the PRENATAL arm via the
    Medicaid pregnancy pathway, but not the postnatal arm."""
    # HoH + 1 dep → size 2, FPL(2)=22,680. income=34,000 ≈ 1.50× FPL.
    units = _make_units([
        {"num_dependents": 1, "num_qualifying_children": 1, "income": 34_000.0,
         "medicaid_receives": False},
    ])
    # income_fpl_cap below the family's ratio so clause 2 fails, but the
    # 196% pregnancy pathway (clause 1) still covers the prenatal arm.
    out = compute_rxkids_for_units(
        units, tax_year=2024, params=RxKidsHIParams(income_fpl_cap=1.0),
    )
    assert float(out["rxkids_prenatal_amount"].iloc[0]) > 0
    assert float(out["rxkids_postnatal_amount"].iloc[0]) == pytest.approx(0.0)


def test_magi_proxy_adds_back_nontaxable_social_security():
    """The forecast's MAGI proxy counts 100% of Social Security: it adds the
    non-taxable 15% (ssp_full − ssp) back onto the model's gross income."""
    import sys
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    import forecast_rxkids_2028 as fc

    df = pd.DataFrame({
        "income": [50_000.0],          # already includes 0.85 × SS = 8,500
        "primary_ssp": [8_500.0],      # 85% taxable portion
        "primary_ssp_full": [10_000.0],
        "secondary_ssp": [0.0],
        "secondary_ssp_full": [0.0],
    })
    magi = fc._magi_proxy(df)
    # MAGI adds back the non-taxable 15% (1,500) → 51,500.
    assert float(magi.iloc[0]) == pytest.approx(51_500.0)


def test_rxkids_family_grain_income_test():
    """When family-grain columns are supplied, the FPL test uses household
    income/size, not the tax unit's. A unit income-eligible at its own small
    tax-unit size is excluded once the larger household income is tested."""
    units = _make_units([
        {"num_dependents": 1, "num_qualifying_children": 1, "income": 40_000.0,
         "medicaid_receives": False, "fam_inc": 120_000.0, "fam_size": 3},
    ])
    # Tax-unit grain: 40k / FPL(2)=22,680 ≈ 1.76× → eligible.
    tu = compute_rxkids_for_units(units, tax_year=2024)
    assert float(tu["rxkids_amount"].iloc[0]) > 0
    # Family grain: 120k / FPL(3)=28,590 ≈ 4.2× → ineligible.
    fam = compute_rxkids_for_units(
        units, tax_year=2024,
        family_income_col="fam_inc", family_size_col="fam_size",
    )
    assert float(fam["rxkids_amount"].iloc[0]) == pytest.approx(0.0)


def test_rxkids_missing_medicaid_column_falls_back_to_clause2(caplog):
    """If medicaid_receives is absent, the function applies clause 2 only
    and warns. Income-eligible units still qualify; income-ineligible ones
    cannot sneak in via the (unavailable) Medicaid clause."""
    import logging

    units = _make_units([
        {"num_dependents": 1, "num_qualifying_children": 1, "income": 50_000.0},
        {"num_dependents": 1, "num_qualifying_children": 1, "income": 90_000.0},
    ])
    assert "medicaid_receives" not in units.columns
    with caplog.at_level(logging.WARNING):
        out = compute_rxkids_for_units(units, tax_year=2024)
    assert any("medicaid_receives" in r.message for r in caplog.records)
    assert float(out["rxkids_amount"].iloc[0]) > 0       # clause 2 still works
    assert float(out["rxkids_amount"].iloc[1]) == pytest.approx(0.0)
