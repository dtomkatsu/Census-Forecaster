# census_forecaster — Claude rules

## ⚠️ Cherry-pick warning

**Housing-Affordability-Tracker** cherry-picks `acs/projection.py` and `kalman/` from this package. Any methodology change must be re-harmonized in that repo (last sync commit `d7cbdf4`, Apr 2026). Queue a follow-up task when touching these modules.

## Package purpose

ACS and BLS time-series forecasting for Hawaiʻi demographic/economic indicators. Outputs feed into tax_modeler calibration anchors and the Housing-Affordability-Tracker.

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
