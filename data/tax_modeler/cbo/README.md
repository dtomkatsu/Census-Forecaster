# CBO Component Growth Rates

Per-component nominal annual growth factors used by `tax_modeler.calibration.cbo_aging`
for ITEP-style year-by-year aging of filer income components.

## Source

CBO publishes the **Budget and Economic Outlook** twice yearly (Jan + summer
update) at https://www.cbo.gov/topics/budget/economic-projections.

The relevant figures live in:
- **Table 2-3** (or current naming): Components of Income, Calendar Years
- 10-year nominal projections per income component
- Re-published every Outlook with revisions

## Versioned CSVs

Each CSV is named `cbo_components_YYYY-MM.csv` for the publication month
of the source Outlook. To refresh:

1. Download the most recent Outlook XLSX from CBO's website
2. Locate Table 2-3 (Components of Income, Calendar Years)
3. For each component (wages, proprietors, dividends, interest,
   capital gains realizations, pensions, etc.), extract nominal level
   per year for 2022-2031
4. Compute `growth_factor_from_2022 = level_y / level_2022`
5. Save as `cbo_components_<vintage>.csv` matching the schema below

## CSV schema

```
component,year,growth_factor_from_2022,annual_cagr_pct,source_note
```

Where:
- `component` ∈ {wages, proprietors, business, capital_gains, dividends,
  interest, retirement, other}
- `business` is an alias mapped to proprietors+partnership+S-corp
  pass-through; CBO publishes them combined as "proprietors income"
- `other` covers rental, transfers, and miscellaneous components

## Component → income field mapping

| CBO component | tax_modeler PUMS / SOI field |
|---|---|
| wages | `primary_wagp + secondary_wagp` |
| proprietors / business | `primary_semp` (Sch C / partnership / S-corp) |
| capital_gains | `synthetic_cg_share × income` (synthesized + imputed) |
| dividends | `primary_div + secondary_div` |
| interest | `primary_intp + secondary_intp` |
| retirement | `primary_retp + primary_ssp_full + ssip + pap` |
| other | residual: rental, royalty, misc |

## Hawaii calibration

CBO is national. Hawaii has documented divergence from national rates,
particularly in wages (HI tourism economy lags national). Apply
component-specific Hawaii adjustment factors at use time — see
`data/tax_modeler/cbo/hawaii_calibration_factors.json` (built by
`backtests/cbo_aging_hawaii_factors.py`).

## Caveats

The values in `cbo_components_2025-01.csv` are derived from the CBO Jan
2025 Outlook published projections. For final fiscal-note publication,
verify against the source XLSX — CBO occasionally revises historical
nominal levels in subsequent Outlooks.
