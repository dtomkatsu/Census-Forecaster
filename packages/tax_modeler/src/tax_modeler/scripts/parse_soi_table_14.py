"""Parse IRS SOI Table 1.4 (national, sources of income by AGI bracket) → tidy CSV.

The published IRS SOI workbook (TY 2022, Publication 1304, Oct 2024) uses
multi-row merged headers that pandas can't parse directly. This script writes
a flat per-tier CSV with the columns we actually use for $500K+ tier
composition: filer count, AGI, wages, capital gains, business/passthrough
income, dividends, interest, retirement income, plus tax and itemized.

Source XLS comes from a local mirror (the ctc-and-eitc repo). Use
``--source-xls`` to override the default path.

Usage
-----
    uv run python -m tax_modeler.scripts.parse_soi_table_14 \\
        --source-xls ~/ctc-and-eitc/data/external/irs_soi_national_2022_income.xls \\
        --year 2022
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Row indices for each AGI tier in the TBL14 sheet (TY 2022 layout).
# These rows are stable across years (same bracket structure since at least
# TY2018) but verify on each new release with --inspect.
SOI_TIER_ROWS = [
    (10, "$1-$5K",       1,        5_000),
    (11, "$5K-$10K",     5_000,    10_000),
    (12, "$10K-$15K",    10_000,   15_000),
    (13, "$15K-$20K",    15_000,   20_000),
    (14, "$20K-$25K",    20_000,   25_000),
    (15, "$25K-$30K",    25_000,   30_000),
    (16, "$30K-$40K",    30_000,   40_000),
    (17, "$40K-$50K",    40_000,   50_000),
    (18, "$50K-$75K",    50_000,   75_000),
    (19, "$75K-$100K",   75_000,   100_000),
    (20, "$100K-$200K",  100_000,  200_000),
    (21, "$200K-$500K",  200_000,  500_000),
    (22, "$500K-$1M",    500_000,  1_000_000),
    (23, "$1M-$1.5M",    1_000_000, 1_500_000),
    (24, "$1.5M-$2M",    1_500_000, 2_000_000),
    (25, "$2M-$5M",      2_000_000, 5_000_000),
    (26, "$5M-$10M",     5_000_000, 10_000_000),
    (27, "$10M+",        10_000_000, float("inf")),
]

# Column indices in TBL14 (verified by header inspection of the TY 2022 file).
# Money amounts are in $thousands in the source XLS.
SOI_COLS = {
    "n_returns":              1,
    "agi_less_deficit_K":     2,
    "total_income_K":         4,
    "wages_K":                6,
    "taxable_interest_K":    20,
    "ordinary_div_K":        24,
    "qualified_div_K":       26,
    "business_net_inc_K":    32,
    "business_net_loss_K":   34,
    "capgain_distributions_K": 36,
    "schd_taxable_gain_K":   38,
    "schd_taxable_loss_K":   40,
    "ira_distributions_K":   46,
    "pensions_total_K":      48,
    "total_rental_royalty_K": 64,
    "partnership_net_inc_K": 68,
    "partnership_net_loss_K": 70,
    "scorp_net_inc_K":       72,
    "scorp_net_loss_K":      74,
    "social_security_taxable_K": 88,
    "itemized_K":           136,
    "taxable_income_K":     142,
    "income_tax_before_credits_K": 148,
}


def parse_soi_table_14(xls_path: Path, sheet_name: str = "TBL14") -> pd.DataFrame:
    """Return a tidy DataFrame: one row per AGI tier, money amounts in $millions."""
    raw = pd.read_excel(xls_path, sheet_name=sheet_name, header=None)
    if raw.shape[0] < 28 or raw.shape[1] < 149:
        raise ValueError(
            f"TBL14 sheet has unexpected shape {raw.shape}; "
            "header layout may have shifted. Re-inspect with --inspect."
        )

    records = []
    for row, label, lo, hi in SOI_TIER_ROWS:
        rec = {"agi_lo": lo, "agi_hi": hi, "tier_label": label}
        for name, col in SOI_COLS.items():
            try:
                v = float(raw.iloc[row, col])
            except (TypeError, ValueError):
                v = float("nan")
            if name.endswith("_K"):
                rec[name.replace("_K", "_M")] = v / 1000.0  # $thousands → $millions
            else:
                rec[name] = v
        # Composite columns
        rec["capgain_M"] = (
            rec["schd_taxable_gain_M"]
            - rec["schd_taxable_loss_M"]
            + rec["capgain_distributions_M"]
        )
        rec["business_M"] = (
            rec["business_net_inc_M"] - rec["business_net_loss_M"]
            + rec["partnership_net_inc_M"] - rec["partnership_net_loss_M"]
            + rec["scorp_net_inc_M"] - rec["scorp_net_loss_M"]
        )
        rec["dividends_M"] = rec["ordinary_div_M"]  # ordinary includes qualified
        rec["retirement_M"] = (
            rec["ira_distributions_M"] + rec["pensions_total_M"]
            + rec["social_security_taxable_M"]
        )
        records.append(rec)

    return pd.DataFrame.from_records(records)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[5]
    default_xls = (
        Path.home() / "ctc-and-eitc" / "data" / "external"
        / "irs_soi_national_2022_income.xls"
    )
    default_out = (
        repo_root / "data" / "tax_modeler" / "irs_soi"
        / "national_soi_table_1_4_2022.csv"
    )
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-xls", type=Path, default=default_xls,
                   help="Path to IRS SOI national income XLS (TBL14 sheet)")
    p.add_argument("--out-csv", type=Path, default=default_out,
                   help="Output CSV path")
    p.add_argument("--year", type=int, default=2022,
                   help="Tax year (recorded in CSV)")
    p.add_argument("--inspect", action="store_true",
                   help="Print header rows and tier rows for verification, then exit")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.source_xls.exists():
        logger.error("source XLS not found: %s", args.source_xls)
        return 1

    if args.inspect:
        raw = pd.read_excel(args.source_xls, sheet_name="TBL14", header=None)
        for row, label, _lo, _hi in SOI_TIER_ROWS:
            label_in_file = str(raw.iloc[row, 0]).strip().replace("\n", " ")
            print(f"  row {row:>2}  expected={label!r:<20} file={label_in_file!r}")
        return 0

    df = parse_soi_table_14(args.source_xls)
    df.insert(0, "year", args.year)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_csv, index=False)
    logger.info("wrote %d tiers to %s", len(df), args.out_csv)
    logger.info("$1M+ aggregate: %d returns, $%.0fM AGI, $%.0fM CG, $%.0fM wages",
                int(df.loc[df["agi_lo"] >= 1_000_000, "n_returns"].sum()),
                float(df.loc[df["agi_lo"] >= 1_000_000, "agi_less_deficit_M"].sum()),
                float(df.loc[df["agi_lo"] >= 1_000_000, "capgain_M"].sum()),
                float(df.loc[df["agi_lo"] >= 1_000_000, "wages_M"].sum()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
