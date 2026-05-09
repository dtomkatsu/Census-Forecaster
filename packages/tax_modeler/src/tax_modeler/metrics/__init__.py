"""Distributional and poverty metrics.

These functions are methodology-agnostic — they accept ``(values, weights)``
or ``(values, threshold, weights)`` and produce the canonical inequality
or poverty statistics. SPM-specific resource calculation lives in
:mod:`tax_modeler.poverty.spm`; the metrics here can serve OPM, SPM, or
any custom threshold scheme.
"""
from __future__ import annotations

from .distribution import (
    atkinson,
    decile_summary,
    gini,
    palma,
    weighted_ntile_labels,
)
from .geographic import distribution_by_geography, poverty_by_geography
from .poverty import poverty_depth, poverty_gap, poverty_rate

__all__ = [
    "atkinson",
    "decile_summary",
    "gini",
    "palma",
    "weighted_ntile_labels",
    "poverty_depth",
    "poverty_gap",
    "poverty_rate",
    # Phase 8 — geographic stratification
    "distribution_by_geography",
    "poverty_by_geography",
]
