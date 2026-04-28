"""Hidden-data hold-out calibration of anchor weights and SE inflators.

Drives the data-driven elements of the production projection:

1. **Per-(indicator, source) RMSE** — drives inverse-variance anchor
   weights inside `anchors.combined_anchor_rate`.
2. **Per-(indicator, method) RMSE** — drives the macro/trend blend
   weight inside `ensemble._calibrated_macro_weight`.
3. **Per-indicator EMPIRICAL_SE_INFLATOR_OVERRIDE** — derived from
   coverage of the projection's 90% CI on hold-out folds. If coverage
   is below 85% or above 95%, scale the inflator to bring it into
   band. Documented in METHODOLOGY.md.

The calibration is *fully out-of-sample*: for each anchor year T we
re-derive every source rate using only data with publication_year ≤ T,
project forward h years to T+h, and score against the actual ACS 1-year
print at T+h. We then aggregate RMSE across folds.

The output JSON has this shape:

```
{
  "schema_version": 2,
  "run_date": "...",
  "anchor_years": [...],
  "horizon": 2,
  "rmse_by_indicator_source": {
    "B19013_001E": {
      "cpi_honolulu_allitems": 0.045,
      "qcew_hawaii_wages":      0.029,
      ...
    }, ...
  },
  "rmse_by_indicator_method": {
    "B19013_001E": {
      "trend_ensemble": 0.061,
      "multi_anchor":   0.041,
      "ensemble_multi_anchor": 0.038,
    }, ...
  },
  "ci90_coverage_by_indicator_method": { ... },
  "se_inflator_override_by_indicator_method": { ... }
}
```

The `project_acs_2026.py` entry point loads this file (if present) and
threads it through `project_ensemble_multi`.
"""
from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Optional, Sequence

from ..models import AcsObservation, ForecastPoint
from .projection import (
    EMPIRICAL_SE_INFLATOR,
    effective_year,
    project_ar1_log_diff,
    project_damped_trend,
)
from .ensemble import combine_forecasts
from .anchors import (
    AnchorRate,
    anchor_as_forecast,
    combined_anchor_rate,
)
from .sources import available_sources


# Coverage band: if 90% CI hits anything outside this, we adjust the
# per-method inflator. 85% and 95% are textbook tolerances around 90%.
COVERAGE_LOWER_BOUND = 0.85
COVERAGE_UPPER_BOUND = 0.95


@dataclass
class HoldOutFold:
    """One hold-out evaluation."""
    indicator: str
    geoid: str
    anchor_year: int
    target_year: int
    horizon: int
    method: str
    actual: float
    projected: float
    ci90_low: float
    ci90_high: float


def _truncate(
    series: Sequence[AcsObservation], anchor_year: int
) -> list[AcsObservation]:
    return [o for o in series if effective_year(o) <= anchor_year]


def _project_trend_only(
    train: Sequence[AcsObservation], target_year: int
) -> Optional[ForecastPoint]:
    """Run the trend-only ensemble (damped + ar1, no anchor)."""
    components: list[ForecastPoint] = []
    f_damped = project_damped_trend(train, target_year)
    if f_damped is not None:
        components.append(f_damped)
    f_ar1 = project_ar1_log_diff(train, target_year)
    if f_ar1 is not None:
        components.append(f_ar1)
    if not components:
        return None
    return combine_forecasts(components, target_year, method_label="trend_ensemble")


def _project_anchor_only(
    train: Sequence[AcsObservation],
    target_year: int,
    anchor_year: int,
    indicator: str,
    per_source_rmse: Optional[dict[str, dict[str, float]]] = None,
) -> Optional[ForecastPoint]:
    """Project from the latest training observation using only the multi-source anchor.

    Uses `train[-1].geoid` so county-level anchors read the right per-county
    series during back-test folds.
    """
    if not train:
        return None
    rate = combined_anchor_rate(
        indicator=indicator,
        end_year=anchor_year,
        calibration=per_source_rmse,
        geoid=train[-1].geoid,
    )
    if rate is None:
        return None
    return anchor_as_forecast(
        latest=train[-1],
        target_year=target_year,
        anchor_rate=rate,
    )


def _per_source_anchor_forecast(
    train: Sequence[AcsObservation],
    target_year: int,
    anchor_year: int,
    indicator: str,
    source_name: str,
) -> Optional[ForecastPoint]:
    """Project at a *single* source's smoothed rate (for per-source RMSE calibration).

    For county-level sources, looks up the source's per-county series via
    `train[-1].geoid`; non-county sources ignore the geoid.
    """
    if not train:
        return None
    sources = [s for s in available_sources(indicator) if s.name == source_name]
    if not sources:
        return None
    src = sources[0]
    rate = src.smoothed_annual_rate(end_year=anchor_year, geoid=train[-1].geoid)
    if rate is None:
        return None
    # Wrap the single rate in an AnchorRate-equivalent for `anchor_as_forecast`.
    single = AnchorRate(
        point_log_rate=rate.log_rate,
        se_log_rate=rate.se_log_rate,
        indicator=indicator,
        end_year=anchor_year,
        components=[(src.name, rate.log_rate, rate.se_log_rate, 1.0)],
    )
    return anchor_as_forecast(
        latest=train[-1],
        target_year=target_year,
        anchor_rate=single,
    )


def run_holdout_calibration(
    series_by_key: dict[tuple[str, str], Sequence[AcsObservation]],
    anchor_years: Sequence[int],
    horizon: int = 2,
) -> dict:
    """Run hold-out calibration across all (geoid, indicator) × anchor years.

    Two passes:
    1. Per-source RMSE pass — each source projects alone and we score
       its forecasts against ACS truth. Results feed inverse-variance
       weights for the anchor combiner.
    2. Per-method RMSE pass — using the per-source RMSE from pass 1,
       run the anchor combiner, the trend ensemble, and the joint
       ensemble; score each.

    Both passes use the same anchor years and horizon.
    """
    folds_pass1: list[HoldOutFold] = []
    folds_pass2: list[HoldOutFold] = []

    # Group indicators we'll iterate over.
    indicators_seen: set[str] = set()
    for (_g, ind) in series_by_key:
        indicators_seen.add(ind)

    # ---- Pass 1: per-source RMSE ----
    for (geoid, indicator), full in series_by_key.items():
        full_sorted = sorted(full, key=lambda o: (effective_year(o), o.vintage))
        for anchor in anchor_years:
            target_year = anchor + horizon
            actual_obs = next(
                (o for o in full_sorted if effective_year(o) == target_year and o.vintage == "1y"),
                None,
            )
            if actual_obs is None or actual_obs.estimate <= 0:
                continue
            train = _truncate(full_sorted, anchor)
            if not train:
                continue
            for src in available_sources(indicator):
                fp = _per_source_anchor_forecast(
                    train, target_year, anchor, indicator, src.name
                )
                if fp is None:
                    continue
                folds_pass1.append(HoldOutFold(
                    indicator=indicator, geoid=geoid,
                    anchor_year=anchor, target_year=target_year, horizon=horizon,
                    method=f"source:{src.name}",
                    actual=actual_obs.estimate, projected=fp.point,
                    ci90_low=fp.ci90_low, ci90_high=fp.ci90_high,
                ))

    # Aggregate pass 1 to RMSE per (indicator, source).
    rmse_by_indicator_source: dict[str, dict[str, float]] = {}
    for f in folds_pass1:
        if f.actual <= 0:
            continue
        ind = f.indicator
        src = f.method.split(":", 1)[1]
        rmse_by_indicator_source.setdefault(ind, {}).setdefault(src, [])  # type: ignore[arg-type]
        rmse_by_indicator_source[ind][src].append(  # type: ignore[union-attr]
            ((f.projected - f.actual) / f.actual) ** 2
        )
    # Reduce to RMSE.
    for ind in list(rmse_by_indicator_source.keys()):
        for src, sq_errs in list(rmse_by_indicator_source[ind].items()):  # type: ignore[union-attr]
            if not sq_errs:
                del rmse_by_indicator_source[ind][src]
                continue
            rmse_by_indicator_source[ind][src] = math.sqrt(
                sum(sq_errs) / len(sq_errs)
            )

    # ---- Pass 2: per-method RMSE using calibration from pass 1 ----
    rmse_by_indicator_method: dict[str, dict[str, list[float]]] = {}
    coverage_by_indicator_method: dict[str, dict[str, list[int]]] = {}

    for (geoid, indicator), full in series_by_key.items():
        full_sorted = sorted(full, key=lambda o: (effective_year(o), o.vintage))
        for anchor in anchor_years:
            target_year = anchor + horizon
            actual_obs = next(
                (o for o in full_sorted if effective_year(o) == target_year and o.vintage == "1y"),
                None,
            )
            if actual_obs is None or actual_obs.estimate <= 0:
                continue
            train = _truncate(full_sorted, anchor)
            if not train:
                continue

            method_runs: dict[str, ForecastPoint] = {}
            tr = _project_trend_only(train, target_year)
            if tr is not None:
                method_runs["trend_ensemble"] = tr
            an = _project_anchor_only(
                train, target_year, anchor, indicator,
                per_source_rmse=rmse_by_indicator_source,
            )
            if an is not None:
                method_runs["multi_anchor"] = an

            for name, fp in method_runs.items():
                bucket_r = rmse_by_indicator_method.setdefault(indicator, {}).setdefault(name, [])
                bucket_r.append(((fp.point - actual_obs.estimate) / actual_obs.estimate) ** 2)
                bucket_c = coverage_by_indicator_method.setdefault(indicator, {}).setdefault(name, [])
                bucket_c.append(1 if fp.ci90_low <= actual_obs.estimate <= fp.ci90_high else 0)

                folds_pass2.append(HoldOutFold(
                    indicator=indicator, geoid=geoid,
                    anchor_year=anchor, target_year=target_year, horizon=horizon,
                    method=name,
                    actual=actual_obs.estimate, projected=fp.point,
                    ci90_low=fp.ci90_low, ci90_high=fp.ci90_high,
                ))

    rmse_per_method: dict[str, dict[str, float]] = {}
    coverage_per_method: dict[str, dict[str, float]] = {}
    for ind, by_m in rmse_by_indicator_method.items():
        rmse_per_method[ind] = {
            m: math.sqrt(sum(v) / len(v)) if v else math.nan
            for m, v in by_m.items()
        }
    for ind, by_m in coverage_by_indicator_method.items():
        coverage_per_method[ind] = {
            m: sum(v) / len(v) if v else math.nan
            for m, v in by_m.items()
        }

    # SE inflator override per (indicator, method): bring coverage into [85%, 95%]
    # by scaling the implied SE such that the corresponding Gaussian z-quantile
    # would have hit ~90% on this fold population.
    #
    # Closed form for one pass:
    #     observed_z = z(coverage) where coverage = P(|Z| ≤ observed_z)
    #     factor = z(0.90) / observed_z = 1.645 / observed_z
    # For coverage already in band, factor ≈ 1.0 and we leave the global
    # EMPIRICAL_SE_INFLATOR alone.
    #
    # Why this is iterative + conservative
    # ------------------------------------
    # Coverage is a *discrete* fraction (k/n folds). For n=24, the
    # smallest non-zero shift is 1/24 ≈ 4.2%. A single closed-form
    # rescaling may overshoot — e.g. a cell at 95.8% (23/24) gets a
    # narrowing factor ~0.81, which can push it to 83.3% (20/24)
    # instead of landing at 21-22/24. We therefore search across
    # candidate overrides via repeated bisection between an "over-cover"
    # bound (factor that gave coverage ≥ 95%) and an "under-cover"
    # bound (factor that gave coverage < 85%), preferring the
    # over-cover bound on tie — better to be slightly conservative
    # than to under-state uncertainty. If no candidate ever lands
    # inside [85%, 95%], we keep the smallest factor that achieved
    # ≥ 85% coverage (or the original 1.30 if that already qualified).
    se_override: dict[str, dict[str, float]] = {}
    max_iter = 6
    history: dict[tuple[str, str], list[tuple[float, float]]] = {}  # (override, cov)
    coverage_current = {
        ind: {m: c for m, c in by_m.items()}
        for ind, by_m in coverage_per_method.items()
    }
    # Seed history with the un-overridden case.
    for ind, by_m in coverage_current.items():
        for m, cov in by_m.items():
            if not math.isfinite(cov):
                continue
            history.setdefault((ind, m), []).append((EMPIRICAL_SE_INFLATOR, cov))

    for _ in range(max_iter):
        any_changed = False
        next_overrides: dict[tuple[str, str], float] = {}
        for ind, by_m in coverage_current.items():
            for m, cov in by_m.items():
                if not math.isfinite(cov):
                    continue
                if COVERAGE_LOWER_BOUND <= cov <= COVERAGE_UPPER_BOUND:
                    continue
                hist = history[(ind, m)]
                # Two-sided bound: smallest override that gave cov ≥ lower,
                # largest override that gave cov ≤ upper.
                over = [(ov, c) for ov, c in hist if c > COVERAGE_UPPER_BOUND]
                under = [(ov, c) for ov, c in hist if c < COVERAGE_LOWER_BOUND]
                if over and under:
                    # Bisect between the over (largest under-cover override)
                    # and under (smallest over-cover override).
                    smallest_over = min(over, key=lambda x: x[0])[0]
                    largest_under = max(under, key=lambda x: x[0])[0]
                    new_override = round((smallest_over + largest_under) / 2.0, 4)
                else:
                    cov_clipped = max(0.50, min(0.999, cov))
                    observed_z = _normal_inv_cdf(0.5 + cov_clipped / 2.0)
                    target_z = 1.645
                    factor = target_z / max(observed_z, 1e-3)
                    prior = se_override.get(ind, {}).get(m, EMPIRICAL_SE_INFLATOR)
                    new_override = round(prior * factor, 4)
                if abs(new_override - se_override.get(ind, {}).get(m, EMPIRICAL_SE_INFLATOR)) < 1e-3:
                    continue
                next_overrides[(ind, m)] = new_override
                any_changed = True
        if not any_changed:
            break
        for (ind, m), v in next_overrides.items():
            se_override.setdefault(ind, {})[m] = v
        cal_for_verify = {
            "rmse_by_indicator_source": rmse_by_indicator_source,
            "se_inflator_override_by_indicator_method": se_override,
        }
        coverage_current = _verify_post_override_coverage(
            series_by_key, anchor_years, horizon, cal_for_verify,
        )
        for ind, by_m in coverage_current.items():
            for m, cov in by_m.items():
                if not math.isfinite(cov):
                    continue
                key = (ind, m)
                ov = se_override.get(ind, {}).get(m, EMPIRICAL_SE_INFLATOR)
                history.setdefault(key, []).append((ov, cov))

    # Pick the best override per cell: prefer in-band; if multiple in-band,
    # pick the override with coverage closest to 0.90; if none in-band,
    # pick the override with maximum coverage (conservative — over-covers).
    final_override: dict[str, dict[str, float]] = {}
    for (ind, m), hist in history.items():
        in_band = [(ov, c) for ov, c in hist if COVERAGE_LOWER_BOUND <= c <= COVERAGE_UPPER_BOUND]
        if in_band:
            best = min(in_band, key=lambda x: abs(x[1] - 0.90))
        else:
            best = max(hist, key=lambda x: x[1])
        if abs(best[0] - EMPIRICAL_SE_INFLATOR) > 1e-4:
            final_override.setdefault(ind, {})[m] = best[0]
    se_override = final_override

    cal_for_verify = {
        "rmse_by_indicator_source": rmse_by_indicator_source,
        "se_inflator_override_by_indicator_method": se_override,
    }
    coverage_post = _verify_post_override_coverage(
        series_by_key, anchor_years, horizon, cal_for_verify,
    )

    return {
        "schema_version": 2,
        "run_date": date.today().isoformat(),
        "anchor_years": list(anchor_years),
        "horizon": horizon,
        "rmse_by_indicator_source": rmse_by_indicator_source,
        "rmse_by_indicator_method": rmse_per_method,
        "ci90_coverage_by_indicator_method": coverage_per_method,
        "ci90_coverage_post_override": coverage_post,
        "se_inflator_override_by_indicator_method": se_override,
        "folds_pass1": [_fold_to_dict(f) for f in folds_pass1],
        "folds_pass2": [_fold_to_dict(f) for f in folds_pass2],
    }


def _verify_post_override_coverage(
    series_by_key: dict[tuple[str, str], Sequence[AcsObservation]],
    anchor_years: Sequence[int],
    horizon: int,
    calibration: dict,
) -> dict[str, dict[str, float]]:
    """Re-run pass 2 with the calibrated SE overrides to confirm CI bands."""
    # Local import to avoid a circular dependency.
    from .ensemble import _apply_se_override

    coverage: dict[str, dict[str, list[int]]] = {}
    for (geoid, indicator), full in series_by_key.items():
        full_sorted = sorted(full, key=lambda o: (effective_year(o), o.vintage))
        for anchor in anchor_years:
            target_year = anchor + horizon
            actual_obs = next(
                (o for o in full_sorted if effective_year(o) == target_year and o.vintage == "1y"),
                None,
            )
            if actual_obs is None or actual_obs.estimate <= 0:
                continue
            train = _truncate(full_sorted, anchor)
            if not train:
                continue

            tr = _project_trend_only(train, target_year)
            if tr is not None:
                tr = _apply_se_override(tr, indicator, "trend_ensemble", calibration)
                coverage.setdefault(indicator, {}).setdefault("trend_ensemble", []).append(
                    1 if tr.ci90_low <= actual_obs.estimate <= tr.ci90_high else 0
                )
            an = _project_anchor_only(
                train, target_year, anchor, indicator,
                per_source_rmse=calibration.get("rmse_by_indicator_source"),
            )
            if an is not None:
                an = _apply_se_override(an, indicator, "multi_anchor", calibration)
                coverage.setdefault(indicator, {}).setdefault("multi_anchor", []).append(
                    1 if an.ci90_low <= actual_obs.estimate <= an.ci90_high else 0
                )

    out: dict[str, dict[str, float]] = {}
    for ind, by_m in coverage.items():
        out[ind] = {m: sum(v) / len(v) if v else math.nan for m, v in by_m.items()}
    return out


def _fold_to_dict(f: HoldOutFold) -> dict:
    return {
        "indicator": f.indicator,
        "geoid": f.geoid,
        "anchor_year": f.anchor_year,
        "target_year": f.target_year,
        "horizon": f.horizon,
        "method": f.method,
        "actual": f.actual,
        "projected": f.projected,
        "ci90_low": f.ci90_low,
        "ci90_high": f.ci90_high,
        "in_ci": int(f.ci90_low <= f.actual <= f.ci90_high),
        "abs_pct_err": abs((f.projected - f.actual) / f.actual) if f.actual > 0 else math.nan,
    }


# -----------------------------------------------------------------------------
# Inverse normal CDF (Beasley-Springer-Moro approximation, sufficient
# precision for coverage→z conversion at this scale).
# -----------------------------------------------------------------------------

def _normal_inv_cdf(p: float) -> float:
    """Approximate inverse standard-normal CDF (Acklam algorithm).

    Used here only to convert observed CI coverage into a "this is what
    z must have been" quantile so we can scale the empirical SE inflator
    to bring 90% coverage into target band. Precision <1e-4 in the
    body of the distribution, which is far more than coverage-band
    targeting requires.
    """
    if not (0.0 < p < 1.0):
        raise ValueError(f"p must be in (0,1), got {p}")
    a = [-3.969683028665376e+01,  2.209460984245205e+02,
         -2.759285104469687e+02,  1.383577518672690e+02,
         -3.066479806614716e+01,  2.506628277459239e+00]
    b = [-5.447609879822406e+01,  1.615858368580409e+02,
         -1.556989798598866e+02,  6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01,
         -2.400758277161838e+00, -2.549732539343734e+00,
          4.374664141464968e+00,  2.938163982698783e+00]
    d = [ 7.784695709041462e-03,  3.224671290700398e-01,
          2.445134137142996e+00,  3.754408661907416e+00]
    plow = 0.02425
    phigh = 1 - plow
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p <= phigh:
        q = p - 0.5
        r = q * q
        return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
               (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
           ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)


def write_calibration(
    payload: dict, path: Path
) -> None:
    """Persist calibration JSON. Drops `folds_*` and `fold_residuals` arrays
    from the on-disk summary file (those go into the back-test report);
    keeps the small RMSE / coverage / override / strata tables that the
    projection loads at runtime.
    """
    DROPPED_KEYS = {"folds_pass1", "folds_pass2", "fold_residuals"}
    summary = {k: v for k, v in payload.items() if k not in DROPPED_KEYS}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)


# =============================================================================
# v3 stratified calibration
# =============================================================================
#
# The v3 layer extends v2 along three axes:
#
# 1. Multi-horizon: holdouts run at h ∈ {1, 2, 3, 4, 5} instead of fixed h=2.
# 2. Population stratification: each county is classified into a 4-level
#    population bucket from its 2020 ACS B01003_001E and the calibration
#    is computed per-cell.
# 3. Geometric bias correction: per-cell `b = mean(log(point/actual))`,
#    clamped to ±10%, gated at n ≥ n_threshold, applied as
#    `point_corrected = point_raw / exp(b)`.
#
# The v3 generator caches per-fold residuals so the SE-override bisection
# can run on cached residuals instead of re-projecting the full panel each
# iteration. This is ~100× faster on the multi-state, multi-horizon panel.

# Default ±10% multiplicative bias clamp, expressed in log space so the
# math composes cleanly with log-space projection. log(1.10) ≈ 0.0953.
DEFAULT_BIAS_CLAMP_LOG: float = math.log(1.10)


@dataclass(frozen=True)
class FoldResidual:
    """One cached projection-vs-truth pairing for a single (geoid, indicator,
    method, anchor, horizon) fold.

    Cached so that the bias-correction and SE-override passes can operate
    in-memory: applying a multiplicative factor to `se_total` (or shifting
    the level by a bias multiplier) and recomputing coverage on the cached
    list is O(folds), versus the v2 approach of re-projecting the entire
    panel inside the override iteration which was O(folds × verify_passes).
    """
    indicator: str
    method: str
    geoid: str
    anchor_year: int
    horizon: int
    pop_bucket: str  # WILDCARD if county population unknown
    h_bucket: str
    actual: float
    point: float
    se_total: float
    se_sample: float
    se_forecast: float
    ci90_low: float
    ci90_high: float


def _apply_bias_to_residual(r: FoldResidual, b: float) -> FoldResidual:
    """Geometric bias correction.

    Multiplies the point and CI bounds by `exp(-b)`; SE components scale
    by the same factor (since SE in log space is invariant under level
    shifts, but in dollar space `σ_y = σ_logy · y`, so dollar-space SE
    rescales proportionally with the level shift).
    """
    if b == 0.0:
        return r
    factor = math.exp(-b)
    return FoldResidual(
        indicator=r.indicator,
        method=r.method,
        geoid=r.geoid,
        anchor_year=r.anchor_year,
        horizon=r.horizon,
        pop_bucket=r.pop_bucket,
        h_bucket=r.h_bucket,
        actual=r.actual,
        point=r.point * factor,
        se_total=r.se_total * factor,
        se_sample=r.se_sample * factor,
        se_forecast=r.se_forecast * factor,
        ci90_low=r.ci90_low * factor,
        ci90_high=r.ci90_high * factor,
    )


def _coverage_at_factor(residuals: Sequence[FoldResidual], factor: float) -> float:
    """Empirical CI90 coverage if SE were rescaled by `factor`.

    The new CI is `point ± factor · (point − ci90_low)`. Since the input
    CI is symmetric (built via `ci_from_se` with `Z=1.645`), this rescales
    the half-width directly without needing to re-evaluate the Gaussian
    quantile. Returns NaN on empty input — caller decides what to do.
    """
    if not residuals:
        return float("nan")
    n_in = 0
    for r in residuals:
        half = factor * (r.point - r.ci90_low)
        new_low = r.point - half
        new_high = r.point + half
        if new_low <= r.actual <= new_high:
            n_in += 1
    return n_in / len(residuals)


def _bisect_se_factor(
    residuals: Sequence[FoldResidual],
    target_low: float = COVERAGE_LOWER_BOUND,
    target_high: float = COVERAGE_UPPER_BOUND,
    max_iter: int = 30,
    tol: float = 5e-3,
) -> tuple[float, float]:
    """Find a multiplicative SE factor that brings coverage into band.

    Wraps `bisect_for_target_coverage` (in `calibration_common.py`) with
    this module's dollar-space `_coverage_at_factor`. The shared
    bisection algorithm is reused by the BLS calibration generator
    against its log-space coverage function.
    """
    from .calibration_common import bisect_for_target_coverage
    return bisect_for_target_coverage(
        coverage_fn=lambda f: _coverage_at_factor(residuals, f),
        target_low=target_low, target_high=target_high,
        max_iter=max_iter, tol=tol,
    )


def _group_residuals(
    residuals: Sequence[FoldResidual],
) -> dict[tuple[str, str, str, str], list[FoldResidual]]:
    """Group residuals into (indicator, method, pop_bucket, h_bucket) cells."""
    groups: dict[tuple[str, str, str, str], list[FoldResidual]] = {}
    for r in residuals:
        key = (r.indicator, r.method, r.pop_bucket, r.h_bucket)
        groups.setdefault(key, []).append(r)
    return groups


def _marginalise_residuals(
    residuals: Sequence[FoldResidual],
    over: str,
) -> dict[tuple, list[FoldResidual]]:
    """Re-group residuals after marginalising out one or more dimensions.

    `over` is one of: "h" (collapse h_bucket), "pop_h" (collapse both).
    The resulting dict has tuple keys `(indicator, method, pop_or_*, h_or_*)`.
    """
    out: dict[tuple, list[FoldResidual]] = {}
    if over == "h":
        for r in residuals:
            key = (r.indicator, r.method, r.pop_bucket, "*")
            out.setdefault(key, []).append(r)
    elif over == "pop_h":
        for r in residuals:
            key = (r.indicator, r.method, "*", "*")
            out.setdefault(key, []).append(r)
    else:
        raise ValueError(f"unknown marginalisation: {over!r}")
    return out


def _estimate_bias_records(
    residuals: Sequence[FoldResidual],
    n_threshold: int,
    bias_clamp_log: float,
) -> list:
    """Compute geometric bias `b = mean(log(point/actual))` per cell.

    Emits records at three granularities:
    1. Exact (indicator, method, pop, h) cells.
    2. h-marginalised (indicator, method, pop, "*") cells.
    3. Globally marginalised (indicator, method, "*", "*") cells.

    Only cells with n ≥ n_threshold receive a non-zero applied bias; lower-n
    cells are still emitted with `value=0.0` so the round-trip is lossless
    and downstream consumers can see *why* no correction fired.

    The applied bias is clamped to `[-bias_clamp_log, +bias_clamp_log]`;
    `extra["b_raw"]` records the unclamped value and `extra["clamped"]`
    flags whether the clamp fired.
    """
    from .strata import StrataRecord, WILDCARD

    def _cell_record(key: tuple, items: Sequence[FoldResidual]) -> StrataRecord:
        ind, method, pop, hb = key
        log_ratios: list[float] = []
        for r in items:
            if r.actual <= 0 or r.point <= 0:
                continue
            try:
                lr = math.log(r.point / r.actual)
            except ValueError:
                continue
            if math.isfinite(lr):
                log_ratios.append(lr)
        n = len(log_ratios)
        if n == 0:
            b_raw = 0.0
        else:
            b_raw = sum(log_ratios) / n
        # Apply n-threshold gate, then clamp.
        if n < n_threshold:
            b_applied = 0.0
            clamped = 0.0
        else:
            b_applied = max(-bias_clamp_log, min(bias_clamp_log, b_raw))
            clamped = 1.0 if abs(b_applied - b_raw) > 1e-12 else 0.0
        return StrataRecord(
            indicator=ind,
            method=method,
            pop_bucket=pop,
            h_bucket=hb,
            value=b_applied,
            n_folds=n,
            extra={"b_raw": b_raw, "clamped": clamped},
        )

    records = []
    for key, items in _group_residuals(residuals).items():
        records.append(_cell_record(key, items))
    for key, items in _marginalise_residuals(residuals, "h").items():
        records.append(_cell_record(key, items))
    for key, items in _marginalise_residuals(residuals, "pop_h").items():
        records.append(_cell_record(key, items))
    return records


def _build_bias_lookup(
    bias_records: Sequence,
    n_threshold: int,
) -> "Callable[[str, str, str, str], float]":
    """Build a fallback lookup over bias records → applied bias `b`.

    Mirrors the strata fallback chain (exact → h-marginalised → global)
    but the floor here is `b=0.0` (no correction).
    """
    from .strata import index_records

    lookup = index_records(
        records=bias_records,
        n_threshold=n_threshold,
        floor_value=0.0,
    )

    def _b(indicator: str, method: str, pop_bucket: str, h_bucket: str) -> float:
        rec, _src = lookup(indicator, method, pop_bucket, h_bucket)
        return rec.value

    return _b


def _bisect_per_cell_records(
    residuals: Sequence[FoldResidual],
    n_threshold: int,
    base_inflator: float,
) -> tuple[list, list, list]:
    """Run per-cell SE bisection, returning (se_records, cov_pre, cov_post).

    `base_inflator` is the global EMPIRICAL_SE_INFLATOR (=1.30). The
    bisection finds a *multiplicative* factor; the absolute κ stored on
    disk is `factor × base_inflator`. Cells with n < n_threshold get
    factor=1.0 (the floor lookup will fall through to a more-aggregated
    cell at projection time).

    Coverage records are emitted at the same granularities as bias
    records — exact, h-marginalised, and globally marginalised — so the
    fallback chain is consistent across all calibrated quantities.
    """
    from .strata import StrataRecord

    def _cells(group_fn) -> dict[tuple, list[FoldResidual]]:
        return group_fn(residuals)

    def _records_for_groups(
        groups: dict[tuple, list[FoldResidual]],
    ) -> tuple[list, list, list]:
        se_recs: list = []
        cov_pre_recs: list = []
        cov_post_recs: list = []
        for key, items in groups.items():
            ind, method, pop, hb = key
            n = len(items)
            cov_pre = _coverage_at_factor(items, 1.0)
            if n < n_threshold or not math.isfinite(cov_pre):
                # Skip bisection; emit factor=1.0 = base_inflator
                factor, cov_post = 1.0, cov_pre
            else:
                factor, cov_post = _bisect_se_factor(items)
            absolute_kappa = factor * base_inflator
            se_recs.append(StrataRecord(
                indicator=ind, method=method, pop_bucket=pop, h_bucket=hb,
                value=absolute_kappa, n_folds=n,
                extra={
                    "factor": factor,
                    "coverage_pre": cov_pre,
                    "coverage_post": cov_post,
                },
            ))
            cov_pre_recs.append(StrataRecord(
                indicator=ind, method=method, pop_bucket=pop, h_bucket=hb,
                value=cov_pre, n_folds=n,
            ))
            cov_post_recs.append(StrataRecord(
                indicator=ind, method=method, pop_bucket=pop, h_bucket=hb,
                value=cov_post, n_folds=n,
            ))
        return se_recs, cov_pre_recs, cov_post_recs

    # Exact cells
    se_x, cov_pre_x, cov_post_x = _records_for_groups(_group_residuals(residuals))
    # h-marginalised
    se_hm, cov_pre_hm, cov_post_hm = _records_for_groups(_marginalise_residuals(residuals, "h"))
    # Globally marginalised
    se_g, cov_pre_g, cov_post_g = _records_for_groups(_marginalise_residuals(residuals, "pop_h"))
    return (
        se_x + se_hm + se_g,
        cov_pre_x + cov_pre_hm + cov_pre_g,
        cov_post_x + cov_post_hm + cov_post_g,
    )


def _rmse_records_from_residuals(
    residuals: Sequence[FoldResidual],
    n_threshold: int,
) -> list:
    """Per-cell RMSE-pct records at all three granularities.

    RMSE is computed on the *bias-corrected* residuals if the caller
    passed those in; otherwise on raw residuals. This routine doesn't
    distinguish — it just operates on whatever residuals it gets.
    """
    from .strata import StrataRecord

    def _rmse(items: Sequence[FoldResidual]) -> float:
        sq = []
        for r in items:
            if r.actual <= 0:
                continue
            sq.append(((r.point - r.actual) / r.actual) ** 2)
        if not sq:
            return float("nan")
        return math.sqrt(sum(sq) / len(sq))

    def _records_for(groups: dict[tuple, list[FoldResidual]]) -> list:
        out: list = []
        for key, items in groups.items():
            ind, method, pop, hb = key
            out.append(StrataRecord(
                indicator=ind, method=method, pop_bucket=pop, h_bucket=hb,
                value=_rmse(items), n_folds=len(items),
            ))
        return out

    return (
        _records_for(_group_residuals(residuals))
        + _records_for(_marginalise_residuals(residuals, "h"))
        + _records_for(_marginalise_residuals(residuals, "pop_h"))
    )


def _marginalised_v2_table(
    records: Sequence,
    *,
    use_h_marg: bool = True,
) -> dict[str, dict[str, float]]:
    """Build a v2-shaped {indicator: {method: float}} table from strata records.

    Picks the globally marginalised ("*", "*") cell when present, falling
    back to the h-marginalised then exact "small" cell as needed. This is
    the table consumed by v2-only consumers that don't know about strata.

    The marginalised cell is computed once by the calibration generator
    (over all populations and horizons in the panel) so this function
    only needs to look it up — no aggregation required.
    """
    from .strata import WILDCARD
    out: dict[str, dict[str, float]] = {}
    for r in records:
        if r.pop_bucket == WILDCARD and r.h_bucket == WILDCARD:
            out.setdefault(r.indicator, {})[r.method] = r.value
    return out


def _marginalised_v2_se_overrides(
    se_records: Sequence,
    base_inflator: float,
    *,
    epsilon: float = 1e-3,
) -> dict[str, dict[str, float]]:
    """Build the v2 sparse override table from v3 SE records.

    Only emits entries where the globally marginalised κ differs from
    `base_inflator` by more than `epsilon` — preserves the v2 semantic
    that overrides are sparse and only listed when meaningful.
    """
    from .strata import WILDCARD
    out: dict[str, dict[str, float]] = {}
    for r in se_records:
        if r.pop_bucket != WILDCARD or r.h_bucket != WILDCARD:
            continue
        if abs(r.value - base_inflator) > epsilon:
            out.setdefault(r.indicator, {})[r.method] = r.value
    return out


# -----------------------------------------------------------------------------
# Public v3 calibration entry point
# -----------------------------------------------------------------------------

def run_stratified_calibration(
    series_by_key: dict[tuple[str, str], Sequence[AcsObservation]],
    anchor_years: Sequence[int],
    horizons: Sequence[int] = (1, 2, 3, 4, 5),
    populations: Optional[dict[str, int]] = None,
    n_threshold: int = 20,
    bias_clamp_log: float = DEFAULT_BIAS_CLAMP_LOG,
    include_ml: bool = False,
) -> dict:
    """v3 stratified hold-out calibration.

    Multi-horizon, population-stratified, geometric-bias-corrected. Caches
    per-fold residuals so SE-override bisection and bias estimation operate
    in-memory; runs roughly 100× faster than the v2 verify-pass approach
    on the multi-state, 5-horizon panel.

    Parameters
    ----------
    series_by_key : {(geoid, indicator) → [AcsObservation, …]}
        Full historical series; the function truncates internally per
        anchor.
    anchor_years : sequence of integer anchor years.
    horizons : sequence of forecast horizons in years (default 1..5).
    populations : optional {geoid → 2020 population}. Used to classify
        each county into a population bucket. If None, every county
        falls into the wildcard pop bucket (effectively a 1-pop-bucket
        configuration that still benefits from horizon stratification).
    n_threshold : minimum folds required for a cell to receive a
        non-default calibration. Below threshold, the cell's records
        are emitted with floor values (κ = base_inflator, b = 0).
    bias_clamp_log : magnitude of the symmetric clamp on the bias term
        in log space. Default `log(1.10)` ≈ ±10% multiplicative.

    Returns
    -------
    dict — schema_version=3 payload with both strata records and
    marginalised v2-style tables for backwards compatibility.
    """
    from .strata import classify_pop, classify_horizon, WILDCARD, record_to_dict

    populations = populations or {}
    anchor_list = list(anchor_years)
    horizon_list = list(horizons)

    # ---- Pass 1: per-source RMSE (h-marginalised; reused from v2 path) ----
    folds_pass1: list[HoldOutFold] = []
    for (geoid, indicator), full in series_by_key.items():
        full_sorted = sorted(full, key=lambda o: (effective_year(o), o.vintage))
        for anchor in anchor_list:
            for h in horizon_list:
                target_year = anchor + h
                actual_obs = next(
                    (o for o in full_sorted
                     if effective_year(o) == target_year and o.vintage == "1y"),
                    None,
                )
                if actual_obs is None or actual_obs.estimate <= 0:
                    continue
                train = _truncate(full_sorted, anchor)
                if not train:
                    continue
                for src in available_sources(indicator):
                    fp = _per_source_anchor_forecast(
                        train, target_year, anchor, indicator, src.name
                    )
                    if fp is None:
                        continue
                    folds_pass1.append(HoldOutFold(
                        indicator=indicator, geoid=geoid,
                        anchor_year=anchor, target_year=target_year, horizon=h,
                        method=f"source:{src.name}",
                        actual=actual_obs.estimate, projected=fp.point,
                        ci90_low=fp.ci90_low, ci90_high=fp.ci90_high,
                    ))
    rmse_by_indicator_source: dict[str, dict] = {}
    for f in folds_pass1:
        if f.actual <= 0:
            continue
        ind = f.indicator
        src = f.method.split(":", 1)[1]
        rmse_by_indicator_source.setdefault(ind, {}).setdefault(src, [])  # type: ignore[arg-type]
        rmse_by_indicator_source[ind][src].append(  # type: ignore[union-attr]
            ((f.projected - f.actual) / f.actual) ** 2
        )
    for ind in list(rmse_by_indicator_source.keys()):
        for src, sq_errs in list(rmse_by_indicator_source[ind].items()):  # type: ignore[union-attr]
            if not sq_errs:
                del rmse_by_indicator_source[ind][src]
                continue
            rmse_by_indicator_source[ind][src] = math.sqrt(sum(sq_errs) / len(sq_errs))

    # ---- Pass 2: produce FoldResidual cache for both methods ----
    fold_residuals: list[FoldResidual] = []
    for (geoid, indicator), full in series_by_key.items():
        full_sorted = sorted(full, key=lambda o: (effective_year(o), o.vintage))
        pop_bucket = classify_pop(populations.get(geoid)) or WILDCARD
        for anchor in anchor_list:
            for h in horizon_list:
                target_year = anchor + h
                actual_obs = next(
                    (o for o in full_sorted
                     if effective_year(o) == target_year and o.vintage == "1y"),
                    None,
                )
                if actual_obs is None or actual_obs.estimate <= 0:
                    continue
                train = _truncate(full_sorted, anchor)
                if not train:
                    continue
                h_bucket = classify_horizon(h) or WILDCARD

                tr = _project_trend_only(train, target_year)
                if tr is not None:
                    fold_residuals.append(FoldResidual(
                        indicator=indicator, method="trend_ensemble",
                        geoid=geoid, anchor_year=anchor, horizon=h,
                        pop_bucket=pop_bucket, h_bucket=h_bucket,
                        actual=actual_obs.estimate,
                        point=tr.point, se_total=tr.se_total,
                        se_sample=tr.se_sample, se_forecast=tr.se_forecast,
                        ci90_low=tr.ci90_low, ci90_high=tr.ci90_high,
                    ))
                an = _project_anchor_only(
                    train, target_year, anchor, indicator,
                    per_source_rmse=rmse_by_indicator_source,
                )
                if an is not None:
                    fold_residuals.append(FoldResidual(
                        indicator=indicator, method="multi_anchor",
                        geoid=geoid, anchor_year=anchor, horizon=h,
                        pop_bucket=pop_bucket, h_bucket=h_bucket,
                        actual=actual_obs.estimate,
                        point=an.point, se_total=an.se_total,
                        se_sample=an.se_sample, se_forecast=an.se_forecast,
                        ci90_low=an.ci90_low, ci90_high=an.ci90_high,
                    ))

    # ---- Pass 2b (optional): ml_trend FoldResidual cache ----
    # Trains one HGB model per (indicator, cutoff=anchor) — ~16 indicators
    # × ~9 anchor years = 144 fits @ ~2s each ≈ 5min. Reuses each model
    # across all (geoid, h) folds at the same cutoff so prediction is
    # cheap (~150 predict() calls per cutoff). Restructured loop ordering
    # is intentional — per-anchor model fitting must happen ONCE per
    # anchor, not once per (geoid, h) combination.
    if include_ml:
        from .ml_features import build_panel_index as _build_panel_index
        from .ml_trend import (
            train_ml_model as _train_ml_model,
            project_ml_trend as _project_ml_trend,
            METHOD_NAME as _ML_METHOD,
        )

        ml_panel = _build_panel_index(series_by_key)
        # Group (geoid, indicator) by indicator so we can iterate
        # indicator-major, anchor-major, then geoid for each.
        by_indicator: dict[str, list[tuple[str, list[AcsObservation]]]] = {}
        for (geoid, indicator), full in series_by_key.items():
            full_sorted = sorted(full, key=lambda o: (effective_year(o), o.vintage))
            by_indicator.setdefault(indicator, []).append((geoid, full_sorted))

        for indicator, county_list in by_indicator.items():
            for anchor in anchor_list:
                model = _train_ml_model(
                    series_by_key=series_by_key,
                    populations=populations,
                    indicator=indicator,
                    cutoff_year=anchor,
                    horizons=horizon_list,
                    panel=ml_panel,
                )
                if model is None:
                    continue
                for geoid, full_sorted in county_list:
                    pop_bucket = classify_pop(populations.get(geoid)) or WILDCARD
                    train = _truncate(full_sorted, anchor)
                    if not train:
                        continue
                    for h in horizon_list:
                        target_year = anchor + h
                        actual_obs = next(
                            (o for o in full_sorted
                             if effective_year(o) == target_year and o.vintage == "1y"),
                            None,
                        )
                        if actual_obs is None or actual_obs.estimate <= 0:
                            continue
                        h_bucket = classify_horizon(h) or WILDCARD
                        ml_fp = _project_ml_trend(
                            series_observations=train,
                            target_year=target_year,
                            model=model,
                            panel=ml_panel,
                            populations=populations,
                        )
                        if ml_fp is None:
                            continue
                        fold_residuals.append(FoldResidual(
                            indicator=indicator, method=_ML_METHOD,
                            geoid=geoid, anchor_year=anchor, horizon=h,
                            pop_bucket=pop_bucket, h_bucket=h_bucket,
                            actual=actual_obs.estimate,
                            point=ml_fp.point, se_total=ml_fp.se_total,
                            se_sample=ml_fp.se_sample, se_forecast=ml_fp.se_forecast,
                            ci90_low=ml_fp.ci90_low, ci90_high=ml_fp.ci90_high,
                        ))

    # ---- Pass A: bias estimation per cell (with marginalisation) ----
    bias_records = _estimate_bias_records(fold_residuals, n_threshold, bias_clamp_log)

    # ---- Pass A.5: apply bias to fold residuals in memory ----
    bias_lookup = _build_bias_lookup(bias_records, n_threshold)
    bias_corrected: list[FoldResidual] = []
    for r in fold_residuals:
        b = bias_lookup(r.indicator, r.method, r.pop_bucket, r.h_bucket)
        bias_corrected.append(_apply_bias_to_residual(r, b))

    # ---- Pass B: per-cell SE override on bias-corrected residuals ----
    se_records, cov_pre_records, cov_post_records = _bisect_per_cell_records(
        bias_corrected, n_threshold, base_inflator=EMPIRICAL_SE_INFLATOR,
    )

    # ---- Pass C: per-cell RMSE on bias-corrected residuals ----
    rmse_records = _rmse_records_from_residuals(bias_corrected, n_threshold)

    # ---- Build marginalised v2-style tables for back-compat ----
    rmse_v2 = _marginalised_v2_table(rmse_records)
    cov_pre_v2 = _marginalised_v2_table(cov_pre_records)
    cov_post_v2 = _marginalised_v2_table(cov_post_records)
    se_override_v2 = _marginalised_v2_se_overrides(se_records, EMPIRICAL_SE_INFLATOR)

    return {
        "schema_version": 3,
        "run_date": date.today().isoformat(),
        "anchor_years": anchor_list,
        "horizons": horizon_list,
        # Pass 1 (h-marginalised): per-source RMSE
        "rmse_by_indicator_source": rmse_by_indicator_source,
        # v3 strata records
        "strata_records": {
            "rmse": [record_to_dict(r) for r in rmse_records],
            "coverage_pre": [record_to_dict(r) for r in cov_pre_records],
            "coverage_post": [record_to_dict(r) for r in cov_post_records],
            "se_inflator": [record_to_dict(r) for r in se_records],
            "bias": [record_to_dict(r) for r in bias_records],
        },
        # Marginalised v2-style tables for back-compat
        "rmse_by_indicator_method": rmse_v2,
        "ci90_coverage_by_indicator_method": cov_pre_v2,
        "ci90_coverage_post_override": cov_post_v2,
        "se_inflator_override_by_indicator_method": se_override_v2,
        # Diagnostic dump (stripped at write time by `write_calibration`)
        "fold_residuals": [
            {
                "indicator": r.indicator, "method": r.method, "geoid": r.geoid,
                "anchor_year": r.anchor_year, "horizon": r.horizon,
                "pop_bucket": r.pop_bucket, "h_bucket": r.h_bucket,
                "actual": r.actual, "point": r.point,
                "se_total": r.se_total, "ci90_low": r.ci90_low, "ci90_high": r.ci90_high,
                "in_ci": int(r.ci90_low <= r.actual <= r.ci90_high),
            }
            for r in fold_residuals
        ],
        "folds_pass1": [_fold_to_dict(f) for f in folds_pass1],
    }
