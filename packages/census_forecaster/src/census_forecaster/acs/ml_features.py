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
from typing import Iterable, Mapping, NamedTuple, Optional, Sequence

from common.models import AcsObservation
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


# Sentinel indicator names for auxiliary admin data stored in estimate_by_key.
# Not added to PanelIndex.indicators so they never appear as cross-indicator
# features for other ACS indicators — only the explicit lag columns use them.
_BPS_INDICATOR = "_BPS_PERMITS_ANNUAL"
_SAIPE_INDICATOR = "_SAIPE_POVERTY_RATE"
_LAUS_INDICATOR = "_LAUS_UNEMPLOYMENT_RATE"

# Market signals are national (geoid-constant): stored once under a
# reserved pseudo-geoid instead of being replicated across every county.
# Signal names arrive from data/leading_indicators/market_signals.json
# (see markets/signals.py, e.g. "mkt_energy_mom") and are stored under
# sentinel "_" + name.upper().
_MKT_GEOID = "__national__"
# The fixed channel set the mkt_* columns read (must stay aligned with
# the mkt_* block in _AUX_COLUMNS).
_MKT_ENERGY = "_MKT_ENERGY_MOM"
_MKT_SHIPPING = "_MKT_SHIPPING_MOM"
_MKT_REIT = "_MKT_REIT_MOM"

# National unemployment leading indicator (CPS LNS14000000, annual avg %),
# also geoid-constant → stored under _MKT_GEOID. Sentinel excluded from
# PanelIndex.indicators (never a cross-indicator feature).
_NATL_UNEMP = "_NATL_UNEMP_RATE"


# ---------------------------------------------------------------------------
# National-macro feature registry
# ---------------------------------------------------------------------------
# A generic, registry-driven channel for national Census/BLS/BEA/FRED
# series (analogous to the market_data channel, but broader). One
# `national_data` param on build_panel_index carries {name: {year: level}};
# each series is stored under the reserved __national__ pseudo-geoid with
# sentinel "_NM_" + name.upper(), and read into feature columns generated
# from this registry. See METHODOLOGY.md §Market signals (national macro).
#
# The registry is the SINGLE source of truth for both the fetch script
# (scripts/refresh_national_macro.py) and the feature columns here, so the
# two never drift. Fixed-order tuple → national_macro_columns() and the
# _build_row reader iterate the same order, preserving the column-order
# invariant by construction.
#
# Column policy (compact, to control geoid-constant year-effect overfitting
# — these are near-collinear with anchor_year_norm):
#   "logchange1"  → 1 col  natl_<name>_chg1 = log(v[Y]/v[Y-1])   (price/index
#                          series whose level is a monotone year proxy)
#   "diff1"       → 1 col  natl_<name>_chg1 = v[Y] - v[Y-1]       (pp change)
#   "level_diff1" → 2 cols natl_<name>_lvl, natl_<name>_chg1      (rate/ratio
#                          series that mean-revert; level is meaningful)

_NM_GEOID = _MKT_GEOID  # national-macro series share the __national__ geoid


class NationalSeriesSpec(NamedTuple):
    """One national-macro series: fetch hint + feature column policy."""
    name: str        # feature stem, e.g. "cpi_rent", "lfpr", "mortgage30"
    source: str      # "CPI_PANEL" | "BLS_FETCH" | "FRED"
    series_id: str   # "CUUR0000SEHA", "CES0500000003", "MORTGAGE30US", ...
    cadence: str     # "monthly" | "weekly" | "daily" | "quarterly"
    agg: str         # monthly→annual aggregation (calendar-year "mean")
    col_policy: str  # "logchange1" | "diff1" | "level_diff1"


NATIONAL_SERIES: tuple[NationalSeriesSpec, ...] = (
    # --- Tier 0: already committed in data/bls_panel/cpi_panel.json (no fetch);
    #     price indexes → change-only (the level is a monotone year proxy). ---
    NationalSeriesSpec("cpi_allitems", "CPI_PANEL", "CUUR0000SA0",   "monthly", "mean", "logchange1"),
    NationalSeriesSpec("cpi_food",     "CPI_PANEL", "CUUR0000SAF11", "monthly", "mean", "logchange1"),
    NationalSeriesSpec("cpi_housing",  "CPI_PANEL", "CUUR0000SAH1",  "monthly", "mean", "logchange1"),
    NationalSeriesSpec("cpi_rent",     "CPI_PANEL", "CUUR0000SEHA",  "monthly", "mean", "logchange1"),
    NationalSeriesSpec("cpi_gas",      "CPI_PANEL", "CUUR0000SETB01","monthly", "mean", "logchange1"),
    # --- Tier 1: new keyless BLS fetches ---
    NationalSeriesSpec("ahe",          "BLS_FETCH", "CES0500000003", "monthly", "mean", "logchange1"),
    NationalSeriesSpec("lfpr",         "BLS_FETCH", "LNS11300000",   "monthly", "mean", "level_diff1"),
    NationalSeriesSpec("emp_pop",      "BLS_FETCH", "LNS12300000",   "monthly", "mean", "level_diff1"),
    NationalSeriesSpec("jolts_openings","BLS_FETCH","JTS000000000000000JOR","monthly","mean","level_diff1"),
    # --- Tier 1: FRED keyless CSV (Census HVS national vacancy/homeownership
    #     ride the FRED mirror) ---
    NationalSeriesSpec("rental_vacancy","FRED",     "RRVRUSQ156N",   "quarterly","mean","level_diff1"),
    NationalSeriesSpec("homeownership","FRED",      "RHORUSQ156N",   "quarterly","mean","level_diff1"),
    NationalSeriesSpec("mortgage30",   "FRED",      "MORTGAGE30US",  "weekly",  "mean", "diff1"),
    NationalSeriesSpec("dgs10",        "FRED",      "DGS10",         "daily",   "mean", "level_diff1"),
)


def national_series_columns(spec: NationalSeriesSpec) -> tuple[str, ...]:
    """Feature column names contributed by one national series."""
    if spec.col_policy in ("logchange1", "diff1"):
        return (f"natl_{spec.name}_chg1",)
    if spec.col_policy == "level_diff1":
        return (f"natl_{spec.name}_lvl", f"natl_{spec.name}_chg1")
    raise ValueError(f"unknown col_policy: {spec.col_policy!r}")


def national_macro_columns() -> tuple[str, ...]:
    """All national-macro feature column names, in registry order."""
    cols: list[str] = []
    for spec in NATIONAL_SERIES:
        cols.extend(national_series_columns(spec))
    return tuple(cols)


def build_panel_index(
    series_by_key: Mapping[tuple[str, str], Sequence[AcsObservation]],
    bps_data: Optional[Mapping[str, Mapping[int, float]]] = None,
    saipe_data: Optional[Mapping[str, Mapping[int, float]]] = None,
    laus_data: Optional[Mapping[str, Mapping[int, float]]] = None,
    market_data: Optional[Mapping[str, Mapping[int, float]]] = None,
    natl_unemp_data: Optional[Mapping[int, float]] = None,
    national_data: Optional[Mapping[str, Mapping[int, float]]] = None,
) -> PanelIndex:
    """Build a PanelIndex from the calibration panel.

    Parameters
    ----------
    bps_data : optional {geoid → {year → total_units_permitted}}
        BPS permit counts injected under sentinel ``_BPS_PERMITS_ANNUAL``.
        Accessed by ``_build_row`` for the BPS lag columns.
    saipe_data : optional {geoid → {year → poverty_rate_pct}}
        Census SAIPE county poverty rates (annual, %).  Used to feed the
        S1701-friendly ``saipe_lag0/1/2`` and ``saipe_3yr_mean`` columns.
    laus_data : optional {geoid → {year → unemployment_rate_pct}}
        BLS LAUS county unemployment rates (annual average, %).  Used to
        feed the S2301-friendly ``laus_lag0/1/2`` and ``laus_3yr_mean``
        columns.
    market_data : optional {signal_name → {year → value}}
        Annual June-cutoff market signals (see ``markets/signals.py``,
        names like ``mkt_energy_mom``). National / geoid-constant:
        stored once under the reserved ``__national__`` pseudo-geoid.
        Momentum values are signed, so unlike the other auxiliaries
        negatives are kept (only non-finite values are dropped).
    natl_unemp_data : optional {year → national_unemployment_rate_pct}
        CPS national unemployment rate (annual average, %), geoid-constant
        (stored under ``__national__``). Feeds the ``natl_unemp_*`` columns
        — the leading-indicator reframing of the rejected national
        unemployment anchor.
    national_data : optional {series_name → {year → level}}
        National-macro registry channel (``NATIONAL_SERIES``): CPI
        subindexes, wages, labour-force participation, JOLTS, mortgage/10yr
        rates, HVS vacancy/homeownership. Geoid-constant (stored under
        ``__national__``, sentinel ``_NM_<NAME>``). Feeds the
        ``natl_<name>_*`` columns per each series' ``col_policy``.

    None of the auxiliary indicators are added to ``indicators`` so they
    never appear as cross-indicator features for other ACS targets —
    only the explicit lag columns reference them.
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

    if saipe_data is not None:
        for geoid, year_vals in saipe_data.items():
            for year, rate in year_vals.items():
                if rate is not None and rate > 0:
                    est[(geoid, _SAIPE_INDICATOR, int(year))] = float(rate)

    if laus_data is not None:
        for geoid, year_vals in laus_data.items():
            for year, rate in year_vals.items():
                if rate is not None and rate > 0:
                    est[(geoid, _LAUS_INDICATOR, int(year))] = float(rate)

    if market_data is not None:
        for name, year_vals in market_data.items():
            sentinel = "_" + name.upper()
            for year, val in year_vals.items():
                if val is not None and math.isfinite(float(val)):
                    est[(_MKT_GEOID, sentinel, int(year))] = float(val)

    if natl_unemp_data is not None:
        for year, rate in natl_unemp_data.items():
            if rate is not None and math.isfinite(float(rate)) and rate > 0:
                est[(_MKT_GEOID, _NATL_UNEMP, int(year))] = float(rate)

    # National-macro registry channel: {series_name: {year: level}} stored
    # under __national__ with sentinel "_NM_"+name.upper(). Levels are signed
    # (rates/yields/index levels), so only non-finite are dropped.
    if national_data is not None:
        for name, year_vals in national_data.items():
            sentinel = "_NM_" + name.upper()
            for year, val in year_vals.items():
                if val is not None and math.isfinite(float(val)):
                    est[(_NM_GEOID, sentinel, int(year))] = float(val)

    return PanelIndex(
        estimate_by_key=est,
        indicators=tuple(sorted(indicators)),
        geoids=tuple(sorted(geoids)),
        state_fips_by_geoid=dict(state_fips),
    )


# -----------------------------------------------------------------------------
# Feature spec
# -----------------------------------------------------------------------------

# Column ordering (must mirror `_build_row` exactly):
#
#     _BASE_COLUMNS  +  cross_indicator_columns  +  _AUX_COLUMNS  +  (horizon,)
#
# `_build_row` emits the base block, then the cross-indicator columns (in
# the panel's `indicators` order, excluding the target), then the auxiliary
# leading-indicator blocks, then horizon. `FeatureSpec.column_names` must
# interleave the cross block in the SAME place — see the property below.
# (A prior version concatenated all aux columns into `_CORE_COLUMNS` ahead
# of the cross block, so `column_names` disagreed with the real row order
# by the cross-column count; harmless to the model, which is name-blind,
# but it mislabeled any name→position lookup such as permutation
# importance. Regression-tested in test_ml_features.py.)

_BASE_COLUMNS: tuple[str, ...] = (
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
)

# Auxiliary leading-indicator blocks — appended AFTER the cross-indicator
# columns in the real row (see `_build_row`).
_AUX_COLUMNS: tuple[str, ...] = (
    # BPS leading-indicator columns (18-24 month lead for vacancy/migration).
    # Log-scaled permit counts; NaN-filled when BPS data absent for that
    # county/year. HistGradientBoosting handles NaN via native missing-value
    # split branches.
    "bps_log_lag0",    # log(permits[anchor])
    "bps_log_lag1",    # log(permits[anchor - 1])
    "bps_log_lag2",    # log(permits[anchor - 2])
    "bps_3yr_mean",    # mean(bps_log_lag0, bps_log_lag1, bps_log_lag2)
    # SAIPE poverty-rate columns (Census Small Area Income & Poverty
    # Estimates).  Direct level signal for S1701; informative through
    # cross-indicator correlations for other targets.  Raw rate (% as
    # decimal) — HGB treats monotonic transforms equivalently and the
    # raw rate keeps mean-of-lags interpretable.
    "saipe_lag0",      # poverty rate (%) at anchor year
    "saipe_lag1",      # poverty rate (%) at anchor - 1
    "saipe_lag2",      # poverty rate (%) at anchor - 2
    "saipe_3yr_mean",  # mean of valid lags
    # LAUS unemployment-rate columns (BLS Local Area Unemployment Statistics).
    # Direct level signal for S2301; the labour-market state also covaries
    # with poverty, in-migration, and rent-burden, so HGB can use it
    # broadly.  Same raw-rate convention as SAIPE.
    "laus_lag0",       # unemployment rate (%) at anchor year
    "laus_lag1",       # unemployment rate (%) at anchor - 1
    "laus_lag2",       # unemployment rate (%) at anchor - 2
    "laus_3yr_mean",   # mean of valid lags
    # Market leading-indicator signals (June-cutoff annual 12-mo momenta;
    # see markets/signals.py). National / geoid-constant → they act as
    # year-effects in the pooled panel, so the block is deliberately
    # small (4 columns) and each channel is gated on the causal screen's
    # 2020-robust survivors. NaN-filled when market_signals.json absent.
    "mkt_energy_mom_lag0",    # XLE channel (energy → Honolulu CPI)
    "mkt_shipping_mom_lag0",  # MATX channel (freight → Honolulu CPI)
    "mkt_reit_mom_lag0",      # REIT channel (XLRE/VNQ → ZHVI/ZORI)
    "mkt_reit_mom_lag1",      # REIT channel, prior year (VNQ Granger
                              # survives at lag 12 — the lead is ~1yr)
    # National unemployment leading-indicator columns (CPS LNS14000000,
    # annual average, %). Geoid-constant (broadcast under __national__).
    # National labour markets turn before local ones, so the level and
    # recent change as of the anchor year hint at where local
    # unemployment / income / rent-burden are heading over the horizon.
    # This is the reframing of the rejected national-unemployment ANCHOR
    # (see acs/sources/base.py + METHODOLOGY.md §Market signals): as a
    # feature the model learns *when* to trust it, dodging the rate-band
    # / coverage failures that sank the anchor. NaN-filled when absent.
    "natl_unemp_lag0",    # national unemployment rate (%) at anchor year
    "natl_unemp_chg1",    # 1-yr change (pp): lag0 − lag1
    "natl_unemp_chg2",    # 2-yr change (pp): lag0 − lag2
    # National-macro registry columns (13 series → 19 cols, generated from
    # NATIONAL_SERIES so fetch + features never drift). Same __national__
    # geoid-constant / year-effect discipline as the mkt_* and natl_unemp
    # blocks; the ablation + permutation-importance decide which earn keep.
    *national_macro_columns(),
)

# Back-compat alias: full core-column tuple (base + aux), length-preserving.
# NOTE: this is NOT the row order — see `_BASE_COLUMNS`/`_AUX_COLUMNS` and
# `FeatureSpec.column_names` for the real ordering with cross columns.
_CORE_COLUMNS: tuple[str, ...] = _BASE_COLUMNS + _AUX_COLUMNS

_HORIZON_COLUMN = "horizon"


@dataclass(frozen=True)
class FeatureSpec:
    """Names + ordering of the feature columns produced by the builder."""
    target_indicator: str
    cross_indicator_columns: tuple[str, ...]

    @property
    def column_names(self) -> tuple[str, ...]:
        # Mirrors `_build_row`: base, then cross, then aux blocks, then horizon.
        return (
            _BASE_COLUMNS
            + self.cross_indicator_columns
            + _AUX_COLUMNS
            + (_HORIZON_COLUMN,)
        )

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

    When lag-1 is absent but lag-2 exists (e.g., anchor_year=2021 when the
    2020 1-year ACS was not released due to COVID-19), lag-2 substitutes for
    lag-1 and ``diff1`` is annualized over the 2-year gap so the feature
    remains comparably scaled to the non-gap case.
    """
    y0 = panel.get(geoid, target_indicator, anchor_year)
    y1 = panel.get(geoid, target_indicator, anchor_year - 1)
    y2 = panel.get(geoid, target_indicator, anchor_year - 2)

    # Handle missing lag-1 year (e.g., 2020 ACS not released due to COVID-19).
    # When lag-1 is absent but lag-2 is present, substitute lag-2 as the
    # effective lag-1 and shift the lag-2 window one step further back.
    # diff1 is then divided by the gap length (2) to keep it annualised.
    _lag_gap = 1
    if (y1 is None or y1 <= 0) and (y2 is not None and y2 > 0):
        y1 = y2
        y2 = panel.get(geoid, target_indicator, anchor_year - 3)
        _lag_gap = 2

    if y0 is None or y0 <= 0 or y1 is None or y1 <= 0:
        return None

    log0 = math.log(y0)
    log1 = math.log(y1)
    log2 = math.log(y2) if (y2 is not None and y2 > 0) else float("nan")

    diff1 = (log0 - log1) / _lag_gap  # annualized over gap
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

    # SAIPE poverty-rate features (raw percentage, e.g. 8.5 for 8.5%).
    saipe0 = panel.get(geoid, _SAIPE_INDICATOR, anchor_year)
    saipe1 = panel.get(geoid, _SAIPE_INDICATOR, anchor_year - 1)
    saipe2 = panel.get(geoid, _SAIPE_INDICATOR, anchor_year - 2)
    saipe_lag0 = float(saipe0) if (saipe0 is not None and saipe0 > 0) else float("nan")
    saipe_lag1 = float(saipe1) if (saipe1 is not None and saipe1 > 0) else float("nan")
    saipe_lag2 = float(saipe2) if (saipe2 is not None and saipe2 > 0) else float("nan")
    saipe_valid = [v for v in (saipe_lag0, saipe_lag1, saipe_lag2) if math.isfinite(v)]
    saipe_3yr = sum(saipe_valid) / len(saipe_valid) if saipe_valid else float("nan")
    row.extend([saipe_lag0, saipe_lag1, saipe_lag2, saipe_3yr])

    # LAUS unemployment-rate features (raw percentage).
    laus0 = panel.get(geoid, _LAUS_INDICATOR, anchor_year)
    laus1 = panel.get(geoid, _LAUS_INDICATOR, anchor_year - 1)
    laus2 = panel.get(geoid, _LAUS_INDICATOR, anchor_year - 2)
    laus_lag0 = float(laus0) if (laus0 is not None and laus0 > 0) else float("nan")
    laus_lag1 = float(laus1) if (laus1 is not None and laus1 > 0) else float("nan")
    laus_lag2 = float(laus2) if (laus2 is not None and laus2 > 0) else float("nan")
    laus_valid = [v for v in (laus_lag0, laus_lag1, laus_lag2) if math.isfinite(v)]
    laus_3yr = sum(laus_valid) / len(laus_valid) if laus_valid else float("nan")
    row.extend([laus_lag0, laus_lag1, laus_lag2, laus_3yr])

    # Market leading-indicator signals (geoid-constant, keyed under the
    # reserved __national__ pseudo-geoid; signed momenta, so no >0 guard).
    def _mkt(sentinel: str, year: int) -> float:
        v = panel.get(_MKT_GEOID, sentinel, year)
        return float(v) if (v is not None and math.isfinite(v)) else float("nan")

    row.extend([
        _mkt(_MKT_ENERGY, anchor_year),
        _mkt(_MKT_SHIPPING, anchor_year),
        _mkt(_MKT_REIT, anchor_year),
        _mkt(_MKT_REIT, anchor_year - 1),
    ])

    # National unemployment features (geoid-constant; raw % and pp changes).
    nu0 = panel.get(_MKT_GEOID, _NATL_UNEMP, anchor_year)
    nu1 = panel.get(_MKT_GEOID, _NATL_UNEMP, anchor_year - 1)
    nu2 = panel.get(_MKT_GEOID, _NATL_UNEMP, anchor_year - 2)
    natl_lag0 = float(nu0) if (nu0 is not None and math.isfinite(nu0)) else float("nan")
    natl_chg1 = (float(nu0) - float(nu1)) if (
        nu0 is not None and nu1 is not None
        and math.isfinite(nu0) and math.isfinite(nu1)) else float("nan")
    natl_chg2 = (float(nu0) - float(nu2)) if (
        nu0 is not None and nu2 is not None
        and math.isfinite(nu0) and math.isfinite(nu2)) else float("nan")
    row.extend([natl_lag0, natl_chg1, natl_chg2])

    # National-macro registry features (geoid-constant). ONE generic loop
    # over NATIONAL_SERIES — same iteration order as national_macro_columns(),
    # so column names and row slots stay aligned by construction. Transform
    # applied here from stored annual levels of Y and Y-1 (level_diff1 emits
    # level+change; logchange1/diff1 emit change only).
    nan = float("nan")
    for spec in NATIONAL_SERIES:
        sentinel = "_NM_" + spec.name.upper()
        v0 = panel.get(_NM_GEOID, sentinel, anchor_year)
        v1 = panel.get(_NM_GEOID, sentinel, anchor_year - 1)
        v0f = float(v0) if (v0 is not None and math.isfinite(v0)) else None
        v1f = float(v1) if (v1 is not None and math.isfinite(v1)) else None
        logchange = (math.log(v0f / v1f)
                     if (v0f and v1f and v0f > 0 and v1f > 0) else nan)
        diff = (v0f - v1f) if (v0f is not None and v1f is not None) else nan
        if spec.col_policy == "logchange1":       # 1 col: change
            row.append(logchange)
        elif spec.col_policy == "diff1":          # 1 col: change (pp)
            row.append(diff)
        elif spec.col_policy == "level_diff1":    # 2 cols: level, change
            row.append(v0f if v0f is not None else nan)
            row.append(diff)
        else:
            raise ValueError(f"unknown col_policy: {spec.col_policy!r}")

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


def _load_anchor_values_by_geoid_year(filename: str) -> Optional[dict[str, dict[int, float]]]:
    """Load values_by_geoid_year from a bundled anchor JSON file."""
    path = Path(__file__).parent.parent / "data" / "anchors" / filename
    if not path.exists():
        return None
    import json as _json
    with open(path) as f:
        payload = _json.load(f)
    raw = payload.get("values_by_geoid_year", {})
    return {
        geoid: {int(yr): float(v) for yr, v in yr_dict.items()
                if v is not None}
        for geoid, yr_dict in raw.items()
    }


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


def load_saipe_data() -> Optional[dict[str, dict[int, float]]]:
    """Load SAIPE county poverty-rate data from the bundled anchor JSON.

    Returns None if the file is absent — callers should treat this as
    "no SAIPE features available" and fill the corresponding row columns
    with NaN.
    """
    return _load_anchor_values_by_geoid_year("saipe_poverty.json")


def load_laus_data() -> Optional[dict[str, dict[int, float]]]:
    """Load BLS LAUS county unemployment-rate data from the bundled anchor JSON.

    Returns None if the file is absent.
    """
    return _load_anchor_values_by_geoid_year("bls_laus.json")


def load_market_signals_data() -> Optional[dict[str, dict[int, float]]]:
    """Load annual market signals from the bundled leading-indicator JSON.

    Returns ``{signal_name → {year → value}}`` (names like
    ``mkt_energy_mom``; see ``markets/signals.py``), or None if the file
    is absent — callers treat that as "no market features" and the
    ``mkt_*`` columns NaN-fill.
    """
    path = (
        Path(__file__).parent.parent / "data" / "leading_indicators"
        / "market_signals.json"
    )
    if not path.exists():
        return None
    import json as _json
    with open(path) as f:
        payload = _json.load(f)
    raw = payload.get("signals", {})
    return {
        name: {int(yr): float(v) for yr, v in yr_dict.items()
               if v is not None}
        for name, yr_dict in raw.items()
    }


def load_national_unemployment_data() -> Optional[dict[int, float]]:
    """Load the national unemployment rate series as ``{year → rate_pct}``.

    Reads ``data/anchors/bls_national_unemployment.json`` (``values_by_year``;
    written by ``refresh_market_panel.py``). Returns None if absent — the
    ``natl_unemp_*`` columns then NaN-fill. This is the leading-indicator
    home of national unemployment; it is deliberately NOT registered as an
    ACS anchor (that was tried and rejected — see ``acs/sources/base.py``).
    """
    path = (
        Path(__file__).parent.parent / "data" / "anchors"
        / "bls_national_unemployment.json"
    )
    if not path.exists():
        return None
    import json as _json
    with open(path) as f:
        payload = _json.load(f)
    raw = payload.get("values_by_year", {})
    return {int(yr): float(v) for yr, v in raw.items() if v is not None}


def load_national_macro_data() -> Optional[dict[str, dict[int, float]]]:
    """Load the national-macro registry series as ``{name → {year → level}}``.

    Reads ``data/leading_indicators/national_macro.json`` (``series`` block;
    written by ``scripts/refresh_national_macro.py``). Returns None if absent
    — callers treat that as "no national-macro features" and the
    ``natl_<name>_*`` columns NaN-fill. Stored values are calendar-year mean
    levels; the log-change / diff / level transform is applied at row-build
    time per each series' ``col_policy``.
    """
    path = (
        Path(__file__).parent.parent / "data" / "leading_indicators"
        / "national_macro.json"
    )
    if not path.exists():
        return None
    import json as _json
    with open(path) as f:
        payload = _json.load(f)
    raw = payload.get("series", {})
    return {
        name: {int(yr): float(v) for yr, v in yr_dict.items()
               if v is not None}
        for name, yr_dict in raw.items()
    }


__all__ = [
    "PanelIndex",
    "FeatureSpec",
    "TrainingMatrix",
    "NationalSeriesSpec",
    "NATIONAL_SERIES",
    "national_macro_columns",
    "build_panel_index",
    "load_bps_data",
    "load_saipe_data",
    "load_laus_data",
    "load_market_signals_data",
    "load_national_unemployment_data",
    "load_national_macro_data",
    "make_feature_spec",
    "make_training_rows",
    "make_inference_row",
]
