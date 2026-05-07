"""One-shot pipeline run against real PUMS data."""
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

# Requires the workspace to be installed: `uv sync --all-packages`.
# (run with `uv run python pipeline_run.py` or after `uv pip install -e packages/...`)

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
        from tax_modeler.revenue.estimator import RevenueEstimator

        wall_start = time.perf_counter()

        if CACHE_FILE.exists():
            print(f"Loading cached units from {CACHE_FILE}...", flush=True)
            units = pd.read_parquet(CACHE_FILE)
            print(f"  {len(units):,} units loaded from cache", flush=True)
        else:
            # Stage 1: Load PUMS
            t0 = time.perf_counter()
            print("Stage 1: Loading PUMS...", flush=True)
            loader = PUMSDataLoader(data_dir=DATA_DIR)
            person_df, hh_df = loader.load_data(state="15", pums_type="5yr")
            print(f"  {len(person_df):,} persons, {len(hh_df):,} households in {time.perf_counter()-t0:.1f}s", flush=True)

            # Stage 2: Construct tax units
            t0 = time.perf_counter()
            print("Stage 2: Constructing tax units...", flush=True)
            constructor = TaxUnitConstructor(
                person_df, hh_df,
                use_soi_calibration=False,
                progress_bar=False,
            )
            units = constructor.create_rule_based_units(parallel=False)
            print(f"  {len(units):,} units in {time.perf_counter()-t0:.1f}s", flush=True)

            # Cache for reruns — save only safe-to-serialize columns
            safe_units = units.copy()
            for col in safe_units.columns:
                if safe_units[col].dtype == object:
                    safe_units[col] = safe_units[col].astype(str)
            safe_units.to_parquet(CACHE_FILE, index=False)
            print(f"  Units cached to {CACHE_FILE}", flush=True)
            del safe_units

        # Stage 3: Enrich
        t0 = time.perf_counter()
        print("Stage 3: Enriching for credits...", flush=True)
        units = _enrich_for_credits(units)
        print(f"  Done in {time.perf_counter()-t0:.1f}s", flush=True)

        # Stage 4: Base tax
        t0 = time.perf_counter()
        print("Stage 4: Computing base tax...", flush=True)
        units = _compute_base_tax(units)
        print(f"  agi range: {units['agi'].min():.0f}–{units['agi'].max():.0f}", flush=True)
        print(f"  Done in {time.perf_counter()-t0:.1f}s", flush=True)

        # Stage 5: Calibrate
        t0 = time.perf_counter()
        print("Stage 5: IPF calibration...", flush=True)
        calibrated = _calibrate(units)
        print(f"  Done in {time.perf_counter()-t0:.1f}s", flush=True)

        # Stage 6: Project
        t0 = time.perf_counter()
        print("Stage 6: Projecting to 2026...", flush=True)
        projected = project_tax_units_forward(calibrated, target_year=2026, method="ensemble")
        print(f"  Done in {time.perf_counter()-t0:.1f}s", flush=True)

        # Stage 7: Revenue estimate
        t0 = time.perf_counter()
        print("Stage 7: Estimating revenue...", flush=True)
        estimator = RevenueEstimator(projected)
        state_summary = estimator.state_summary()
        by_county = estimator.by_county()
        by_filing = estimator.by_filing_status()
        by_quintile = estimator.by_income_quintile()
        print(f"  Done in {time.perf_counter()-t0:.1f}s", flush=True)

        elapsed = time.perf_counter() - wall_start

        print("\n=== PIPELINE COMPLETE ===", flush=True)
        print(f"Total elapsed: {elapsed:.1f}s", flush=True)
        print(f"Units: {len(projected):,}", flush=True)
        print(f"Weighted filers: {state_summary['total_weighted_filers']:,.0f}", flush=True)

        print("\n=== STATE SUMMARY ===", flush=True)
        for k, v in state_summary.items():
            if isinstance(v, float):
                print(f"  {k}: {v:,.0f}", flush=True)
            else:
                print(f"  {k}: {v}", flush=True)

        print("\n=== BY COUNTY ===", flush=True)
        print(by_county.to_string(), flush=True)

        print("\n=== BY FILING STATUS ===", flush=True)
        print(by_filing.to_string(), flush=True)

        print("\n=== BY INCOME QUINTILE ===", flush=True)
        print(by_quintile.to_string(), flush=True)

    except Exception as e:
        print(f"\nERROR: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
