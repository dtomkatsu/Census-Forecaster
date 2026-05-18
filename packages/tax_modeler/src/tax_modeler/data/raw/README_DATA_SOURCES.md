# Cached external data sources

## `irs_soi_zip_hawaii_2022.csv`

Hawaiʻi rows extracted from the IRS Statistics of Income (SOI) ZIP-code data,
tax year 2022 release (published Feb 2025).

- **Source:** <https://www.irs.gov/statistics/soi-tax-stats-individual-income-tax-statistics-zip-code-data-soi>
- **Direct file:** <https://www.irs.gov/pub/irs-soi/22zpallnoagi.csv>
- **Subset:** STATE='HI' rows only (60 rows, 58 active ZIPs + state-total + 99999 placeholder)
- **Columns kept:** `STATEFIPS, STATE, ZIPCODE, agi_stub, N1, A00100, N59660, A59660, N11070, A11070, N2, N03220, A03220`
- **Used by:** `tax_modeler.analysis.district_raking.rake_weights_to_irs_zip`
- **State-total cross-check:** N59660 (EITC count) = 84,010 ✓ matches `hawaii_caseload.csv` IRS SOI anchor.

## CBPP table 367 (unavailable)

The original Tier 2 plan called for caching CBPP's EITC/CTC State Legislative
District spreadsheet as `cbpp_table367_ty2022.csv`. **CBPP no longer publishes
EITC/CTC data at the SLD level on its Program Participation Data Dashboard
(<https://apps.cbpp.org/program_participation/>);** only SNAP has SLD-level
exports, and those are gated behind a Cloudflare/captcha wall that blocks both
`curl` and direct browser downloads from this session.

The IRS SOI ZIP cache above is the authoritative replacement for the
EITC/CTC-by-geography use case (richer columns, ZIP rather than SLD granularity,
direct IRS source). The Tier 2 task is marked closed on these grounds.

If a CBPP-style SLD comparison is needed in the future, paths to explore:
1. Email CBPP directly for the historical SLD spreadsheet
2. Sign in via the Hawaiʻi Appleseed CBPP partner account, if any
3. Use a residential browser proxy to bypass Cloudflare
