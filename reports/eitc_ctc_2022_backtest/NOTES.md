# TY 2022 backtest — notes

## Source

`scripts/eitc_ctc_geo_report.py --tax-year 2022 --compare-cbpp --apply-takeup`
on Hawaii ACS PUMS 5-year (2018–2022, FIPS 15). IRS take-up imputation
calibrated to `hawaii_caseload.csv` rows: `eitc` (84,010 returns / $184.7M),
`actc` (60,600 / $117.8M).

## State totals vs IRS SOI Hawaii TY 2022

| Metric                | Modeler   | IRS SOI   | Δ      |
|-----------------------|-----------|-----------|--------|
| EITC claimants        | 84,063    | 84,010    | +0.1%  |
| EITC dollars          | $124.3M   | $184.7M   | -32.7% |
| CTC dollars (total)   | $670.1M   | $469.5M   | +42.7% |
| Refundable CTC (ACTC) | $247.1M   | $117.8M   | +109%  |

**Claimant counts match** to within 0.1% — the take-up imputation is doing
its job. **Dollar totals diverge**:

- **EITC dollars are 33% LOW**: average modeled EITC is ~$1,480/claimant vs
  IRS ~$2,200/claimant. Likely under-counting qualifying children for some
  households (PUMS-derived dependent ages are synthetic — `enrich_for_credits`
  assumes age=10 for every counted dependent) or under-estimating earned
  income for the phase-in band.
- **CTC dollars are 43% HIGH**: enrichment counts every dependent as a
  qualifying child under 17 (synthetic age=10), so non-child dependents
  (elderly relatives, adult students) are erroneously credited. This is
  documented in `pipeline.py:31-39`.
- **Refundable CTC (ACTC) is 109% HIGH** for the same reason — combined with
  ACTC take-up only zeroing out 60K returns out of ~120K eligible.

Both gaps are upstream microsim issues, not Phase 3 take-up logic.
Closing them requires person-level join with PUMS to recover actual
dependent ages (CTC eligibility ends at age 17). Captured as follow-up.

## CBPP table 367 comparison

**Not generated**: CBPP's data endpoint
(`apps.cbpp.org/program_participation/data/getSpreadsheetByID&table_id=367`)
returns HTTP 403 to programmatic clients (Cloudflare). The script falls
back to a cached file at
`packages/tax_modeler/src/tax_modeler/data/raw/cbpp_table367_ty2022.csv`
when present.

**To enable comparison**: download CBPP table 367 (Senate Districts, Tax
Year 2022) from <https://apps.cbpp.org/program_participation/#table/367>
in a browser, save the CSV/Excel export, normalise to columns
`senate_district, eitc_returns, eitc_dollars, ctc_dollars`, drop into
`packages/tax_modeler/src/tax_modeler/data/raw/cbpp_table367_ty2022.csv`,
and re-run.

## Geographic coverage

- by_state.csv: 1 row (state total).
- by_county.csv: 4 rows (all Hawaii counties present).
- by_house_district.csv: 33 of 51 HDs. Districts with zero or near-zero
  PUMS sample assignments (PUMA→HD hash) are dropped.
- by_senate_district.csv: 18 of 25 SDs (same reason).

The PUMS→district hash gives one average per PUMA spread across overlapping
HDs/SDs, so districts whose underlying PUMA had no eligible filers get no
row. CBPP uses IRS ZIP-code claim data raked to LD geography, which has
much finer within-PUMA resolution. See EITC_CTC_GEO_PLAN.md "Out of scope"
for the raking follow-up.
