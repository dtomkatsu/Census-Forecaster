"""Iterative Proportional Fitting (IPF) / raking for PUMS reweighting.

Given observed PUMS microdata weights and target marginal distributions
(county controls from census_forecaster), adjust the weights iteratively
so that the reweighted margins match the targets.

Algorithm
---------
Deming-Stephan iterative proportional fitting (1940).  Each full iteration
cycles through all margin variables.  For each variable, every record's
weight is scaled by::

    scale = target_total_for_category / current_weighted_total_for_category

Convergence criterion: the maximum absolute relative change in any margin
cell across one full iteration falls below ``tol`` (default 1e-4).

Reference
---------
Deming, W. E., & Stephan, F. F. (1940). On a Least Squares Adjustment of
a Sampled Frequency Table When the Expected Marginal Totals are Known.
*Annals of Mathematical Statistics*, 11(4), 427–444.
"""
from __future__ import annotations

from ..models import PumsRecord, CountyControls


def rake(
    records: list[PumsRecord],
    controls: CountyControls,
    max_iter: int = 100,
    tol: float = 1e-4,
) -> list[float]:
    """Reweight PUMS records via IPF to match county margin controls.

    Parameters
    ----------
    records : list[PumsRecord]
        PUMS records for the source geography (PUMAs covering or
        overlapping the target county).  Typically pre-filtered and
        allocation-factor-adjusted before calling this function.
    controls : CountyControls
        Target marginal totals.  Only variables present in
        ``controls.margins`` are constrained; others float freely.
    max_iter : int
        Maximum number of full-cycle iterations (default 100).
    tol : float
        Convergence tolerance (default 1e-4).  Iteration stops when
        the maximum |scale − 1| across all margin cells is below ``tol``.

    Returns
    -------
    list[float]
        Reweighted record weights, in the same order as ``records``.
        Input ``PumsRecord`` objects are not mutated.

    Notes
    -----
    Records missing a variable referenced in ``controls.margins`` are
    skipped for that variable's raking step — their weight is unaffected
    by that constraint.
    """
    weights = [r.weight for r in records]
    if not records or not controls.margins:
        return weights

    for _iteration in range(max_iter):
        max_delta = 0.0

        for var_name, targets in controls.margins.items():
            # --- accumulate current weighted totals per category ---
            current: dict[str, float] = {cat: 0.0 for cat in targets}
            for rec, w in zip(records, weights):
                val = rec.variables.get(var_name)
                if val is None:
                    continue
                cat = _categorise(val, targets)
                if cat in current:
                    current[cat] += w

            # --- scale weights ---
            for i, (rec, w) in enumerate(zip(records, weights)):
                val = rec.variables.get(var_name)
                if val is None:
                    continue
                cat = _categorise(val, targets)
                if cat not in targets:
                    continue
                curr_total = current.get(cat, 0.0)
                target_total = targets[cat]
                if curr_total > 0 and target_total >= 0:
                    scale = target_total / curr_total
                    weights[i] = w * scale
                    delta = abs(scale - 1.0)
                    if delta > max_delta:
                        max_delta = delta

        if max_delta < tol:
            break

    return weights


def _categorise(value: float, targets: dict[str, float]) -> str:
    """Map a numeric PUMS value to the matching category key in *targets*.

    Handles three label styles:
    - Exact integer string: "0", "1", "2", …
    - Ceiling / "X+" style: "2+", "3+", "4+" — the value ≥ threshold.
    - Range style: "2-4" — not yet implemented; falls back to str(int(value)).
    """
    int_val = int(value)
    str_val = str(int_val)
    if str_val in targets:
        return str_val
    for cat in targets:
        if cat.endswith("+"):
            try:
                threshold = int(cat[:-1])
            except ValueError:
                continue
            if int_val >= threshold:
                return cat
    return str_val
