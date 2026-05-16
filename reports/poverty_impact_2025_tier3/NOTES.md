# Tier 3 production report — TY 2025 (not yet generated)

Placeholder. See `reports/poverty_impact_2022_tier3/NOTES.md` for full
context; rerun the same command with `--tax-year 2025` and
`--out reports/poverty_impact_2025_tier3/` when PUMS files land.

## Note on TY 2025

The TY 2025 run exercises `project_tax_units_forward(target_year=2025)`
with year-keyed federal brackets (Rev. Proc. 2024-40 inflation
adjustments) and the IRS take-up calibration falling back to TY 2022
SOI anchors. Sanity-check: 2025 baseline rate ≤ 2024 (inflation
adjustments raise both thresholds and EITC/CTC parameters, so absolute
poverty should not rise materially relative to 2024).
