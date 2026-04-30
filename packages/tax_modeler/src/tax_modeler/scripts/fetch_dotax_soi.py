"""Fetch Hawaii DOTAX Statistics-of-Income (SOI) tables.

The Hawaii Department of Taxation publishes annual SOI tables (A2, A4,
A8, A9, A12, A13, A17, A21, plus the "Selected Resident Return Data"
sub-tables) used by tax_modeler's calibration step. The published tables
are CSVs uploaded to https://files.hawaii.gov/tax/stats/stats/, but
historical naming is inconsistent — tax_modeler keeps a curated mirror
inside the ``data/tax_modeler/raw/`` directory (gitignored).

This script populates that directory.

Usage
-----

    uv run python -m tax_modeler.scripts.fetch_dotax_soi
    uv run python -m tax_modeler.scripts.fetch_dotax_soi --year 2022 --out-dir <PATH>

Output is written atomically (tmp file + rename) so an interrupted run
leaves the existing snapshot intact.

This is a STUB. The original ctc-and-eitc DOTAX scraper lived in
``scripts/`` of that repo and required a non-trivial set of CSS selectors
+ multi-sheet Excel pivots. The full porting is tracked as a follow-up
task; for now this script raises NotImplementedError with a pointer to
the manual refresh procedure documented in ctc-and-eitc/PIPELINE_SETUP.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence


DEFAULT_YEAR = 2022


def _default_out_dir() -> Path:
    """Resolve to monorepo-root data/tax_modeler/raw/.

    File-relative path: ``packages/tax_modeler/src/tax_modeler/scripts/`` ->
    six ``parent`` calls reach the repo root (``Census-Forecaster/``), then
    descend into ``data/tax_modeler/raw``.
    """
    return Path(__file__).resolve().parents[5] / "data" / "tax_modeler" / "raw"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Hawaii DOTAX SOI tables for tax_modeler.",
    )
    parser.add_argument(
        "--year", type=int, default=DEFAULT_YEAR,
        help=f"Tax year (default {DEFAULT_YEAR}).",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=_default_out_dir(),
        help="Output directory (default: data/tax_modeler/raw/ at repo root).",
    )
    args = parser.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    raise NotImplementedError(
        "tax_modeler.scripts.fetch_dotax_soi is a stub. The original "
        "ctc-and-eitc DOTAX scraper has not yet been ported to the "
        "monorepo. For now, manually copy the SOI CSVs from "
        "https://files.hawaii.gov/tax/stats/stats/ into "
        f"{args.out_dir} (or run the legacy ctc-and-eitc refresh "
        "script and copy the resulting data/raw/ tree). "
        "Tracking issue: TODO."
    )


if __name__ == "__main__":
    sys.exit(main())
