"""BLS (Bureau of Labor Statistics) forecasting subpackage.

Modules
-------
* `client` — public-API BLS fetcher + period helpers (find_nearest_periods,
  expected_latest_period_bimonthly, fetch_if_stale, ...).
* `projection` — recency-weighted, damped, capped CPI forward-projection
  with closed-form 90% prediction intervals, calibrated to ~90% empirical
  coverage on a Honolulu CPI panel.

The projection module's `_PROJ_SE_INFLATOR=1.50` was calibrated on a
5-series × 63-anchor × 3-horizon walk-forward. Re-derive for your own
region with `census_forecaster.backtest.cpi.calibrate_inflator`.
"""
from .client import (
    BLS_API_URL,
    fetch_cpi_data,
    fetch_and_cache,
    fetch_if_stale,
    load_cached_cpi,
    get_value,
    get_latest,
    date_to_bls_period,
    find_nearest_periods,
    expected_latest_period_bimonthly,
    cache_has_period,
    HONOLULU_DATA_MONTHS,
    BLS_RELEASE_DAY,
)
from .projection import (
    ProjectionResult,
    project_forward,
    project_forward_full,
    smoothed_monthly_rate,
    residual_log_std,
    forecast_se_log,
    damped_compound_factor,
    compute_cpi_ratio,
    PROJ_DAMPING,
    PROJ_MONTHLY_CAP,
)

__all__ = [
    # Client
    "BLS_API_URL",
    "fetch_cpi_data",
    "fetch_and_cache",
    "fetch_if_stale",
    "load_cached_cpi",
    "get_value",
    "get_latest",
    "date_to_bls_period",
    "find_nearest_periods",
    "expected_latest_period_bimonthly",
    "cache_has_period",
    "HONOLULU_DATA_MONTHS",
    "BLS_RELEASE_DAY",
    # Projection
    "ProjectionResult",
    "project_forward",
    "project_forward_full",
    "smoothed_monthly_rate",
    "residual_log_std",
    "forecast_se_log",
    "damped_compound_factor",
    "compute_cpi_ratio",
    "PROJ_DAMPING",
    "PROJ_MONTHLY_CAP",
]
