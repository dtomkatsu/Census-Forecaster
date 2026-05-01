"""Bridge from tax_modeler's income-projection API onto :mod:`census_forecaster`.

This module exposes a **simple** scalar-growth-factor helper that
delegates to :mod:`census_forecaster`'s multi-source ensemble
(``project_ensemble_multi``). It's a thin wrapper for callers that just
want "how much should I scale 2022 income to get a 2026 estimate?".

When to use which projection entry point:

  - **Use this adapter** for the simple "one-step scalar growth factor
    for an indicator's level series" use case. It doesn't need BLS OES
    wage data, occupation matching, or PUMS-specific reweighting.

  - **Use** :class:`tax_modeler.projection.EnsembleProjector` when you
    need its specific features that don't exist in
    ``census_forecaster``: BLS OES wage-growth blending,
    occupation-code matching, hierarchical confidence scoring across
    multiple PUMS-row groups, and tax-unit-vectorized projection
    (``project_income`` returns a fully-projected DataFrame rather
    than a scalar). These are essential when you're projecting a
    full PUMS-derived calibration panel forward, but overkill for
    one-off level adjustments.

The two paths coexist intentionally — they cover different use cases.
Both are exported at the package level via :mod:`tax_modeler.__init__`.
"""
from __future__ import annotations

from typing import Sequence

from census_forecaster.acs.ensemble import project_ensemble_multi
from common.models import AcsObservation


def project_income_growth(
    history: Sequence[AcsObservation],
    target_year: int,
) -> float:
    """Return a one-step scalar growth factor for ``target_year``.

    Runs the census_forecaster multi-source ensemble
    (``project_ensemble_multi``: damped trend + AR(1) + CPI/PCE/QCEW
    anchors + v3 bias-correction) on ``history`` and returns the ratio
    of the projected level to the most recent observed level.

    Parameters
    ----------
    history:
        Sequence of :class:`common.models.AcsObservation` values. Must be
        non-empty and end at a year strictly less than ``target_year``.
        Observations must carry ``geoid`` and ``indicator`` fields so that
        ``project_ensemble_multi`` can look up multi-source anchors.
    target_year:
        Year to project to (inclusive). Must be > ``history[-1].year``.

    Returns
    -------
    float
        ``projected_level / history[-1].estimate``. A value > 1.0 indicates
        positive growth.

    Raises
    ------
    ValueError
        If ``history`` is empty or ``target_year`` is not in the future.
    RuntimeError
        If ``project_ensemble_multi`` returns ``None`` (insufficient data).
    """
    if not history:
        raise ValueError("project_income_growth: history must be non-empty")
    last = history[-1]
    if target_year <= last.year:
        raise ValueError(
            f"project_income_growth: target_year={target_year} must be greater "
            f"than history[-1].year={last.year}"
        )

    fp = project_ensemble_multi(list(history), target_year)
    if fp is None:
        raise RuntimeError(
            f"project_ensemble_multi returned None for target_year={target_year}"
        )
    return fp.point / last.estimate
