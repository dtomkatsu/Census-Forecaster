# census_forecaster — Claude rules

## ⚠️ Cherry-pick warning

**Housing-Affordability-Tracker** cherry-picks `acs/projection.py` and `kalman/` from this package. Any methodology change must be re-harmonized in that repo (last sync commit `d7cbdf4`, Apr 2026). Queue a follow-up task when touching these modules.

## Package purpose

ACS and BLS time-series forecasting for Hawaiʻi demographic/economic indicators. Outputs feed into tax_modeler calibration anchors and the Housing-Affordability-Tracker.

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

185/185 tests must pass. Honolulu County MAPE ≤ 6.76% on backtest.

## Market signals

`src/census_forecaster/markets/` (tracker, causal screen, signal derivation) is **NOT part of the Housing-Affordability-Tracker cherry-pick** — only `acs/projection.py` and `kalman/` sync there. Market-signal methodology lives in `METHODOLOGY.md` §Market signals; signals are screen-gated (BH-FDR + 2020-robustness) and ablation-gated before touching any forecast path.
