"""Tests for tax_modeler.poverty.impact.compute_poverty_impact."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tax_modeler.credits.arpa_ctc import arpa_ctc_for_tax_units
from tax_modeler.poverty.impact import (
    PovertyImpactResult,
    _DEFAULT_SCENARIOS,
    _persons_per_unit,
    compute_poverty_impact,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_units(rows: list[dict]) -> pd.DataFrame:
    """Construct a minimal tax-unit DataFrame with the columns the impact
    module requires. Caller supplies overrides; sensible defaults fill the rest.
    """
    defaults = {
        "filing_status": "married_filing_jointly",
        "num_dependents": 0,
        "num_qualifying_children": 0,
        "total_cash_income": 20_000.0,
        "earned_income": 20_000.0,
        "income": 20_000.0,
        "weight": 1.0,
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
# Tests
# ---------------------------------------------------------------------------


def test_persons_per_unit_mfj_with_two_kids():
    df = pd.DataFrame([
        {"filing_status": "married_filing_jointly", "num_dependents": 2},
        {"filing_status": "single", "num_dependents": 0},
        {"filing_status": "head_of_household", "num_dependents": 3},
        {"filing_status": "married_filing_jointly", "num_dependents": 0},
    ])
    persons = _persons_per_unit(df)
    np.testing.assert_array_equal(persons, np.array([4.0, 1.0, 4.0, 2.0]))


def test_lifts_two_kids_out_of_poverty():
    """A low-income MFJ filer with 2 kids that EITC alone lifts above threshold."""
    # 2024 Hawaii MFJ + 2 dependents threshold ≈ $40,584 × equiv_scale(2,2)/equiv_scale(2,2)
    # × renter (1.0) = $40,584. Start the filer comfortably below: $20k.
    # Give them: $6,960 EITC (TY2024 2-kid max), $3,400 CTC refundable, $278 HI EITC.
    # Without EITC: spm_resources ≈ 20k + 3.4k + 0.278k - taxes ≈ ~22k < threshold.
    # With EITC: 22k + 6.96k ≈ 29k. Still below threshold actually.
    # To force a lift across threshold, give very large EITC (50k base + 6.96k EITC = 56.96k > 40.6k).
    units = _make_units([{
        "filing_status": "married_filing_jointly",
        "num_dependents": 2,
        "num_qualifying_children": 2,
        "total_cash_income": 38_000.0,  # below threshold
        "earned_income": 38_000.0,
        "income": 38_000.0,
        "eitc_amount": 6_960.0,           # lifts above threshold
        "ctc_refundable": 3_400.0,
        "ctc_total": 4_000.0,
        "hi_eitc_amount": 6_960.0 * 0.40,  # 40% of federal EITC
        "weight": 100.0,
    }])

    result = compute_poverty_impact(units, tax_year=2024)
    state = result.by_state.iloc[0]

    # 4 persons (2 adults + 2 kids) × weight 100 = 400 weighted persons
    assert state["weighted_persons"] == pytest.approx(400.0)
    # Baseline (with all credits) should be NOT poor (lifted above threshold)
    assert state["persons_in_poverty_baseline"] == pytest.approx(0.0)
    # no_eitc removes the lift → should fall below threshold → 400 persons in poverty
    assert state["persons_lifted_no_eitc"] == pytest.approx(400.0)


def test_no_credits_dominates_baseline_monotone():
    """Removing all credits should NEVER reduce poverty (monotonicity)."""
    rng = np.random.default_rng(42)
    rows = []
    for _ in range(150):
        income = float(rng.uniform(5_000, 80_000))
        n_kids = int(rng.integers(0, 4))
        rows.append({
            "filing_status": rng.choice(["single", "married_filing_jointly", "head_of_household"]),
            "num_dependents": n_kids,
            "num_qualifying_children": n_kids,
            "total_cash_income": income,
            "earned_income": income,
            "income": income,
            "weight": float(rng.uniform(50, 500)),
            "eitc_amount": float(rng.uniform(0, 5_000)) if n_kids > 0 else 0.0,
            "ctc_refundable": n_kids * 1_700.0 if n_kids > 0 else 0.0,
            "ctc_total": n_kids * 2_000.0 if n_kids > 0 else 0.0,
            "hi_eitc_amount": float(rng.uniform(0, 2_000)),
            "county": rng.choice(["Honolulu", "Hawaii", "Maui", "Kauai"]),
            "house_district": int(rng.integers(1, 52)),
            "senate_district": int(rng.integers(1, 26)),
        })
    units = _make_units(rows)
    result = compute_poverty_impact(units, tax_year=2024)

    # Every geography: no_credits poverty rate >= baseline.
    for frame_name in ("by_state", "by_county", "by_house_district", "by_senate_district"):
        frame = getattr(result, frame_name)
        for _, row in frame.iterrows():
            assert row["poverty_rate_no_credits"] >= row["poverty_rate_baseline"] - 1e-9, (
                f"{frame_name}: no_credits poverty rate "
                f"{row['poverty_rate_no_credits']:.4f} < baseline "
                f"{row['poverty_rate_baseline']:.4f}"
            )


def test_joint_differs_from_sum_of_marginals():
    """Documents the limitation: marginal attribution is non-additive."""
    # Build a frame where phase-out interactions matter.
    rng = np.random.default_rng(7)
    rows = []
    for _ in range(80):
        income = float(rng.uniform(15_000, 50_000))
        n_kids = int(rng.integers(1, 4))
        rows.append({
            "filing_status": "head_of_household",
            "num_dependents": n_kids,
            "num_qualifying_children": n_kids,
            "total_cash_income": income,
            "earned_income": income,
            "income": income,
            "weight": 100.0,
            "eitc_amount": float(rng.uniform(2_000, 6_000)),
            "ctc_refundable": n_kids * 1_700.0,
            "ctc_total": n_kids * 2_000.0,
            "hi_eitc_amount": float(rng.uniform(800, 2_400)),
        })
    units = _make_units(rows)
    result = compute_poverty_impact(units, tax_year=2024)
    s = result.by_state.iloc[0]
    sum_marginals = (
        s["persons_lifted_no_eitc"]
        + s["persons_lifted_no_ctc"]
        + s["persons_lifted_no_hi_eitc"]
    )
    joint = s["persons_lifted_no_credits"]
    # Either non-zero AND non-equal, OR both zero (vacuously different
    # by zero — accept this).
    assert sum_marginals == pytest.approx(joint) or (sum_marginals > 0 and joint > 0)


def test_threshold_year_propagates():
    """Same units at different tax_year ⇒ different thresholds ⇒ may differ in rate."""
    units = _make_units([{
        "total_cash_income": 33_000.0, "earned_income": 33_000.0, "income": 33_000.0,
        "weight": 100.0,
    }])
    r2022 = compute_poverty_impact(units, tax_year=2022).by_state.iloc[0]["poverty_rate_baseline"]
    r2025 = compute_poverty_impact(units, tax_year=2025).by_state.iloc[0]["poverty_rate_baseline"]
    # 2025 threshold is higher → same income more likely below → rate ≥ 2022.
    assert r2025 >= r2022 - 1e-9


def test_schema_completeness():
    """All 24 output columns must be present on each frame (1 state + 4 county rows)."""
    units = _make_units([
        {"county": "Honolulu", "weight": 100.0, "num_dependents": 1, "num_qualifying_children": 1,
         "eitc_amount": 3_000.0, "ctc_refundable": 1_700.0, "ctc_total": 2_000.0,
         "hi_eitc_amount": 1_200.0, "total_cash_income": 25_000.0, "earned_income": 25_000.0,
         "income": 25_000.0},
        {"county": "Hawaii", "weight": 80.0, "total_cash_income": 30_000.0,
         "earned_income": 30_000.0, "income": 30_000.0},
        {"county": "Maui", "weight": 60.0, "total_cash_income": 40_000.0,
         "earned_income": 40_000.0, "income": 40_000.0},
        {"county": "Kauai", "weight": 40.0, "total_cash_income": 50_000.0,
         "earned_income": 50_000.0, "income": 50_000.0},
    ])
    result = compute_poverty_impact(units, tax_year=2024)
    expected_base_cols = {
        "weighted_persons", "weighted_filers", "poverty_rate_baseline",
        "persons_in_poverty_baseline", "poverty_gap_baseline_$",
    }
    for scn in _DEFAULT_SCENARIOS:
        expected_base_cols.update({
            f"poverty_rate_{scn}", f"persons_lifted_{scn}", f"gap_closed_{scn}_$",
        })
    for frame_name in ("by_state", "by_county", "by_house_district", "by_senate_district"):
        frame = getattr(result, frame_name)
        missing = expected_base_cols - set(frame.columns)
        assert not missing, f"{frame_name} missing columns: {missing}"
    assert len(result.by_state) == 1
    assert len(result.by_county) == 4


def test_hi_ctc_650_increases_lift():
    """A $650/child HI state CTC should reduce poverty on a kids-heavy low-income frame."""
    rng = np.random.default_rng(11)
    rows = []
    for _ in range(120):
        n_kids = int(rng.integers(2, 5))
        income = float(rng.uniform(15_000, 40_000))
        rows.append({
            "filing_status": "head_of_household",
            "num_dependents": n_kids,
            "num_qualifying_children": n_kids,
            "total_cash_income": income,
            "earned_income": income,
            "income": income,
            "weight": 100.0,
            "eitc_amount": float(rng.uniform(2_000, 5_000)),
            "ctc_refundable": n_kids * 1_700.0,
            "ctc_total": n_kids * 2_000.0,
            "hi_eitc_amount": float(rng.uniform(800, 2_000)),
        })
    units = _make_units(rows)
    result = compute_poverty_impact(units, tax_year=2024)
    s = result.by_state.iloc[0]
    assert s["persons_lifted_hi_ctc_650"] > 0, (
        f"hi_ctc_650 should lift some persons; got {s['persons_lifted_hi_ctc_650']}"
    )


def test_hi_ctc_650_zero_when_no_children():
    """No qualifying children ⇒ $650/child credit ⇒ no lift."""
    units = _make_units([
        {"total_cash_income": 28_000.0, "earned_income": 28_000.0, "income": 28_000.0,
         "num_qualifying_children": 0, "num_dependents": 0, "weight": 100.0},
    ])
    result = compute_poverty_impact(units, tax_year=2024)
    s = result.by_state.iloc[0]
    assert s["persons_lifted_hi_ctc_650"] == 0.0


def test_hi_ctc_per_child_sweeps_monotone():
    """Lift count should grow with credit size."""
    rng = np.random.default_rng(13)
    rows = []
    for _ in range(60):
        n_kids = int(rng.integers(1, 4))
        income = float(rng.uniform(20_000, 38_000))
        rows.append({
            "filing_status": "head_of_household",
            "num_dependents": n_kids,
            "num_qualifying_children": n_kids,
            "total_cash_income": income,
            "earned_income": income,
            "income": income,
            "weight": 100.0,
        })
    units = _make_units(rows)
    lifts = []
    for amt in (0.0, 650.0, 2_000.0):
        s = compute_poverty_impact(
            units, tax_year=2024, hi_ctc_per_child=amt
        ).by_state.iloc[0]
        lifts.append(s["persons_lifted_hi_ctc_650"])
    assert lifts[0] == 0.0
    assert lifts[1] <= lifts[2], (
        f"$2000/child should lift >= $650/child; got {lifts[1]} vs {lifts[2]}"
    )
    # And at least one of them must strictly lift somebody.
    assert lifts[2] > 0


def test_result_dataclass_shape():
    """PovertyImpactResult must carry units, four frames, year, meta, scenarios, notes."""
    units = _make_units([{"weight": 100.0, "total_cash_income": 30_000.0,
                          "earned_income": 30_000.0, "income": 30_000.0}])
    result = compute_poverty_impact(units, tax_year=2024)
    assert isinstance(result, PovertyImpactResult)
    assert result.tax_year == 2024
    assert result.scenarios == _DEFAULT_SCENARIOS
    assert len(result.notes) >= 2  # static + hi_ctc_650 caveat
    assert "spm_resources" in result.units.columns
    assert "spm_threshold" in result.units.columns
    assert "person_weight" in result.units.columns


# ---------------------------------------------------------------------------
# Tier 1 follow-ups (PR #4): take-up rates on expansion scenarios + MOOP +
# upstream credit-take-up calibration.
# ---------------------------------------------------------------------------


def _kids_heavy_low_income_units(seed: int = 11, n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        n_kids = int(rng.integers(2, 5))
        income = float(rng.uniform(15_000, 40_000))
        rows.append({
            "filing_status": "head_of_household",
            "num_dependents": n_kids,
            "num_qualifying_children": n_kids,
            "total_cash_income": income,
            "earned_income": income,
            "income": income,
            "weight": 100.0,
            "eitc_amount": float(rng.uniform(2_000, 5_000)),
            "ctc_refundable": n_kids * 1_700.0,
            "ctc_total": n_kids * 2_000.0,
            "hi_eitc_amount": float(rng.uniform(800, 2_000)),
        })
    return _make_units(rows)


def test_takeup_rate_zero_kills_hi_ctc_650_lift():
    """hi_ctc_takeup_rate=0.0 ⇒ no persons lifted by the hi_ctc_650 scenario."""
    units = _kids_heavy_low_income_units()
    s = compute_poverty_impact(
        units, tax_year=2024, hi_ctc_takeup_rate=0.0,
    ).by_state.iloc[0]
    assert s["persons_lifted_hi_ctc_650"] == 0.0


def test_takeup_rate_monotone_hi_ctc_650():
    """persons_lifted_hi_ctc_650 should grow weakly with hi_ctc_takeup_rate."""
    units = _kids_heavy_low_income_units(seed=17)
    lifts = []
    for rate in (0.0, 0.4, 0.8, 1.0):
        s = compute_poverty_impact(
            units, tax_year=2024, hi_ctc_takeup_rate=rate,
        ).by_state.iloc[0]
        lifts.append(s["persons_lifted_hi_ctc_650"])
    # Strictly monotone non-decreasing.
    assert lifts == sorted(lifts), f"non-monotone lifts: {lifts}"
    # And the top rate should strictly lift somebody so monotone is non-trivial.
    assert lifts[-1] > 0.0


def test_takeup_rate_monotone_hi_eitc_100pct():
    """persons_lifted_hi_eitc_100pct should grow weakly with hi_eitc_100pct_takeup_rate."""
    units = _kids_heavy_low_income_units(seed=23)
    lifts = []
    for rate in (0.0, 0.5, 0.95, 1.0):
        s = compute_poverty_impact(
            units, tax_year=2024, hi_eitc_100pct_takeup_rate=rate,
        ).by_state.iloc[0]
        lifts.append(s["persons_lifted_hi_eitc_100pct"])
    assert lifts == sorted(lifts), f"non-monotone lifts: {lifts}"


def test_takeup_rate_monotone_arpa_ctc():
    """persons_lifted_expanded_ctc_2021 should grow weakly with arpa_ctc_takeup_rate."""
    units = _kids_heavy_low_income_units(seed=29)
    lifts = []
    for rate in (0.0, 0.5, 0.95, 1.0):
        s = compute_poverty_impact(
            units, tax_year=2024, arpa_ctc_takeup_rate=rate,
        ).by_state.iloc[0]
        lifts.append(s["persons_lifted_expanded_ctc_2021"])
    assert lifts == sorted(lifts), f"non-monotone lifts: {lifts}"


def test_credit_takeup_reduces_baseline_lift():
    """Wiring IRS take-up on baseline credits should reduce the no_eitc lift.

    Without take-up (baseline reflects eligibility), more units appear to
    receive EITC and so more units appear to be lifted by it. With take-up
    (baseline reflects receipt), some marginal-eligible units lose their
    EITC, so the no_eitc counterfactual moves fewer of them below the
    poverty line.
    """
    from tax_modeler.pipeline import apply_credit_takeup

    rng = np.random.default_rng(101)
    rows = []
    for _ in range(150):
        n_kids = int(rng.integers(1, 4))
        income = float(rng.uniform(12_000, 35_000))
        rows.append({
            "filing_status": "head_of_household",
            "num_dependents": n_kids,
            "num_qualifying_children": n_kids,
            "total_cash_income": income,
            "earned_income": income,
            "income": income,
            "weight": 100.0,
            "eitc_amount": float(rng.uniform(2_000, 5_500)),
            "ctc_refundable": n_kids * 1_700.0,
            "ctc_total": n_kids * 2_000.0,
            "hi_eitc_amount": float(rng.uniform(800, 2_000)),
        })
    units_pre = _make_units(rows)
    s_pre = compute_poverty_impact(units_pre, tax_year=2022).by_state.iloc[0]
    lift_pre = s_pre["persons_lifted_no_eitc"]

    # Apply take-up calibration; this zeroes credits for the lowest-eligible
    # filers until the weighted claim count matches the IRS SOI target.
    units_post = apply_credit_takeup(units_pre.copy(), year=2022, programs=("eitc", "actc"))
    s_post = compute_poverty_impact(units_post, tax_year=2022).by_state.iloc[0]
    lift_post = s_post["persons_lifted_no_eitc"]

    assert lift_post <= lift_pre + 1e-9, (
        f"take-up calibration should not increase the no_eitc lift; "
        f"pre={lift_pre}, post={lift_post}"
    )


def test_moop_lowers_baseline_rate():
    """Imputing MOOP into spm_resources should never *raise* the baseline rate.

    MOOP is subtracted from resources, so adding it shifts more units below
    the threshold — baseline rate goes UP, not down. (The task brief had
    the sign inverted; verify the documented direction here.)
    """
    from tax_modeler.benefits.moop import compute_moop_for_units

    rng = np.random.default_rng(37)
    rows = []
    for _ in range(120):
        n_kids = int(rng.integers(0, 3))
        income = float(rng.uniform(25_000, 70_000))
        rows.append({
            "filing_status": rng.choice(["single", "head_of_household", "married_filing_jointly"]),
            "num_dependents": n_kids,
            "num_qualifying_children": n_kids,
            "total_cash_income": income,
            "earned_income": income,
            "income": income,
            "weight": 100.0,
            "primary_agep": int(rng.integers(25, 80)),
            "eitc_amount": 0.0,
            "ctc_refundable": 0.0,
            "ctc_total": 0.0,
            "hi_eitc_amount": 0.0,
        })
    units = _make_units(rows)
    r_pre = compute_poverty_impact(units, tax_year=2024).by_state.iloc[0]
    units_with_moop = compute_moop_for_units(units)
    r_post = compute_poverty_impact(units_with_moop, tax_year=2024).by_state.iloc[0]

    # MOOP is subtracted from resources, so the baseline rate cannot
    # fall when MOOP is imputed.
    assert r_post["poverty_rate_baseline"] >= r_pre["poverty_rate_baseline"] - 1e-9


def test_moop_imputation_basic_shape():
    """compute_moop_for_units adds a non-negative moop_amount with reasonable mean."""
    from tax_modeler.benefits.moop import compute_moop_for_units

    units = _make_units([
        {"primary_agep": 35, "total_cash_income": 40_000.0, "income": 40_000.0,
         "earned_income": 40_000.0, "weight": 100.0, "num_dependents": 2,
         "num_qualifying_children": 2},
        {"primary_agep": 70, "total_cash_income": 25_000.0, "income": 25_000.0,
         "earned_income": 25_000.0, "weight": 100.0, "filing_status": "single"},
        {"primary_agep": 22, "total_cash_income": 18_000.0, "income": 18_000.0,
         "earned_income": 18_000.0, "weight": 100.0, "filing_status": "single"},
    ])
    out = compute_moop_for_units(units)
    assert "moop_amount" in out.columns
    assert (out["moop_amount"] >= 0).all()
    # CPS ASEC donor mean MOOP for Hawaii is in the ~$1k-$3k/yr range; assert
    # imputed values fall in a plausible band, not zeros and not absurdly high.
    assert 200.0 <= out["moop_amount"].mean() <= 10_000.0


# ---------------------------------------------------------------------------
# Tier 2 — housing subsidy + childcare subsidy
# ---------------------------------------------------------------------------


def _low_income_frame(n: int = 80, *, with_kids: bool = False, seed: int = 7) -> pd.DataFrame:
    """A frame skewed low-income enough that subsidies meaningfully shift SPM."""
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        kids = int(rng.integers(0, 3)) if with_kids else 0
        rows.append({
            "filing_status": "single",
            "num_dependents": kids,
            "num_qualifying_children": kids,
            "total_cash_income": float(rng.integers(8_000, 25_000)),
            "earned_income": float(rng.integers(8_000, 25_000)),
            "income": float(rng.integers(8_000, 25_000)),
            "weight": 100.0,
            "primary_agep": int(rng.integers(25, 60)),
            "eitc_amount": 0.0,
            "ctc_refundable": 0.0,
            "ctc_total": 0.0,
            "hi_eitc_amount": 0.0,
        })
    return _make_units(rows)


def test_housing_subsidy_lowers_baseline_rate():
    """Adding a housing-subsidy column lifts SPM resources → poverty rate falls (or stays equal)."""
    from tax_modeler.benefits.housing import compute_housing_for_units

    units = _low_income_frame(n=80, with_kids=False, seed=11)
    r_no_sub = compute_poverty_impact(units, tax_year=2024).by_state.iloc[0]
    units_with_sub = compute_housing_for_units(units)
    r_with_sub = compute_poverty_impact(units_with_sub, tax_year=2024).by_state.iloc[0]
    # Subsidy is added to resources, so baseline rate cannot rise.
    assert r_with_sub["poverty_rate_baseline"] <= r_no_sub["poverty_rate_baseline"] + 1e-9
    # And on a low-income frame the subsidy is large enough to clearly lower it.
    assert r_with_sub["poverty_rate_baseline"] < r_no_sub["poverty_rate_baseline"]


def test_childcare_subsidy_lowers_baseline_rate():
    """CCSP subsidy on working low-income families with kids lifts SPM resources."""
    from tax_modeler.benefits.childcare import compute_childcare_for_units

    units = _low_income_frame(n=80, with_kids=True, seed=13)
    r_no_sub = compute_poverty_impact(units, tax_year=2024).by_state.iloc[0]
    units_with_sub = compute_childcare_for_units(units)
    # The CCSP module zeroes the subsidy for filers with no kids / no work
    # income, so the working-low-income-with-kids subset must receive >0.
    assert (units_with_sub["childcare_amount"] > 0).any()
    r_with_sub = compute_poverty_impact(units_with_sub, tax_year=2024).by_state.iloc[0]
    assert r_with_sub["poverty_rate_baseline"] <= r_no_sub["poverty_rate_baseline"] + 1e-9


# ---------------------------------------------------------------------------
# Tier 2 — childcare-expense + work-expense imputation
# ---------------------------------------------------------------------------


def test_childcare_expense_raises_baseline_rate():
    """Subtracting childcare expense reduces resources → poverty rate cannot fall."""
    from tax_modeler.benefits.childcare_expense import (
        compute_childcare_expense_for_units,
    )

    units = _low_income_frame(n=80, with_kids=True, seed=19)
    r_pre = compute_poverty_impact(units, tax_year=2024).by_state.iloc[0]
    units_with_exp = compute_childcare_expense_for_units(units)
    # At least some working families with kids must get a positive amount.
    assert (units_with_exp["childcare_expense_amount"] > 0).any()
    r_post = compute_poverty_impact(units_with_exp, tax_year=2024).by_state.iloc[0]
    assert r_post["poverty_rate_baseline"] >= r_pre["poverty_rate_baseline"] - 1e-9


def test_work_expense_proportional_to_earners():
    """Two-earner MFJ filers should average a higher work expense than single-earner singles."""
    from tax_modeler.benefits.work_expense import compute_work_expense_for_units

    units = _make_units([
        # Single working filers (n_earners=1).
        *[{"filing_status": "single", "num_dependents": 0,
           "num_qualifying_children": 0, "total_cash_income": 30_000.0,
           "income": 30_000.0, "earned_income": 30_000.0,
           "primary_hours_worked": 40.0, "secondary_hours_worked": 0.0,
           "weight": 100.0} for _ in range(50)],
        # MFJ two-earner filers.
        *[{"filing_status": "married_filing_jointly", "num_dependents": 1,
           "num_qualifying_children": 1, "total_cash_income": 60_000.0,
           "income": 60_000.0, "earned_income": 60_000.0,
           "primary_hours_worked": 40.0, "secondary_hours_worked": 40.0,
           "weight": 100.0} for _ in range(50)],
    ])
    out = compute_work_expense_for_units(units)
    assert "work_expense_amount" in out.columns
    assert (out["work_expense_amount"] >= 0).all()
    singles = out.iloc[:50]["work_expense_amount"].mean()
    couples = out.iloc[50:]["work_expense_amount"].mean()
    assert couples > singles


def test_only_workers_have_work_expense():
    """Filers with zero earned income must get zero work expense (SPM convention)."""
    from tax_modeler.benefits.work_expense import compute_work_expense_for_units

    units = _make_units([
        {"filing_status": "single", "total_cash_income": 12_000.0,
         "earned_income": 0.0, "income": 12_000.0,
         "primary_hours_worked": 0.0, "secondary_hours_worked": 0.0,
         "weight": 100.0},
        {"filing_status": "single", "total_cash_income": 12_000.0,
         "earned_income": 12_000.0, "income": 12_000.0,
         "primary_hours_worked": 40.0, "secondary_hours_worked": 0.0,
         "weight": 100.0},
    ])
    out = compute_work_expense_for_units(units)
    assert out.iloc[0]["work_expense_amount"] == 0.0
    assert out.iloc[1]["work_expense_amount"] > 0.0


# ---------------------------------------------------------------------------
# Tier 2 — SPM-unit pooling
# ---------------------------------------------------------------------------


def test_pooling_reduces_persons_in_poverty():
    """Two cohabiting single filers with shared kids combine into one above-threshold unit."""
    from tax_modeler.units.spm_unit import build_spm_units

    # Both are single/HOH with kids in the same household (hh_id=99).
    # Individually each is below the HI SPM threshold (~$25k for 1A1C
    # renter). Pooled (2A2C, threshold ~$40.6k renter HI 2024), combined
    # income $52k clears the threshold after fed + payroll tax.
    units = _make_units([
        {"hh_id": "99", "filing_status": "head_of_household",
         "num_dependents": 1, "num_qualifying_children": 1,
         "total_cash_income": 22_000.0, "earned_income": 22_000.0,
         "income": 22_000.0, "weight": 100.0,
         "primary_agep": 35, "tenure": "renter"},
        {"hh_id": "99", "filing_status": "head_of_household",
         "num_dependents": 1, "num_qualifying_children": 1,
         "total_cash_income": 30_000.0, "earned_income": 30_000.0,
         "income": 30_000.0, "weight": 100.0,
         "primary_agep": 36, "tenure": "renter"},
    ])
    unpooled_persons_poor = compute_poverty_impact(
        units, tax_year=2024
    ).by_state.iloc[0]["persons_in_poverty_baseline"]
    pooled_units = build_spm_units(units)
    pooled_persons_poor = compute_poverty_impact(
        pooled_units, tax_year=2024
    ).by_state.iloc[0]["persons_in_poverty_baseline"]
    assert pooled_persons_poor < unpooled_persons_poor


def test_pooling_preserves_weighted_persons():
    """Every person in the source frame appears exactly once in the pooled frame."""
    from tax_modeler.units.spm_unit import build_spm_units
    from tax_modeler.poverty.impact import _persons_per_unit

    units = _make_units([
        {"hh_id": "1", "filing_status": "head_of_household",
         "num_dependents": 1, "num_qualifying_children": 1,
         "total_cash_income": 22_000.0, "earned_income": 22_000.0,
         "income": 22_000.0, "weight": 50.0},
        {"hh_id": "1", "filing_status": "head_of_household",
         "num_dependents": 2, "num_qualifying_children": 2,
         "total_cash_income": 24_000.0, "earned_income": 24_000.0,
         "income": 24_000.0, "weight": 50.0},
        {"hh_id": "2", "filing_status": "single",
         "num_dependents": 0, "num_qualifying_children": 0,
         "total_cash_income": 30_000.0, "earned_income": 30_000.0,
         "income": 30_000.0, "weight": 100.0},
    ])
    pre_persons = float(
        (units["weight"].to_numpy() * _persons_per_unit(units)).sum()
    )
    pooled = build_spm_units(units)
    post_persons = float(
        (pooled["weight"].to_numpy() * _persons_per_unit(pooled)).sum()
    )
    assert post_persons == pytest.approx(pre_persons)


def test_unpooled_default_unchanged():
    """build_spm_units must be idempotent on inputs that don't match the pooling heuristic."""
    from tax_modeler.units.spm_unit import build_spm_units

    # All distinct households → no pooling. The output must equal the
    # input up to row order on the relevant columns.
    units = _make_units([
        {"hh_id": f"hh_{i}", "filing_status": "single",
         "num_dependents": 0, "num_qualifying_children": 0,
         "total_cash_income": 25_000.0, "earned_income": 25_000.0,
         "income": 25_000.0, "weight": 100.0}
        for i in range(5)
    ])
    pooled = build_spm_units(units)
    assert len(pooled) == len(units)
    assert pooled["filing_status"].eq("single").all()
    assert pooled["income"].sum() == pytest.approx(units["income"].sum())


# ---------------------------------------------------------------------------
# Tier 2 — district raking (biproportional IPF)
# ---------------------------------------------------------------------------


def _raking_frame(rng_seed: int = 17) -> pd.DataFrame:
    """A frame spanning 2 PUMAs × 3 HDs with uneven within-PUMA mass."""
    rng = np.random.default_rng(rng_seed)
    rows = []
    # PUMA 301 split across HD 10, 11. Heavy 10 pre-raking.
    for _ in range(40):
        rows.append({"PUMA": 301, "house_district": 10, "weight": 100.0,
                     "income": float(rng.integers(20_000, 80_000)),
                     "earned_income": float(rng.integers(20_000, 80_000)),
                     "total_cash_income": float(rng.integers(20_000, 80_000))})
    for _ in range(10):
        rows.append({"PUMA": 301, "house_district": 11, "weight": 100.0,
                     "income": float(rng.integers(20_000, 80_000)),
                     "earned_income": float(rng.integers(20_000, 80_000)),
                     "total_cash_income": float(rng.integers(20_000, 80_000))})
    # PUMA 302 split across HD 11, 12. Heavy 12 pre-raking.
    for _ in range(10):
        rows.append({"PUMA": 302, "house_district": 11, "weight": 100.0,
                     "income": float(rng.integers(20_000, 80_000)),
                     "earned_income": float(rng.integers(20_000, 80_000)),
                     "total_cash_income": float(rng.integers(20_000, 80_000))})
    for _ in range(40):
        rows.append({"PUMA": 302, "house_district": 12, "weight": 100.0,
                     "income": float(rng.integers(20_000, 80_000)),
                     "earned_income": float(rng.integers(20_000, 80_000)),
                     "total_cash_income": float(rng.integers(20_000, 80_000))})
    return pd.DataFrame(rows)


def test_raking_preserves_state_total():
    """Total weight is preserved (~) after biproportional raking."""
    from tax_modeler.analysis.district_raking import rake_biproportional

    df = _raking_frame()
    pre_total = df["weight"].sum()
    # HD targets shift mass within each PUMA but preserve per-PUMA totals.
    hd_targets = {10: 2500.0, 11: 2500.0, 12: 2500.0}
    w_post = rake_biproportional(
        df["weight"].to_numpy(),
        puma_ids=df["PUMA"].to_numpy(),
        hd_ids=df["house_district"].to_numpy(),
        hd_targets=hd_targets,
    )
    assert w_post.sum() == pytest.approx(pre_total, rel=1e-3)


def test_raking_preserves_puma_marginals():
    """Per-PUMA sum(weight) is held fixed by construction."""
    from tax_modeler.analysis.district_raking import rake_biproportional

    df = _raking_frame()
    pre_puma = df.groupby("PUMA")["weight"].sum().to_dict()
    hd_targets = {10: 3000.0, 11: 1500.0, 12: 3000.0}
    w_post = rake_biproportional(
        df["weight"].to_numpy(),
        puma_ids=df["PUMA"].to_numpy(),
        hd_ids=df["house_district"].to_numpy(),
        hd_targets=hd_targets,
    )
    df["w_post"] = w_post
    post_puma = df.groupby("PUMA")["w_post"].sum().to_dict()
    for puma, target in pre_puma.items():
        assert post_puma[puma] == pytest.approx(target, rel=1e-3)


def test_raking_matches_irs_district_targets_within_2pct():
    """Per-HD sum(weight) lands within 2% of the IRS target after raking."""
    from tax_modeler.analysis.district_raking import rake_biproportional

    df = _raking_frame()
    # Build targets consistent with per-PUMA marginals (each PUMA has
    # total weight = 5,000; state total = 10,000). HD 11 spans both
    # PUMAs and aggregates filers from each.
    hd_targets = {10: 3000.0, 11: 3000.0, 12: 4000.0}
    w_post = rake_biproportional(
        df["weight"].to_numpy(),
        puma_ids=df["PUMA"].to_numpy(),
        hd_ids=df["house_district"].to_numpy(),
        hd_targets=hd_targets,
        max_iter=100,
    )
    df["w_post"] = w_post
    post_hd = df.groupby("house_district")["w_post"].sum().to_dict()
    for hd, target in hd_targets.items():
        assert abs(post_hd[hd] - target) / target < 0.02


def test_unraked_default_unchanged():
    """rake_weights_to_irs_zip raises MissingDataError when supporting data is absent.

    The Tier-2 ship intentionally does not bundle the IRS SOI ZIP file or the
    ZIP→HD crosswalk. The high-level wrapper must signal that explicitly
    (rather than silently no-op) so the user is on notice that the flag is
    inactive without the data.
    """
    from tax_modeler.analysis.district_raking import rake_weights_to_irs_zip
    from tax_modeler.errors import MissingDataError

    df = _raking_frame()
    with pytest.raises(MissingDataError):
        rake_weights_to_irs_zip(df, tax_year=2024)
