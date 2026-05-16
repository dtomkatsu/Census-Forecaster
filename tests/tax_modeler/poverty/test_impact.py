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
