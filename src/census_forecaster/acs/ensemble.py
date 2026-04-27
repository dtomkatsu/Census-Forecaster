"""Ensemble combiner for ACS projections.

The two base models in `projection.py` (damped log trend + AR(1) on log
diffs) trade off bias and variance differently. Damped trend is more
biased toward "things will continue at a slowing rate" — robust at low
sample sizes. AR(1) on diffs is more responsive but noisier. Combining
them with inverse-variance weights gives a forecast that's at least as
accurate as the better individual model on every walk-forward fold we
tried (see backtests/results/).

Two macro-anchor flavors are supported:

* `project_ensemble(...)` — legacy, takes a single user-supplied
  `macro_annual_rate` and blends at a configurable weight (default
  derived from calibration if available, else 0.30 for backwards
  compatibility with prior tests).
* `project_ensemble_multi(...)` — new in v0.2: builds a multi-source
  anchor via `anchors.combined_anchor_rate(indicator, end_year)`,
  inverse-variance-weighting CPI / PCE / QCEW / HUD FMR / FHFA HPI
  per indicator. Macro/trend blend weight is also derived from
  back-test RMSE — no hardcoded 70/30.

Why a per-indicator calibrated weight beats the hardcoded 0.30
---------------------------------------------------------------
Different indicators have different macro/idiosyncratic ratios. Median
home value is dominated by FHFA HPI (very tight macro signal); median
rent is more idiosyncratic county to county; median income sits in
between. A single 0.30 weight either over-anchors home value (forfeits
macro signal) or under-anchors rent (lets ACS noise drive). The
calibrated weight is `RMSE_trend² / (RMSE_trend² + RMSE_anchor²)`
per (indicator, source-set), which is the *optimal* combination
weight for two independent unbiased estimators (Bates & Granger 1969).

References
----------
Granger & Ramanathan (1984), "Improved methods of combining forecasts."
J. Forecasting. — inverse-variance weights.
Bates & Granger (1969), "The combination of forecasts." OR Quarterly. —
optimal combination weight derivation.
Cleveland Fed WP 22-38r — anchor-blend pattern (used in the existing
`blend_rent_nowcast` in this repo).
"""
from __future__ import annotations

import math
from typing import Sequence

from ..models import AcsObservation, ForecastPoint
from ..moe import moe_to_se, combine_se, ci_from_se
from .projection import (
    project_damped_trend,
    project_ar1_log_diff,
    ANNUAL_RATE_CAP,
    effective_year,
)


def _inverse_variance_weights(forecasts: Sequence[ForecastPoint]) -> list[float]:
    """Inverse-variance combination weights, normalised to sum to 1.

    A model with infinite variance gets weight 0; if all variances are
    zero (degenerate), fall back to equal weights.
    """
    inv = []
    for f in forecasts:
        v = f.se_total ** 2
        if not math.isfinite(v) or v <= 0:
            inv.append(0.0)
        else:
            inv.append(1.0 / v)
    total = sum(inv)
    if total <= 0:
        n = len(forecasts)
        return [1.0 / n for _ in forecasts] if n else []
    return [w / total for w in inv]


def macro_anchor_projection(
    latest: AcsObservation,
    target_year: int,
    annual_growth_rate: float,
    sample_se_floor: float | None = None,
) -> ForecastPoint:
    """Project a single observation forward at an exogenous annual rate.

    Used as the macro-anchor input to ensembles: e.g. project median rent
    forward at the BLS Honolulu rent-CPI-implied annual growth, or
    project median income at the wage-growth implied by Hawaii DLIR
    QCEW data. The caller supplies the rate; this function does the
    compounding, applies the cap, and returns a ForecastPoint with
    sample SE pulled from the input MOE.

    The forecast variance for a "use the macro rate as truth" model is
    explicitly the sample variance of the input (no model residuals to
    add) — this is documented and intentional. If the user wants a
    macro projection with its *own* uncertainty, blend the macro rate's
    SE in by pre-inflating sample_se_floor.
    """
    horizon = target_year - effective_year(latest)
    if horizon <= 0:
        sample_se = moe_to_se(latest.moe)
        ci_lo, ci_hi = ci_from_se(latest.estimate, sample_se)
        return ForecastPoint(
            point=latest.estimate,
            se_total=sample_se if math.isfinite(sample_se) else 0.0,
            se_sample=sample_se if math.isfinite(sample_se) else 0.0,
            se_forecast=0.0,
            ci90_low=ci_lo,
            ci90_high=ci_hi,
            method="macro_anchor",
            target_year=target_year,
            geoid=latest.geoid,
            indicator=latest.indicator,
            horizon=int(round(horizon)),
            notes="target at/before latest observation",
        )

    # Cap and compound.
    rate = max(min(annual_growth_rate, ANNUAL_RATE_CAP), -ANNUAL_RATE_CAP)
    notes = ""
    if rate != annual_growth_rate:
        notes = (
            f"macro rate {annual_growth_rate * 100:+.2f}%/yr "
            f"capped to {rate * 100:+.2f}%/yr"
        )
    point = latest.estimate * ((1.0 + rate) ** horizon)

    # Sample SE scaled to the projection magnitude.
    sample_relative = moe_to_se(latest.moe) / latest.estimate if latest.estimate > 0 else 0.0
    if not math.isfinite(sample_relative):
        sample_relative = 0.0
    se_sample = sample_relative * point
    if sample_se_floor is not None and math.isfinite(sample_se_floor):
        se_sample = max(se_sample, sample_se_floor)

    se_total = se_sample
    ci_lo, ci_hi = ci_from_se(point, se_total)
    return ForecastPoint(
        point=point,
        se_total=se_total,
        se_sample=se_sample,
        se_forecast=0.0,
        ci90_low=ci_lo,
        ci90_high=ci_hi,
        method="macro_anchor",
        target_year=target_year,
        geoid=latest.geoid,
        indicator=latest.indicator,
        horizon=int(round(horizon)),
        notes=notes,
    )


def combine_forecasts(
    forecasts: Sequence[ForecastPoint],
    target_year: int,
    method_label: str = "ensemble",
) -> ForecastPoint | None:
    """Inverse-variance combine a list of forecasts for the same target.

    All forecasts must agree on geoid, indicator, and target_year — a
    hard validation rather than silent averaging-of-apples-and-oranges.
    The combined SE is computed from the weighted sum's variance, which
    *can* be smaller than any individual SE (that's the value of
    combining). The 90% CI is symmetric around the weighted point.
    """
    forecasts = list(forecasts)
    if not forecasts:
        return None
    geoids = {f.geoid for f in forecasts}
    indicators = {f.indicator for f in forecasts}
    years = {f.target_year for f in forecasts}
    if len(geoids) != 1 or len(indicators) != 1 or len(years) != 1:
        raise ValueError(
            "combine_forecasts: forecasts must share geoid, indicator, target_year"
        )
    weights = _inverse_variance_weights(forecasts)
    point = sum(w * f.point for w, f in zip(weights, forecasts))

    # Variance of weighted sum, treating component forecasts as
    # *correlated*. The two component models (damped trend + AR(1) on
    # log-diffs) consume the same input series and share parameter
    # estimation noise, so the independence assumption (ρ=0) yields an
    # artificially tight combined CI. We use ρ=0.7, a conservative
    # value at the high end of what Tebaldi & Knutti (2007) and the
    # IPCC AR6 multi-model literature derive for "different methods,
    # same training data" forecast pairs. Lower ρ would make the
    # ensemble CI look misleadingly precise; ρ=1 collapses the variance
    # to the weighted sum of component SEs and forfeits the diversity
    # benefit. Walk-forward calibration on the Hawaii panel confirmed
    # 0.7 brings ensemble CI90-coverage into the 88-92% band.
    rho = 0.7
    n = len(forecasts)
    var = 0.0
    for i in range(n):
        for j in range(n):
            corr = 1.0 if i == j else rho
            var += weights[i] * weights[j] * forecasts[i].se_total * forecasts[j].se_total * corr
    se_total = math.sqrt(var) if var > 0 else 0.0

    # Decompose into sample + forecast components by the same weighting
    # for audit; the values won't sum exactly to se_total under the
    # correlation assumption but they show the relative contribution.
    se_sample = math.sqrt(sum((w * f.se_sample) ** 2 for w, f in zip(weights, forecasts)))
    se_forecast = math.sqrt(sum((w * f.se_forecast) ** 2 for w, f in zip(weights, forecasts)))

    ci_lo, ci_hi = ci_from_se(point, se_total)
    horizons = {f.horizon for f in forecasts}
    horizon = horizons.pop() if len(horizons) == 1 else max(horizons)

    component_notes = "; ".join(
        f"{f.method}={w:.2f}" for f, w in zip(forecasts, weights)
    )
    cap_notes = [f.notes for f in forecasts if f.notes]
    notes = f"weights[{component_notes}]"
    if cap_notes:
        notes += " | " + " ; ".join(sorted(set(cap_notes)))

    return ForecastPoint(
        point=point,
        se_total=se_total,
        se_sample=se_sample,
        se_forecast=se_forecast,
        ci90_low=ci_lo,
        ci90_high=ci_hi,
        method=method_label,
        target_year=target_year,
        geoid=forecasts[0].geoid,
        indicator=forecasts[0].indicator,
        horizon=horizon,
        notes=notes,
    )


def project_ensemble(
    series_observations: Sequence[AcsObservation],
    target_year: int,
    macro_annual_rate: float | None = None,
    macro_weight: float = 0.30,
) -> ForecastPoint | None:
    """Run the standard ensemble: damped trend + AR(1) (+ optional macro).

    Components
    ----------
    1. damped_log_trend     — always run if there are ≥2 observations.
    2. ar1_log_diff         — run if there are ≥4 observations.
    3. macro_anchor         — run if `macro_annual_rate` is not None.
       Inserted at fixed weight `macro_weight`; the remaining
       (1 − macro_weight) is split across (1)+(2) by inverse variance.

    Returns the ensemble ForecastPoint, or `None` if no component can
    be fit (e.g. a 1-observation series with no macro anchor).
    """
    if not series_observations:
        return None

    components: list[ForecastPoint] = []
    f_damped = project_damped_trend(series_observations, target_year)
    if f_damped is not None:
        components.append(f_damped)
    f_ar1 = project_ar1_log_diff(series_observations, target_year)
    if f_ar1 is not None:
        components.append(f_ar1)

    if not components and macro_annual_rate is None:
        return None

    if macro_annual_rate is not None:
        anchor = macro_anchor_projection(
            series_observations[-1], target_year, macro_annual_rate
        )
        # Two-stage combination: ensemble the trend models first, then
        # blend the anchor at a fixed weight. This matches the
        # `blend_rent_nowcast` 70/30 pattern used elsewhere in this repo.
        if components:
            inner = combine_forecasts(components, target_year, method_label="trend_ensemble")
            if inner is None:
                return anchor
            point = (1 - macro_weight) * inner.point + macro_weight * anchor.point
            # Variance of fixed-weight blend, again with corr=0.5.
            rho = 0.5
            w = [1 - macro_weight, macro_weight]
            ses = [inner.se_total, anchor.se_total]
            var = 0.0
            for i in range(2):
                for j in range(2):
                    corr = 1.0 if i == j else rho
                    var += w[i] * w[j] * ses[i] * ses[j] * corr
            se_total = math.sqrt(var) if var > 0 else 0.0
            se_sample = math.sqrt((w[0] * inner.se_sample) ** 2 + (w[1] * anchor.se_sample) ** 2)
            se_forecast = math.sqrt((w[0] * inner.se_forecast) ** 2 + (w[1] * anchor.se_forecast) ** 2)
            ci_lo, ci_hi = ci_from_se(point, se_total)
            notes = (
                f"macro_blend(macro={macro_weight:.2f}, trend={1 - macro_weight:.2f}); "
                f"inner: {inner.notes}"
            )
            if anchor.notes:
                notes += f"; anchor: {anchor.notes}"
            return ForecastPoint(
                point=point,
                se_total=se_total,
                se_sample=se_sample,
                se_forecast=se_forecast,
                ci90_low=ci_lo,
                ci90_high=ci_hi,
                method="ensemble_macro",
                target_year=target_year,
                geoid=inner.geoid,
                indicator=inner.indicator,
                horizon=inner.horizon,
                notes=notes,
            )
        return anchor

    return combine_forecasts(components, target_year, method_label="ensemble")


# -----------------------------------------------------------------------------
# Multi-source anchor ensemble
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# v3 calibration lookup helpers
# -----------------------------------------------------------------------------
#
# The v2 path looked up a single (indicator, method) → kappa override in a
# nested dict at top level of the calibration payload. The v3 path looks up
# (indicator, method, pop_bucket, h_bucket) → kappa, with a fallback chain
# (exact → h-marginalised → globally marginalised → v2 key → global default).
# Both consumers (_apply_se_override, _apply_bias_correction) need the same
# lookup machinery, so factor it here.

def _v3_strata_lookup(
    calibration: dict | None,
    kind: str,
    floor_value: float,
):
    """Build an indexed strata lookup over `calibration["strata_records"][kind]`.

    Returns None when the calibration is v2 (no strata_records key) or
    when records for `kind` are absent. Caller falls back to v2 path.
    """
    if calibration is None:
        return None
    sr = calibration.get("strata_records")
    if not sr:
        return None
    raw = sr.get(kind)
    if not raw:
        return None
    from .strata import index_records, record_from_dict, DEFAULT_N_THRESHOLD
    records = [record_from_dict(d) for d in raw]
    return index_records(
        records=records,
        n_threshold=DEFAULT_N_THRESHOLD,
        floor_value=floor_value,
    )


def _apply_se_override(
    fp: ForecastPoint,
    indicator: str,
    method_key: str,
    calibration: dict | None,
    pop_bucket: str | None = None,
    h_bucket: str | None = None,
) -> ForecastPoint:
    """Re-scale a ForecastPoint's *total* SE by the calibrated κ.

    Looks up the appropriate κ via the v3 strata fallback chain when the
    calibration carries v3 records; otherwise uses the v2 single-key
    lookup `calibration["se_inflator_override_by_indicator_method"]`.

    The override is the *absolute* κ value (matching the global
    `EMPIRICAL_SE_INFLATOR=1.30` baked into projection.py); the linear
    factor we multiply `se_total` by is `override / EMPIRICAL_SE_INFLATOR`.
    If the target SE would drop below the irreducible sample SE (negative
    forecast variance), we clamp at se_sample — an honest floor since the
    ACS MOE itself caps how tight any 90% CI can legitimately get.

    Backwards compatible: if `pop_bucket` and `h_bucket` are None and the
    calibration is v2, behaves exactly as the pre-v3 implementation.
    """
    if calibration is None or fp is None:
        return fp

    from .projection import EMPIRICAL_SE_INFLATOR as _SE_INF

    override: float | None = None
    source_label = ""

    # v3 strata lookup if available
    se_lookup = _v3_strata_lookup(calibration, "se_inflator", floor_value=_SE_INF)
    if se_lookup is not None:
        rec, src = se_lookup(indicator, method_key, pop_bucket, h_bucket)
        if src != "floor":
            override = rec.value
            source_label = f"strata={src}"

    # v2 fallback (also used when v3 strata lookup fell through to floor)
    if override is None:
        override = (
            calibration.get("se_inflator_override_by_indicator_method", {})
            .get(indicator, {})
            .get(method_key)
        )
        if override is not None:
            source_label = "v2"

    if override is None or not math.isfinite(override) or override <= 0:
        return fp

    factor = override / _SE_INF
    new_se_total = max(fp.se_total * factor, fp.se_sample)
    forecast_var = max(new_se_total ** 2 - fp.se_sample ** 2, 0.0)
    new_se_forecast = math.sqrt(forecast_var)
    ci_lo, ci_hi = ci_from_se(fp.point, new_se_total)
    notes = fp.notes
    suffix = f"se_override={override:.3f}"
    if source_label:
        suffix += f"({source_label})"
    notes = f"{notes}; {suffix}" if notes else suffix
    return ForecastPoint(
        point=fp.point,
        se_total=new_se_total,
        se_sample=fp.se_sample,
        se_forecast=new_se_forecast,
        ci90_low=ci_lo,
        ci90_high=ci_hi,
        method=fp.method,
        target_year=fp.target_year,
        geoid=fp.geoid,
        indicator=fp.indicator,
        horizon=fp.horizon,
        notes=notes,
    )


def _apply_bias_correction(
    fp: ForecastPoint,
    indicator: str,
    method_key: str,
    calibration: dict | None,
    pop_bucket: str | None = None,
    h_bucket: str | None = None,
) -> ForecastPoint:
    """Apply geometric bias correction to a ForecastPoint.

    Looks up the bias `b = mean(log(point/actual))` for this cell from
    the v3 strata records and applies `point_corrected = point / exp(b)`.
    All SE components and CI bounds rescale by the same factor so the CI
    width tracks the corrected level (in log space, a level shift is
    multiplicative on dollar-space SEs).

    No-op when:
    * calibration is v2 (no `strata_records["bias"]` key)
    * cell falls below n_threshold (lookup returns floor with value=0)
    * bias is exactly 0 (numerical no-op)

    The order of application matters: callers should run this **before**
    `_apply_se_override`. The SE override was calibrated on
    bias-corrected residuals, so applying κ to a still-biased point
    would double-count the level miscalibration in the CI.
    """
    if calibration is None or fp is None:
        return fp
    bias_lookup = _v3_strata_lookup(calibration, "bias", floor_value=0.0)
    if bias_lookup is None:
        return fp
    rec, src = bias_lookup(indicator, method_key, pop_bucket, h_bucket)
    b = rec.value
    if b == 0.0 or not math.isfinite(b):
        return fp
    factor = math.exp(-b)
    new_point = fp.point * factor
    new_se_total = fp.se_total * factor
    new_se_sample = fp.se_sample * factor
    new_se_forecast = fp.se_forecast * factor
    new_ci_low = fp.ci90_low * factor
    new_ci_high = fp.ci90_high * factor
    notes = fp.notes
    suffix = f"bias_corr={b * 100:+.2f}%(strata={src})"
    notes = f"{notes}; {suffix}" if notes else suffix
    return ForecastPoint(
        point=new_point,
        se_total=new_se_total,
        se_sample=new_se_sample,
        se_forecast=new_se_forecast,
        ci90_low=new_ci_low,
        ci90_high=new_ci_high,
        method=fp.method,
        target_year=fp.target_year,
        geoid=fp.geoid,
        indicator=fp.indicator,
        horizon=fp.horizon,
        notes=notes,
    )


def _calibrated_macro_weight(
    indicator: str,
    calibration: dict | None,
    fallback: float = 0.30,
    floor: float = 0.05,
    ceiling: float = 0.80,
) -> float:
    """Return the macro/(macro+trend) blend weight for an indicator.

    From Bates-Granger optimal combination of two unbiased estimators:
        w_macro* = RMSE_trend² / (RMSE_trend² + RMSE_macro²)

    `calibration` is the dict written by `scripts/calibrate_anchors.py`;
    if absent or missing this indicator we fall back to `fallback` so
    legacy tests still pass. Bound the result to [floor, ceiling] so a
    single anomalous calibration run can't degenerate the blend (a
    1.0 weight would discard the trend ensemble entirely).
    """
    if calibration is None:
        return fallback
    rmse_table = calibration.get("rmse_by_indicator_method") or {}
    rmse_trend = rmse_table.get(indicator, {}).get("trend_ensemble")
    rmse_anchor = rmse_table.get(indicator, {}).get("multi_anchor")
    if rmse_trend is None or rmse_anchor is None:
        return fallback
    if rmse_trend <= 0 or rmse_anchor <= 0:
        return fallback
    w = (rmse_trend ** 2) / (rmse_trend ** 2 + rmse_anchor ** 2)
    return max(floor, min(ceiling, w))


def _resolve_pop_bucket(
    geoid: str,
    populations: dict[str, int] | None,
) -> str | None:
    """Look up a county's 2020 population bucket.

    Population dict can be passed in explicitly, or this function will
    lazily load the bundled `county_population_2020.json` if available.
    Returns None when the county has no known population (the v3 lookup
    chain treats this as "skip exact, go to global marginalised").
    """
    from .strata import classify_pop
    if populations is None:
        try:
            from ..scripts.load_calibration_panel import load_populations as _lp
            populations = _lp()
        except Exception:  # PanelMissingError or any I/O error
            return None
    pop = populations.get(geoid) if populations else None
    return classify_pop(pop)


def _combine_two_with_rho(
    a: ForecastPoint,
    b: ForecastPoint,
    target_year: int,
    method_label: str,
    rho: float,
) -> ForecastPoint | None:
    """Inverse-variance combine two ForecastPoints at a given correlation.

    Generalises ``combine_forecasts`` for the (trend_ensemble, ml_trend)
    pair, where the appropriate ρ is the inner-correlation (default 0.7
    since both consume the same series). Used internally by
    ``project_ensemble_multi`` when ``use_ml=True``.
    """
    if a.geoid != b.geoid or a.indicator != b.indicator:
        return None
    inv_a = 1.0 / (a.se_total ** 2) if (math.isfinite(a.se_total) and a.se_total > 0) else 0.0
    inv_b = 1.0 / (b.se_total ** 2) if (math.isfinite(b.se_total) and b.se_total > 0) else 0.0
    total = inv_a + inv_b
    if total <= 0:
        # Degenerate: equal weights.
        wa, wb = 0.5, 0.5
    else:
        wa, wb = inv_a / total, inv_b / total
    point = wa * a.point + wb * b.point
    var = (
        (wa * a.se_total) ** 2
        + (wb * b.se_total) ** 2
        + 2.0 * rho * wa * wb * a.se_total * b.se_total
    )
    se_total = math.sqrt(var) if var > 0 else 0.0
    se_sample = math.sqrt((wa * a.se_sample) ** 2 + (wb * b.se_sample) ** 2)
    se_forecast = math.sqrt((wa * a.se_forecast) ** 2 + (wb * b.se_forecast) ** 2)
    ci_lo, ci_hi = ci_from_se(point, se_total)
    notes = (
        f"{method_label}({a.method}={wa:.2f}, {b.method}={wb:.2f}, rho={rho:.2f}); "
        f"{a.method}: {a.notes or ''}; {b.method}: {b.notes or ''}"
    )
    return ForecastPoint(
        point=point,
        se_total=se_total,
        se_sample=se_sample,
        se_forecast=se_forecast,
        ci90_low=ci_lo,
        ci90_high=ci_hi,
        method=method_label,
        target_year=target_year,
        geoid=a.geoid,
        indicator=a.indicator,
        horizon=max(a.horizon, b.horizon),
        notes=notes,
    )


def project_ensemble_multi(
    series_observations: Sequence[AcsObservation],
    target_year: int,
    end_year: int | None = None,
    calibration: dict | None = None,
    correlation_rho_inner: float = 0.7,
    correlation_rho_anchor: float = 0.5,
    populations: dict[str, int] | None = None,
    use_ml: bool = False,
    ml_series_by_key: dict[tuple[str, str], Sequence[AcsObservation]] | None = None,
    ml_populations: dict[str, int] | None = None,
    ml_model_cache: dict | None = None,
    ml_panel=None,
) -> "ForecastPoint | None":
    """Multi-source anchor ensemble.

    Pulls in CPI / PCE / QCEW / HUD FMR / FHFA HPI (whichever apply
    to the indicator) via `anchors.combined_anchor_rate`, projects
    `latest` forward at the multi-source rate, and combines with the
    trend ensemble at the calibrated optimal weight.

    v3 calibration support
    ----------------------
    When the calibration payload is schema_version=3 (carries
    `strata_records`), each component (trend_ensemble, multi_anchor) is
    individually:

    1. **Bias-corrected** via the geometric multiplier
       `point' = point / exp(b)` looked up by
       (indicator, method, pop_bucket, h_bucket) in the v3 bias records.
    2. **SE-rescaled** via the per-cell κ from the v3 SE records.

    Order matters: bias correction is applied first, then SE override.
    The SE override was calibrated on bias-corrected residuals; reversing
    the order would double-count the level miscalibration in the CI.

    Components are corrected *pre-blend* because the bias and κ records
    are keyed by component method (`trend_ensemble`, `multi_anchor`),
    not by the blended `ensemble_multi_anchor` label.

    Parameters
    ----------
    end_year : int, optional
        The "as-of" year for visibility into anchor sources. Defaults
        to the effective_year of the latest ACS observation. Setting
        this lower simulates a back-test in which only data visible
        on or before `end_year` is used.
    calibration : dict, optional
        Pre-computed calibration payload from
        `scripts/calibrate_anchors.py`. Determines per-source anchor
        weights, macro/trend blend weight, SE inflators, and (v3 only)
        bias corrections. If absent, falls back to equal anchor weights
        and the legacy 0.30 macro weight.
    populations : dict[str, int], optional
        County 2020 populations (geoid → pop). Used to classify the
        target county into a population bucket for v3 stratified
        lookups. If None, the bundled
        `data/calibration_panel/county_population_2020.json` is loaded
        lazily if available; otherwise pop_bucket is None and the v3
        lookup chain falls through to globally marginalised cells.
    use_ml : bool, default False
        Include the cross-county ``ml_trend`` member in the ensemble.
        Requires ``ml_series_by_key`` and ``ml_populations`` to be
        non-None; sklearn must be importable. Falls back gracefully
        (ml_fp = None) when those preconditions don't hold.
    ml_series_by_key, ml_populations : the calibration panel + 2020
        population lookup needed by the HGB trainer. Pass the same dicts
        across many forecasts so the model cache (below) is effective.
    ml_model_cache : dict, optional
        Mutable cache keyed by (indicator, cutoff_year) → TrainedMlModel.
        Pass the same dict across many forecasts at the same cutoff to
        amortise training cost (~2s per indicator × 16 indicators).
    ml_panel : PanelIndex, optional
        Pre-built panel index (output of ``ml_features.build_panel_index``).
        Pass it explicitly when projecting many counties at the same
        cutoff to avoid rebuilding it for each forecast.
    """
    # Local import to avoid a circular dependency between ensemble and anchors.
    from .anchors import combined_anchor_rate, anchor_as_forecast, load_calibration
    from .strata import classify_horizon

    if not series_observations:
        return None
    indicator = series_observations[-1].indicator
    geoid = series_observations[-1].geoid
    if end_year is None:
        end_year = int(round(effective_year(series_observations[-1])))
    if calibration is None:
        calibration = load_calibration()

    # v3 strata classifications. Both may be None — the lookup chain
    # handles that gracefully by skipping to the global marginalisation.
    horizon_years = target_year - end_year
    h_bucket = classify_horizon(horizon_years) if horizon_years > 0 else None
    pop_bucket = _resolve_pop_bucket(geoid, populations)

    # Trend ensemble first.
    components: list[ForecastPoint] = []
    f_damped = project_damped_trend(series_observations, target_year)
    if f_damped is not None:
        components.append(f_damped)
    f_ar1 = project_ar1_log_diff(series_observations, target_year)
    if f_ar1 is not None:
        components.append(f_ar1)

    inner = (
        combine_forecasts(components, target_year, method_label="trend_ensemble")
        if components else None
    )
    if inner is not None:
        # v3: bias correction first, then SE override (correct order)
        inner = _apply_bias_correction(
            inner, indicator, "trend_ensemble", calibration,
            pop_bucket=pop_bucket, h_bucket=h_bucket,
        )
        inner = _apply_se_override(
            inner, indicator, "trend_ensemble", calibration,
            pop_bucket=pop_bucket, h_bucket=h_bucket,
        )

    # ML trend (third member). Optional — controlled by `use_ml`. We build
    # a cross-county HGB forecast and combine it with the classical trend
    # ensemble at correlation `correlation_rho_inner` (both are
    # target-side models that share the same (geoid, indicator) input
    # series, hence high correlation).
    ml_fp: ForecastPoint | None = None
    if use_ml and ml_series_by_key is not None and ml_populations is not None:
        try:
            from .ml_trend import project_ml_trend_one_shot, METHOD_NAME as _ML_METHOD
            ml_fp = project_ml_trend_one_shot(
                series_by_key=ml_series_by_key,
                populations=ml_populations,
                series_observations=series_observations,
                target_year=target_year,
                cutoff_year=end_year,
                model_cache=ml_model_cache,
                panel=ml_panel,
            )
        except Exception:  # pragma: no cover — graceful degradation
            ml_fp = None
        if ml_fp is not None:
            ml_fp = _apply_bias_correction(
                ml_fp, indicator, _ML_METHOD, calibration,
                pop_bucket=pop_bucket, h_bucket=h_bucket,
            )
            ml_fp = _apply_se_override(
                ml_fp, indicator, _ML_METHOD, calibration,
                pop_bucket=pop_bucket, h_bucket=h_bucket,
            )

    # If we have both classical trend AND ML, fuse them into a single
    # target-side ensemble before the macro blend. Inverse-variance
    # combination with ρ=correlation_rho_inner (default 0.7) since both
    # consume the same underlying ACS series.
    if inner is not None and ml_fp is not None:
        target_inner = _combine_two_with_rho(
            inner, ml_fp, target_year,
            method_label="target_ensemble",
            rho=correlation_rho_inner,
        )
        if target_inner is not None:
            inner = target_inner
    elif ml_fp is not None and inner is None:
        # No classical trend (e.g. <2 obs), use ML alone as the inner.
        inner = ml_fp

    # Multi-source macro anchor. `combined_anchor_rate` expects the
    # `rmse_by_indicator_source` slice — pass it explicitly so the full
    # calibration dict can be threaded through here without confusion.
    per_source_calib = (calibration or {}).get("rmse_by_indicator_source")
    anchor_rate = combined_anchor_rate(
        indicator=indicator,
        end_year=end_year,
        calibration=per_source_calib,
        calibration_horizon=max(int(round(horizon_years)), 1),
    )
    anchor_fp: ForecastPoint | None = None
    if anchor_rate is not None:
        anchor_fp = anchor_as_forecast(
            latest=series_observations[-1],
            target_year=target_year,
            anchor_rate=anchor_rate,
        )
        # Same order: bias first, then SE override.
        anchor_fp = _apply_bias_correction(
            anchor_fp, indicator, "multi_anchor", calibration,
            pop_bucket=pop_bucket, h_bucket=h_bucket,
        )
        anchor_fp = _apply_se_override(
            anchor_fp, indicator, "multi_anchor", calibration,
            pop_bucket=pop_bucket, h_bucket=h_bucket,
        )

    if inner is None and anchor_fp is None:
        return None
    if inner is None:
        return anchor_fp
    if anchor_fp is None:
        return inner

    # Blend at calibrated weight.
    macro_weight = _calibrated_macro_weight(indicator, calibration)
    w = [1 - macro_weight, macro_weight]
    pieces = [inner, anchor_fp]

    point = sum(w[i] * pieces[i].point for i in range(2))
    rho = correlation_rho_anchor
    var = 0.0
    for i in range(2):
        for j in range(2):
            corr = 1.0 if i == j else rho
            var += w[i] * w[j] * pieces[i].se_total * pieces[j].se_total * corr
    se_total = math.sqrt(var) if var > 0 else 0.0
    se_sample = math.sqrt(sum((w[i] * pieces[i].se_sample) ** 2 for i in range(2)))
    se_forecast = math.sqrt(sum((w[i] * pieces[i].se_forecast) ** 2 for i in range(2)))
    ci_lo, ci_hi = ci_from_se(point, se_total)

    notes = (
        f"multi_anchor_blend(macro={macro_weight:.2f}, trend={1 - macro_weight:.2f}); "
        f"trend: {inner.notes}; anchor: {anchor_fp.notes}"
    )
    return ForecastPoint(
        point=point,
        se_total=se_total,
        se_sample=se_sample,
        se_forecast=se_forecast,
        ci90_low=ci_lo,
        ci90_high=ci_hi,
        method="ensemble_multi_anchor",
        target_year=target_year,
        geoid=inner.geoid,
        indicator=inner.indicator,
        horizon=inner.horizon,
        notes=notes,
    )
