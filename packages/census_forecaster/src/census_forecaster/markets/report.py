"""Tracker CLI: per-ticker status table + CSV output.

Usage
-----
    python -m census_forecaster.markets.report
    python -m census_forecaster.markets.report --csv-dir reports/market_signals/

Reads the committed prices panel (no network) and prints per ticker:
last close, 3/6/12-month momentum, trailing-36-month annualised vol,
data span, and fetch provenance. ``--csv-dir`` also writes
``tracker_status.csv`` there.

Phase 2 extends this CLI with ``--forecast`` and ``--screen-summary``.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path
from typing import Optional, Sequence

from .panel import PricesPanel, load_prices_panel
from .universe import TICKERS


def _pct(logret: Optional[float]) -> str:
    if logret is None:
        return "     —"
    return f"{(math.exp(logret) - 1) * 100:+6.1f}%"


def build_status_rows(panel: PricesPanel) -> list[dict]:
    """One status dict per universe ticker present in the panel."""
    rows: list[dict] = []
    for spec in TICKERS:
        if spec.symbol not in panel.series:
            continue
        bars = panel.bars(spec.symbol)
        if not bars:
            continue
        last = bars[-1]
        vol = panel.annualized_vol(spec.symbol)
        rows.append({
            "symbol": spec.symbol,
            "name": spec.name,
            "tier": spec.tier,
            "last_month": f"{last.year}-{last.month:02d}",
            "last_close": round(last.adj_close, 2),
            "mom_3m": panel.momentum(spec.symbol, 3),
            "mom_6m": panel.momentum(spec.symbol, 6),
            "mom_12m": panel.momentum(spec.symbol, 12),
            "vol_36m_ann": round(vol, 4) if vol is not None else None,
            "first_month": f"{bars[0].year}-{bars[0].month:02d}",
            "n_obs": len(bars),
            "source": panel.provenance.get(spec.symbol, "?"),
        })
    return rows


def print_status_table(rows: Sequence[dict], out=sys.stdout) -> None:
    print(
        f"{'symbol':<7}{'tier':<8}{'last':>9}{'close':>10}"
        f"{'3m':>8}{'6m':>8}{'12m':>8}{'vol':>7}{'since':>9}  src",
        file=out,
    )
    for r in rows:
        vol = f"{r['vol_36m_ann']:.2f}" if r["vol_36m_ann"] is not None else "—"
        print(
            f"{r['symbol']:<7}{r['tier']:<8}{r['last_month']:>9}"
            f"{r['last_close']:>10.2f}"
            f"{_pct(r['mom_3m']):>8}{_pct(r['mom_6m']):>8}"
            f"{_pct(r['mom_12m']):>8}{vol:>7}{r['first_month']:>9}"
            f"  {r['source']}",
            file=out,
        )


def write_status_csv(rows: Sequence[dict], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "symbol", "name", "tier", "last_month", "last_close",
        "mom_3m", "mom_6m", "mom_12m", "vol_36m_ann",
        "first_month", "n_obs", "source",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            out = dict(r)
            for k in ("mom_3m", "mom_6m", "mom_12m"):
                out[k] = round(out[k], 6) if out[k] is not None else ""
            writer.writerow(out)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Market-signals tracker: per-ticker status from the "
                    "committed prices panel (offline).",
    )
    parser.add_argument(
        "--panel", type=Path, default=None,
        help="Path to prices_panel.json (default: bundled panel).",
    )
    parser.add_argument(
        "--csv-dir", type=Path, default=None,
        help="Also write tracker_status.csv into this directory.",
    )
    args = parser.parse_args(argv)

    try:
        panel = load_prices_panel(args.panel)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    rows = build_status_rows(panel)
    if not rows:
        print("ERROR: panel contains no universe tickers", file=sys.stderr)
        return 2

    print(f"[tracker] panel fetched {panel.fetch_date}; "
          f"{len(rows)} tickers\n", file=sys.stderr)
    print_status_table(rows)

    if args.csv_dir is not None:
        csv_path = args.csv_dir / "tracker_status.csv"
        write_status_csv(rows, csv_path)
        print(f"\n[tracker] wrote {csv_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
