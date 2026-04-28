"""Split-conformal prediction interval floor for ACS fold residuals.

For a set of calibration-fold residuals {(point_i, actual_i, se_total_i)}:

    non-conformity score:  s_i = |actual_i - point_i| / se_total_i

    finite-sample quantile: q = ⌈(n+1)(1-α)⌉-th order statistic of
                               {s_1, …, s_n} when that index ≤ n,
                               else ∞  (no coverage guarantee possible).

The conformal CI is:  point ± q · se_total.

When used alongside the κ-based CI, take the maximum half-width:
    final_half = max(kappa_half, q · se_total)

This provides a marginal-coverage floor: across all forecasts in the
stratum, at least (1-α) fraction will contain the truth — provably, not
just empirically.  See Angelopoulos & Bates (2022) "A Gentle Introduction
to Conformal Prediction and Distribution-Free Uncertainty Quantification".

Reference: Venn, Shafer, Vovk (2005); Papadopoulos et al. (2002).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from .strata import WILDCARD


@dataclass(frozen=True)
class ConformalRecord:
    """Per-stratum conformal quantile derived from calibration folds."""
    indicator: str
    method: str
    pop_bucket: str
    h_bucket: str
    quantile: float         # q: CI half-width = q · se_total
    n_calibration: int
    target_coverage: float  # nominal α = 1 - target_coverage


def _conformal_quantile(scores: list[float], alpha: float = 0.10) -> float:
    """Finite-sample split-conformal quantile.

    Returns the ⌈(n+1)(1-α)⌉-th order statistic of `scores` (1-indexed),
    or ∞ when the required index exceeds n (coverage guarantee requires
    adding an ∞ sentinel, making the interval infinite).
    """
    n = len(scores)
    if n == 0:
        return float("inf")
    level = math.ceil((n + 1) * (1.0 - alpha))
    if level > n:
        return float("inf")
    return sorted(scores)[level - 1]


def compute_conformal_quantiles(
    residuals: Sequence,           # Sequence[FoldResidual]
    target_coverage: float = 0.90,
    n_threshold: int = 20,
) -> list[ConformalRecord]:
    """Compute per-stratum conformal quantiles from a set of fold residuals.

    Parameters
    ----------
    residuals:
        Bias-corrected FoldResidual objects from the calibration split.
        These should come from the *calibration* fold year(s) — not the
        tuning folds used to fit κ, and not the evaluation folds.
    target_coverage:
        Nominal coverage level (default 0.90 → 90% CI).
    n_threshold:
        Minimum calibration folds per stratum.  Strata with fewer folds
        produce no record (conformal guarantee not reliable below ~20).
    """
    alpha = 1.0 - target_coverage

    # Group non-conformity scores by (indicator, method, pop_bucket, h_bucket).
    groups: dict[tuple[str, str, str, str], list[float]] = {}
    for r in residuals:
        if r.se_total <= 0 or not math.isfinite(r.se_total):
            continue
        score = abs(r.actual - r.point) / r.se_total
        if not math.isfinite(score):
            continue
        key = (r.indicator, r.method, r.pop_bucket, r.h_bucket)
        groups.setdefault(key, []).append(score)

    records: list[ConformalRecord] = []
    for (indicator, method, pop_bucket, h_bucket), scores in sorted(groups.items()):
        n = len(scores)
        if n < n_threshold:
            continue
        q = _conformal_quantile(scores, alpha)
        if not math.isfinite(q):
            continue
        records.append(ConformalRecord(
            indicator=indicator,
            method=method,
            pop_bucket=pop_bucket,
            h_bucket=h_bucket,
            quantile=q,
            n_calibration=n,
            target_coverage=target_coverage,
        ))
    return records


def build_conformal_lookup(
    records: Sequence[ConformalRecord],
):
    """Build a fast lookup function from conformal records.

    Returns a callable `lookup(indicator, method, pop_bucket, h_bucket)`
    that returns the conformal quantile (float) for the best matching
    stratum, or None if no record covers the combination.

    Falls back through the same marginalisation chain used for κ:
      exact → (ind, method, WILDCARD, h) → (ind, method, pop, WILDCARD)
      → (ind, method, WILDCARD, WILDCARD) → None.
    """
    index: dict[tuple[str, str, str, str], float] = {
        (r.indicator, r.method, r.pop_bucket, r.h_bucket): r.quantile
        for r in records
    }

    def lookup(
        indicator: str,
        method: str,
        pop_bucket: Optional[str],
        h_bucket: Optional[str],
    ) -> Optional[float]:
        pb = pop_bucket or WILDCARD
        hb = h_bucket or WILDCARD
        for p, h in (
            (pb, hb),
            (WILDCARD, hb),
            (pb, WILDCARD),
            (WILDCARD, WILDCARD),
        ):
            q = index.get((indicator, method, p, h))
            if q is not None:
                return q
        return None

    return lookup
