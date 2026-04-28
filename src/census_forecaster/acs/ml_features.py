"""Feature engineering for the cross-county ML forecaster.

This module builds the feature matrix consumed by `ml_trend.py`.
Features are pure-Python lists (NaN-filled when an input is missing) so
the module has zero numpy dependency at import time — sklearn is the
only ML library and it is loaded lazily inside `ml_trend.py`.

Feature design rationale
------------------------
The two existing trend models in ``projection.py`` (damped log trend +
AR(1)) operate on a single (geoid, indicator) series in isolation. The
ML model's value-add is *cross-county pooling*: a tree learner can
borrow strength across counties via:

* **Lagged target** (3 years of log levels + 2 YoY log-diffs + 3-yr
  trailing mean diff) — captures the same autoregressive signal the
  classical models exploit, but lets the tree learn level-dependent and
  growth-rate-dependent rules.
* **County metadata** (log 2020 population, pop_class one-hot, state
  FIPS) — county fixed effects that the per-series models can't see.
* **Cross-indicator features** (other ACS indicators' log values at the
  anchor year) — this is the genuinely new signal. Median rent depends
  on local wages and homeownership rate; unemployment depends on
  educational attainment and median age; etc. The classical models
  cannot learn these cross-indicator interactions because they look at
  one series at a time.
* **Horizon as a feature** — one model serves all horizons h ∈ 1..5,
  which lets the tree learn that the same growth signal compounds
  differently at h=1 vs h=5.

Walk-forward discipline
-----------------------
The training set must not see any observation whose effective year > the
caller-supplied ``anchor_year``. For a row whose features are anchored at
``src_anchor`` and target at ``src_anchor + h``, this means
``src_anchor + h ≤ anchor_year``. ``make_training_rows`` enforces this
strictly so the back-test harness gets honest hold-out residuals.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

from ..models import AcsObservation
from .projection import effective_year


# -----------------------------------------------------------------------------
# Panel index
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class PanelIndex:
    """O(1) lookup over the full calibration panel.

    Built once per calibration / projection run, then re-used across all
    feature constructions. Keys are (geoid, indicator, effective_year)
    tuples; the value is the published 1-year ACS estimate (5-year
    estimates are excluded so the cross-indicator feature uses the
    cleanest signal — 5-yr midpoints would smear the temporal alignment).
    """
    estimate_by_key: Mapping[tuple[str, str, int], float]
    indicators: tuple[str, ...]
    geoids: tuple[str, ...]
    state_fips_by_geoid: Mapping[str, int]

    def get(self, geoid: str, indicator: str, year: int) -> Optional[float]:
        return self.estimate_by_key.get((geoid, indicator, year))


# Sentinel indicator name for BPS data stored in estimate_by_key.
# Not added to PanelIndex.indicators so it never appears as a cross-indicator
# feature for other ACS indicators — only the explicit BPS columns use it.
_BPS_INDICATOR = "_BPS_PERMITS_ANNUAL"


def build_panel_index(
    series_by_key: Mapping[tuple[str, str], Sequence[AcsObservation]],
    bps_data: Optional[Mapping[str, Mapping[int, float]]] = None,
) -> PanelIndex:
    """Build a PanelIndex from the calibration panel.

    Parameters
    ----------
    bps_data : optional {geoid → {year → total_units_permitted}}
        When provided, BPS permit counts are injected into `estimate_by_key`
        under the sentinel key ``_BPS_PERMITS_ANNUAL``.  They are accessed by
        ``_build_row`` to produce the four BPS lag columns; they are NOT added
        to ``indicators`` so they never appear as cross-indicator features.
    """
    est: dict[tuple[str, str, int], float] = {}
    indicators: set[str] = set()
    geoids: set[str] = set()
    state_fips: dict[str, int] = {}

    for (geoid, indicator), obs_list in series_by_key.items():
        indicators.add(indicator)
        geoids.add(geoid)
        if geoid not in state_fips:
            try:
                state_fips[geoid] = int(geoid[:2])
            except (TypeError, ValueError):
                state_fips[geoid] = 0
        for o in obs_list:
            if o.vintage != "1y":
                continue
            if not (o.estimate is not None and math.isfinite(o.estimate) and o.estimate > 0):
                continue
            year = int(round(effective_year(o)))
            est[(geoid, indicator, year)] = float(o.estimate)

    if bps_data is not None:
        for geoid, year_vals in bps_data.items():
            for year, count in year_vals.items():
                if count is not None and count >= 0:
                    est[(geoid, _BPS_INDICATOR, int(year))] = float(count)

    return PanelIndex(
        estimate_by_key=est,
        indicators=tuple(sorted(indicators)),
        geoids=tuple(sorted(geoids)),
        state_fips_by_geoid=dict(state_fips),
    )


# -----------------------------------------------------------------------------
# Feature spec
# -----------------------------------------------------------------------------

# Fixed order of "core" feature columns (lagged target + county metadata).
# Cross-indicator columns are appended in the panel's `indicators` order
# (ascending by code), excluding the target indicator. Horizon column is
# always last so back-end code can index by name.

_CORE_COLUMNS: tuple[str, ...] = (
    "log_lag_0",       # log(y[anchor])
    "log_lag_1",       # log(y[anchor - 1])
    "log_lag_2",       # log(y[anchor - 2])
    "diff_1",          # log(y[anchor]) - log(y[anchor - 1])
    "diff_2",          # log(y[anchor - 1]) - log(y[anchor - 2])
    "trailing_3yr_mean_diff",
    "log_pop_2020",
    "pop_small",
    "pop_medium",
    "pop_large",
    "pop_xlarge",
    "state_fips_int",
    # Filled in with sin/cos of 2-pi · (anchor mod 11) / 11 — no actual
    # cyclical structure, but a robust target-encoded pseudo-time index.
    "anchor_year_norm",
    # BPS leading-indicator columns (18-24 month lead for vacancy/migration).
    # Log-scaled permit counts; NaN-filled when BPS data absent for that
    # county/year. HistGradientBoosting handles NaN via native missing-value
    # split branches.
    "bps_log_lag0",    # log(permits[anchor])
    "bps_log_lag1",    # log(permits[anchor - 1])
    "bps_log_lag2",    # log(permits[anchor - 2])
    "bps_3yr_mean",    # mean(bps_log_lag0, bps_log_lag1, bps_log_lag2)
)

_HORIZON_COLUMN = "horizon"


@dataclass(frozen=True)
class FeatureSpec:
    """Names + ordering of the feature columns produced by the builder."""
    target_indicator: str
    cross_indicator_columns: tuple[str, ...]

    @property
    def column_names(self) -> tuple[str, ...]:
        return _CORE_COLUMNS + self.cross_indicator_columns + (_HORIZON_COLUMN,)

    @property
    def n_features(self) -> int:
        return len(self.column_names)


def make_feature_spec(target_indicator: str, panel: PanelIndex) -> FeatureSpec:
    """Build a deterministic FeatureSpec for one target indicator."""
    cross = tuple(
        f"x_{ind}"
        for ind in panel.indicators
        if ind != target_indicator
    )
    return FeatureSpec(
        target_indicator=target_indicator,
        cross_indicator_columns=cross,
    )


# -----------------------------------------------------------------------------
# Row builders
# -----------------------------------------------------------------------------

# Population bucket boundaries — must match `strata.classify_pop`.
# Repeated here to keep this module a clean dataflow leaf with no
# back-edge into the calibration layer.
_POP_BOUNDS: tuple[tuple[str, int, Optional[int]], ...] = (
    ("small",  0,        50_000),
    ("medium", 50_000,   200_000),
    ("large",  200_000,  1_000_000),
    ("xlarge", 1_000_000, None),
)


def _pop_one_hot(pop: Optional[float]) -> tuple[float, float, float, float]:
    """Return (small, medium, large, xlarge) one-hot tuple. All-zeros if missing."""
    if pop is None or not math.isfinite(pop) or pop < 0:
        return (0.0, 0.0, 0.0, 0.0)
    for i, (_name, lo, hi) in enumerate(_POP_BOUNDS):
        if hi is None:
            if pop >= lo:
                return tuple(1.0 if j == i else 0.0 for j in range(4))  # type: ignore[return-value]
        elif lo <= pop < hi:
            return tuple(1.0 if j == i else 0.0 for j in range(4))  # type: ignore[return-value]
    return (0.0, 0.0, 0.0, 0.0)


def _anchor_year_norm(year: int) -> float:
    """Cheap pseudo-time encoding so the model sees relative recency.

    Maps year ∈ [2010, 2030] → roughly [-1, 1]. Trees split on raw values
    fine; this just keeps the magnitude tame so future calibration code
    that uses standardised features won't blow up on unbounded input.
    """
    return (year - 2017.0) / 10.0


def _build_row(
    panel: PanelIndex,
    populations: Mapping[str, int],
    geoid: str,
    target_indicator: str,
    anchor_year: int,
    horizon: int,
    spec: FeatureSpec,
) -> Optional[list[float]]:
    """Build one feature row for (geoid, target_indicator, anchor_year, horizon).

    Returns ``None`` when the *required* lag-0 and lag-1 anchors are
    missing (without two consecutive years we cannot construct ``diff_1``,
    which is the model's most informative single feature). Lag-2 and the
    cross-indicator panel cells are NaN-filled when missing — the
    `HistGradientBoosting` learner natively handles missing values via its
    `is_missing` split branch.
    """
    y0 = panel.get(geoid, target_indicator, anchor_year)
    y1 = panel.get(geoid, target_indicator, anchor_year - 1)
    if y0 is None or y0 <= 0 or y1 is None or y1 <= 0:
        return None
    y2 = panel.get(geoid, target_indicator, anchor_year - 2)

    log0 = math.log(y0)
    log1 = math.log(y1)
    log2 = math.log(y2) if (y2 is not None and y2 > 0) else float("nan")

    diff1 = log0 - log1
    diff2 = (log1 - log2) if math.isfinite(log2) else float("nan")
    if math.isfinite(diff2):
        trailing = (diff1 + diff2) / 2.0
    else:
        trailing = diff1

    pop = populations.get(geoid)
    pop_f = float(pop) if pop is not None else float("nan")
    log_pop = math.log(pop_f) if (math.isfinite(pop_f) and pop_f > 0) else float("nan")
    p_s, p_m, p_l, p_x = _pop_one_hot(pop_f)
    state_fips = panel.state_fips_by_geoid.get(geoid, 0)

    row: list[float] = [
        log0,
        log1,
        log2,
        diff1,
        diff2,
        trailing,
        log_pop,
        p_s,
        p_m,
        p_l,
        p_x,
        float(state_fips),
        _anchor_year_norm(anchor_year),
    ]

    # Cross-indicator features (in spec order; spec excludes target_indicator).
    for col in spec.cross_indicator_columns:
        other = col[2:]  # strip "x_" prefix
        v = panel.get(geoid, other, anchor_year)
        row.append(math.log(v) if (v is not None and v > 0) else float("nan"))

    # BPS leading-indicator features (log-scaled permit counts).
    bps0 = panel.get(geoid, _BPS_INDICATOR, anchor_year)
    bps1 = panel.get(geoid, _BPS_INDICATOR, anchor_year - 1)
    bps2 = panel.get(geoid, _BPS_INDICATOR, anchor_year - 2)
    # BPS can be zero for low-activity counties; treat 0 as missing (log undefined).
    log_bps0 = math.log(bps0) if (bps0 is not None and bps0 > 0) else float("nan")
    log_bps1 = math.log(bps1) if (bps1 is not None and bps1 > 0) else float("nan")
    log_bps2 = math.log(bps2) if (bps2 is not None and bps2 > 0) else float("nan")
    bps_valid = [v for v in (log_bps0, log_bps1, log_bps2) if math.isfinite(v)]
    bps_3yr = sum(bps_valid) / len(bps_valid) if bps_valid else float("nan")
    row.extend([log_bps0, log_bps1, log_bps2, bps_3yr])

    row.append(float(horizon))
    return row


# -----------------------------------------------------------------------------
# Training and inference row generators
# -----------------------------------------------------------------------------

@dataclass
class TrainingMatrix:
    """Output of `make_training_rows`.

    ``X`` and ``y`` are aligned in the obvious way; ``meta`` carries the
    (geoid, anchor_year, target_year, horizon) tuple for each row so
    downstream residual analysis (e.g. per-h SE estimation) can stratify
    without re-deriving the index.
    """
    X: list[list[float]] = field(default_factory=list)
    y: list[float] = field(default_factory=list)
    meta: list[tuple[str, int, int, int]] = field(default_factory=list)
    spec: Optional[FeatureSpec] = None


def make_training_rows(
    panel: PanelIndex,
    populations: Mapping[str, int],
    target_indicator: str,
    cutoff_year: int,
    horizons: Iterable[int] = (1, 2, 3, 4, 5),
) -> TrainingMatrix:
    """Build a walk-forward training matrix for one target indicator.

    For every (geoid, src_anchor, h) where ``src_anchor + h ≤ cutoff_year``
    and the panel has both the anchor and the target observation, emit
    one training row.

    The target ``y_row`` is the *log-growth from anchor to target*:
    ``y_row = log(y[target_year] / y[src_anchor])``. Predicting log-growth
    instead of raw level matches the parameterisation of the existing
    classical trend models (which all live in log-space) and lets the
    tree learn growth dynamics rather than memorising county levels.
    """
    spec = make_feature_spec(target_indicator, panel)
    out = TrainingMatrix(spec=spec)
    horizons = tuple(int(h) for h in horizons)

    for geoid in panel.geoids:
        for src_anchor in range(2010, cutoff_year + 1):
            for h in horizons:
                target_year = src_anchor + h
                if target_year > cutoff_year:
                    continue
                anchor_val = panel.get(geoid, target_indicator, src_anchor)
                target_val = panel.get(geoid, target_indicator, target_year)
                if (anchor_val is None or anchor_val <= 0
                        or target_val is None or target_val <= 0):
                    continue
                row = _build_row(
                    panel, populations, geoid, target_indicator,
                    src_anchor, h, spec,
                )
                if row is None:
                    continue
                out.X.append(row)
                out.y.append(math.log(target_val / anchor_val))
                out.meta.append((geoid, src_anchor, target_year, h))

    return out


def make_inference_row(
    panel: PanelIndex,
    populations: Mapping[str, int],
    geoid: str,
    target_indicator: str,
    anchor_year: int,
    horizon: int,
    spec: FeatureSpec,
) -> Optional[list[float]]:
    """Build the single prediction-time feature row.

    Returns ``None`` when the anchor or anchor-1 are unavailable for this
    (geoid, indicator) — the caller falls back to the classical models.
    """
    if spec.target_indicator != target_indicator:
        raise ValueError(
            f"FeatureSpec target {spec.target_indicator!r} != requested "
            f"{target_indicator!r} (specs are not interchangeable)"
        )
    return _build_row(
        panel, populations, geoid, target_indicator,
        anchor_year, horizon, spec,
    )


def load_bps_data() -> Optional[dict[str, dict[int, float]]]:
    """Load BPS permit data from the bundled JSON file, or None if absent."""
    bps_path = (
        Path(__file__).parent.parent / "data" / "leading_indicators" / "bps_permits.json"
    )
    if not bps_path.exists():
        return None
    import json as _json
    with open(bps_path) as f:
        payload = _json.load(f)
    raw = payload.get("values_by_geoid_year", {})
    # Convert {geoid: {str_year: count}} → {geoid: {int_year: float}}
    return {
        geoid: {int(yr): float(cnt) for yr, cnt in yr_dict.items()}
        for geoid, yr_dict in raw.items()
    }


__all__ = [
    "PanelIndex",
    "FeatureSpec",
    "TrainingMatrix",
    "build_panel_index",
    "load_bps_data",
    "make_feature_spec",
    "make_training_rows",
    "make_inference_row",
]
