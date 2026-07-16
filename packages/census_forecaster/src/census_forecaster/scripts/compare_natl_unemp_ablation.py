"""National-unemployment feature ablation (Phase-3 follow-up ship gate).

The national-unemployment *anchor* was rejected (see acs/sources/base.py).
This tests its reframing as an ML **leading-indicator feature**
(natl_unemp_* columns): does adding it on top of the shipped ML baseline
(which already carries the mkt_* market signals) help, hurt, or wash?

Two arms on the bundled panel, both with include_ml=True + market signals:

  A. natl_unemp_data={}    — shipped ML baseline (no national-unemp feature)
  B. natl_unemp_data=real  — baseline + national-unemployment feature

Gate (mirrors the other ablations): ensemble_with_ml RMSE must not
regress by > 2% absolute on any indicator; CI90 coverage stays in
[85%, 95%]. Improvement is a bonus, not required — the feature ships
opt-in (`use_ml=False` default) either way.

Also reports permutation importance of the natl_unemp_* columns. These
numbers are trustworthy now that FeatureSpec.column_names matches the
real row order (a prior name↔position bug mislabeled the mkt importance
table in market_ml_ablation_2026-07-14.md — see that file's note).

Usage::

    python -m census_forecaster.scripts.compare_natl_unemp_ablation
    python -m census_forecaster.scripts.compare_natl_unemp_ablation \\
        --anchors 2018,2019,2020,2021,2022 --output report.md
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Optional, Sequence

from ..acs.calibration import run_stratified_calibration
from ..acs.ml_features import (
    load_market_signals_data,
    load_national_unemployment_data,
)
from .compare_market_ablation import (
    COVERAGE_BAND,
    RMSE_REGRESSION_LIMIT,
    _metrics_table,
)
from .compare_ml_ablation import (
    _aggregate_per_indicator,
    _apply_v3_corrections,
    _build_with_ml_residuals,
    _residuals_from_calibration,
)
from .load_calibration_panel import load_panel

_REPO_ROOT = Path(__file__).resolve().parents[5]
_RESULTS_DIR = _REPO_ROOT / "backtests" / "results"

_NATL_COLS = ("natl_unemp_lag0", "natl_unemp_chg1", "natl_unemp_chg2")


def _natl_permutation_importance(series, populations, market, natl) -> list[str]:
    try:
        import numpy as np
        from sklearn.inspection import permutation_importance
    except ImportError:
        return ["(sklearn unavailable — importance check skipped)"]

    from ..acs.ml_features import (
        build_panel_index,
        load_bps_data,
        load_laus_data,
        load_saipe_data,
        make_training_rows,
    )
    from ..acs.ml_trend import train_ml_model

    panel = build_panel_index(
        series,
        bps_data=load_bps_data(),
        saipe_data=load_saipe_data(),
        laus_data=load_laus_data(),
        market_data=market,
        natl_unemp_data=natl,
    )
    lines = []
    for indicator in ("B19013_001E", "S1701_C03_001E", "S2301_C04_001E"):
        model = train_ml_model(series, populations, indicator,
                               cutoff_year=2022, panel=panel)
        if model is None:
            lines.append(f"- {indicator}: model unavailable")
            continue
        matrix = make_training_rows(panel, populations, indicator, 2022)
        if not matrix.X:
            lines.append(f"- {indicator}: no rows")
            continue
        X = np.asarray(matrix.X, dtype=float)
        y = np.asarray(matrix.y, dtype=float)
        r = permutation_importance(model.estimator, X, y, n_repeats=5,
                                   random_state=0)
        cols = matrix.spec.column_names
        for name in _NATL_COLS:
            i = cols.index(name)
            lines.append(
                f"- {indicator} / {name}: "
                f"{r.importances_mean[i]:+.5f} ± {r.importances_std[i]:.5f}")
    return lines


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--anchors", type=str,
                   default="2014,2015,2016,2017,2018,2019,2020,2021,2022")
    p.add_argument("--horizons", type=str, default="1,2,3,4,5")
    p.add_argument("--output", type=Path, default=None)
    args = p.parse_args(list(argv) if argv is not None else None)

    anchor_years = [int(s) for s in args.anchors.split(",")]
    horizons = [int(s) for s in args.horizons.split(",")]

    natl = load_national_unemployment_data()
    if natl is None:
        print("ERROR: bls_national_unemployment.json absent — run "
              "refresh_market_panel first", file=sys.stderr)
        return 2
    market = load_market_signals_data() or {}

    print("[natl-ablation] loading panel ...", file=sys.stderr)
    series, populations, _ = load_panel()

    print("[natl-ablation] arm A: ML baseline (no natl feature) ...",
          file=sys.stderr)
    cal_a = run_stratified_calibration(
        series_by_key=series, anchor_years=anchor_years, horizons=horizons,
        populations=populations, include_ml=True,
        market_data=market, natl_unemp_data={},
    )
    print("[natl-ablation] arm B: ML + national-unemployment feature ...",
          file=sys.stderr)
    cal_b = run_stratified_calibration(
        series_by_key=series, anchor_years=anchor_years, horizons=horizons,
        populations=populations, include_ml=True,
        market_data=market, natl_unemp_data=natl,
    )

    res_a = _apply_v3_corrections(_residuals_from_calibration(cal_a), cal_a)
    res_b = _apply_v3_corrections(_residuals_from_calibration(cal_b), cal_b)
    ens_a = _build_with_ml_residuals(res_a, series, populations)
    ens_b = _build_with_ml_residuals(res_b, series, populations)
    m_a = _aggregate_per_indicator(list(res_a) + ens_a, "ensemble_with_ml")
    m_b = _aggregate_per_indicator(list(res_b) + ens_b, "ensemble_with_ml")
    rows, violations = _metrics_table("baseline", m_a, "+natl", m_b)

    verdict = (["## Verdict: **GATE FAILED**", ""]
               + [f"- {v}" for v in violations]) if violations else \
        ["## Verdict: **GATE PASSED** — no RMSE regression, coverage in "
         "band. (`use_ml` remains opt-in.)"]

    report = "\n".join([
        f"# National-unemployment feature ablation — {date.today().isoformat()}",
        "",
        f"Panel: {len(series)} series; anchors {anchor_years}; "
        f"horizons {horizons}. Gates: no RMSE regression > "
        f"{RMSE_REGRESSION_LIMIT:.0%} absolute; CI90 coverage in "
        f"[{COVERAGE_BAND[0]:.0%}, {COVERAGE_BAND[1]:.0%}]. Both arms carry "
        "the shipped mkt_* market features; the only difference is the "
        "natl_unemp_* columns.",
        "",
        "## ensemble_with_ml — baseline (A) vs +national-unemployment (B)",
        "",
        "| indicator | RMSE A | RMSE B | ΔRMSE | coverage A → B | flag |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
        "## natl_unemp_* permutation importance",
        "",
        *_natl_permutation_importance(series, populations, market, natl),
        "",
        *verdict,
        "",
    ])
    out = args.output or (
        _RESULTS_DIR / f"natl_unemp_ablation_{date.today().isoformat()}.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(f"[natl-ablation] wrote {out}", file=sys.stderr)
    print("\n".join(verdict), file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
