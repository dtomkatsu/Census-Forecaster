# census_forecaster — Claude rules

## ⚠️ Downstream consumer (not a cherry-pick)

**Cost-of-Living-Tracker** (`~/Cost-of-Living-Tracker`, formerly Housing-Affordability-Tracker — renamed 2026-08) consumes this package as a **pinned git dependency**, not a cherry-pick. It vendors nothing: its `census_forecasting/` directory is scripts + data + docs that `import census_forecaster.*` from the installed package, and both hashes in its `requirements.txt` pin one Census-Forecaster commit.

So there is **no copy of `acs/projection.py` or `kalman/` to re-harmonize** — verified 2026-08-07, no `kalman` file or reference exists in that repo. A change here reaches it only when someone bumps the pin (both hashes together, then `pip install -r requirements.txt` + pytest there). Do not queue "re-harmonize the cherry-pick" follow-ups; queue "bump the pin" ones, and only when the change actually affects something that repo uses.

*(It genuinely did vendor the projection module until 2026-04-25, when `547b3bb` migrated it to the package. The `d7cbdf4` "last sync commit" this file cited is a commit in that repo, not this one.)*

## Package purpose

ACS and BLS time-series forecasting for Hawaiʻi demographic/economic indicators. Outputs feed into tax_modeler calibration anchors and Cost-of-Living-Tracker.

## Plain-language methodology doc — keep it in sync

**`METHODOLOGY_SIMPLE.md`** (this directory) explains the ensemble design, the lag/change feature scheme, the BLS anchor mechanism, and the tax_modeler hand-off in plain language, no formulas. **Whenever you change the ensemble members, the feature set (`ml_features.py`), the lag/change policy, or the anchor logic (`acs/anchors.py`, `acs/sources/`), update `METHODOLOGY_SIMPLE.md` in the same commit.** It should never describe a mechanism the code has moved away from. The precise technical version (formulas, parameters, backtest numbers) stays in the root `METHODOLOGY.md` §2.3.1 — `METHODOLOGY_SIMPLE.md` is the companion explanation, not a replacement.

## Key entry points

| File | Purpose |
|------|---------|
| `src/census_forecaster/acs/projection.py` | `project_acs_ensemble()` — primary public API |
| `src/census_forecaster/acs/calibration.py` | ACS calibration panel construction |
| `src/census_forecaster/kalman/filter.py` | Kalman filter core |
| `src/census_forecaster/bls/projection.py` | BLS employment projections |

## Public API

```python
from census_forecaster.acs.projection import project_acs_ensemble
from census_forecaster.models import AcsObservation
```

## Non-negotiable parameters (from METHODOLOGY.md §2.3.1)

- **Cadence-aware damping**: φ=0.92/month for monthly series (CPI), φ=0.85/yr for annual (ACS)
- **Trend initialization**: recency-weighted geometric mean
- **Prediction intervals**: empirically calibrated 90% PIs via backtest, NOT analytical
- **Honolulu County backtest baseline MAPE: 6.76%** — regression is a failure

Never copy a φ from one cadence to another. Never switch to analytical PIs without a backtest.

## Test baseline

The full suite must pass — no regressions, no new skips. (The literal count drifts; 1,955 passed / 3 skipped on 2026-08-07. The "185/185" that stood here was years stale — compare against a run on current HEAD.) Honolulu County MAPE ≤ 6.76% on backtest.

## Market signals

`src/census_forecaster/markets/` (tracker, causal screen, signal derivation) ships in the package like everything else; downstream repos get it or not according to their pinned commit (see the cherry-pick note above — there is no per-module sync). Market-signal methodology lives in `METHODOLOGY.md` §Market signals; signals are screen-gated (BH-FDR + 2020-robustness) and ablation-gated before touching any forecast path.
