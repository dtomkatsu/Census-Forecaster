"""Refresh DOL ETA-539 Hawaii weekly UI initial claims (→ monthly means).

Why this exists
---------------
Weekly unemployment-insurance initial claims are administrative
head-counts of new filings — the classic recession canary. They are the
**fastest labour signal in the panel**: the all-states CSV updates
weekly with roughly an 11-day lag, versus ~6 weeks for LAUS/CES. Unlike
LAUS (which is partly modelled), claims are direct counts, so they carry
genuinely independent information about labour-market turning points.

Source
------
``https://oui.doleta.gov/unemploy/csv/ar539.csv`` — keyless, all states,
weekly back to the 1980s (~13 MB). Columns are the ETA-539 report
fields: ``st`` (state), ``c2`` (reflect-week ending date), ``c3``
(state initial claims, excluding the federal programs in c4/c5).

The screen runs on a monthly grid, so weekly values are aggregated to
**calendar-month means of weekly initial claims** (mean, not sum, so
4-week and 5-week months stay comparable). The current partial month is
included — a mean of available weeks is a level, same no-peeking
posture as ``refresh_national_macro.aggregate_to_annual``.

Writes
------
``DOL_HI_INITIAL_CLAIMS`` (monthly mean of weekly IC) into
``data/markets/macro_monthly.json``, additively.

Usage
-----
    python -m census_forecaster.scripts.refresh_ui_claims --dry-run
    python -m census_forecaster.scripts.refresh_ui_claims
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Sequence

import requests

from .refresh_zillow_laus_anchors import _atomic_write_json

_PKG_DATA = Path(__file__).resolve().parent.parent / "data"
_MARKETS_DIR = _PKG_DATA / "markets"
MACRO_MONTHLY_FILE = _MARKETS_DIR / "macro_monthly.json"

ETA539_CSV = "https://oui.doleta.gov/unemploy/csv/ar539.csv"
SERIES_ID = "DOL_HI_INITIAL_CLAIMS"
STATE = "HI"


def _parse_week_ending(raw: str) -> Optional[date]:
    """c2 arrives as ISO (2026-07-18) or US (7/18/2026) depending on era."""
    raw = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_hi_weekly(text: str, *, state: str = STATE) -> list[tuple[date, float]]:
    """ETA-539 CSV text → sorted ``[(week_ending, initial_claims)]``."""
    out: list[tuple[date, float]] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        if (row.get("st") or "").strip() != state:
            continue
        week = _parse_week_ending(row.get("c2", ""))
        if week is None:
            continue
        try:
            ic = float(str(row.get("c3", "")).replace(",", "").strip())
        except (TypeError, ValueError):
            continue
        if ic < 0:
            continue
        out.append((week, ic))
    out.sort(key=lambda t: t[0])
    return out


def weekly_to_monthly_mean(weekly: Sequence[tuple[date, float]]) -> list[dict]:
    """Mean weekly initial claims per calendar month of the week-ending.

    Mean rather than sum keeps 4-week and 5-week months on the same
    scale; the partial current month is a mean of its available weeks.
    """
    by_month: dict[tuple[int, int], list[float]] = defaultdict(list)
    for week, ic in weekly:
        by_month[(week.year, week.month)].append(ic)
    rows = [{"year": y, "period": f"M{m:02d}",
             "value": round(sum(v) / len(v), 2)}
            for (y, m), v in by_month.items()]
    rows.sort(key=lambda r: (r["year"], r["period"]))
    return rows


def merge_into_macro_monthly(rows: list[dict],
                             *, path: Path = MACRO_MONTHLY_FILE) -> dict:
    if path.exists():
        with open(path) as f:
            payload = json.load(f)
    else:
        payload = {"version": 1, "series": {}, "sources": {}, "limitations": []}

    payload.setdefault("series", {})[SERIES_ID] = rows
    payload.setdefault("sources", {})["DOL_ETA539"] = (
        f"{ETA539_CSV} — weekly state UI initial claims (c3), "
        "aggregated to calendar-month means"
    )
    payload["fetch_date"] = date.today().isoformat()

    note = (
        "DOL_HI_INITIAL_CLAIMS is the calendar-month MEAN of ETA-539 "
        "weekly state initial claims (c3; excludes the federal-program "
        "counts). Administrative filings, not survey estimates; weekly "
        "source updates with ~11-day lag and back-weeks are revised. "
        "The current partial month is a mean of available weeks."
    )
    lims = payload.setdefault("limitations", [])
    if note not in lims:
        lims.append(note)
    return payload


def _parse_args(argv: Optional[Sequence[str]] = None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        resp = requests.get(ETA539_CSV, timeout=180)
        resp.raise_for_status()
        weekly = parse_hi_weekly(resp.text)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: ETA-539 fetch/parse failed: {exc}", file=sys.stderr)
        return 1

    if len(weekly) < 100:
        print(f"ERROR: only {len(weekly)} HI weeks parsed — refusing to "
              "overwrite the bundled series with a fragment.", file=sys.stderr)
        return 1

    rows = weekly_to_monthly_mean(weekly)
    print(f"  {SERIES_ID}: {len(weekly)} weeks → {len(rows)} months "
          f"({rows[0]['year']}-{rows[0]['period']} → "
          f"{rows[-1]['year']}-{rows[-1]['period']})", flush=True)

    payload = merge_into_macro_monthly(rows)
    if args.dry_run:
        print(f"[dry-run] would write {SERIES_ID} to {MACRO_MONTHLY_FILE}")
        return 0
    _atomic_write_json(MACRO_MONTHLY_FILE, payload)
    print(f"Wrote {MACRO_MONTHLY_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
