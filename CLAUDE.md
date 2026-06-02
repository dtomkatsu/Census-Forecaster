# Census-Forecaster — Claude rules

## Hard rules

- **`SB3125_CD2_FORECAST.md` MUST be updated before committing** whenever methodology, parameters, scenario design, behavioral channels, tax treatment, k-values, or results tables change. The doc has a maintenance note pointing here. Update the relevant sections, the Section 10 results table, and the decomposition.
- **Cadence-aware damping is non-negotiable**: φ=0.92/month for monthly series (CPI), φ=0.85/yr for annual (ACS). Half-lives explicitly documented in `METHODOLOGY.md` §2.3.1. Never copy a φ from one cadence to another.
- **Recency-weighted geometric mean** for trend initialization. Empirically calibrated 90% PIs via backtest, not analytical.
- **Repo-relative paths only** in commits/prompts. Madison's workdir is `~/repos/Census-Forecaster/`.
- **185/185 tests must pass** before committing. Honolulu County backtest baseline MAPE: 6.76%.

## Companion sync

- Housing-Affordability-Tracker cherry-picks the projection module via `census_forecasting/` subpackage. **Any change here must keep the cherry-pick coherent** — last sync commit `d7cbdf4` (Apr 2026). If you make a methodology change that affects the cherry-pick, queue a follow-up task to re-harmonize Housing's copy.

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
