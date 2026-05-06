"""Tests for cbo_aging: per-component CBO Outlook filer aging."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tax_modeler.calibration.cbo_aging import (
    CBO_COMPONENTS,
    DEFAULT_HAWAII_FACTORS,
    CBOComponentRates,
    age_filers_with_components,
    load_cbo_rates,
)


@pytest.fixture(scope="module")
def cbo_csv_present(repo_data_dir: Path) -> Path:
    csv = repo_data_dir / "cbo" / "cbo_components_2025-01.csv"
    if not csv.exists():
        pytest.skip(f"CBO rates CSV not present at {csv}")
    return csv


@pytest.fixture(scope="module")
def cbo_rates(cbo_csv_present: Path) -> CBOComponentRates:
    return load_cbo_rates(vintage="2025-01", csv_path=cbo_csv_present)


def test_load_cbo_rates_has_all_components(cbo_rates: CBOComponentRates):
    expected_components = {"wages", "proprietors", "business", "capital_gains",
                           "dividends", "interest", "retirement", "other"}
    assert set(cbo_rates.factors.keys()) == expected_components


def test_cbo_base_year_factor_is_one(cbo_rates: CBOComponentRates):
    for component, years in cbo_rates.factors.items():
        assert abs(years[2022] - 1.0) < 1e-6, (
            f"{component} 2022 factor should be 1.0, got {years[2022]}"
        )


def test_cbo_factors_monotonically_increase(cbo_rates: CBOComponentRates):
    """Each component's growth factor should grow year-over-year (no negative)."""
    for component, years in cbo_rates.factors.items():
        ys = sorted(years.keys())
        for i in range(1, len(ys)):
            assert years[ys[i]] >= years[ys[i - 1]], (
                f"{component}: {ys[i - 1]}={years[ys[i - 1]]:.3f} > "
                f"{ys[i]}={years[ys[i]]:.3f}"
            )


def test_capital_gains_grows_faster_than_wages(cbo_rates: CBOComponentRates):
    """The CG-vs-wages differential is the whole reason for component aging."""
    cg_2027 = cbo_rates.factor("capital_gains", 2027)
    wages_2027 = cbo_rates.factor("wages", 2027)
    assert cg_2027 > wages_2027, (
        f"CG should grow faster than wages by 2027: CG={cg_2027:.3f}, "
        f"wages={wages_2027:.3f}"
    )


def _make_units(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    inc = rng.uniform(50_000, 250_000, n)
    return pd.DataFrame({
        "income": inc,
        "agi": inc,
        "weight": np.full(n, 50.0),
        "filing_status": rng.choice(
            ["single", "married_filing_jointly", "head_of_household"], n,
        ),
        "primary_wagp": inc * 0.70,
        "primary_intp": inc * 0.05,
        "primary_div": inc * 0.03,
        "primary_retp": inc * 0.05,
        "primary_ssp_full": inc * 0.05,
        "primary_semp": inc * 0.10,
        "synthetic_cg_share": np.full(n, 0.02),
    })


def test_age_filers_grows_aggregate_income(cbo_rates: CBOComponentRates):
    units = _make_units()
    pre = (units["income"] * units["weight"]).sum()
    # Test pure CBO aging without HI calibration — sanity-check the engine,
    # not the HI factor magnitudes (those have a separate test).
    aged = age_filers_with_components(
        units, target_year=2027, base_year=2022, cbo_rates=cbo_rates,
        hawaii_factors={c: 1.0 for c in CBO_COMPONENTS},
    )
    post = (aged["income"] * aged["weight"]).sum()
    # 5-year aging at CBO national rates (~4-5% wages, ~5% CG) should grow
    # aggregate by 22-30% on a wage-heavy filer mix.
    growth = post / pre - 1
    assert 0.20 < growth < 0.32, (
        f"5-year pure-CBO growth {growth:.1%} outside 20-32% sanity band"
    )


def test_per_component_columns_emitted(cbo_rates: CBOComponentRates):
    units = _make_units()
    aged = age_filers_with_components(units, target_year=2027, cbo_rates=cbo_rates)
    for comp in ("wages", "capital_gains", "business", "dividends",
                 "interest", "retirement", "other"):
        col = f"cbo_aged_{comp}"
        assert col in aged.columns, f"missing {col}"


def test_hawaii_factors_reduce_growth(cbo_rates: CBOComponentRates):
    units = _make_units()
    no_hi = age_filers_with_components(
        units, target_year=2027, cbo_rates=cbo_rates,
        hawaii_factors={c: 1.0 for c in CBO_COMPONENTS},
    )
    with_hi = age_filers_with_components(
        units, target_year=2027, cbo_rates=cbo_rates,
        hawaii_factors=DEFAULT_HAWAII_FACTORS,
    )
    no_hi_total = (no_hi["income"] * no_hi["weight"]).sum()
    with_hi_total = (with_hi["income"] * with_hi["weight"]).sum()
    # HI factors are mostly < 1, so HI-calibrated aging should produce less growth
    assert with_hi_total < no_hi_total, (
        f"HI calibration should reduce growth: no_hi={no_hi_total:.0f}, "
        f"with_hi={with_hi_total:.0f}"
    )


def test_round_trip_to_base_year_preserves_income(cbo_rates: CBOComponentRates):
    units = _make_units()
    pre = (units["income"] * units["weight"]).sum()
    aged = age_filers_with_components(
        units, target_year=2022, base_year=2022, cbo_rates=cbo_rates,
        hawaii_factors={c: 1.0 for c in CBO_COMPONENTS},
    )
    post = (aged["income"] * aged["weight"]).sum()
    # Some drift acceptable due to PUMS decomposition rounding (other component
    # absorbs residual). Within 1% is fine.
    assert abs(post / pre - 1) < 0.01, (
        f"Base-year round-trip drift {post/pre - 1:.4f} > 1%"
    )


def test_synthetic_cg_share_refreshed_after_aging(cbo_rates: CBOComponentRates):
    """After component aging, synthetic_cg_share must reflect post-aged composition.

    A filer starting at 60% CG / 40% wages will have a different CG share after
    CBO aging because CG and wages grow at different rates. The share should
    shift by more than 0.5pp over 9 years (2022→2031).
    """
    # One $5M filer: 60% CG, 40% wages; no PUMS columns so decomposition
    # falls back to synthetic_cg_share and synthetic_wages_share for CG/wages.
    df = pd.DataFrame({
        "income": [5_000_000.0],
        "agi": [5_000_000.0],
        "weight": [1.0],
        "filing_status": ["married_filing_jointly"],
        "synthetic_cg_share": [0.60],
        # No primary_wagp etc. — forces synthetic-share path.
    })
    aged = age_filers_with_components(
        df, target_year=2031, base_year=2022, cbo_rates=cbo_rates,
        hawaii_factors={c: 1.0 for c in CBO_COMPONENTS},
    )
    new_share = float(aged["synthetic_cg_share"].iloc[0])
    # CG and wages grow at different CBO rates → share must have moved.
    assert abs(new_share - 0.60) > 0.005, (
        f"synthetic_cg_share should change after 9-yr differential CBO aging, "
        f"but moved only {abs(new_share - 0.60):.4f} (pre=0.60, post={new_share:.4f})"
    )
    # Share must remain a valid fraction.
    assert 0.0 <= new_share <= 1.0, f"share out of range: {new_share}"
