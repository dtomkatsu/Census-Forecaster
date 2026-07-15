"""Tests for market-signal ML features (mkt_* columns in ml_features)."""
from __future__ import annotations

import math

import pytest

from census_forecaster.acs.ml_features import (
    _CORE_COLUMNS,
    _MKT_GEOID,
    build_panel_index,
    load_market_signals_data,
    make_feature_spec,
    make_training_rows,
)
from census_forecaster.models import AcsObservation


def _obs(geoid, indicator, year, estimate):
    return AcsObservation(estimate=estimate, moe=1.0, year=year,
                          vintage="1y", geoid=geoid, indicator=indicator)


def _series(geoid="15003", indicator="B19013_001E",
            years=range(2012, 2025), base=80_000.0, growth=0.03):
    return {
        (geoid, indicator): [
            _obs(geoid, indicator, y, base * (1 + growth) ** (y - 2012))
            for y in years
        ]
    }


MARKET = {
    "mkt_energy_mom": {y: 0.10 + 0.01 * (y - 2012) for y in range(2012, 2025)},
    "mkt_shipping_mom": {y: -0.05 for y in range(2012, 2025)},
    "mkt_reit_mom": {y: 0.02 * (y - 2012) for y in range(2012, 2025)},
}

_MKT_COLS = ("mkt_energy_mom_lag0", "mkt_shipping_mom_lag0",
             "mkt_reit_mom_lag0", "mkt_reit_mom_lag1")


# ---------------------------------------------------------------------------
# Column layout
# ---------------------------------------------------------------------------

def test_mkt_columns_present_and_last_before_horizon():
    # The mkt block is the tail of _CORE_COLUMNS (order stability matters
    # for any persisted model's feature alignment).
    assert _CORE_COLUMNS[-4:] == _MKT_COLS


def test_spec_column_order_stable_with_market_data():
    series = _series()
    plain = make_feature_spec("B19013_001E", build_panel_index(series))
    with_mkt = make_feature_spec(
        "B19013_001E", build_panel_index(series, market_data=MARKET))
    assert plain.column_names == with_mkt.column_names


# ---------------------------------------------------------------------------
# Injection semantics
# ---------------------------------------------------------------------------

def test_sentinels_kept_out_of_indicators_and_geoids():
    panel = build_panel_index(_series(), market_data=MARKET)
    assert all(not i.startswith("_MKT") for i in panel.indicators)
    assert _MKT_GEOID not in panel.geoids
    assert panel.get(_MKT_GEOID, "_MKT_ENERGY_MOM", 2020) == pytest.approx(0.18)


def test_negative_momentum_values_survive_injection():
    panel = build_panel_index(_series(), market_data=MARKET)
    assert panel.get(_MKT_GEOID, "_MKT_SHIPPING_MOM", 2020) == pytest.approx(-0.05)


def test_rows_carry_market_values_geoid_constant():
    series = {**_series("15003"), **_series("15001")}
    panel = build_panel_index(series, market_data=MARKET)
    matrix = make_training_rows(panel, {"15003": 1_000_000, "15001": 200_000},
                                "B19013_001E", cutoff_year=2024)
    assert matrix.X, "no training rows built"
    cols = matrix.spec.column_names
    i_energy = cols.index("mkt_energy_mom_lag0")
    i_reit0 = cols.index("mkt_reit_mom_lag0")
    i_reit1 = cols.index("mkt_reit_mom_lag1")

    for row, (geoid, anchor, _t, _h) in zip(matrix.X, matrix.meta):
        assert row[i_energy] == pytest.approx(MARKET["mkt_energy_mom"][anchor])
        assert row[i_reit0] == pytest.approx(MARKET["mkt_reit_mom"][anchor])
        assert row[i_reit1] == pytest.approx(
            MARKET["mkt_reit_mom"][anchor - 1])

    # Geoid-constant: same anchor year → identical mkt features across counties.
    by_anchor = {}
    for row, (geoid, anchor, _t, h) in zip(matrix.X, matrix.meta):
        by_anchor.setdefault((anchor, h), []).append(row[i_energy])
    for vals in by_anchor.values():
        assert len(set(vals)) == 1


def test_rows_nan_fill_when_market_data_absent():
    panel = build_panel_index(_series())      # no market_data
    matrix = make_training_rows(panel, {"15003": 1_000_000},
                                "B19013_001E", cutoff_year=2024)
    assert matrix.X
    cols = matrix.spec.column_names
    for name in _MKT_COLS:
        i = cols.index(name)
        assert all(math.isnan(row[i]) for row in matrix.X)


def test_partial_market_coverage_nan_fills_missing_years():
    market = {"mkt_energy_mom": {2020: 0.5}}   # single year only
    panel = build_panel_index(_series(), market_data=market)
    matrix = make_training_rows(panel, {"15003": 1_000_000},
                                "B19013_001E", cutoff_year=2024)
    cols = matrix.spec.column_names
    i = cols.index("mkt_energy_mom_lag0")
    for row, (_g, anchor, _t, _h) in zip(matrix.X, matrix.meta):
        if anchor == 2020:
            assert row[i] == pytest.approx(0.5)
        else:
            assert math.isnan(row[i])


# ---------------------------------------------------------------------------
# Bundled loader (real committed file, if present)
# ---------------------------------------------------------------------------

def test_bundled_market_signals_load_and_align():
    data = load_market_signals_data()
    if data is None:
        pytest.skip("market_signals.json not yet committed")
    assert set(data) <= {"mkt_energy_mom", "mkt_shipping_mom", "mkt_reit_mom"}
    for name, by_year in data.items():
        assert by_year, name
        assert all(isinstance(y, int) for y in by_year)
        assert all(math.isfinite(v) for v in by_year.values())
        # momenta are log changes; anything beyond ±2 (≈ ±640%) is corrupt
        assert all(abs(v) < 2.0 for v in by_year.values()), name
