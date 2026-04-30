"""Bridge from tax_modeler's income-projection API onto :mod:`census_forecaster`.

The original ctc-and-eitc project shipped its own ``src/projection/ensemble.py``
(``EnsembleProjector``, now living at :mod:`tax_modeler.projection.ensemble`)
that combined ACS trends with BLS OES wage growth to project tax-unit income
forward.

Inside the Census-Forecaster monorepo, the same statistical machinery already
exists in :mod:`census_forecaster` as the ACS ensemble (damped-trend +
AR(1) + macro-anchor blending). This adapter exposes a small surface for
tax_modeler callers that just want a one-year scalar growth factor for a
given series, delegating the heavy lifting to ``census_forecaster``.

Use this module as the **preferred new API**. The legacy
``tax_modeler.projection.ensemble.EnsembleProjector`` is still importable for
back-compat but will be removed in a future tax_modeler release.
"""
from __future__ import annotations

from typing import Sequence

from census_forecaster import (
    fit_damped_trend,
    project_damped_trend,
)
from common.models import AcsObservation


def project_income_growth(
    history: Sequence[AcsObservation],
    target_year: int,
) -> float:
    """Return a one-step scalar growth factor for ``target_year``.

    Fits a damped-trend model to ``history`` (must already be sorted
    ascending by year), projects forward to ``target_year``, and returns
    the ratio of the projected level to the most recent observed level.

    Parameters
    ----------
    history:
        Sequence of :class:`common.models.AcsObservation` values. Must be
        non-empty and end at a year strictly less than ``target_year``.
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
    """
    if not history:
        raise ValueError("project_income_growth: history must be non-empty")
    last = history[-1]
    if target_year <= last.year:
        raise ValueError(
            f"project_income_growth: target_year={target_year} must be greater "
            f"than history[-1].year={last.year}"
        )

    h = target_year - last.year
    fit = fit_damped_trend(list(history))
    projection = project_damped_trend(fit, h=h)
    if not projection:
        raise RuntimeError("project_damped_trend returned empty result")
    return projection[-1].point / last.estimate
