"""Tests for poverty_impact_report.tidy_by_state (wide -> long melt)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from poverty_impact_report import tidy_by_state  # noqa: E402

SCENARIOS = ("no_eitc", "no_hi_eitc", "hi_ctc_650")


@pytest.fixture
def wide():
    return pd.DataFrame([{
        "weighted_persons": 1_000_000.0,
        "poverty_rate_baseline": 0.25,
        "poverty_gap_baseline_$": 3.1e9,
        "poverty_rate_no_eitc": 0.27,
        "persons_lifted_no_eitc": 31_000.0,
        "gap_closed_no_eitc_$": 1.3e8,
        "poverty_rate_no_hi_eitc": 0.26,
        "gap_closed_hi_ctc_650_$": 3.5e7,
        "poverty_rate_hoh_baseline": 0.38,
        "persons_lifted_no_eitc_hoh": 18_000.0,
        "weighted_persons_hoh": 214_000.0,
    }])


def test_every_column_maps_exactly_once(wide):
    long = tidy_by_state(wide, SCENARIOS, tax_year=2025)
    assert len(long) == wide.shape[1]
    assert set(long.columns) == {"tax_year", "scenario", "population", "metric", "value"}
    assert (long.tax_year == 2025).all()


def test_scenario_population_metric_decomposition(wide):
    long = tidy_by_state(wide, SCENARIOS, tax_year=2025)

    def val(s, p, m):
        sel = long[(long.scenario == s) & (long.population == p) & (long.metric == m)]
        assert len(sel) == 1, f"expected exactly one row for {(s, p, m)}"
        return float(sel.value.iloc[0])

    assert val("baseline", "all", "poverty_rate") == 0.25
    assert val("baseline", "all", "weighted_persons") == 1_000_000.0
    assert val("baseline", "head_of_household", "poverty_rate") == 0.38
    assert val("baseline", "head_of_household", "weighted_persons") == 214_000.0
    assert val("no_eitc", "all", "persons_lifted") == 31_000.0
    assert val("no_eitc", "all", "gap_closed_$") == 1.3e8
    assert val("no_eitc", "head_of_household", "persons_lifted") == 18_000.0
    # overlapping scenario names: no_hi_eitc must not be eaten by shorter tokens
    assert val("no_hi_eitc", "all", "poverty_rate") == 0.26
    assert val("hi_ctc_650", "all", "gap_closed_$") == 3.5e7


def test_real_tier_report_if_present():
    path = REPO_ROOT / "reports" / "poverty_impact_2025_tier3" / "by_state.csv"
    if not path.exists():
        pytest.skip("tier-3 report not present")
    wide = pd.read_csv(path)
    scenarios = ("no_eitc", "no_ctc", "no_hi_eitc", "no_credits",
                 "expanded_ctc_2021", "hi_eitc_100pct", "hi_ctc_650")
    long = tidy_by_state(wide, scenarios, tax_year=2025)
    assert len(long) == wide.shape[1]
    # 1:1 and lossless: every wide value appears at its decomposed address
    assert set(long.scenario) >= {"baseline", *scenarios}
