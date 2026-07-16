"""Tests for scripts/refresh_national_macro.py — aggregation, parse, merge.

No network: fetchers are monkeypatched.
"""
from __future__ import annotations

import json

import pytest

from census_forecaster.acs.ml_features import (
    NATIONAL_SERIES,
    national_macro_columns,
)
from census_forecaster.scripts import refresh_national_macro as script


# ---------------------------------------------------------------------------
# Registry ↔ column consistency
# ---------------------------------------------------------------------------

def test_registry_produces_19_columns():
    assert len(national_macro_columns()) == 19
    assert len(NATIONAL_SERIES) == 13


def test_every_series_has_a_known_source_and_policy():
    for s in NATIONAL_SERIES:
        assert s.source in ("CPI_PANEL", "BLS_FETCH", "FRED")
        assert s.col_policy in ("logchange1", "diff1", "level_diff1")


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def test_aggregate_to_annual_from_bls_rows():
    rows = [{"year": 2020, "period": "M01", "value": 4.0},
            {"year": 2020, "period": "M02", "value": 6.0},
            {"year": 2021, "period": "M01", "value": 5.0}]
    assert script.aggregate_to_annual(rows) == {2020: 5.0, 2021: 5.0}


def test_aggregate_to_annual_from_fred_rows():
    rows = [{"date": "2020-01-01", "value": 3.0},
            {"date": "2020-07-01", "value": 5.0},
            {"date": "2021-01-01", "value": 4.0}]
    assert script.aggregate_to_annual(rows) == {2020: 4.0, 2021: 4.0}


def test_aggregate_partial_year_is_mean_of_available():
    rows = [{"date": "2026-01-01", "value": 6.0},
            {"date": "2026-02-01", "value": 6.4}]
    assert script.aggregate_to_annual(rows) == {2026: 6.2}


def test_resample_monthly_averages_within_month():
    # weekly-ish prints, two in Jan, one in Feb
    rows = [{"date": "2020-01-03", "value": 3.0},
            {"date": "2020-01-31", "value": 3.4},
            {"date": "2020-02-07", "value": 3.8}]
    out = script.resample_monthly(rows)
    assert out == [{"year": 2020, "period": "M01", "value": 3.2},
                   {"year": 2020, "period": "M02", "value": 3.8}]


def test_resample_monthly_passes_bls_rows_through():
    rows = [{"year": 2020, "period": "M03", "value": 62.1}]
    assert script.resample_monthly(rows) == [
        {"year": 2020, "period": "M03", "value": 62.1}]


# ---------------------------------------------------------------------------
# FRED CSV parse
# ---------------------------------------------------------------------------

def test_fetch_fred_csv_parses_and_skips_missing(monkeypatch):
    csv_text = (
        "observation_date,MORTGAGE30US\n"
        "2023-01-05,6.48\n"
        "2023-01-12,.\n"          # FRED missing sentinel → dropped
        "2023-01-19,6.15\n"
        "2023-01-26,\n"           # empty → dropped
    )

    class _Resp:
        text = csv_text
        def raise_for_status(self): pass
    monkeypatch.setattr(script.requests, "get",
                        lambda url, **kw: _Resp())
    rows = script.fetch_fred_csv("MORTGAGE30US")
    assert rows == [{"date": "2023-01-05", "value": 6.48},
                    {"date": "2023-01-19", "value": 6.15}]


# ---------------------------------------------------------------------------
# CPI-panel reader
# ---------------------------------------------------------------------------

def test_read_cpi_panel_series_from_bundle():
    # The bundled panel is committed; the registry's CPI ids must resolve.
    rows = script.read_cpi_panel_series("CUUR0000SA0")
    if not rows:
        pytest.skip("cpi_panel.json not present")
    assert rows[0]["period"].startswith("M")
    assert isinstance(rows[0]["value"], (int, float))


# ---------------------------------------------------------------------------
# macro_monthly merge preserves existing keys
# ---------------------------------------------------------------------------

def test_merge_macro_monthly_preserves_existing(tmp_path, monkeypatch):
    existing = {
        "version": 1, "fetch_date": "2026-01-01",
        "series": {"LNS14000000": [{"year": 2020, "period": "M01", "value": 6.0}],
                   "ZHVI_HONOLULU_MONTHLY": [{"year": 2020, "period": "M01", "value": 8e5}]},
        "sources": {"LNS14000000": "BLS"},
        "limitations": ["existing note"],
    }
    f = tmp_path / "macro_monthly.json"
    f.write_text(json.dumps(existing))
    monkeypatch.setattr(script, "MACRO_MONTHLY_FILE", f)

    script._merge_macro_monthly(
        {"MORTGAGE30US": [{"year": 2020, "period": "M01", "value": 3.1}]})
    out = json.loads(f.read_text())
    # existing keys survive, new key added
    assert "LNS14000000" in out["series"]
    assert "ZHVI_HONOLULU_MONTHLY" in out["series"]
    assert out["series"]["MORTGAGE30US"][0]["value"] == 3.1
    assert "existing note" in out["limitations"]


# ---------------------------------------------------------------------------
# Dry-run writes nothing
# ---------------------------------------------------------------------------

def test_dry_run_no_network_no_write(monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("network during --dry-run")
    monkeypatch.setattr(script, "fetch_bls_monthly", boom)
    monkeypatch.setattr(script, "fetch_fred_csv", boom)
    rc = script.main(["--dry-run"])
    assert rc == 0
    assert "dry-run" in capsys.readouterr().err
