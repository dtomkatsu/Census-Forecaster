# Census-Forecaster — Claude rules

## Hard rules

- **`SB3125_CD2_FORECAST.md` MUST be updated before committing** whenever methodology, parameters, scenario design, behavioral channels, tax treatment, k-values, or results tables change. The doc has a maintenance note pointing here. Update the relevant sections, the Section 10 results table, and the decomposition.
- **Cadence-aware damping is non-negotiable**: φ=0.92/month for monthly series (CPI), φ=0.85/yr for annual (ACS). Half-lives explicitly documented in `METHODOLOGY.md` §2.3.1. Never copy a φ from one cadence to another.
- **Recency-weighted geometric mean** for trend initialization. Empirically calibrated 90% PIs via backtest, not analytical.
- **Repo-relative paths only** in commits/prompts. Madison's workdir is `~/repos/Census-Forecaster/`.
- **The full suite must pass before committing** — no regressions, no new skips. (The literal count drifts as tests are added; it was 1,955 passed / 3 skipped on 2026-08-07, having been written here as "185/185" long after that stopped being true. Compare against a run on the current HEAD, not a number in this file.) Honolulu County backtest baseline MAPE: 6.76%.

## Companion sync

- **Cost-of-Living-Tracker** (`~/Cost-of-Living-Tracker`, formerly
  Housing-Affordability-Tracker — renamed 2026-08) consumes this package as a
  **pinned git dependency**, not a cherry-pick. Both hashes in its
  `requirements.txt` point at one Census-Forecaster commit
  (`census-common` and `census-forecaster`, each `#subdirectory=packages/...`).
  There is **no vendored copy to re-harmonize**: its `census_forecasting/`
  directory holds only scripts, data, backtests and docs, which `import
  census_forecaster.*` from the installed package.
- So a change here reaches that repo only when someone **bumps the pin**. Per
  its own instruction: update both hashes to the same upstream commit, then
  re-run `pip install -r requirements.txt` and pytest there. Nothing is
  automatic, and an un-bumped pin is not a bug — it is the isolation the pin
  exists to provide.
- *(History: it did vendor the projection module until 2026-04-25, when
  `547b3bb` migrated to the package. The old "last sync commit `d7cbdf4`" noted
  here for years is a commit in **that** repo, not this one — it never resolved
  against Census-Forecaster.)*

## Stack

- Python package, fully-typed dataclasses, scipy/numpy.
- Public API: `project_acs_ensemble`, `AcsObservation`, BLS forecaster.
- pytest for tests.

## Source-of-truth docs

- `METHODOLOGY.md` — math and parameter discipline.
- `SB3125_CD2_FORECAST.md` — SB 3125 CD2 methodology, scenarios, results.
- `CBO_COMPONENT_AGING_SCOPE.md` — scoping doc for a future feature.

## Companion docs (in vault)

- `~/.openclaw/workspace/projects/Census-Forecaster.md`
- `~/.openclaw/workspace/tasks/Census-Forecaster.md`
