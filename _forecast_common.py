"""Shared preamble for the root-level forecast_*.py scripts.

Consolidates the constants, CLI parsing, and cache-loading blocks that
were copy-pasted across the SB 3125 / HB 2306 script family. Root
scripts only — package code must not import this module.
"""
from __future__ import annotations

import logging
import os
import sys
import warnings
from pathlib import Path

REPO = Path(__file__).parent

# Raw PUMS location (only needed when rebuilding the tax-unit cache).
#
# CAUTION: the default deliberately points OUTSIDE the repo. The
# 2020-24 5yr vintage the cache is built from lives in
# ~/ctc-and-eitc/data/raw/pums; the in-repo packages/data/raw/pums holds
# the OLDER 2018-2022 vintage (verified 2026-08-03: the files differ).
# Vendoring the current vintage in-repo is scoped for Phase 1 of
# DASHBOARD_PIPELINE_SCOPE.md — until then, do not "fix" this default.
DATA_DIR = Path(
    os.environ.get("HAWAII_PUMS_DIR")
    or Path.home() / "ctc-and-eitc" / "data" / "raw" / "pums"
)

# Versioned artifacts live in-repo (gitignored) — /tmp caches had no
# invalidation and silently served stale bases across code changes.
ARTIFACT_DIR = REPO / "data" / "artifacts"
CACHE_FILE = ARTIFACT_DIR / "tax_units_cache.parquet"
CALIBRATED_PKL = ARTIFACT_DIR / "sb3125_calibrated_base.pkl"

TARGET_YEARS = [2027, 2028, 2029, 2030, 2031]


def silence_noise() -> None:
    """Suppress library warnings/log spam in analytical script output."""
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)


def parse_cd_args(description: str | None = None):
    """Standard ``--cd {1,2}`` CLI shared by the SB 3125 scripts."""
    import argparse

    p = argparse.ArgumentParser(description=description)
    p.add_argument(
        "--cd", choices=["1", "2"], default="1",
        help="Conference draft to model: 1=CD1 (default), 2=CD2",
    )
    return p.parse_args()


def load_cached_units(cd: str = "1"):
    """Load the tax-unit cache, exiting with guidance if it is missing.

    Returns the raw cached units DataFrame (sidecar-verified).
    """
    import pandas as pd

    from tax_modeler.artifacts import check_cache_sidecar

    if not CACHE_FILE.exists():
        print(f"ERROR: tax-unit cache not found at {CACHE_FILE}", flush=True)
        print(f"Run forecast_sb3125.py --cd {cd} first to populate the cache.", flush=True)
        sys.exit(1)

    print(f"Loading cached units from {CACHE_FILE}...", flush=True)
    check_cache_sidecar(CACHE_FILE)
    units = pd.read_parquet(CACHE_FILE)
    print(f"  {len(units):,} units loaded", flush=True)
    return units
