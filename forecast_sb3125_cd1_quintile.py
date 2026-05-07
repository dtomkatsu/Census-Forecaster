"""SB 3125 CD1 distributional analysis by income quintile, TY 2027–2031.

For each tax year, computes the per-filer bracket-change impact (SB 3125 CD1
vs Act 46 baseline) and aggregates into five equal-population income quintiles.

Scope: bracket change only (§235-51).  REEC/CGEC/TCRA credit components are
aggregate static-scoring overlays not attributable to individual filers and are
excluded from the quintile breakdown.

Scenario: MID (Pareto α=1.5, itemized_adj=True) — calibrated best-estimate.
Static incidence scoring: per-unit tax is computed at projected income before
ETI/migration adjustments, consistent with standard distributional analysis
(CBO / Tax Policy Center methodology).

Output:
  /tmp/sb3125_cd1_quintile_2027_2031.csv
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path

DATA_DIR = Path(
    os.environ.get("HAWAII_PUMS_DIR")
    or Path.home() / "ctc-and-eitc" / "data" / "raw" / "pums"
)
CACHE_FILE = Path("/tmp/tax_units_cache.parquet")
OUT_CSV   = Path("/tmp/sb3125_cd1_quintile_2027_2031.csv")
TARGET_YEARS = [2027, 2028, 2029, 2030, 2031]

# MID scenario parameters (calibrated best-estimate)
PARETO_ALPHA   = 1.5
ITEMIZED_ADJ   = True
TOP_PREMIUM    = 0.0   # no additional top-income growth premium for MID

REPO = Path(__file__).parent
sys.path.insert(0, str(REPO / "packages" / "tax_modeler" / "src"))
sys.path.insert(0, str(REPO / "packages" / "census_forecaster" / "src"))
sys.path.insert(0, str(REPO / "packages" / "pums_estimator" / "src"))
sys.path.insert(0, str(REPO / "packages" / "common" / "src"))

QUINTILE_LABELS = [
    "Q1 (Bottom 20%)",
    "Q2",
    "Q3",
    "Q4",
    "Q5 (Top 20%)",
]


def _fmt_dollar(x: float) -> str:
    if abs(x) >= 1_000_000:
        return f"${x/1_000_000:,.2f}M"
    if abs(x) >= 1_000:
        return f"${x:,.0f}"
    return f"${x:.0f}"


def compute_quintile_breakdown(projected, baseline_cfg, scenario_cfg, calc):
    """Return a DataFrame with one row per income quintile for the given year."""
    import pandas as pd

    proj = projected.copy()

    # ---- Per-unit tax under each system (static scoring) --------------------
    # CG income for §235-16 cap: synthetic filers carry synthetic_cg_share;
    # base PUMS units don't (default 0 → no cap applied, consistent with
    # ACS not capturing realized capital gains for sub-$1M filers).
    import numpy as _np
    cg_shares = (
        proj["synthetic_cg_share"].fillna(0.0).values
        if "synthetic_cg_share" in proj.columns
        else _np.zeros(len(proj))
    )
    base_tax, scen_tax = [], []
    ndep_col = proj.get("num_dependents") if hasattr(proj, "get") else proj["num_dependents"]
    for inc, fs, ndep, cg_share in zip(
        proj["income"], proj["filing_status"], ndep_col, cg_shares
    ):
        cg_inc = float(inc) * float(cg_share)
        b = calc.calculate_tax(inc, baseline_cfg, fs,
                               num_exemptions=int(ndep) + 1, cg_income=cg_inc)
        s = calc.calculate_tax(inc, scenario_cfg, fs,
                               num_exemptions=int(ndep) + 1, cg_income=cg_inc)
        base_tax.append(b["tax_liability"])
        scen_tax.append(s["tax_liability"])

    proj["base_tax"] = base_tax
    proj["scen_tax"] = scen_tax
    proj["delta"]    = proj["scen_tax"] - proj["base_tax"]

    # ---- Quintile assignment (equal-population, cumulative weight) ----------
    proj_sorted = proj.sort_values("income").reset_index(drop=True)
    cumw        = proj_sorted["weight"].cumsum()
    total_w     = float(cumw.iloc[-1])
    proj_sorted["quintile"] = pd.cut(
        cumw / total_w,
        bins=[i / 5 for i in range(6)],
        labels=QUINTILE_LABELS,
        include_lowest=True,
    )

    # ---- Weighted aggregation per quintile ----------------------------------
    grp = proj_sorted.groupby("quintile", observed=True)

    def wsum(col):
        return grp.apply(lambda d: (d[col] * d["weight"]).sum())

    def wavg(col):
        return grp.apply(
            lambda d: (d[col] * d["weight"]).sum() / d["weight"].sum()
        )

    result = pd.DataFrame({
        "income_min_$":           grp["income"].min(),
        "income_max_$":           grp["income"].max(),
        "avg_income_$":           wavg("income"),
        "n_filers":               grp["weight"].sum(),
        "base_tax_total_$M":      wsum("base_tax") / 1e6,
        "sb3125_cd1_tax_total_$M": wsum("scen_tax") / 1e6,
        "delta_total_$M":         wsum("delta") / 1e6,
        "avg_delta_per_filer_$":  wavg("delta"),
        "pct_filers_with_change": grp.apply(
            lambda d: d.loc[d["delta"] != 0, "weight"].sum() / d["weight"].sum() * 100
        ),
    }).reset_index()

    return result


def print_quintile_table(year: int, qt):
    """Pretty-print a quintile table for one tax year."""
    print(f"\n{'─'*95}", flush=True)
    print(
        f"TY {year} — SB 3125 CD1 vs Act 46  |  Bracket change by income quintile (MID scenario)",
        flush=True,
    )
    print(
        "  (Bracket only; REEC/CGEC/TCRA credit overlay not included in quintile delta)",
        flush=True,
    )
    print(f"{'─'*95}", flush=True)
    hdr = (
        f"  {'Quintile':<20}  {'Income range':>26}  {'Avg income':>12}  "
        f"{'N filers':>10}  {'Delta $M':>10}  {'Avg $/filer':>13}  {'% affected':>10}"
    )
    print(hdr, flush=True)
    print(f"  {'─'*89}", flush=True)
    total_delta = 0.0
    for _, row in qt.iterrows():
        rng = f"{_fmt_dollar(row['income_min_$'])} – {_fmt_dollar(row['income_max_$'])}"
        delta_str = f"{row['delta_total_$M']:+.1f}"
        avg_str   = f"{row['avg_delta_per_filer_$']:+,.0f}"
        pct_str   = f"{row['pct_filers_with_change']:.1f}%"
        print(
            f"  {row['quintile']:<20}  {rng:>26}  "
            f"{_fmt_dollar(row['avg_income_$']):>12}  "
            f"{row['n_filers']:>10,.0f}  "
            f"{delta_str:>10}  "
            f"{avg_str:>13}  "
            f"{pct_str:>10}",
            flush=True,
        )
        total_delta += row["delta_total_$M"]
    print(f"  {'─'*89}", flush=True)
    print(f"  {'TOTAL (all quintiles)':<20}  {'':>26}  {'':>12}  "
          f"{'':>10}  {total_delta:>+10.1f}", flush=True)


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)

    try:
        import time
        import pandas as pd

        print("Importing modules...", flush=True)
        from tax_modeler.pipeline import _enrich_for_credits, _compute_base_tax, _calibrate
        from tax_modeler.projection.tax_unit_projector import project_tax_units_forward
        from tax_modeler.config.tax_system_config import (
            TaxCalculator, TaxSystemRegistry,
        )
        from tax_modeler.scenarios.top_income_synthesis import (
            synthesize_top_filers, validate_top_synthesis,
            rescale_synthetic_tail_to_tax_target,
        )
        from tax_modeler.scenarios.behavioral_response import (
            apply_top_income_growth_premium,
            apply_itemized_deduction_adjustment,
        )

        wall_start = time.perf_counter()

        # ---- One-time setup -------------------------------------------------
        if not CACHE_FILE.exists():
            print(f"ERROR: cache not found at {CACHE_FILE}", flush=True)
            print("Run forecast_sb3125_cd1.py first to build the cache.", flush=True)
            sys.exit(1)

        print(f"Loading cached units from {CACHE_FILE}...", flush=True)
        units = pd.read_parquet(CACHE_FILE)
        print(f"  {len(units):,} units loaded", flush=True)

        print("Enriching + base tax + calibrating...", flush=True)
        t0 = time.perf_counter()
        units = _enrich_for_credits(units)
        units = _compute_base_tax(units)
        units = _calibrate(units)
        print(f"  Done in {time.perf_counter()-t0:.1f}s", flush=True)

        print(f"Synthesizing top-income filers (Pareto α={PARETO_ALPHA})...", flush=True)
        t0 = time.perf_counter()
        units = synthesize_top_filers(units, pareto_alpha=PARETO_ALPHA)
        units = _compute_base_tax(units)
        units, tail_k = rescale_synthetic_tail_to_tax_target(units)
        units = _compute_base_tax(units)
        v = validate_top_synthesis(units)
        print(f"  {v['filers_1m_plus']:,.0f} filers @ $1M+ "
              f"({100*v['filer_target_ratio']:.1f}%), "
              f"${v['tax_1m_plus_$M']:,.1f}M tax "
              f"({100*v['tax_target_ratio']:.1f}% of $663M target), "
              f"tail_k={tail_k:.4f} "
              f"in {time.perf_counter()-t0:.1f}s", flush=True)

        # ---- Per-year quintile analysis -------------------------------------
        calc = TaxCalculator()
        all_rows = []

        for year in TARGET_YEARS:
            t0 = time.perf_counter()
            print(f"\nTY {year}: projecting...", flush=True)

            projected = project_tax_units_forward(
                units, target_year=year, method="ensemble"
            )
            # MID adjustments: no growth premium, itemized deduction adjustment
            projected = apply_top_income_growth_premium(
                projected, target_year=year, annual_premium=TOP_PREMIUM
            )
            if ITEMIZED_ADJ:
                projected = apply_itemized_deduction_adjustment(projected)

            baseline_cfg = TaxSystemRegistry.get_act46_system(year)
            scenario_cfg = TaxSystemRegistry.get_sb3125_cd1_system(year)

            print(f"  Computing per-unit tax ({len(projected):,} units × 2 systems)...",
                  flush=True)
            qt = compute_quintile_breakdown(projected, baseline_cfg, scenario_cfg, calc)
            qt.insert(0, "tax_year", year)

            print_quintile_table(year, qt)
            all_rows.append(qt)
            print(f"  TY {year} done in {time.perf_counter()-t0:.1f}s", flush=True)

        # ---- Save combined CSV ----------------------------------------------
        df_out = pd.concat(all_rows, ignore_index=True)
        df_out.to_csv(OUT_CSV, index=False)

        # ---- Summary pivot: Q5 delta across years ---------------------------
        print(f"\n{'='*95}", flush=True)
        print("Q5 (Top 20%) bracket delta by year — the filers driving most of the revenue gain",
              flush=True)
        print(f"{'='*95}", flush=True)
        q5 = df_out[df_out["quintile"] == "Q5 (Top 20%)"].set_index("tax_year")
        for yr in TARGET_YEARS:
            r = q5.loc[yr]
            print(f"  TY {yr}: income ${r['income_min_$']:,.0f}–${r['income_max_$']:,.0f}  "
                  f"avg ${r['avg_income_$']:,.0f}  "
                  f"delta {r['delta_total_$M']:+.1f}M  "
                  f"avg/filer ${r['avg_delta_per_filer_$']:+,.0f}",
                  flush=True)

        print(f"\nSaved: {OUT_CSV}", flush=True)
        print(f"Total elapsed: {time.perf_counter()-wall_start:.1f}s", flush=True)

    except Exception as e:
        print(f"\nERROR: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
