"""Download and build the Census PUMA-to-county crosswalk.

Source
------
Census does not publish a direct PUMA-to-county file.  This script derives
one from the Census Tract-to-PUMA relationship files, which map each census
tract to exactly one PUMA.  The allocation factor for a (PUMA, county) pair
is the fraction of that PUMA's tracts that fall in the county (uniform
tract-count weighting — a standard approximation).

Tract-to-PUMA source files:
  2020 PUMAs: https://www2.census.gov/geo/docs/maps-data/data/rel2020/
              2020_Census_Tract_to_2020_PUMA.txt
  2010 PUMAs: https://www2.census.gov/geo/docs/maps-data/data/rel/
              2010_Census_Tract_to_2010_PUMA.txt

CSV format written: PUMA7CE (2-digit state + 5-digit PUMA), GEOID (5-digit
county FIPS), AFACT (allocation factor, sums to 1.0 per PUMA).

Commit the generated file; PUMA boundaries change only every ~10 years.

Usage
-----
    python -m pums_estimator.scripts.refresh_crosswalk [--vintage {2020,2010}]
                                                        [--output-dir PATH]
                                                        [--dry-run]
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import sys
from pathlib import Path

import requests

_TRACT_TO_PUMA_URLS: dict[str, str] = {
    "2020": (
        "https://www2.census.gov/geo/docs/maps-data/data/rel2020/"
        "2020_Census_Tract_to_2020_PUMA.txt"
    ),
    "2010": (
        "https://www2.census.gov/geo/docs/maps-data/data/rel/"
        "2010_Census_Tract_to_2010_PUMA.txt"
    ),
}


def _default_crosswalk_dir() -> Path:
    # packages/pums_estimator/src/pums_estimator/scripts/refresh_crosswalk.py
    # .parents[5] → repo root
    return Path(__file__).resolve().parents[5] / "data" / "crosswalks"


def _fetch_and_transform(
    url: str,
    timeout: float = 120.0,
) -> list[dict[str, object]]:
    """Download tract-to-PUMA file and derive PUMA-to-county allocation factors.

    Allocation factor = (# tracts in PUMA that are in county) / (# tracts in PUMA).
    This is a uniform tract-count approximation; population-weighted AFACTs would
    require the decennial Census population file but are not materially different
    for PUMS reweighting purposes.
    """
    print(f"Downloading {url} ...", file=sys.stderr)
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()

    # utf-8-sig automatically strips the UTF-8 BOM that Census files include.
    text = resp.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames:
        reader.fieldnames = [f.strip() for f in reader.fieldnames]

    # Count tracts per (PUMA7CE, GEOID) pair and per PUMA.
    puma_county_tracts: dict[tuple[str, str], int] = collections.Counter()
    puma_tracts: dict[str, int] = collections.Counter()

    for row in reader:
        state = row.get("STATEFP", "").strip().zfill(2)
        county3 = row.get("COUNTYFP", "").strip().zfill(3)
        puma5 = row.get("PUMA5CE", "").strip().zfill(5)
        if not state or not county3 or not puma5:
            continue
        puma7 = state + puma5
        geoid = state + county3
        puma_county_tracts[(puma7, geoid)] += 1
        puma_tracts[puma7] += 1

    rows: list[dict[str, object]] = []
    for (puma7, geoid), count in sorted(puma_county_tracts.items()):
        total = puma_tracts.get(puma7, count)
        afact = count / total if total > 0 else 1.0
        rows.append({"PUMA7CE": puma7, "GEOID": geoid, "AFACT": round(afact, 6)})

    return rows


def _atomic_write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["PUMA7CE", "GEOID", "AFACT"])
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download Census PUMA-to-county crosswalk files.",
    )
    parser.add_argument(
        "--vintage",
        choices=["2020", "2010"],
        default="2020",
        help="PUMA vintage year (default: 2020; use 2010 for pre-2022 ACS).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to write CSV files (default: data/crosswalks/ at repo root).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download and parse but do not write files.",
    )
    args = parser.parse_args(argv)

    vintage: str = args.vintage
    out_dir: Path = args.output_dir or _default_crosswalk_dir()
    url = _TRACT_TO_PUMA_URLS[vintage]

    rows = _fetch_and_transform(url)

    n_rows = len(rows)
    n_pumas = len({r["PUMA7CE"] for r in rows})
    print(
        f"Parsed {n_rows} rows covering {n_pumas} PUMAs.",
        file=sys.stderr,
    )

    if args.dry_run:
        print("[dry-run] No files written.", file=sys.stderr)
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"puma_county_{vintage}.csv"
    _atomic_write_csv(dest, rows)
    print(f"Wrote {dest}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
