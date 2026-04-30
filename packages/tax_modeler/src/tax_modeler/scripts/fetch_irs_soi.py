"""Fetch IRS national Statistics-of-Income (SOI) Excel files.

The IRS SOI Division publishes per-state and national income / deduction
distributions used by tax_modeler's high-income calibration and
ultra-high-income synthesis modules. These are Excel ``.xls``/``.xlsx``
files at https://www.irs.gov/statistics/soi-tax-stats-individual-tax-statistics.

This script populates the gitignored ``data/tax_modeler/external/``
directory (~639 MB of national tables) and ``data/tax_modeler/external/cex/``
(Consumer Expenditure Survey support files used by the optional CEX
loader; install with ``tax-modeler[cex]``).

Usage
-----

    uv run python -m tax_modeler.scripts.fetch_irs_soi
    uv run python -m tax_modeler.scripts.fetch_irs_soi --year 2022 --out-dir <PATH>

Atomic writes (tmp + rename) are used so an interrupted run leaves the
existing snapshot intact.

This is a STUB. The original ctc-and-eitc had a per-table fetcher in
``scripts/parse_irs_soi_data.py`` that hand-crafted URLs for each SOI
publication year; the full porting is tracked as a follow-up. Until
then this script raises NotImplementedError with a pointer to the manual
refresh procedure.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence


DEFAULT_YEAR = 2022


def _default_out_dir() -> Path:
    """Resolve to monorepo-root data/tax_modeler/external/."""
    return Path(__file__).resolve().parents[5] / "data" / "tax_modeler" / "external"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch IRS national SOI Excel files for tax_modeler.",
    )
    parser.add_argument(
        "--year", type=int, default=DEFAULT_YEAR,
        help=f"Tax year (default {DEFAULT_YEAR}).",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=_default_out_dir(),
        help="Output directory (default: data/tax_modeler/external/ at repo root).",
    )
    args = parser.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    raise NotImplementedError(
        "tax_modeler.scripts.fetch_irs_soi is a stub. The original "
        "ctc-and-eitc IRS SOI scraper has not yet been ported to the "
        "monorepo. For now, manually download the SOI Excel tables from "
        "https://www.irs.gov/statistics/soi-tax-stats-individual-tax-statistics "
        f"into {args.out_dir} (or run the legacy ctc-and-eitc "
        "scripts/parse_irs_soi_data.py and copy the resulting "
        "data/external/ tree). Tracking issue: TODO."
    )


if __name__ == "__main__":
    sys.exit(main())
