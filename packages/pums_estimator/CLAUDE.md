# pums_estimator — Claude rules

## Package purpose

PUMS-based population estimation and raking/calibration utilities. Provides raked weights for PUMS microdata so that weighted sums match ACS published totals on demographic control margins.

## Key entry points

| File | Purpose |
|------|---------|
| `src/pums_estimator/estimation/rake.py` | Iterative proportional fitting (IPF/raking) |
| `src/pums_estimator/pums/client.py` | PUMS data fetching and caching |
| `src/pums_estimator/controls.py` | Control total definitions |

## Consumers

This package is used **only** by `tax_modeler/loaders/` for weight calibration. It is not imported directly by any root-level forecast scripts.

## Notes

- `estimation/synthetic.py` — synthetic population generation for testing; do not use for production estimates
- `pums/crosswalk.py` — geographic PUMA crosswalk; refresh with `scripts/refresh_crosswalk.py` when Census updates PUMA boundaries
