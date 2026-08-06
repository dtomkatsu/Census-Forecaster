"""Tests for the DOL ETA-539 UI-claims fetcher (network-free)."""

from __future__ import annotations

import json
from datetime import date

from census_forecaster.markets.screen import HAWAII_PREDICTORS, HYPOTHESIS_PAIRS
from census_forecaster.scripts import refresh_ui_claims as ui

CSV_HEAD = '"st","rptdate","c1","c2","c3","c4","c5"\n'


def test_parses_hi_rows_only():
    text = (CSV_HEAD
            + 'HI,2026-07-25,29,2026-07-18,978,3,10\n'
            + 'CA,2026-07-25,29,2026-07-18,40000,3,10\n'
            + 'HI,2026-08-01,30,2026-07-25,1005,0,2\n')
    weekly = ui.parse_hi_weekly(text)
    assert weekly == [(date(2026, 7, 18), 978.0), (date(2026, 7, 25), 1005.0)]


def test_us_date_format_and_bad_rows():
    text = (CSV_HEAD
            + 'HI,1/8/1990,1,1/6/1990,"1,234",0,0\n'   # US date + comma value
            + 'HI,x,1,not-a-date,50,0,0\n'             # bad date -> skipped
            + 'HI,x,1,1/13/1990,abc,0,0\n'             # bad value -> skipped
            + 'HI,x,1,1/20/1990,-5,0,0\n')             # negative -> skipped
    weekly = ui.parse_hi_weekly(text)
    assert weekly == [(date(1990, 1, 6), 1234.0)]


def test_monthly_mean_not_sum():
    """4- and 5-week months must stay on the same scale."""
    weekly = [(date(2026, 1, d), 1000.0) for d in (3, 10, 17, 24, 31)]  # 5 wks
    weekly += [(date(2026, 2, d), 1000.0) for d in (7, 14, 21, 28)]     # 4 wks
    rows = ui.weekly_to_monthly_mean(weekly)
    assert rows == [
        {"year": 2026, "period": "M01", "value": 1000.0},
        {"year": 2026, "period": "M02", "value": 1000.0},
    ]


def test_month_assignment_by_week_ending():
    rows = ui.weekly_to_monthly_mean([
        (date(2026, 1, 31), 900.0),
        (date(2026, 2, 7), 1100.0),
    ])
    assert [r["period"] for r in rows] == ["M01", "M02"]


def test_merge_is_additive(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"series": {"KEEP": [1]}, "sources": {},
                                "limitations": []}))
    merged = ui.merge_into_macro_monthly(
        [{"year": 2026, "period": "M07", "value": 1033.33}], path=path)
    assert merged["series"]["KEEP"] == [1]
    assert merged["series"][ui.SERIES_ID][0]["value"] == 1033.33
    assert "DOL_ETA539" in merged["sources"]


def test_screen_wiring():
    assert HAWAII_PREDICTORS["HI_UI_CLAIMS"] == ui.SERIES_ID
    assert ("HI_UI_CLAIMS", "HI_UNEMPLOYMENT") in HYPOTHESIS_PAIRS
    assert ("HI_PAYROLLS", "HI_UNEMPLOYMENT") in HYPOTHESIS_PAIRS
    assert HAWAII_PREDICTORS["HI_PAYROLLS"] == "SMS15000000000000001"
