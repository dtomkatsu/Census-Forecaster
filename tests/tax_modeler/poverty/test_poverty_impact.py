"""
Tests for the poverty-impact module.

Covers:
  - SPM threshold calculation (4-person, 2022)
  - SPM resources computation
  - SPM poor flag
  - compute_poverty_impact (all 8 scenarios present)
  - Federal tax fallback rate table
  - HI EITC (Act 209, 40% of federal)
  - ARPA 2021 CTC ($3,600 under-6, $3,000 age 6-17)
  - HI EITC empirical take-up from IRS SOI 2022
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# SPM aggregation tests
# ---------------------------------------------------------------------------

from tax_modeler.poverty.spm_aggregation import (
    compute_spm_resources,
    compute_spm_threshold,
    flag_spm_poor,
    SPM_THRESHOLD_BASE_4PERSON_2022,
    SPM_HI_RPP_2022,
)


def test_spm_threshold_four_person_2022():
    """4-person 2022 Hawaii SPM threshold should be ~$36,192 (within ±5%)."""
    sizes = pd.Series([4])
    threshold = compute_spm_threshold(sizes, year=2022)
    expected = SPM_THRESHOLD_BASE_4PERSON_2022 * SPM_HI_RPP_2022  # = 36,192
    assert len(threshold) == 1
    actual = float(threshold.iloc[0])
    assert actual == pytest.approx(expected, rel=0.05), (
        f"4-person threshold {actual:.0f} not within 5% of expected {expected:.0f}"
    )


def test_spm_threshold_single_person_2022():
    """Single-person threshold should be ~52% of 4-person threshold."""
    sizes = pd.Series([1])
    threshold = compute_spm_threshold(sizes, year=2022)
    four_person = SPM_THRESHOLD_BASE_4PERSON_2022 * SPM_HI_RPP_2022
    expected_single = four_person * 0.52
    assert float(threshold.iloc[0]) == pytest.approx(expected_single, rel=0.01)


def test_spm_threshold_five_person_scales():
    """5-person threshold = 4-person × (1 + 0.15 × 1) = 1.15×."""
    sizes_4 = pd.Series([4])
    sizes_5 = pd.Series([5])
    t4 = float(compute_spm_threshold(sizes_4, year=2022).iloc[0])
    t5 = float(compute_spm_threshold(sizes_5, year=2022).iloc[0])
    assert t5 == pytest.approx(t4 * 1.15, rel=0.01)


def test_spm_resources_includes_eitc():
    """SPM resources should equal income + EITC when no taxes present."""
    df = pd.DataFrame({
        "income": [20_000.0, 30_000.0],
        "eitc_amount": [3_000.0, 0.0],
    })
    resources = compute_spm_resources(df)
    assert float(resources.iloc[0]) == pytest.approx(23_000.0)
    assert float(resources.iloc[1]) == pytest.approx(30_000.0)


def test_spm_resources_subtracts_taxes():
    """SPM resources should subtract federal and state taxes."""
    df = pd.DataFrame({
        "income": [50_000.0],
        "federal_tax_effective": [5_000.0],
        "hi_tax_liability": [2_000.0],
    })
    resources = compute_spm_resources(df)
    assert float(resources.iloc[0]) == pytest.approx(43_000.0)


def test_spm_resources_negative_eitc_ignored():
    """Negative eitc_amount should be treated as 0 (clipped to 0)."""
    df = pd.DataFrame({
        "income": [20_000.0],
        "eitc_amount": [-500.0],
    })
    resources = compute_spm_resources(df)
    assert float(resources.iloc[0]) == pytest.approx(20_000.0)


def test_flag_spm_poor_basic():
    """Poor flag: unit with resources < threshold is True; above is False."""
    # 4-person threshold at 2022 ≈ $36,192
    threshold_4p = SPM_THRESHOLD_BASE_4PERSON_2022 * SPM_HI_RPP_2022

    df = pd.DataFrame({
        "income": [threshold_4p - 1_000, threshold_4p + 1_000],
        "num_people": [4, 4],
    })
    poor = flag_spm_poor(df, year=2022)
    assert bool(poor.iloc[0]) is True, "Unit below threshold should be poor"
    assert bool(poor.iloc[1]) is False, "Unit above threshold should not be poor"


def test_flag_spm_poor_missing_size_col():
    """flag_spm_poor should default to family-size=1 if no size column present."""
    # Single threshold at 2022 ≈ $16,640 × 1.131 / 0.52 correction ... actually:
    # threshold_single = 32000 × 1.131 × 0.52 ≈ 18,819
    threshold_single = SPM_THRESHOLD_BASE_4PERSON_2022 * SPM_HI_RPP_2022 * 0.52
    df = pd.DataFrame({"income": [threshold_single - 500]})
    poor = flag_spm_poor(df, year=2022)
    assert bool(poor.iloc[0]) is True


# ---------------------------------------------------------------------------
# compute_poverty_impact tests
# ---------------------------------------------------------------------------

from tax_modeler.poverty.impact import (
    compute_poverty_impact,
    _apply_federal_tax_fallback,
    _DEFAULT_SCENARIOS,
    HI_EITC_BASE_TAKEUP,
    HI_EITC_100PCT_TAKEUP,
    ARPA_CTC_TAKEUP,
)


def _make_synthetic_tax_units(n: int = 20, seed: int = 42) -> pd.DataFrame:
    """Build a small synthetic tax-unit DataFrame for testing."""
    rng = np.random.default_rng(seed)
    # Mix of poor and non-poor units
    incomes = np.concatenate([
        rng.uniform(5_000, 30_000, n // 2),   # likely poor
        rng.uniform(40_000, 80_000, n // 2),  # likely not poor
    ])
    n_people = rng.integers(1, 6, size=n)
    n_children = np.minimum(rng.integers(0, 4, size=n), n_people - 1).clip(min=0)
    eitc_amounts = np.where(incomes < 35_000, rng.uniform(500, 4_000, size=n), 0.0)
    ctc_refundable = n_children * rng.uniform(200, 600, size=n)

    return pd.DataFrame({
        "income": incomes,
        "num_people": n_people,
        "num_children": n_children,
        "eitc_amount": eitc_amounts,
        "ctc_refundable": ctc_refundable,
        "weight": np.ones(n),
    })


def test_compute_poverty_impact_returns_all_scenarios():
    """compute_poverty_impact must return one row per default scenario."""
    df = _make_synthetic_tax_units()
    result = compute_poverty_impact(df, year=2022)
    assert set(result["scenario"]) == set(_DEFAULT_SCENARIOS)
    assert len(result) == len(_DEFAULT_SCENARIOS)


def test_compute_poverty_impact_columns():
    """Result DataFrame must have the expected columns."""
    df = _make_synthetic_tax_units()
    result = compute_poverty_impact(df, year=2022)
    required_cols = {
        "scenario", "persons_lifted", "families_lifted", "children_lifted",
        "pct_poor_baseline", "pct_poor_with_credit", "poverty_reduction_pp",
    }
    assert required_cols.issubset(set(result.columns))


def test_compute_poverty_impact_nonnegative_lifts():
    """Persons/families/children lifted should be >= 0 for all scenarios."""
    df = _make_synthetic_tax_units()
    result = compute_poverty_impact(df, year=2022)
    assert (result["persons_lifted"] >= 0).all()
    assert (result["families_lifted"] >= 0).all()
    assert (result["children_lifted"] >= 0).all()


def test_compute_poverty_impact_custom_scenario_subset():
    """Should work with a user-supplied subset of scenarios."""
    df = _make_synthetic_tax_units()
    result = compute_poverty_impact(df, scenarios=["hi_eitc", "hi_ctc_300"])
    assert set(result["scenario"]) == {"hi_eitc", "hi_ctc_300"}


def test_compute_poverty_impact_no_tax_columns():
    """Should not crash when federal_tax_effective / hi_tax_liability are absent."""
    df = pd.DataFrame({
        "income": [15_000.0, 50_000.0, 80_000.0],
        "eitc_amount": [2_000.0, 0.0, 0.0],
        "num_people": [2, 3, 4],
        "num_children": [1, 1, 2],
        "weight": [1.0, 1.0, 1.0],
    })
    result = compute_poverty_impact(df, year=2022)
    assert len(result) == len(_DEFAULT_SCENARIOS)


# ---------------------------------------------------------------------------
# Federal tax fallback rate table test
# ---------------------------------------------------------------------------


def test_federal_tax_fallback_rate_table_50k():
    """Effective rate for $50K income should be ~8.32% per SOI table."""
    df = pd.DataFrame({"income": [50_000.0]})
    fed_tax = _apply_federal_tax_fallback(df)
    assert float(fed_tax.iloc[0]) == pytest.approx(50_000 * 0.0832, rel=0.01)


def test_federal_tax_fallback_rate_table_zero():
    """$0 income should produce $0 tax."""
    df = pd.DataFrame({"income": [0.0]})
    fed_tax = _apply_federal_tax_fallback(df)
    assert float(fed_tax.iloc[0]) == pytest.approx(0.0, abs=1.0)


def test_federal_tax_fallback_rate_table_high_income():
    """$1M income should use the top bracket rate (23.16%)."""
    df = pd.DataFrame({"income": [1_000_000.0]})
    fed_tax = _apply_federal_tax_fallback(df)
    assert float(fed_tax.iloc[0]) == pytest.approx(1_000_000 * 0.2316, rel=0.01)


def test_federal_tax_fallback_vectorized():
    """Fallback should work on multi-row DataFrames without looping.

    Bracket boundaries map to the bracket they open:
      $5,000  -> [5_000, 10_000) bracket  -> rate 0.0012
      $25,000 -> [25_000, 30_000) bracket -> rate 0.0407
      $100,000 -> [100_000, 200_000) bracket -> rate 0.1233
      $500,000 -> [500_000, inf) bracket  -> rate 0.2316
    """
    incomes = [5_000, 25_000, 100_000, 500_000]
    expected_rates = [0.0012, 0.0407, 0.1233, 0.2316]
    df = pd.DataFrame({"income": incomes})
    fed_tax = _apply_federal_tax_fallback(df)
    for i, (inc, rate) in enumerate(zip(incomes, expected_rates)):
        assert float(fed_tax.iloc[i]) == pytest.approx(inc * rate, rel=0.01), (
            f"Row {i}: income={inc}, expected rate={rate}"
        )


# ---------------------------------------------------------------------------
# HI EITC (Act 209) tests
# ---------------------------------------------------------------------------

from tax_modeler.credits.hi_eitc import calculate_hi_eitc, HI_EITC_RATE


def test_hi_eitc_calculation():
    """HI EITC = 40% of federal EITC (Act 209)."""
    federal_eitc = 3_000.0
    result = calculate_hi_eitc(
        {"eitc_amount": federal_eitc, "eitc_eligible": True}
    )
    assert result["hi_eitc_eligible"] is True
    assert result["hi_eitc_amount"] == pytest.approx(federal_eitc * HI_EITC_RATE, rel=0.01)


def test_hi_eitc_rate_is_40pct():
    """Policy constant HI_EITC_RATE must equal 0.40 (Act 209)."""
    assert HI_EITC_RATE == pytest.approx(0.40, abs=1e-9)


def test_hi_eitc_no_federal_eitc():
    """If no federal EITC, HI EITC should be $0 and ineligible."""
    result = calculate_hi_eitc({"eitc_amount": 0.0})
    assert result["hi_eitc_amount"] == 0.0
    assert result["hi_eitc_eligible"] is False


def test_hi_eitc_uses_parameter_fallback():
    """calculate_hi_eitc accepts federal_eitc_amount as a fallback."""
    result = calculate_hi_eitc({}, federal_eitc_amount=2_000.0)
    assert result["hi_eitc_amount"] == pytest.approx(800.0, abs=0.01)


# ---------------------------------------------------------------------------
# ARPA 2021 CTC tests
# ---------------------------------------------------------------------------

from tax_modeler.credits.arpa_ctc import (
    calculate_arpa_ctc,
    ARPA_CTC_UNDER_6,
    ARPA_CTC_6_TO_17,
)


def _child(age: int, rel: int = 22, cit: int = 1) -> dict:
    return {"age": age, "relationship": rel, "citizenship": cit}


def test_arpa_ctc_under_6():
    """ARPA CTC for a child under 6 should be $3,600."""
    unit = {
        "filing_status": "single",
        "income": 30_000,
        "dependents": [_child(3)],
    }
    result = calculate_arpa_ctc(unit)
    assert result["arpa_ctc_total"] == pytest.approx(ARPA_CTC_UNDER_6)
    assert result["qualifying_children"] == 1


def test_arpa_ctc_6_to_17():
    """ARPA CTC for a child age 6-17 should be $3,000."""
    unit = {
        "filing_status": "single",
        "income": 30_000,
        "dependents": [_child(10)],
    }
    result = calculate_arpa_ctc(unit)
    assert result["arpa_ctc_total"] == pytest.approx(ARPA_CTC_6_TO_17)
    assert result["qualifying_children"] == 1


def test_arpa_ctc_mixed_ages():
    """ARPA CTC for two children (one under 6, one 6-17) = $3,600 + $3,000."""
    unit = {
        "filing_status": "single",
        "income": 40_000,
        "dependents": [_child(3), _child(10)],
    }
    result = calculate_arpa_ctc(unit)
    assert result["arpa_ctc_total"] == pytest.approx(6_600.0)
    assert result["qualifying_children"] == 2


def test_arpa_ctc_fully_refundable():
    """ARPA CTC is fully refundable: arpa_ctc_refundable == arpa_ctc_total."""
    unit = {
        "filing_status": "single",
        "income": 20_000,
        "dependents": [_child(5)],
    }
    result = calculate_arpa_ctc(unit)
    assert result["arpa_ctc_refundable"] == pytest.approx(result["arpa_ctc_total"])


def test_arpa_ctc_no_children():
    """No qualifying children → zero credit."""
    unit = {"filing_status": "single", "income": 50_000, "dependents": []}
    result = calculate_arpa_ctc(unit)
    assert result["arpa_ctc_total"] == 0.0
    assert result["qualifying_children"] == 0


def test_arpa_ctc_calculation():
    """Parameterized check: $3,600 for under-6 and $3,000 for 6-17."""
    assert ARPA_CTC_UNDER_6 == 3_600
    assert ARPA_CTC_6_TO_17 == 3_000


# ---------------------------------------------------------------------------
# HI EITC take-up estimation tests
# ---------------------------------------------------------------------------

from tax_modeler.calibration.hi_eitc_takeup_estimate import (
    estimate_hi_eitc_takeup,
    takeup_uncertainty_band,
    HI_EITC_SOI_CLAIMS_2022,
    HI_EITC_PUMS_ELIGIBLE_2022,
    HI_EITC_TAKEUP_EMPIRICAL,
)


def test_hi_eitc_takeup_empirical():
    """Empirical take-up = 84,010 / 120,000 ≈ 0.70."""
    computed = estimate_hi_eitc_takeup(
        soi_claims=HI_EITC_SOI_CLAIMS_2022,
        pums_eligible=HI_EITC_PUMS_ELIGIBLE_2022,
    )
    assert computed == pytest.approx(0.70, abs=0.005), (
        f"Expected ~0.70, got {computed}"
    )


def test_hi_eitc_takeup_constant_matches_computed():
    """HI_EITC_TAKEUP_EMPIRICAL constant should match the computed value."""
    computed = estimate_hi_eitc_takeup()
    assert HI_EITC_TAKEUP_EMPIRICAL == pytest.approx(computed, abs=0.005)


def test_hi_eitc_takeup_uncertainty_band_width():
    """90% CI band should be non-trivially wide (> 0.05 gap)."""
    low, high = takeup_uncertainty_band(HI_EITC_TAKEUP_EMPIRICAL)
    assert high > low
    assert (high - low) > 0.05, "Band too narrow; expect ~0.14 at 12% PUMS SE"


def test_hi_eitc_takeup_uncertainty_band_bounds():
    """Band values should be within [0, 1]."""
    low, high = takeup_uncertainty_band(0.70)
    assert 0.0 <= low <= 1.0
    assert 0.0 <= high <= 1.0


def test_hi_eitc_soi_claims_constant():
    """SOI claims constant = 84,010 (IRS SOI TY2022 Hawaii)."""
    assert HI_EITC_SOI_CLAIMS_2022 == 84_010


def test_hi_eitc_pums_eligible_constant():
    """PUMS eligible estimate = 120,000."""
    assert HI_EITC_PUMS_ELIGIBLE_2022 == 120_000


# ---------------------------------------------------------------------------
# Take-up constants tests
# ---------------------------------------------------------------------------


def test_take_up_constants():
    """Check empirical take-up constants are within reasonable bounds."""
    assert 0.0 < HI_EITC_BASE_TAKEUP <= 1.0
    assert 0.0 < HI_EITC_100PCT_TAKEUP <= 1.0
    assert 0.0 < ARPA_CTC_TAKEUP <= 1.0
    # 100% scenario rate should be >= base rate (it's for existing claimants)
    assert HI_EITC_100PCT_TAKEUP >= HI_EITC_BASE_TAKEUP
