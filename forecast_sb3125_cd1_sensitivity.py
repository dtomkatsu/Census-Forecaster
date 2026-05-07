"""SB 3125 CD1 fiscal-impact sensitivity analysis.

Runs the forecast under three parameter combinations (low/mid/high)
varying the two key uncertain inputs:

  1. Pareto alpha for top-income synthesis
       1.4 = heavy tail (more $5M+ filers, larger 13% bracket impact)
       1.5 = mid (default; matches IRS SOI 2022 Hawaii tail shape)
       1.6 = light tail (fewer ultra-high earners, smaller impact)

  2. REEC demand scenario (post-OBBBA federal Section 25D termination)
       pre_obbba    = no decay (full $99.6M baseline, max cap savings)
       obbba_mid    = SEIA-tempered (default; -10% in 2026, recovery)
       obbba_severe = SEIA national applied (-19% in 2026, slow recovery)

Combinations:
  LOW    = (alpha=1.6, reec=obbba_severe)  -- conservative for revenue
  MID    = (alpha=1.5, reec=obbba_mid)     -- recommended default
  HIGH   = (alpha=1.4, reec=pre_obbba)     -- aggressive for revenue

Output:
  /tmp/sb3125_cd1_sensitivity_2027_2031.csv
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
OUT_CSV = Path("/tmp/sb3125_cd1_sensitivity_2027_2031.csv")
TARGET_YEARS = [2027, 2028, 2029, 2030, 2031]

SCENARIOS = [
    ("LOW",  1.6, "obbba_severe"),
    ("MID",  1.5, "obbba_mid"),
    ("HIGH", 1.4, "pre_obbba"),
]

REPO = Path(__file__).parent
sys.path.insert(0, str(REPO / "packages" / "tax_modeler" / "src"))
sys.path.insert(0, str(REPO / "packages" / "census_forecaster" / "src"))
sys.path.insert(0, str(REPO / "packages" / "pums_estimator" / "src"))
sys.path.insert(0, str(REPO / "packages" / "common" / "src"))


def run_one_scenario(
    base_calibrated, *, label, pareto_alpha, reec_scenario,
    _enrich_for_credits, _compute_base_tax,
    project_tax_units_forward,
    TaxCalculator, TaxSystemRegistry, compare_systems,
    compute_credit_overlay, synthesize_top_filers, validate_top_synthesis,
):
    import time
    print(f"\n{'='*70}\nSCENARIO {label}: pareto_alpha={pareto_alpha}, reec={reec_scenario}\n{'='*70}", flush=True)

    # Synthesize fresh from the (uncalibrated-for-top-income) base
    units = synthesize_top_filers(base_calibrated, pareto_alpha=pareto_alpha)
    units = _compute_base_tax(units)
    v = validate_top_synthesis(units)
    print(f"  Synthesis: {v['filers_1m_plus']:,.0f} filers @ $1M+ "
          f"({100*v['filer_target_ratio']:.1f}%), ${v['tax_1m_plus_$M']:,.1f}M tax "
          f"({100*v['tax_target_ratio']:.1f}%)", flush=True)

    calc = TaxCalculator()
    rows = []
    for year in TARGET_YEARS:
        t0 = time.perf_counter()
        projected = project_tax_units_forward(units, target_year=year, method="ensemble")

        baseline_cfg = TaxSystemRegistry.get_act46_system(year)
        scenario_cfg = TaxSystemRegistry.get_sb3125_cd1_system(year)
        cmp = compare_systems(projected, baseline_cfg, scenario_cfg, calculator=calc)
        diff_row = cmp[cmp["system"] == "Difference"].iloc[0]
        bracket_delta = float(diff_row["revenue_millions"])

        credit = compute_credit_overlay(year, reec_demand_scenario=reec_scenario)
        total = bracket_delta + credit["total_credit_savings_$M"]

        rows.append({
            "scenario":       label,
            "tax_year":       year,
            "bracket_delta_$M":  round(bracket_delta, 2),
            "reec_savings_$M":   credit["reec_savings_$M"],
            "cgec_savings_$M":   credit["cgec_savings_$M"],
            "tcra_savings_$M":   credit["tcra_savings_$M"],
            "credit_total_$M":   credit["total_credit_savings_$M"],
            "total_impact_$M":   round(total, 2),
        })
        print(f"  TY {year}: bracket={bracket_delta:+.1f}M  "
              f"credit={credit['total_credit_savings_$M']:+.1f}M  "
              f"total={total:+.1f}M  ({time.perf_counter()-t0:.1f}s)", flush=True)
    return rows


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
            TaxCalculator, TaxSystemRegistry, compare_systems,
        )
        from tax_modeler.scenarios.sb3125_cd1_credits import compute_credit_overlay
        from tax_modeler.scenarios.top_income_synthesis import (
            synthesize_top_filers, validate_top_synthesis,
        )

        wall_start = time.perf_counter()

        # Load and prep units once (no synthesis yet)
        if not CACHE_FILE.exists():
            print(f"ERROR: tax-unit cache not found at {CACHE_FILE}", flush=True)
            print("Run forecast_sb3125_cd1.py first to populate the cache.", flush=True)
            sys.exit(1)

        print(f"Loading cached units from {CACHE_FILE}...", flush=True)
        units = pd.read_parquet(CACHE_FILE)
        print(f"  {len(units):,} units loaded", flush=True)

        print("Enriching + base tax + calibrating (one-time)...", flush=True)
        units = _enrich_for_credits(units)
        units = _compute_base_tax(units)
        calibrated_base = _calibrate(units)

        # Run all three scenarios
        all_rows = []
        for label, alpha, reec in SCENARIOS:
            all_rows.extend(run_one_scenario(
                calibrated_base, label=label, pareto_alpha=alpha, reec_scenario=reec,
                _enrich_for_credits=_enrich_for_credits,
                _compute_base_tax=_compute_base_tax,
                project_tax_units_forward=project_tax_units_forward,
                TaxCalculator=TaxCalculator,
                TaxSystemRegistry=TaxSystemRegistry,
                compare_systems=compare_systems,
                compute_credit_overlay=compute_credit_overlay,
                synthesize_top_filers=synthesize_top_filers,
                validate_top_synthesis=validate_top_synthesis,
            ))

        df = pd.DataFrame(all_rows)
        df.to_csv(OUT_CSV, index=False)

        # ---- Pivot for clean summary --------------------------------------
        print("\n" + "=" * 90, flush=True)
        print("SB 3125 CD1 FISCAL IMPACT SENSITIVITY ($M, vs Act 46 baseline)", flush=True)
        print("=" * 90, flush=True)

        # Total impact pivot
        pv = df.pivot(index="tax_year", columns="scenario", values="total_impact_$M")
        pv = pv[["LOW", "MID", "HIGH"]]
        pv.loc["5yr cum"] = pv.sum()
        print("\nTotal annual fiscal impact ($M):")
        print(pv.to_string(float_format=lambda x: f"{x:>9,.1f}"), flush=True)

        # Bracket-only pivot
        pv_b = df.pivot(index="tax_year", columns="scenario", values="bracket_delta_$M")[["LOW","MID","HIGH"]]
        pv_b.loc["5yr cum"] = pv_b.sum()
        print("\nBracket-change impact only ($M):")
        print(pv_b.to_string(float_format=lambda x: f"{x:>9,.1f}"), flush=True)

        # Credit-only pivot
        pv_c = df.pivot(index="tax_year", columns="scenario", values="credit_total_$M")[["LOW","MID","HIGH"]]
        pv_c.loc["5yr cum"] = pv_c.sum()
        print("\nCredit-cap impact only ($M):")
        print(pv_c.to_string(float_format=lambda x: f"{x:>9,.1f}"), flush=True)

        print(f"\nSaved: {OUT_CSV}", flush=True)
        print(f"Total elapsed: {time.perf_counter() - wall_start:.1f}s", flush=True)

    except Exception as e:
        print(f"\nERROR: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
