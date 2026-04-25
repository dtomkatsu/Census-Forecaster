"""Forward-projection of BLS CPI series past the latest observed print.

Use case
~~~~~~~~
You have a BLS CPI series (e.g. Honolulu food at home `CUURS49ASAF11`) with
the latest print at month T₀, and you want a value at T₀ + h months. This
module produces it via a recency-weighted, damped, capped compound trend,
with a calibrated 90% prediction interval.

Algorithm
~~~~~~~~~
1. Recency-weighted geometric mean of pairwise per-month rates over the
   last *N* pairs (`max_pairs`, default = all). Most recent pair weight
   1.0; each step back halves the weight.
2. Clip the rate to ±`PROJ_MONTHLY_CAP` (default 0.0189/mo ≈ ±25%/yr).
3. Apply Gardner-McKenzie damped compounding: at horizon h, rate at month
   k applies ``rate × phi^(k-1)``. Default phi = 0.92, half-life ≈ 8 months.
4. Compute closed-form forecast SE in log space using residual std of the
   pairwise rates × inflator κ. Default κ = 1.50 (calibrated on a Hawaii
   CPI panel; re-derive for your own region via the backtest harness).

Discipline rules (shared with the ACS forecaster):
* Compound rates, not arithmetic — `(1+r)^h`, never `1 + r·h`.
* Per-period rate cap stops noisy single-print spikes from compounding
  forever.
* Method tagging — every result carries `cap_fired`, `monthly_rate`,
  `forecast_se_log`, `point_uncapped`.

References
----------
Gardner, E. & McKenzie, E. (1985). "Forecasting trends in time series."
  *Management Science.* — damped trend pattern.
Hyndman, R. & Athanasopoulos, G. (2018). *Forecasting: Principles and
  Practice* (2nd ed.). — modern damped-trend treatment.
Cleveland Fed WP 24-06 — short-horizon CPI nowcasting evaluations.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from .client import find_nearest_periods


# Per-month projection cap: bounds noisy bimonthly print from compounding
# into an unrealistic extrapolation. (1+0.0189)^12 ≈ 1.252 → ±~25%/yr.
PROJ_MONTHLY_CAP = 0.0189

# Damping factor (Gardner & McKenzie 1985). Each successive month of
# forecast carries phi^(h-1) of the trend, so the projection asymptotes
# rather than compounding indefinitely. phi=0.92 means by month 6 we apply
# ~61% of the latest trend; by month 12, ~37%. Trend half-life ~8.3 months.
PROJ_DAMPING = 0.92

# Empirical SE inflator. Multiplies the closed-form forecast SE (in log
# space) so that walk-forward 90% prediction intervals achieve ~90% coverage.
# Calibrated value 1.50 derived from a 5-series × 63-anchor × 3-horizon
# walk-forward on the Hawaii Honolulu CPI panel: κ=1.0 gave ~72% coverage,
# κ=1.5 gave ~89% (closest to 90% on a 0.1-step grid).
#
# This is a single global multiplier — *not* tuned per series. Re-derive
# for your own region with `census_forecaster.backtest.cpi.calibrate`.
_PROJ_SE_INFLATOR = 1.50

# Fallback residual log-std for series with only one valid pair (n=2).
# Median across-series in-sample std of pairwise log rates is ≈ 0.005 for
# Honolulu food/rent/all-items at the bimonthly cadence.
_RESIDUAL_LOG_STD_PRIOR = 0.005

# Z-score for symmetric 90% prediction intervals (Φ⁻¹(0.95)).
_Z_90 = 1.6448536269514722


@dataclass(frozen=True)
class ProjectionResult:
    """Diagnostic-rich output of a forward CPI projection.

    Attributes
    ----------
    value : float
        Projected CPI index value at the target date, after damping + cap.
    monthly_rate : float
        Recency-weighted, *capped* per-month compound rate that drove the
        projection. Equals the smoothed rate clamped to ±cap.
    cap_fired : bool
        True if the smoothed rate exceeded the cap and was clipped.
    residual_log_std : float
        In-sample std of pairwise log rates against the smoothed rate.
        Falls back to `_RESIDUAL_LOG_STD_PRIOR` when only one pair exists.
    forecast_se_log : float
        Closed-form forecast SE in log space at the target horizon. Use
        with `_Z_90` to construct a CI: log(value) ± _Z_90 × forecast_se_log.
    point_uncapped : float
        What the projection would have been with no cap, useful for honest
        CI widening when cap_fired=True.
    horizon_months : int
        Months between the latest observed point and the target date.
    """
    value: float
    monthly_rate: float
    cap_fired: bool
    residual_log_std: float
    forecast_se_log: float
    point_uncapped: float
    horizon_months: int


def _latest_observed_point(points: list[dict]) -> dict | None:
    """Most recent (year, period) observation."""
    if not points:
        return None
    return max(points, key=lambda p: (p["year"], int(p["period"][1:])))


def smoothed_monthly_rate(
    ordered: list[dict],
    max_pairs: int | None = None,
) -> float | None:
    """Recency-weighted geometric mean of pairwise per-month growth rates.

    For a series with N≥2 observations, computes the per-month compound
    rate between each consecutive pair, then blends with exponential
    recency weights (most-recent = 1.0, prior = 0.5, prior-prior = 0.25, …).

    With exactly 2 points, returns the single pairwise rate (degenerate
    case preserved for backwards compatibility). With 3+ points, smoothing
    absorbs single-period noise.

    `max_pairs` (optional) caps the lookback to the most recent N pairs.

    Returns None if no usable pair exists.
    """
    if max_pairs is not None and max_pairs > 0 and len(ordered) > max_pairs + 1:
        ordered = ordered[-(max_pairs + 1):]

    pairs: list[tuple[float, float]] = []
    for i in range(1, len(ordered)):
        prev, curr = ordered[i - 1], ordered[i]
        prev_y, prev_m = prev["year"], int(prev["period"][1:])
        curr_y, curr_m = curr["year"], int(curr["period"][1:])
        months_between = (curr_y - prev_y) * 12 + (curr_m - prev_m)
        if months_between <= 0 or prev["value"] <= 0:
            continue
        monthly_rate = (curr["value"] / prev["value"]) ** (1.0 / months_between) - 1.0
        weight = 0.5 ** (len(ordered) - 1 - i)
        pairs.append((monthly_rate, weight))

    if not pairs:
        return None
    return sum(r * w for r, w in pairs) / sum(w for _, w in pairs)


def residual_log_std(
    ordered: list[dict],
    smoothed_rate: float,
    max_pairs: int | None = None,
) -> float:
    """In-sample std of pairwise log rates against the smoothed rate.

    Falls back to `_RESIDUAL_LOG_STD_PRIOR` when fewer than 2 pairs are
    available, since std is undefined in that case.
    """
    if max_pairs is not None and max_pairs > 0 and len(ordered) > max_pairs + 1:
        ordered = ordered[-(max_pairs + 1):]

    log_smoothed = math.log1p(smoothed_rate) if smoothed_rate > -1.0 else 0.0
    log_rates: list[float] = []
    for i in range(1, len(ordered)):
        prev, curr = ordered[i - 1], ordered[i]
        prev_y, prev_m = prev["year"], int(prev["period"][1:])
        curr_y, curr_m = curr["year"], int(curr["period"][1:])
        months_between = (curr_y - prev_y) * 12 + (curr_m - prev_m)
        if months_between <= 0 or prev["value"] <= 0 or curr["value"] <= 0:
            continue
        log_rates.append(math.log(curr["value"] / prev["value"]) / months_between)

    if len(log_rates) < 2:
        return _RESIDUAL_LOG_STD_PRIOR

    residuals = [r - log_smoothed for r in log_rates]
    mean_r = sum(residuals) / len(residuals)
    var = sum((r - mean_r) ** 2 for r in residuals) / (len(residuals) - 1)
    return math.sqrt(max(var, 0.0))


def forecast_se_log(
    residual_std: float,
    h_months: int,
    phi: float = PROJ_DAMPING,
    inflator: float = 1.0,
) -> float:
    """Closed-form damped-trend forecast SE in log space at horizon h.

    Variance of cumulative h-step damped-trend forecast on log-CPI:
        Var(log_target) = σ² · Σ_{j=1..h} φ^{2(j−1)} · κ²
    Geometric sum collapses to h when phi → 1, else
        Σ = (1 − φ^{2h}) / (1 − φ²).
    """
    if h_months <= 0 or residual_std <= 0:
        return 0.0
    if abs(phi - 1.0) < 1e-9:
        var_factor = float(h_months)
    else:
        phi2 = phi * phi
        var_factor = (1.0 - phi2 ** h_months) / (1.0 - phi2)
    var_log = (residual_std ** 2) * var_factor * (inflator ** 2)
    return math.sqrt(var_log)


def damped_compound_factor(
    monthly_rate: float,
    months_beyond: int,
    phi: float = PROJ_DAMPING,
) -> float:
    """Compound growth over `months_beyond` with Gardner-McKenzie damping.

    Each successive month applies `phi^(h-1)` of the trend. Reduces to
    standard compounding when `phi == 1.0`, and to flat when
    `monthly_rate == 0`.
    """
    factor = 1.0
    for h in range(1, months_beyond + 1):
        damped_rate = monthly_rate * (phi ** (h - 1))
        factor *= 1.0 + damped_rate
    return factor


def project_forward_full(
    points: list[dict],
    target_date: date,
    *,
    phi: float = PROJ_DAMPING,
    cap: float = PROJ_MONTHLY_CAP,
    max_pairs: int | None = None,
    inflator: float = _PROJ_SE_INFLATOR,
) -> ProjectionResult:
    """Forward CPI projection with full diagnostic output.

    Compute path:
      1. Recency-weighted smoothed per-month compound rate.
      2. Clip rate to ±cap, recording whether the cap fired.
      3. Apply damped compounding to get the point estimate.
      4. Compute residual log-std and closed-form forecast SE.
      5. Also compute the *uncapped* projection for honest CI widening.
    """
    if not points:
        raise ValueError("cannot project forward from empty series")

    ordered = sorted(points, key=lambda p: (p["year"], int(p["period"][1:])))
    latest = ordered[-1]
    latest_value = float(latest["value"])
    latest_year, latest_month = latest["year"], int(latest["period"][1:])
    months_beyond = (
        (target_date.year - latest_year) * 12 + (target_date.month - latest_month)
    )

    if months_beyond <= 0 or len(ordered) < 2:
        return ProjectionResult(
            value=latest_value, monthly_rate=0.0, cap_fired=False,
            residual_log_std=_RESIDUAL_LOG_STD_PRIOR, forecast_se_log=0.0,
            point_uncapped=latest_value,
            horizon_months=max(months_beyond, 0),
        )

    smoothed = smoothed_monthly_rate(ordered, max_pairs=max_pairs)
    if smoothed is None:
        return ProjectionResult(
            value=latest_value, monthly_rate=0.0, cap_fired=False,
            residual_log_std=_RESIDUAL_LOG_STD_PRIOR, forecast_se_log=0.0,
            point_uncapped=latest_value, horizon_months=months_beyond,
        )

    capped_rate = max(min(smoothed, cap), -cap)
    cap_fired = (capped_rate != smoothed)

    point = latest_value * damped_compound_factor(capped_rate, months_beyond, phi=phi)
    point_uncapped = latest_value * damped_compound_factor(smoothed, months_beyond, phi=phi)

    residual_std = residual_log_std(ordered, capped_rate, max_pairs=max_pairs)
    se_log = forecast_se_log(residual_std, months_beyond, phi=phi, inflator=inflator)

    return ProjectionResult(
        value=float(point),
        monthly_rate=float(capped_rate),
        cap_fired=bool(cap_fired),
        residual_log_std=float(residual_std),
        forecast_se_log=float(se_log),
        point_uncapped=float(point_uncapped),
        horizon_months=int(months_beyond),
    )


def project_forward(points: list[dict], target_date: date) -> float:
    """Backwards-compatible scalar wrapper over `project_forward_full`."""
    return project_forward_full(points, target_date).value


def compute_cpi_ratio(
    cpi_data: dict,
    series_id: str,
    baseline_date: date,
    target_date: date,
) -> dict:
    """Compute CPI ratio (target / baseline) for a series.

    Returns a dict with full diagnostic surface:

        ratio              float    — target_cpi / baseline_cpi (1.0 if unavailable)
        is_projected       bool     — target is past the latest observation
        method             str      — 'exact' | 'interpolated' | 'projected' | 'unavailable'
        latest_observed    str|None — ISO "YYYY-MM" of the latest print
        target_period      str      — ISO of the target date
        cap_fired          bool|None
        monthly_rate       float|None — capped monthly compound rate used
        implied_annual_rate float|None — (1 + monthly_rate)^12 − 1
        forecast_se        float|None — log-space SE on the ratio
        ratio_ci90_low     float|None
        ratio_ci90_high    float|None
        horizon_months     int|None

    The projection-only fields are None unless `method == 'projected'`,
    so existing callers only reading the headline `ratio` / `method`
    fields are unaffected.

    When `cap_fired` is True, the upper CI is widened to at least the
    uncapped projection's implied ratio — honest about the truncation.
    """
    target_iso = f"{target_date.year}-{target_date.month:02d}"
    points = cpi_data.get(series_id, [])
    latest = _latest_observed_point(points)
    latest_iso = (
        f"{latest['year']}-{int(latest['period'][1:]):02d}"
        if latest is not None else None
    )

    result = {
        "ratio":               1.0,
        "is_projected":        False,
        "method":              "unavailable",
        "latest_observed":     latest_iso,
        "target_period":       target_iso,
        "cap_fired":           None,
        "monthly_rate":        None,
        "implied_annual_rate": None,
        "forecast_se":         None,
        "ratio_ci90_low":      None,
        "ratio_ci90_high":     None,
        "horizon_months":      None,
    }

    baseline_cpi, _b_method, _b_proj = _value_at(cpi_data, series_id, points, latest, baseline_date)
    target_cpi, t_method, t_proj    = _value_at(cpi_data, series_id, points, latest, target_date)

    if baseline_cpi is None or target_cpi is None or baseline_cpi == 0:
        return result

    ratio = target_cpi / baseline_cpi
    result["ratio"]        = ratio
    result["method"]       = t_method
    result["is_projected"] = (t_method == "projected")

    if t_proj is not None:
        annual_rate = (1.0 + t_proj.monthly_rate) ** 12 - 1.0
        se_log_ratio = t_proj.forecast_se_log
        if se_log_ratio > 0:
            ci_lo = ratio * math.exp(-_Z_90 * se_log_ratio)
            ci_hi = ratio * math.exp(+_Z_90 * se_log_ratio)
        else:
            ci_lo = ci_hi = ratio
        if t_proj.cap_fired and t_proj.point_uncapped > t_proj.value:
            ci_hi = max(ci_hi, t_proj.point_uncapped / baseline_cpi)

        result["cap_fired"]           = t_proj.cap_fired
        result["monthly_rate"]        = t_proj.monthly_rate
        result["implied_annual_rate"] = annual_rate
        result["forecast_se"]         = se_log_ratio
        result["ratio_ci90_low"]      = ci_lo
        result["ratio_ci90_high"]     = ci_hi
        result["horizon_months"]      = t_proj.horizon_months

    return result


def _value_at(
    cpi_data: dict, series_id: str, points: list[dict], latest: dict | None,
    target_date: date,
) -> tuple[float | None, str, ProjectionResult | None]:
    """Resolve a CPI index value at *target_date* and label which method was used.

    Returns (value, method, projection_or_none) where method is one of:
        'exact'        — target matches an observed period
        'interpolated' — target is strictly between two observed points
        'projected'    — target is past the latest observation
        'unavailable'  — no usable data
    """
    if latest is None:
        return None, "unavailable", None

    before, after = find_nearest_periods(
        cpi_data, series_id, target_date.year, target_date.month
    )
    if before is None:
        return None, "unavailable", None

    latest_year, latest_month = latest["year"], int(latest["period"][1:])
    beyond_latest = (target_date.year, target_date.month) > (latest_year, latest_month)

    if after is None:
        if beyond_latest:
            proj = project_forward_full(points, target_date)
            return proj.value, "projected", proj
        return float(before["value"]), "exact", None

    return _interpolate(before, after, target_date), "interpolated", None


def _interpolate(before: dict, after: dict, target: date) -> float:
    """Linear interpolation between two CPI data points."""
    if before == after:
        return before["value"]
    b_month = before["year"] * 12 + int(before["period"][1:])
    a_month = after["year"] * 12 + int(after["period"][1:])
    t_month = target.year * 12 + target.month
    span = a_month - b_month
    if span == 0:
        return before["value"]
    fraction = (t_month - b_month) / span
    return before["value"] + fraction * (after["value"] - before["value"])
