"""Census Forecaster — forecast current-period values from older ACS / BLS data.

Two parallel forecasting surfaces:

* `census_forecaster.acs` — project ACS estimates (annual cadence, 1y/5y
  vintages) forward to a target year, with full MOE → SE → CI propagation.
* `census_forecaster.bls` — project BLS time series (typically monthly /
  bimonthly CPI) forward to a target month, with calibrated 90% CIs.

Quick start (ACS):
    >>> from census_forecaster import AcsObservation, project_acs_ensemble
    >>> obs = [
    ...     AcsObservation(estimate=63488, moe=812, year=2018, vintage="5y",
    ...                    geoid="15003", indicator="B19013_001E"),
    ...     # ... more observations
    ... ]
    >>> forecast = project_acs_ensemble(obs, target_year=2026)
    >>> forecast.point, forecast.ci90_low, forecast.ci90_high

Quick start (BLS CPI):
    >>> from datetime import date
    >>> from census_forecaster.bls import (
    ...     fetch_cpi_data, project_forward_full,
    ... )
    >>> data = fetch_cpi_data(["CUURS49ASA0"], 2018, 2026)
    >>> proj = project_forward_full(data["CUURS49ASA0"], date(2026, 4, 1))
    >>> proj.value, proj.cap_fired, proj.forecast_se_log
"""
from common.models import (
    AcsObservation,
    BlsObservation,
    ForecastPoint,
    GeographySeries,
)
from .acs.projection import (
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
from .acs.ensemble import (
    project_ensemble as project_acs_ensemble,
    macro_anchor_projection,
    combine_forecasts,
)

__version__ = "0.2.0"

__all__ = [
    # Data classes
    "AcsObservation",
    "BlsObservation",
    "ForecastPoint",
    "GeographySeries",
    # ACS forecasting
    "project_damped_trend",
    "project_ar1_log_diff",
    "project_acs_ensemble",
    "fit_damped_trend",
    "fit_ar1_log_diff",
    "DampedTrendFit",
    "AR1LogDiffFit",
    "macro_anchor_projection",
    "combine_forecasts",
    "effective_year",
    "ANNUAL_RATE_CAP",
    "EMPIRICAL_SE_INFLATOR",
    "__version__",
]
