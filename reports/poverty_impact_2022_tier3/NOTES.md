# Tier 3 production report — TY 2022 (not yet generated)

This directory is a placeholder. The Tier 3 poverty-impact CSVs for
TY 2022 have NOT been generated on this branch because the real Hawaii
PUMS files (`packages/data/raw/pums/psam_{h,p}15.{parquet,csv}`) are
not present in the local working tree where the Tier 3 code landed.

## What to run when PUMS files are available

```bash
.venv/bin/python scripts/poverty_impact_report.py \
    --tax-year 2022 \
    --apply-snap \
    --apply-credit-takeup \
    --apply-moop \
    --apply-housing-subsidy \
    --apply-childcare-subsidy \
    --apply-spm-expenses \
    --apply-wic \
    --apply-liheap \
    --apply-federal-tax \
    --pums-data-dir packages/data/raw/pums \
    --out reports/poverty_impact_2022_tier3/
```

Expected outputs:
* `by_state.csv`
* `by_county.csv`
* `by_house_district.csv`
* `by_senate_district.csv`

## Acceptance criterion

Baseline SPM poverty rate must land in `[0.08, 0.14]` (Census P60-280
Hawaii published range ~10–12%). If not, do NOT commit — instead update
this NOTES.md describing what fell out of range.

## Flags intentionally OFF

* `--pool-spm-units` — Tier 3 validation shows the heuristic doesn't
  fire on synthetic data; magnitude check on real PUMS is pending.
* `--rake-to-irs-zip` — IRS SOI ZIP filer counts + ZIP→HD crosswalk
  not yet bundled; both queued in `tasks/Census-Forecaster.md`.
