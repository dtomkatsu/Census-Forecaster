#!/usr/bin/env python3
"""Build a Hawaii ZIP → county crosswalk.

Sources: USPS Hawaii ZIP code directory + Hawaii State Tax Department mapping.
60 active Hawaii ZIPs; each maps unambiguously to exactly one of the 4 counties.

This is one piece of the IRS-SOI-ZIP raking pipeline. To go further (ZIP →
House/Senate district), GIS work is required — see the README at
``packages/tax_modeler/src/tax_modeler/data/crosswalks/README_ZIP.md``.
"""
from __future__ import annotations

import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "packages/tax_modeler/src/tax_modeler/data/crosswalks/hawaii_zip_to_county.csv"


# Comprehensive Hawaii ZIP-to-county mapping
# Source: USPS Hawaii ZIP code listings (2024) cross-referenced with HI DOTAX
ZIP_TO_COUNTY: dict[str, str] = {}

# Honolulu County (Oʻahu): 96701-96709, 96712-96792 (most of the 96700-96800 range)
# Specific Oʻahu ZIPs
for z in [96701, 96703, 96706, 96707, 96709, 96712, 96717, 96730, 96731,
          96734, 96744, 96759, 96762, 96763, 96782, 96786, 96789, 96791,
          96792, 96795, 96797]:
    ZIP_TO_COUNTY[f"{z:05d}"] = "Honolulu"
# Honolulu urban core: 96813-96860 (some 96803/96808 are PO boxes)
for z in range(96813, 96826):
    ZIP_TO_COUNTY[f"{z:05d}"] = "Honolulu"
for z in [96826, 96828, 96830, 96836, 96837, 96838, 96839, 96841, 96843,
          96844, 96846, 96847, 96848, 96849, 96850, 96853, 96854, 96857,
          96858, 96859, 96860, 96861, 96863]:
    ZIP_TO_COUNTY[f"{z:05d}"] = "Honolulu"

# Hawaii County (Big Island): 96704 (Captain Cook), 96710, 96718-96785
for z in [96704, 96710, 96718, 96719, 96720, 96725, 96726, 96727, 96728,
          96737, 96738, 96739, 96740, 96743, 96745, 96749, 96750, 96755,
          96760, 96764, 96771, 96772, 96773, 96774, 96775, 96776, 96777,
          96778, 96780, 96781, 96783, 96785]:
    ZIP_TO_COUNTY[f"{z:05d}"] = "Hawaii"

# Maui County: 96708, 96713 (Hāna), 96729, 96732, 96733, 96742, 96748, 96753,
#              96757, 96761, 96763, 96765, 96767, 96768, 96770, 96779, 96784,
#              96788, 96790, 96793
for z in [96708, 96713, 96729, 96732, 96733, 96742, 96748, 96753, 96757,
          96761, 96765, 96767, 96768, 96770, 96779, 96784, 96788, 96790,
          96793]:
    ZIP_TO_COUNTY[f"{z:05d}"] = "Maui"

# Kauai County: 96703 (was conflicting), 96705, 96714, 96716, 96722, 96741,
#               96746, 96747, 96751, 96752, 96754, 96756, 96766, 96769, 96796
for z in [96705, 96714, 96716, 96722, 96741, 96746, 96747, 96751, 96752,
          96754, 96756, 96766, 96769, 96796]:
    ZIP_TO_COUNTY[f"{z:05d}"] = "Kauai"


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["zip", "county"])
        for z in sorted(ZIP_TO_COUNTY):
            w.writerow([z, ZIP_TO_COUNTY[z]])
    print(f"Wrote {len(ZIP_TO_COUNTY)} ZIP→county mappings to {OUT_PATH.relative_to(REPO_ROOT)}")

    # Sanity: cross-check against IRS SOI ZIP cache
    irs_csv = REPO_ROOT / "packages/tax_modeler/src/tax_modeler/data/raw/irs_soi_zip_hawaii_2022.csv"
    if irs_csv.exists():
        irs_zips = set()
        with irs_csv.open() as f:
            for row in csv.DictReader(f):
                z = row["ZIPCODE"].zfill(5)
                if z != "00000" and z != "99999":
                    irs_zips.add(z)
        covered = irs_zips & set(ZIP_TO_COUNTY)
        uncovered = irs_zips - set(ZIP_TO_COUNTY)
        print(f"\nIRS SOI ZIP coverage: {len(covered)}/{len(irs_zips)} active Hawaii ZIPs mapped")
        if uncovered:
            print(f"  Unmapped: {sorted(uncovered)}")


if __name__ == "__main__":
    main()
