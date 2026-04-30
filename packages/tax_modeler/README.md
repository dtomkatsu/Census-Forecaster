# tax_modeler

Hawaii state income tax + federal EITC microsimulation, ported from
[ctc-and-eitc](https://github.com/dtomkatsu/ctc-and-eitc) and integrated into the
Census-Forecaster monorepo as a fourth workspace package alongside `common`,
`census_forecaster`, and `pums_estimator`.

## What it does

- **Liability**: Hawaii state income tax bracket-walk math (2022 brackets, 2027
  baseline scenarios).
- **Credits**: Federal EITC + Hawaii state credits (food/excise, dependent care,
  renewable energy).
- **Deductions**: Standard + itemized deduction calculations.
- **Tax-unit construction**: Builds tax filing units from PUMS microdata —
  filing-status repair, dependent assignment, household aggregation. PUMS data
  is sourced via `pums_estimator.fetch_pums` (replacing the original
  `PUMSDataLoader`).
- **Calibration**: IPF, DOTAX SOI parsing, IRS bracket calibration, Pareto
  bracket scaling, ultra-high-income synthesis.
- **Validation**: Revenue validation against IRS SOI and Hawaii DOTAX tables.
- **Projection**: Income-growth and inflation factors via
  `census_forecaster`'s ensemble (replacing the original `EnsembleProjector`).

## Public API

```python
from tax_modeler import (
    # Domain types
    TaxUnit, FilingStatus, HawaiiTaxParameters,
    # Calculations
    calculate_hawaii_tax, calculate_hawaii_tax_for_units,
    compute_eitc, compute_standard_deduction, load_hawaii_brackets,
    # Orchestration
    TaxSystemConfig, TaxSystemRegistry, TaxCalculator,
    # Calibration / adjustments / validation
    CalibrationOrchestrator, IPFCalibrationOrchestrator, DOTAXSOIParser,
    apply_pareto_adjustment, synthesize_high_income,
    validate_against_irs_soi, validate_against_dotax,
    # Adapters (bridges to other monorepo packages)
    load_hawaii_pums, project_income_growth,
)
```

## Data files

Bundled in the wheel (small reference tables, ~25 KB):
- `data/tax_tables/hawaii_2022/*.json` — bracket and exemption tables
- `data/policy/baseline_2022_deductions.json` — standard/itemized policy
  baseline

Checked into the repo at `data/tax_modeler/` (~2 MB total):
- `crosswalks/` — PUMA / district / ZIP geography crosswalks
- `irs_soi/` — small IRS SOI summary tables

Fetched on demand (gitignored — see scripts):
- `data/tax_modeler/raw/` — Hawaii DOTAX SOI tables (~83 MB).
  Run `python -m tax_modeler.scripts.fetch_dotax_soi`.
- `data/tax_modeler/external/` — IRS national SOI Excel files (~639 MB).
  Run `python -m tax_modeler.scripts.fetch_irs_soi`.
- `data/tax_modeler/processed/` — calibration run artifacts.

Tests that depend on `raw/` or `external/` are skipped automatically when those
directories are empty so a fresh clone has a green test suite.

## Installation

From the monorepo root:

```bash
uv sync --all-packages --extra dev    # installs all four packages in editable mode
```

Optional extras:
- `tax-modeler[ui]` — pulls Streamlit for the UI demo
- `tax-modeler[geo]` — pulls geopandas for shapefile-based analysis

## Two entry points each for PUMS and projection

The simple "give me a DataFrame / scalar" use cases delegate to the
monorepo's `pums_estimator` / `census_forecaster` packages via thin
adapters. The full-fat loaders from ctc-and-eitc are kept alongside
because they have functionality the simple adapters don't:

| Task | Simple adapter (preferred) | Full-fat loader (advanced) |
|---|---|---|
| Load Hawaii PUMS | `tax_modeler.load_hawaii_pums(year)` (delegates to `pums_estimator.fetch_pums`) | `tax_modeler.PUMSDataLoader().load_data(...)` — incremental batched loads, vintage column handling, `create_tax_units` shortcut |
| Income growth factor | `tax_modeler.project_income_growth(history, target_year)` (delegates to `census_forecaster.fit_damped_trend`) | `tax_modeler.EnsembleProjector(...)` — BLS OES wage blending, occupation matching, tax-unit-vectorized `project_income` |

For one-off analysis use the simple helpers; for full-population
pipeline runs use the full-fat loaders. Both are exported at the
package level — `from tax_modeler import load_hawaii_pums, PUMSDataLoader`.

## Other reused infrastructure

| ctc-and-eitc original | Replaced by |
|---|---|
| `src/config/income_growth_factors.py` | `census_forecaster.macro_anchor_projection` |
| Local FIPS parsing | `common.geography.state_fips`, `common.geography.county_fips` |

## Provenance

Imported via `git subtree add` on 2026-04-29 from
`/Users/dtomkatsu/ctc-and-eitc` branch `feature/bea-rates-dotax-fix`
(commit `0bea005`, "Align calculator to TY2027 baseline; remove CDCC"). Run
`git log --follow <file>` on any moved file to see its full pre-import history.
