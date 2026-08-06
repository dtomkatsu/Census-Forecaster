"""Tests for the DBEDT MEI fetcher (network-free)."""

from __future__ import annotations

import io
import json
from datetime import datetime

import openpyxl
import pytest

from census_forecaster.markets.screen import HAWAII_PREDICTORS, MONTHLY_TARGETS
from census_forecaster.scripts import refresh_dbedt_mei as mei


def _workbook(headers, rows) -> bytes:
    """MEI look-alike: row 3 = series names, col A = timestamps from row 5."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.cell(row=1, column=1, value="Monthly Economic Indicator")
    ws.cell(row=3, column=1, value="Series")
    for i, h in enumerate(headers):
        ws.cell(row=3, column=2 + i, value=h)
    ws.cell(row=4, column=1, value="UNIT")
    for r, (stamp, vals) in enumerate(rows):
        ws.cell(row=5 + r, column=1, value=stamp)
        for i, v in enumerate(vals):
            if v is not None:
                ws.cell(row=5 + r, column=2 + i, value=v)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


HEADERS = ["Civilian labor force 1/", "Visitor arrivals by air 2/",
           "Private Building Permits"]


def test_parses_wanted_series_only():
    out = mei.parse_mei_workbook(_workbook(HEADERS, [
        (datetime(1990, 1, 1), [400000, 555000, 120.5]),
        (datetime(1990, 2, 1), [401000, 500000, 98.0]),
    ]))
    assert set(out) == {"DBEDT_ARRIVALS_", "DBEDT_PERMITS_"}  # not labor force
    assert out["DBEDT_ARRIVALS_"][0] == {"year": 1990, "period": "M01",
                                         "value": 555000.0}
    assert out["DBEDT_PERMITS_"][1]["value"] == 98.0


def test_blank_months_skipped_not_zeroed():
    """Unpublished months (e.g. Maui arrivals after 2026-01) are blank."""
    out = mei.parse_mei_workbook(_workbook(HEADERS, [
        (datetime(2026, 1, 1), [1, 111111, 5.0]),
        (datetime(2026, 2, 1), [1, None, 6.0]),      # arrivals gap
    ]))
    assert len(out["DBEDT_ARRIVALS_"]) == 1
    assert len(out["DBEDT_PERMITS_"]) == 2


def test_non_datetime_rows_ignored():
    out = mei.parse_mei_workbook(_workbook(HEADERS, [
        ("Source: DBEDT", [None, None, None]),
        (datetime(2000, 6, 1), [1, 2.0, 3.0]),
    ]))
    assert len(out["DBEDT_ARRIVALS_"]) == 1


def test_missing_series_raises():
    with pytest.raises(ValueError, match="no wanted series"):
        mei.parse_mei_workbook(_workbook(["Something else"], [
            (datetime(2000, 1, 1), [1.0]),
        ]))


def test_discover_picks_latest_date(monkeypatch):
    html = ('href="https://files.hawaii.gov/dbedt/economic/data_reports/mei/2026-05-honolulu.xlsx"'
            'href="https://files.hawaii.gov/dbedt/economic/data_reports/mei/2026-06-honolulu.xlsx"'
            'href="https://files.hawaii.gov/dbedt/economic/data_reports/mei/2026-06-state.xlsx"')

    class _R:
        text = html
        def raise_for_status(self): pass

    monkeypatch.setattr(mei.requests, "get", lambda *a, **k: _R())
    urls = mei.discover_workbooks()
    assert urls["honolulu"].endswith("2026-06-honolulu.xlsx")   # latest wins
    assert set(urls) == {"honolulu", "state"}


def test_merge_is_additive(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"series": {"KEEP": [1]}, "sources": {},
                                "limitations": []}))
    merged = mei.merge_into_macro_monthly(
        {"DBEDT_ARRIVALS_STATEWIDE": []}, path=path)
    assert merged["series"]["KEEP"] == [1]
    assert "DBEDT_MEI" in merged["sources"]


def test_screen_repointed_to_current_series():
    """HI_VISITORS must use the DBEDT series (current through today),
    not the HTA workbook series that ends at its final year."""
    assert MONTHLY_TARGETS["HI_VISITORS"][0] == "DBEDT_ARRIVALS_STATEWIDE"
    assert HAWAII_PREDICTORS["HI_VISITORS_ARRIVALS"] == "DBEDT_ARRIVALS_STATEWIDE"
    emitted = {p + g for p in mei.SERIES.values() for g in mei.GEOS.values()}
    assert MONTHLY_TARGETS["HI_VISITORS"][0] in emitted
