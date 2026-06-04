"""Unit tests for the Hawaii-empirical HI EITC take-up estimator.

Covers:
  * Point estimate equals ``admin_target / weighted_eligible`` exactly.
  * SDR SE matches the canonical PUMS formula `sqrt((4/R)·Σ(τ_r-τ_0)²)`
    on a hand-computed 2-replicate fixture.
  * Graceful no-replicate fallback: ``replicate_cols=()`` returns
    ``se=0.0, n_replicates=0`` (no error).
  * Band clipping: ``band()`` clips to ``[0, 1]`` even at extremes.
  * Eligibility resolution: explicit ``eligibility_col`` overrides the
    default ``eitc_amount > 0`` signal.
  * Auto-detection of ``weight_r01..weight_r80`` columns.
  * Error handling: missing weight column / all-zero eligible raise.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tax_modeler.calibration import TakeupEstimate, estimate_hi_eitc_takeup


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _two_replicate_frame() -> pd.DataFrame:
    """Hand-computed fixture: 5 units, 3 eligible at weight 100.

    weight totals:           eligible weighted = 300
    weight_r01 inflates:     eligible weighted = 330  (τ_r1 = 240/330)
    weight_r02 deflates:     eligible weighted = 270  (τ_r2 = 240/270)
    """
    return pd.DataFrame({
        "weight":      [100.0, 100.0, 100.0, 100.0, 100.0],
        "eitc_amount": [1000.0, 0.0, 2000.0, 500.0, 0.0],
        "weight_r01":  [110.0, 110.0, 110.0, 110.0, 110.0],
        "weight_r02":  [90.0, 90.0, 90.0, 90.0, 90.0],
    })


# ---------------------------------------------------------------------------
# Point estimate
# ---------------------------------------------------------------------------

def test_point_estimate_matches_admin_over_denom():
    df = _two_replicate_frame()
    # admin=240, denom=300 → τ=0.8 exactly
    est = estimate_hi_eitc_takeup(df, admin_target=240.0)
    assert est.point == pytest.approx(240.0 / 300.0, abs=1e-9)
    assert est.denom_eligible == pytest.approx(300.0, abs=1e-9)
    assert est.admin_target == 240.0


def test_point_estimate_uses_explicit_eligibility_col():
    """``eligibility_col`` overrides the default eitc_amount > 0 signal."""
    df = pd.DataFrame({
        "weight":      [100.0, 100.0, 100.0],
        "eitc_amount": [1000.0, 0.0, 2000.0],  # would give 2 eligible by default
        "is_eligible": [True, True, False],     # but explicit signal says 2 (different ones)
    })
    est = estimate_hi_eitc_takeup(
        df, admin_target=100.0, eligibility_col="is_eligible",
    )
    # denom = 200 (rows 0 and 1)
    assert est.point == pytest.approx(0.5, abs=1e-9)


# ---------------------------------------------------------------------------
# SDR SE
# ---------------------------------------------------------------------------

def test_sdr_se_matches_hand_computed_two_replicate():
    df = _two_replicate_frame()
    est = estimate_hi_eitc_takeup(df, admin_target=240.0)
    # τ_0  = 240/300 = 0.8
    # τ_r1 = 240/330; τ_r2 = 240/270
    # V = (4/2) · ((τ_r1 - τ_0)² + (τ_r2 - τ_0)²)
    expected_se = float(np.sqrt(
        (4.0 / 2) * ((240/330 - 0.8) ** 2 + (240/270 - 0.8) ** 2)
    ))
    assert est.se == pytest.approx(expected_se, rel=1e-9)
    assert est.n_replicates == 2


def test_no_replicates_yields_zero_se():
    """Empty ``replicate_cols`` ⇒ SE=0, n=0, band collapses to point."""
    df = _two_replicate_frame().drop(columns=["weight_r01", "weight_r02"])
    est = estimate_hi_eitc_takeup(df, admin_target=240.0)
    assert est.se == 0.0
    assert est.n_replicates == 0
    low, mid, high = est.band()
    assert low == mid == high == pytest.approx(0.8, abs=1e-9)


def test_explicit_empty_replicate_cols_suppresses_sdr():
    """Passing ``replicate_cols=()`` suppresses SDR even when columns are present."""
    df = _two_replicate_frame()
    est = estimate_hi_eitc_takeup(df, admin_target=240.0, replicate_cols=())
    assert est.se == 0.0
    assert est.n_replicates == 0


def test_auto_detects_weight_r_columns():
    df = _two_replicate_frame()
    # Auto-detect picks up weight_r01 and weight_r02 (the only two present).
    est = estimate_hi_eitc_takeup(df, admin_target=240.0)
    assert est.n_replicates == 2


# ---------------------------------------------------------------------------
# Band clipping
# ---------------------------------------------------------------------------

def test_band_clips_to_zero_one():
    """band() must never return < 0 or > 1 even at extreme SE."""
    est = TakeupEstimate(
        point=0.05, se=1.0, n_replicates=10,
        admin_target=100.0, denom_eligible=2000.0,
    )
    low, mid, high = est.band(k=2.0)
    assert low == 0.0  # 0.05 - 2.0 = -1.95 → clipped to 0
    assert mid == 0.05
    assert high == 1.0  # 0.05 + 2.0 = 2.05 → clipped to 1

    est_high = TakeupEstimate(
        point=0.99, se=0.05, n_replicates=10,
        admin_target=100.0, denom_eligible=100.0,
    )
    low, _, high = est_high.band(k=2.0)
    assert low == pytest.approx(0.89, abs=1e-9)
    assert high == 1.0


def test_band_k_parameter():
    """k=1 gives ~68% band; k=2 gives ~95% band."""
    est = TakeupEstimate(
        point=0.70, se=0.05, n_replicates=80,
        admin_target=84_010.0, denom_eligible=120_000.0,
    )
    low1, mid1, high1 = est.band(k=1.0)
    low2, mid2, high2 = est.band(k=2.0)
    assert mid1 == mid2 == 0.70
    assert (high1 - low1) == pytest.approx(0.10, abs=1e-9)  # ±0.05
    assert (high2 - low2) == pytest.approx(0.20, abs=1e-9)  # ±0.10


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_to_dict_round_trips_band():
    est = TakeupEstimate(
        point=0.6970, se=0.012, n_replicates=80,
        admin_target=84_010.0, denom_eligible=120_535.0,
    )
    d = est.to_dict()
    assert d["point"] == 0.6970
    assert d["se"] == 0.012
    assert d["n_replicates"] == 80
    assert d["admin_target_year"] == 2022
    assert "IRS SOI" in d["admin_target_source"]
    assert d["band_low"] == pytest.approx(0.6730, abs=1e-9)
    assert d["band_high"] == pytest.approx(0.7210, abs=1e-9)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_raises_when_weight_col_missing():
    df = pd.DataFrame({"eitc_amount": [1000.0, 2000.0]})
    with pytest.raises(KeyError, match="weight_col"):
        estimate_hi_eitc_takeup(df, weight_col="weight")


def test_raises_when_no_eligible_units():
    """All-zero EITC ⇒ denom=0 ⇒ undefined ratio ⇒ ValueError."""
    df = pd.DataFrame({
        "weight": [100.0, 100.0],
        "eitc_amount": [0.0, 0.0],
    })
    with pytest.raises(ValueError, match="weighted-eligible denominator"):
        estimate_hi_eitc_takeup(df, admin_target=100.0)


def test_raises_when_eligibility_signal_absent():
    """No eligibility_col and no eitc_amount ⇒ KeyError with helpful message."""
    df = pd.DataFrame({"weight": [100.0, 100.0]})
    with pytest.raises(KeyError, match="neither"):
        estimate_hi_eitc_takeup(df, admin_target=100.0)


# ---------------------------------------------------------------------------
# Realistic order-of-magnitude check
# ---------------------------------------------------------------------------

def test_hawaii_realistic_point_estimate_range():
    """With realistic Hawaii-scale numbers, τ should land in [0.5, 0.95]."""
    # Synthetic ~32K Hawaii households, ~30% with positive EITC
    n = 32_000
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "weight": rng.uniform(1.0, 20.0, n),
        "eitc_amount": np.where(rng.random(n) < 0.30, 2_500.0, 0.0),
    })
    est = estimate_hi_eitc_takeup(df, admin_target=84_010.0)
    # Denom roughly = 0.30 × n × E[weight] ≈ 0.30 × 32000 × 10.5 ≈ 100,800.
    # τ ≈ 84,010 / 100,800 ≈ 0.83. Sanity check that we're in range.
    assert 0.5 < est.point < 0.95, (
        f"sanity check failed: τ = {est.point:.3f} outside [0.5, 0.95]"
    )
