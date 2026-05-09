"""Build the bundled Hawaii CPS-ASEC slice for donor-match imputation.

Downloads the most recent public-use CPS Annual Social and Economic
Supplement (ASEC) file from Census, filters to Hawaii residents
(``GESTFIPS == 15``), selects the columns needed for SPM-style donor
matching, and writes a small parquet to:

    packages/tax_modeler/src/tax_modeler/data/cps_donor/cps_asec_hawaii.parquet

This is a one-time setup script. The output parquet is committed to the
repo so subsequent users / CI runs skip the download.

CPS ASEC public-use files are released annually each September. The
schema is documented at:

  * Census Bureau: https://www.census.gov/data/datasets/2024/demo/cps/cps-asec-2024.html
  * Data dictionary: https://www2.census.gov/programs-surveys/cps/datasets/2024/march/asec2024_ddl_pub_full.pdf

Usage::

    python scripts/build_cps_asec_slice.py [--year 2024] [--local-csv PATH]

If ``--local-csv`` is supplied (e.g. you've already downloaded the file
manually), the download step is skipped.
"""
from __future__ import annotations

import argparse
import io
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

OUT_PARQUET = (
    Path(__file__).resolve().parents[1]
    / "packages" / "tax_modeler" / "src" / "tax_modeler"
    / "data" / "cps_donor" / "cps_asec_hawaii.parquet"
)

CENSUS_BASE = "https://www2.census.gov/programs-surveys/cps/datasets"

# Columns we need for SPM-style donor matching. Match-side: demographics +
# household composition + income. Donor-side: MOOP, childcare expenses,
# work expenses (the components of SPM resource adjustment).
#
# CPS ASEC public-use column names (per asec2024_ddl_pub_full.pdf):
_COLUMNS = [
    # Linker + weights
    "PH_SEQ",       # Household sequence number (links to HH file)
    "PPPOS",        # Person position within HH
    "PERIDNUM",     # Person identifier
    "MARSUPWT",     # March supplement weight (note: this column is x100 of true weight)
    # Demographic match features
    "A_AGE",        # Age
    "A_SEX",        # Sex
    "A_MARITL",     # Marital status
    "PRDTRACE",     # Detailed race
    "PEHSPNON",     # Hispanic/non-Hispanic
    "A_HGA",        # Educational attainment
    # Employment + income
    "A_LFSR",       # Labor force status
    "WSAL_VAL",     # Wages and salary
    "PTOTVAL",      # Total income
    # SPM components (the donor variables — universe varies by year)
    "SPM_NUMPER",   # Number of persons in SPM unit
    "SPM_NUMADULTS",
    "SPM_NUMKIDS",
    "SPM_RESOURCES",  # SPM resources (post-tax-and-transfer)
    "SPM_TOTVAL",     # alt. name in some years
    "SPM_MEDXPNS",    # Medical out-of-pocket expenses (annual)
    "SPM_CHILDCAREXPNS",  # Out-of-pocket childcare expenses
    "SPM_CAPWKCCXPNS",    # Capped work + childcare expenses
    "SPM_FICA",     # FICA payroll tax
    "SPM_FEDTAX",   # Federal income tax
    "SPM_FEDTAXBC", # Federal income tax before credits
    "SPM_EITC",     # EITC received
    "SPM_GEOADJ",   # Geographic adjustment factor (for SPM threshold)
    "SPM_EQUIVSCALE",
    "SPM_FAMTYPE",
    "SPM_HAGE",     # Householder age (for SPM unit)
    "MOOP",         # Person-level MOOP (raw, pre-SPM)
]
_FALLBACK_NAME_MAP = {
    "SPM_RESOURCES": "SPM_TOTVAL",   # Census renamed in newer years
}


def _download_csv_zip(year: int) -> Path:
    """Download the asecpub<yy>csv.zip file from Census FTP, return local path."""
    yy = year % 100
    url = f"{CENSUS_BASE}/{year}/march/asecpub{yy}csv.zip"
    local = Path(f"/tmp/asecpub{yy}csv.zip")
    if local.exists():
        print(f"  using cached {local}", flush=True)
        return local
    print(f"  fetching {url} (~140MB)...", flush=True)
    r = requests.get(url, stream=True, timeout=600)
    r.raise_for_status()
    with open(local, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 20):
            f.write(chunk)
    print(f"  wrote {local} ({local.stat().st_size / 1e6:.1f} MB)", flush=True)
    return local


def _read_filtered_csv(zip_path: Path, *, statefips: int = 15) -> pd.DataFrame:
    """Open the zip, link HH state to person rows, return Hawaii-only persons.

    CPS-ASEC public-use files split data across three CSVs (household,
    family, person). State FIPS lives on the household file
    (``hhpub<yy>.csv``, column ``GESTFIPS``) keyed by ``H_SEQ``; person
    rows in ``pppub<yy>.csv`` join via ``PH_SEQ``. This function reads
    the HH file, gets HI ``H_SEQ`` values, then stream-filters the
    person file.
    """
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        hh_csv = next((m for m in names if m.lower().startswith("hhpub")), None)
        person_csv = next((m for m in names if m.lower().startswith("pppub")), None)
        if not hh_csv or not person_csv:
            raise RuntimeError(
                f"Could not find hhpub*.csv + pppub*.csv in {zip_path}; "
                f"available: {names}"
            )
        print(f"  reading {hh_csv} for HI household IDs...", flush=True)
        with zf.open(hh_csv) as f:
            hh = pd.read_csv(
                io.TextIOWrapper(f, encoding="utf-8"),
                usecols=["H_SEQ", "GESTFIPS"],
                low_memory=False,
            )
        hi_seqs = set(hh.loc[hh["GESTFIPS"] == statefips, "H_SEQ"].astype(int))
        print(f"  {len(hi_seqs):,} HI households", flush=True)

        print(f"  reading {person_csv} (chunked, filtering to HI)...", flush=True)
        chunks = []
        with zf.open(person_csv) as f:
            for chunk in pd.read_csv(
                io.TextIOWrapper(f, encoding="utf-8"),
                chunksize=50_000, low_memory=False,
            ):
                seqs = chunk["PH_SEQ"].astype(int)
                hi_chunk = chunk[seqs.isin(hi_seqs)]
                if not hi_chunk.empty:
                    chunks.append(hi_chunk)
        df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
    print(f"  Hawaii person rows: {len(df):,}", flush=True)
    return df


def _select_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Select the subset of CPS ASEC columns we use for donor matching."""
    available = set(df.columns)
    keep: list[str] = []
    seen: set[str] = set()
    for col in _COLUMNS:
        target = col if col in available else _FALLBACK_NAME_MAP.get(col)
        if target and target in available and target not in seen:
            keep.append(target)
            seen.add(target)
    out = df[keep].copy()
    # Standardize column names for downstream donor matcher
    rename = {
        "A_AGE": "age",
        "WSAL_VAL": "wage_income",
        "PTOTVAL": "income",
        "SPM_NUMPER": "spm_unit_size",
        "SPM_TOTVAL": "spm_resources",
        "SPM_RESOURCES": "spm_resources",
        "SPM_MEDXPNS": "moop",   # SPM-unit-level MOOP — preferred over MOOP person-level
        "SPM_CHILDCAREXPNS": "childcare_expense",
        "SPM_CAPWKCCXPNS": "work_childcare_expense",
        "MARSUPWT": "weight",
    }
    out = out.rename(columns={k: v for k, v in rename.items() if k in out.columns})
    # Dedupe column names (both SPM_TOTVAL and SPM_RESOURCES rename to spm_resources)
    out = out.loc[:, ~out.columns.duplicated()]
    # MARSUPWT is documented as x100; divide for true population weight
    if "weight" in out.columns:
        out["weight"] = out["weight"].astype(float) / 100.0
    # Derive work_expense as work_childcare_expense - childcare_expense if both present;
    # else zero
    if "work_childcare_expense" in out.columns and "childcare_expense" in out.columns:
        out["work_expense"] = (
            out["work_childcare_expense"].astype(float)
            - out["childcare_expense"].astype(float)
        ).clip(lower=0)
    else:
        out["work_expense"] = 0.0
    # Add hh_size proxy (use SPM unit size if present, else 1)
    if "spm_unit_size" in out.columns:
        out["hh_size"] = out["spm_unit_size"]
    else:
        out["hh_size"] = 1
    # Ensure required donor columns exist (zero-fill missing)
    for col in ("moop", "childcare_expense", "work_expense"):
        if col not in out.columns:
            out[col] = 0.0
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2024,
                        help="CPS ASEC publication year (default 2024)")
    parser.add_argument("--local-csv", type=Path, default=None,
                        help="Path to a pre-downloaded asecpub<yy>csv.zip; "
                             "skips the Census download.")
    parser.add_argument("--statefips", type=int, default=15,
                        help="FIPS state code to filter to (15 = Hawaii)")
    parser.add_argument("--out", type=Path, default=OUT_PARQUET)
    args = parser.parse_args(argv)

    print(f"Building HI CPS-ASEC slice for year={args.year}...", flush=True)

    if args.local_csv:
        zip_path = args.local_csv
        if not zip_path.exists():
            print(f"ERROR: {zip_path} not found", file=sys.stderr)
            return 1
    else:
        try:
            zip_path = _download_csv_zip(args.year)
        except Exception as e:
            print(f"\nDownload failed: {e}", file=sys.stderr)
            print("Workaround: download asecpub<yy>csv.zip manually from", file=sys.stderr)
            print(f"  {CENSUS_BASE}/{args.year}/march/", file=sys.stderr)
            print("then re-run with --local-csv <path>", file=sys.stderr)
            return 1

    df = _read_filtered_csv(zip_path, statefips=args.statefips)
    if df.empty:
        print(f"ERROR: no rows for STATEFIPS={args.statefips}", file=sys.stderr)
        return 1

    out = _select_columns(df)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # PERIDNUM in CPS-ASEC is a 14-digit identifier — too big for int64.
    # Cast it (and any other ID-like overflowing object columns) to string.
    for col in out.columns:
        if col == "PERIDNUM" or out[col].dtype == "object":
            out[col] = out[col].astype(str)
        elif pd.api.types.is_integer_dtype(out[col]):
            out[col] = out[col].astype("int64")
    out.to_parquet(args.out, index=False)
    print(f"\nWrote {len(out):,} rows × {len(out.columns)} cols → {args.out}", flush=True)
    print(f"  size: {args.out.stat().st_size / 1024:.1f} KB", flush=True)
    print(f"  mean MOOP: ${out['moop'].mean():,.0f}", flush=True)
    print(f"  mean childcare expense: ${out.get('childcare_expense', pd.Series([0])).mean():,.0f}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
