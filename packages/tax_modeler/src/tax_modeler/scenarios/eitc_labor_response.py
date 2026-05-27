"""Single-mother LFP behavioral response to a Hawaii state EITC rate cut.

Extensive-margin labor-supply response: when the combined federal + Hawaii
EITC value falls, some single-mother heads-of-household exit the labor
force. This module computes the *expected* per-filer resource loss from
that response and writes it to a column that the
``hi_eitc_revert_20_behavioral`` scenario in
:mod:`tax_modeler.poverty.impact` consumes.

The implementation operates on the tax-unit frame **before** SPM-unit
aggregation, so the loss propagates cleanly through
:func:`tax_modeler.poverty.spm_aggregation.aggregate_to_spm_units` (the
``lfp_behavioral_resource_loss`` column is summed across tax units in
each SPM unit; see ``_SUM_COLS`` in that module).

Method
------
For each HoH filer with ``earned_income > 0`` and ``hi_eitc_amount > 0``:

  p_exit  = elasticity × |log((1 + hi_rate_scenario) / (1 + hi_rate_baseline))|

  loss_if_exit = earned_income            # cash earnings lost
               + eitc_amount              # federal EITC zeros on exit
               + 0.5 × hi_eitc_amount     # remaining HI EITC at 20% rate
               - FICA_RATE × earned_income # payroll tax no longer paid
               - federal_tax_liability    # federal income tax saved

  expected_loss = p_exit × loss_if_exit

The 50%-of-HI-EITC static term is **already** subtracted by the
``hi_eitc_revert_20`` branch in ``_scenario_resources``. The behavioral
term we write here additionally captures the resource loss for the
fraction of HoH filers who exit the LFP entirely.

Elasticity
----------
Default ``elasticity = 0.5`` is the Meyer & Rosenbaum (2001, QJE)
midpoint for single-mother labor-force-participation response to EITC
value. Literature range: 0.3–0.7 (Eissa & Liebman 1996 QJE, Hoynes &
Patel 2018 AEJ Applied). With the default 40%→20% revert, p_exit ≈
0.077 (~7.7% of affected HoH filers).

Caveats
-------
* **Scope** is filing-status HoH (single-mother proxy). Includes single
  fathers (~10% of HoH per HI ACS S1101) — overstates response by ~10%.
* **Linear approximation** of FICA + federal-tax savings using baseline
  values. Most affected single-mother filers fall below the federal
  standard deduction, so ``federal_tax_liability ≈ 0`` already.
* **Excludes** intensive-margin (hours), marriage, and fertility
  responses, and SNAP/UI uptake from new non-workers. The first three
  are smaller in the literature; ignoring SNAP/UI uptake produces a
  slight upward bias on post-response poverty (a marginal LFP exiter
  often qualifies for SNAP that partially replaces the lost EITC +
  earnings).

References
----------
* Meyer, B. D. & Rosenbaum, D. T. (2001). "Welfare, the Earned Income
  Tax Credit, and the Labor Supply of Single Mothers." Quarterly Journal
  of Economics 116(3): 1063–1114.
* Eissa, N. & Liebman, J. B. (1996). "Labor Supply Response to the
  Earned Income Tax Credit." Quarterly Journal of Economics 111(2):
  605–637.
* Hoynes, H. & Patel, A. J. (2018). "Effective Policy for Reducing
  Poverty and Inequality? The Earned Income Tax Credit and the
  Distribution of Income." American Economic Journal: Applied Economics
  10(4): 174–212.
"""
from __future__ import annotations

import logging
import math
from typing import Optional

import numpy as np
import pandas as pd

from tax_modeler.poverty.spm import _EMPLOYEE_FICA_RATE

logger = logging.getLogger(__name__)


LFP_LOSS_COLUMN = "lfp_behavioral_resource_loss"
LFP_EXIT_PROB_COLUMN = "_lfp_exit_prob"


def apply_hi_eitc_lfp_response(
    df: pd.DataFrame,
    *,
    elasticity: float = 0.5,
    hi_rate_baseline: float = 0.40,
    hi_rate_scenario: float = 0.20,
    earned_income_col: str = "earned_income",
    eitc_col: str = "eitc_amount",
    hi_eitc_col: str = "hi_eitc_amount",
    federal_tax_col: str = "federal_tax_liability",
    filing_status_col: str = "filing_status",
    weight_col: str = "weight",
    inplace: bool = False,
) -> tuple[pd.DataFrame, dict]:
    """Compute expected per-filer SPM-resource loss from LFP exit response.

    Writes ``lfp_behavioral_resource_loss`` (and the diagnostic
    ``_lfp_exit_prob``) to the returned frame. Non-affected filers get
    zero. See module docstring for the formula.

    Parameters
    ----------
    df:
        Tax-unit frame after federal EITC, HI EITC, federal income tax,
        and SPM-input enrichment. Must carry ``earned_income``,
        ``eitc_amount``, ``hi_eitc_amount``, ``filing_status``, and
        ``weight``. ``federal_tax_liability`` is optional (treated as 0
        if missing).
    elasticity:
        Single-mother LFP elasticity wrt EITC value. Default 0.5
        (Meyer-Rosenbaum midpoint). Setting to 0 produces all-zero loss.
    hi_rate_baseline, hi_rate_scenario:
        HI state EITC rate as fraction of federal — current law (0.40)
        and scenario (0.20). Used in the Δlog(EITC) factor.
    inplace:
        Modify ``df`` in place if True. Default False.

    Returns
    -------
    (df, diagnostics):
        df has the two new columns; diagnostics summarizes affected
        population and aggregate loss.
    """
    out = df if inplace else df.copy()

    required = [earned_income_col, eitc_col, hi_eitc_col, filing_status_col, weight_col]
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise KeyError(
            f"apply_hi_eitc_lfp_response: missing required columns {missing}"
        )

    if elasticity <= 0:
        out[LFP_LOSS_COLUMN] = 0.0
        out[LFP_EXIT_PROB_COLUMN] = 0.0
        return out, {
            "elasticity": float(elasticity),
            "affected_filers_weighted": 0.0,
            "avg_exit_prob": 0.0,
            "expected_lfp_exits_weighted": 0.0,
            "aggregate_lost_earnings_$M": 0.0,
            "aggregate_resource_loss_$M": 0.0,
        }

    # Δlog of combined federal + HI EITC. Combined value = federal × (1 + hi_rate).
    # Federal piece cancels in the log ratio.
    delta_log_eitc = abs(math.log((1.0 + hi_rate_scenario) / (1.0 + hi_rate_baseline)))
    p_exit = elasticity * delta_log_eitc  # per-filer exit probability (same for all)

    earned = out[earned_income_col].fillna(0).to_numpy(dtype=float)
    fed_eitc = out[eitc_col].fillna(0).to_numpy(dtype=float)
    hi_eitc = out[hi_eitc_col].fillna(0).to_numpy(dtype=float)
    fs = out[filing_status_col].to_numpy()
    weight = out[weight_col].fillna(0).to_numpy(dtype=float)
    if federal_tax_col in out.columns:
        fed_tax = out[federal_tax_col].fillna(0).to_numpy(dtype=float)
    else:
        fed_tax = np.zeros_like(earned)

    affected = (fs == "head_of_household") & (earned > 0) & (hi_eitc > 0)

    loss_if_exit = (
        earned
        + fed_eitc
        + 0.5 * hi_eitc
        - _EMPLOYEE_FICA_RATE * earned
        - fed_tax
    )
    # Clamp loss to non-negative — a filer whose baseline federal tax
    # exceeds earnings+credits (unlikely for affected HoH with EITC) would
    # otherwise show a "loss" that's actually a gain. Defensive.
    loss_if_exit = np.maximum(loss_if_exit, 0.0)

    expected_loss = np.where(affected, p_exit * loss_if_exit, 0.0)
    exit_prob_col = np.where(affected, p_exit, 0.0)

    out[LFP_LOSS_COLUMN] = expected_loss
    out[LFP_EXIT_PROB_COLUMN] = exit_prob_col

    affected_w = float(weight[affected].sum())
    diagnostics = {
        "elasticity": float(elasticity),
        "delta_log_eitc": float(delta_log_eitc),
        "p_exit": float(p_exit),
        "affected_filers_weighted": affected_w,
        "avg_exit_prob": float(p_exit) if affected_w > 0 else 0.0,
        "expected_lfp_exits_weighted": float(affected_w * p_exit),
        "aggregate_lost_earnings_$M": float((weight * affected * earned).sum() * p_exit / 1e6),
        "aggregate_resource_loss_$M": float((weight * expected_loss).sum() / 1e6),
    }
    logger.info(
        "apply_hi_eitc_lfp_response: η=%.2f, Δlog(EITC)=%.4f, p_exit=%.4f, "
        "affected_weighted=%.0f, expected_exits=%.0f, resource_loss=$%.2fM",
        elasticity, delta_log_eitc, p_exit, affected_w,
        affected_w * p_exit, diagnostics["aggregate_resource_loss_$M"],
    )
    return out, diagnostics
