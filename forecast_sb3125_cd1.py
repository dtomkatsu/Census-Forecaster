"""SB 3125 CD1 fiscal-impact forecast for TY 2027 through 2031.

Compares projected revenue under:
  - Baseline:  Act 46 as currently enacted (Hawaii's 2024 tax-cut phase-in)
  - Scenario:  SB 3125 CD1 (2026 conference draft) which overrides §235-51

Computes two impact channels:
  - Bracket microsimulation: per-unit recalculation under each bracket
    schedule using calibrated PUMS-derived tax units.
  - Credit-cap overlay: static-scoring of §235-12.5 ($40M cap, $0 from
    2031) and §235-110.7 (sunset 12/31/2027) using DOTAX TY2023 actuals.

The constructed/calibrated units are cached at /tmp/tax_units_cache.parquet
so reruns skip the ~3 minute TaxUnitConstructor stage.

Output:
  /tmp/sb3125_cd1_fiscal_impact_2027_2031.csv
"""
from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path

DATA_DIR = Path("/Users/dtomkatsu/ctc-and-eitc/data/raw/pums")
CACHE_FILE = Path("/tmp/tax_units_cache.parquet")
OUT_CSV = Path("/tmp/sb3125_cd1_fiscal_impact_2027_2031.csv")
TARGET_YEARS = [2027, 2028, 2029, 2030, 2031]

REPO = Path(__file__).parent
sys.path.insert(0, str(REPO / "packages" / "tax_modeler" / "src"))
sys.path.insert(0, str(REPO / "packages" / "census_forecaster" / "src"))
sys.path.insert(0, str(REPO / "packages" / "pums_estimator" / "src"))
sys.path.insert(0, str(REPO / "packages" / "common" / "src"))

if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)

    try:
        import time
        import pandas as pd

        print("Importing modules...", flush=True)
        from tax_modeler.pipeline import _enrich_for_credits, _compute_base_tax, _calibrate
        from tax_modeler.loaders.pums_loader import PUMSDataLoader
        from tax_modeler.units.constructor import TaxUnitConstructor
        from tax_modeler.projection.tax_unit_projector import project_tax_units_forward
        from tax_modeler.config.tax_system_config import (
            TaxCalculator, TaxSystemRegistry, compare_systems,
        )
        from tax_modeler.scenarios.sb3125_cd1_credits import compute_credit_overlay

        wall_start = time.perf_counter()

        # ---- Build calibrated base-year units (cached) ---------------------
        if CACHE_FILE.exists():
            print(f"Loading cached units from {CACHE_FILE}...", flush=True)
            units = pd.read_parquet(CACHE_FILE)
            print(f"  {len(units):,} units loaded from cache", flush=True)
        else:
            t0 = time.perf_counter()
            print("Loading PUMS...", flush=True)
            loader = PUMSDataLoader(data_dir=DATA_DIR)
            person_df, hh_df = loader.load_data(state="15", pums_type="5yr")
            print(f"  {len(person_df):,} persons, {len(hh_df):,} households in {time.perf_counter()-t0:.1f}s", flush=True)

            t0 = time.perf_counter()
            print("Constructing tax units...", flush=True)
            constructor = TaxUnitConstructor(
                person_df, hh_df,
                use_soi_calibration=False,
                progress_bar=False,
            )
            units = constructor.create_rule_based_units(parallel=False)
            print(f"  {len(units):,} units in {time.perf_counter()-t0:.1f}s", flush=True)

            safe_units = units.copy()
            for col in safe_units.columns:
                if safe_units[col].dtype == object:
                    safe_units[col] = safe_units[col].astype(str)
            safe_units.to_parquet(CACHE_FILE, index=False)
            print(f"  Units cached to {CACHE_FILE}", flush=True)
            del safe_units

        t0 = time.perf_counter()
        print("Enriching + base tax + calibrating...", flush=True)
        units = _enrich_for_credits(units)
        units = _compute_base_tax(units)
        calibrated = _calibrate(units)
        print(f"  Done in {time.perf_counter()-t0:.1f}s", flush=True)

        # ---- Top-income synthesis (Priority 1a fix) ------------------------
        # Inject Pareto-derived $1M+ filers; rake's 1.5x weight cap can't
        # close the 5x gap on its own. See packages/tax_modeler/src/
        # tax_modeler/scenarios/top_income_synthesis.py for details.
        from tax_modeler.scenarios.top_income_synthesis import (
            synthesize_top_filers, validate_top_synthesis,
        )
        t0 = time.perf_counter()
        print("Synthesizing top-income ($1M+) filers...", flush=True)
        before = validate_top_synthesis(calibrated)
        print(f"  Before: {before['filers_1m_plus']:,.0f} filers "
              f"({100*before['filer_target_ratio']:.1f}% of target), "
              f"${before['tax_1m_plus_$M']:,.1f}M tax "
              f"({100*before['tax_target_ratio']:.1f}% of $663M)", flush=True)
        calibrated = synthesize_top_filers(calibrated)
        # Recompute base tax for the new synthetic rows
        calibrated = _compute_base_tax(calibrated)
        after = validate_top_synthesis(calibrated)
        print(f"  After:  {after['filers_1m_plus']:,.0f} filers "
              f"({100*after['filer_target_ratio']:.1f}% of target), "
              f"${after['tax_1m_plus_$M']:,.1f}M tax "
              f"({100*after['tax_target_ratio']:.1f}% of $663M)", flush=True)
        print(f"  Filing mix at $1M+: MFJ {100*after['mfj_share']:.0f}% / "
              f"Single {100*after['single_share']:.0f}% / "
              f"HoH {100*after['hoh_share']:.0f}% / "
              f"MFS {100*after['mfs_share']:.0f}%", flush=True)
        print(f"  Done in {time.perf_counter()-t0:.1f}s", flush=True)

        # ---- Per-year fiscal impact ----------------------------------------
        calc = TaxCalculator()
        rows = []
        for year in TARGET_YEARS:
            t0 = time.perf_counter()
            print(f"\nProjecting + scoring TY {year}...", flush=True)
            projected = project_tax_units_forward(
                calibrated, target_year=year, method="ensemble"
            )

            baseline_cfg = TaxSystemRegistry.get_act46_system(year)
            scenario_cfg = TaxSystemRegistry.get_sb3125_cd1_system(year)
            cmp = compare_systems(projected, baseline_cfg, scenario_cfg, calculator=calc)

            base_row = cmp[cmp["system"] == baseline_cfg.name].iloc[0]
            scen_row = cmp[cmp["system"] == scenario_cfg.name].iloc[0]
            diff_row = cmp[cmp["system"] == "Difference"].iloc[0]

            credit = compute_credit_overlay(year)

            row = {
                "tax_year": year,
                "act46_revenue_$M":         round(base_row["revenue_millions"], 2),
                "sb3125_cd1_revenue_$M":    round(scen_row["revenue_millions"], 2),
                "bracket_delta_$M":         round(diff_row["revenue_millions"], 2),
                "reec_baseline_$M":         credit["reec_baseline_$M"],
                "reec_eligible_$M":         credit["reec_eligible_$M"],
                "reec_savings_$M":          credit["reec_savings_$M"],
                "cgec_savings_$M":          credit["cgec_savings_$M"],
                "tcra_savings_$M":          credit["tcra_savings_$M"],
                "total_credit_savings_$M":  credit["total_credit_savings_$M"],
                "total_impact_$M":          round(
                    diff_row["revenue_millions"] + credit["total_credit_savings_$M"], 2
                ),
            }
            rows.append(row)
            print(f"  TY {year}: bracket_delta={row['bracket_delta_$M']:+.1f}M  "
                  f"credit_savings={row['total_credit_savings_$M']:+.1f}M  "
                  f"total={row['total_impact_$M']:+.1f}M  "
                  f"({time.perf_counter()-t0:.1f}s)", flush=True)

        # ---- Output table ---------------------------------------------------
        df = pd.DataFrame(rows)
        df.to_csv(OUT_CSV, index=False)

        print("\n" + "=" * 110, flush=True)
        print(f"SB 3125 CD1 FISCAL IMPACT ($ millions, vs. Act 46 baseline)", flush=True)
        print("=" * 110, flush=True)
        print(df.to_string(index=False), flush=True)
        print("\nNote: positive total_impact_$M = revenue gained for the State", flush=True)
        print(f"\nSaved: {OUT_CSV}", flush=True)
        print(f"Total elapsed: {time.perf_counter() - wall_start:.1f}s", flush=True)

    except Exception as e:
        print(f"\nERROR: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
