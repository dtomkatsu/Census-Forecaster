"""ACS (American Community Survey) forecasting subpackage.

Modules
-------
* `client` — public-API ACS fetcher with on-disk JSON cache.
* `projection` — damped local linear trend (log space) and AR(1) on
  log-differences. Both produce `ForecastPoint` outputs with sample SE
  (from MOE) and forecast SE (from residual variance) propagated.
* `ensemble` — inverse-variance combination of trend + AR(1), with
  optional macro anchor (BLS-derived growth rate) at fixed weight.
"""
from .client import AcsClient, DEFAULT_CACHE_PATH, SUSPENDED_ONE_YEAR
from .projection import (
    project_damped_trend,
    project_ar1_log_diff,
    fit_damped_trend,
    fit_ar1_log_diff,
    DampedTrendFit,
    AR1LogDiffFit,
    effective_year,
    ANNUAL_RATE_CAP,
    EMPIRICAL_SE_INFLATOR,
)
from .ensemble import (
    project_ensemble,
    macro_anchor_projection,
    combine_forecasts,
)

__all__ = [
    "AcsClient",
    "DEFAULT_CACHE_PATH",
    "SUSPENDED_ONE_YEAR",
    "project_damped_trend",
    "project_ar1_log_diff",
    "project_ensemble",
    "fit_damped_trend",
    "fit_ar1_log_diff",
    "DampedTrendFit",
    "AR1LogDiffFit",
    "macro_anchor_projection",
    "combine_forecasts",
    "effective_year",
    "ANNUAL_RATE_CAP",
    "EMPIRICAL_SE_INFLATOR",
]
