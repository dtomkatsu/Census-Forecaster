"""Geographic stratification helpers (PUMA, county, district).

Phase 8 adds convenience wrappers around the metrics primitives so
results can be reported at sub-state granularity without manually
groupby-ing every time.

The :class:`tax_modeler.revenue.RevenueEstimator` already exposes a
``by_district(col)`` method for tax-unit-level aggregation; this module
covers the *poverty* and *SPM* side, which operates on resource and
threshold columns rather than tax dollars.
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd

from tax_modeler.errors import ConfigError, DataValidationError

from .distribution import gini, palma
from .poverty import poverty_depth, poverty_gap, poverty_rate


def poverty_by_geography(
    units: pd.DataFrame,
    *,
    resources_col: str,
    threshold,
    weight_col: str = "weight",
    geo_col: str = "PUMA",
) -> pd.DataFrame:
    """Compute SPM-style poverty metrics broken down by a geographic column.

    Parameters
    ----------
    units:
        DataFrame with at least ``resources_col``, ``weight_col``, and
        ``geo_col``.
    resources_col:
        Column holding per-unit SPM resources (or any other resource
        concept).
    threshold:
        Either a scalar (single statewide threshold) or an
        equal-length array/Series providing a per-unit threshold (e.g.
        from :func:`tax_modeler.poverty.threshold_for_units`).
    geo_col:
        Geographic identifier to group on. Defaults to ``"PUMA"``;
        ``"county"`` and ``"house_district"`` are also valid if those
        columns exist on the units frame.

    Returns
    -------
    pd.DataFrame
        One row per geography with: ``count_weighted``, ``poverty_rate``,
        ``poverty_depth``, ``poverty_gap`` (in $ within that geography),
        ``mean_resources``.
    """
    for c in (resources_col, weight_col, geo_col):
        if c not in units.columns:
            raise DataValidationError(
                f"poverty_by_geography requires column {c!r}", missing_columns=[c]
            )

    if isinstance(threshold, (pd.Series, np.ndarray, list, tuple)):
        thr_arr = np.asarray(threshold, dtype=float)
        if len(thr_arr) != len(units):
            raise DataValidationError(
                f"threshold length {len(thr_arr)} != len(units) {len(units)}"
            )
    else:
        thr_arr = np.full(len(units), float(threshold))

    rows = []
    for geo, group in units.groupby(geo_col, observed=True):
        idx = group.index
        thr_subset = thr_arr[units.index.get_indexer(idx)]
        r = group[resources_col].fillna(0).to_numpy(dtype=float)
        w = group[weight_col].fillna(0).to_numpy(dtype=float)
        if w.sum() == 0:
            continue
        rows.append({
            geo_col: geo,
            "count_weighted": float(w.sum()),
            "poverty_rate": poverty_rate(r, thr_subset, w),
            "poverty_depth": poverty_depth(r, thr_subset, w),
            "poverty_gap_$": poverty_gap(r, thr_subset, w),
            "mean_resources_$": float((r * w).sum() / w.sum()),
        })
    return pd.DataFrame(rows).set_index(geo_col).sort_index()


def distribution_by_geography(
    units: pd.DataFrame,
    *,
    value_col: str,
    weight_col: str = "weight",
    geo_col: str = "PUMA",
    indices: Sequence[str] = ("gini", "palma"),
) -> pd.DataFrame:
    """Per-geography inequality indices on a value column.

    Parameters
    ----------
    units, value_col, weight_col, geo_col:
        Standard DataFrame inputs.
    indices:
        Subset of ``("gini", "palma")``. Atkinson is omitted because its
        ``eps`` parameter complicates the API; call atkinson directly
        per group if needed.
    """
    for c in (value_col, weight_col, geo_col):
        if c not in units.columns:
            raise DataValidationError(
                f"distribution_by_geography requires column {c!r}",
                missing_columns=[c],
            )
    bad = set(indices) - {"gini", "palma"}
    if bad:
        raise ConfigError(
            f"unknown inequality indices: {sorted(bad)}",
            available=["gini", "palma"],
        )

    rows = []
    for geo, group in units.groupby(geo_col, observed=True):
        v = group[value_col].fillna(0).to_numpy(dtype=float)
        w = group[weight_col].fillna(0).to_numpy(dtype=float)
        if w.sum() == 0 or len(v) < 2:
            continue
        # Inequality indices need non-negative values
        v_pos = np.clip(v, 0.0, None)
        row = {
            geo_col: geo,
            "count_weighted": float(w.sum()),
            "mean_$": float((v * w).sum() / w.sum()),
        }
        if "gini" in indices:
            row["gini"] = gini(v_pos, w)
        if "palma" in indices:
            row["palma"] = palma(v_pos, w)
        rows.append(row)
    return pd.DataFrame(rows).set_index(geo_col).sort_index()


__all__ = ["poverty_by_geography", "distribution_by_geography"]
