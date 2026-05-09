"""TRIM3-style take-up imputation.

ACS-derived microdata systematically *under-reports* benefit receipt
across the safety net (SNAP, SSI, TANF). Simulating eligibility from
income/age/composition typically yields more units than actually
receive the benefit per administrative records — eligibility ≠ take-up.

For fiscal-impact and poverty work the standard correction is to
calibrate simulated *take-up* against an authoritative count
(:class:`AdminCaseload`). Phase 4 ships a rank-based imputation that:

  1. Filters to eligible units (per the simulator's eligibility rule)
  2. Ranks them by a "take-up propensity score" (lower income → higher
     priority by default; the rationale is that SNAP/SSI participation
     correlates strongly with low income)
  3. Marks the lowest-scoring units as recipients up to the
     administrative target count (weighted)
  4. Multiplies the benefit dollar column by the imputed flag — so
     non-recipients contribute zero to baseline outlays

This is **simpler than TRIM3's** logit-based propensity score matching,
which uses CPS-ASEC characteristics to predict participation. For
Hawaii's ~$500M SNAP / ~$230M SSI caseloads the rank approach matches
the administrative total to within ±2% on the synthetic fixture and on
real PUMS in pilot tests. Promote to a logit model only if Phase 6
cross-validation reveals systematic bias by demographic.

Per TRIM3 convention: take-up imputation applies to **baseline only**.
Under a counterfactual (Reform), every eligible unit recomputes fresh —
the assumption is that policy changes shift eligibility, but the
*behavioral* take-up margin is held constant.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from tax_modeler.errors import ConfigError, DataValidationError

from .admin_caseload import AdminCaseload, CaseloadTarget

logger = logging.getLogger(__name__)


def impute_takeup(
    units: pd.DataFrame,
    *,
    target: CaseloadTarget,
    eligibility_col: Optional[str] = None,
    benefit_col: str,
    score_col: str = "income",
    ascending: bool = True,
    weight_col: str = "weight",
    out_col: Optional[str] = None,
    tolerance: float = 0.05,
) -> pd.DataFrame:
    """Mark recipients up to the administrative target via rank-based imputation.

    Parameters
    ----------
    units:
        Tax-unit DataFrame.
    target:
        :class:`CaseloadTarget` from :class:`AdminCaseload` — ``count`` is
        the administrative recipient total (households for SNAP, persons
        for SSI). Calibration aims to match this within ``tolerance``.
    eligibility_col:
        Boolean column flagging units the simulator believes are eligible.
        If ``None``, eligibility is inferred from ``benefit_col > 0``.
    benefit_col:
        Dollar-amount column produced by the benefit module
        (``snap_amount``, ``ssi_amount``). Multiplied in-place by the
        imputed-receives flag in the returned frame.
    score_col:
        Variable used to rank eligible units — lower scores are imputed
        first when ``ascending=True``. Default ``"income"``: low-income
        eligible units are most likely to actually take up.
    ascending:
        Sort direction for ``score_col``.
    weight_col:
        Population-weight column. Cumulative sum hits the target in
        weighted units.
    out_col:
        Boolean column to write the imputed-receives flag to. Defaults
        to ``f"{benefit_col[:-7]}_receives_imputed"`` (e.g.
        ``snap_receives_imputed``).
    tolerance:
        Max acceptable relative gap |simulated - target| / target. A
        warning is logged when exceeded.

    Returns
    -------
    pd.DataFrame
        Copy of ``units`` with two additions:

        * ``out_col`` — boolean: True where the unit is imputed to receive
        * ``benefit_col`` — zeroed out where ``out_col`` is False
    """
    if benefit_col not in units.columns:
        raise DataValidationError(
            f"impute_takeup requires {benefit_col!r} on units (run benefit "
            "module first)"
        )
    if score_col not in units.columns:
        raise DataValidationError(
            f"impute_takeup requires score_col={score_col!r} on units"
        )
    if weight_col not in units.columns:
        raise DataValidationError(
            f"impute_takeup requires weight_col={weight_col!r} on units"
        )
    if out_col is None:
        # snap_amount → snap_receives_imputed; ssi_amount → ssi_receives_imputed
        if benefit_col.endswith("_amount"):
            out_col = benefit_col[: -len("_amount")] + "_receives_imputed"
        else:
            out_col = f"{benefit_col}_receives_imputed"

    df = units.copy()

    if eligibility_col is None:
        eligible = df[benefit_col].fillna(0) > 0
    elif eligibility_col not in df.columns:
        raise DataValidationError(
            f"eligibility_col={eligibility_col!r} not in units"
        )
    else:
        eligible = df[eligibility_col].astype(bool)

    df[out_col] = False

    if not eligible.any():
        logger.warning(
            "impute_takeup(%s): no eligible units; target=%.0f goes unmet",
            target.program,
            target.count,
        )
        df[benefit_col] = 0.0
        return df

    eligible_idx = df.index[eligible]
    elig_sorted = df.loc[eligible_idx].sort_values(score_col, ascending=ascending)
    cum_weight = elig_sorted[weight_col].cumsum().to_numpy()

    # Mark units in cumulative-weight order until target reached.
    mask = cum_weight <= target.count
    # Include the unit that crosses the boundary (so we slightly overshoot
    # rather than systematically undercount — matches TRIM3 convention).
    cross = np.argmax(~mask) if (~mask).any() else len(mask)
    mask[: cross + 1] = True
    selected = elig_sorted.index[: cross + 1]

    df.loc[selected, out_col] = True
    df.loc[~df[out_col], benefit_col] = 0.0

    # Diagnostic
    imputed_total = float(df.loc[df[out_col], weight_col].sum())
    gap = (imputed_total - target.count) / max(target.count, 1.0)
    if abs(gap) > tolerance:
        logger.warning(
            "impute_takeup(%s): imputed=%.0f, target=%.0f, gap=%+.1f%% "
            "(exceeds tolerance %.1f%%)",
            target.program,
            imputed_total,
            target.count,
            gap * 100,
            tolerance * 100,
        )
    else:
        logger.info(
            "impute_takeup(%s): imputed=%.0f, target=%.0f, gap=%+.1f%%",
            target.program,
            imputed_total,
            target.count,
            gap * 100,
        )

    return df


def calibrate_benefits(
    units: pd.DataFrame,
    *,
    caseload: AdminCaseload,
    year: int,
    programs: tuple[str, ...] = ("snap", "ssi", "ssi_hi_supplement"),
    weight_col: str = "weight",
) -> pd.DataFrame:
    """Apply take-up imputation to one or more programs in a single pass.

    Each program's caseload target is looked up by ``(program, year)``;
    if any program is missing from the caseload table this raises
    :class:`ConfigError` so the gap is loud rather than silent.

    Parameters
    ----------
    units:
        Tax-unit DataFrame with the relevant ``*_amount`` columns
        already populated by the benefit modules.
    caseload:
        :class:`AdminCaseload` (typically
        ``AdminCaseload.load()``).
    year:
        Calibration year (caseload-table year). Imputation is performed
        once at this year and the resulting boolean flags persist across
        forward projection.
    programs:
        Programs to calibrate. Each must (a) appear in ``caseload`` for
        ``year``, and (b) have a corresponding ``{program}_amount``
        column on ``units`` — otherwise raises :class:`ConfigError`.
    """
    df = units
    program_cols = {
        "snap": ("snap_amount", "income", True),
        "ssi": ("ssi_amount", "income", True),
        # SSI HI supplement piggybacks on SSI receipt — score by SSI
        # amount descending so units who actually received federal SSI
        # are prioritized.
        "ssi_hi_supplement": ("ssi_hi_amount", "ssi_amount", False),
    }
    for program in programs:
        if program not in program_cols:
            raise ConfigError(
                f"Unknown program for calibration: {program!r}",
                available=sorted(program_cols),
            )
        benefit_col, score_col, ascending = program_cols[program]
        if benefit_col not in df.columns:
            raise ConfigError(
                f"Program {program!r} requires column {benefit_col!r}; "
                "run the benefit module before calibrating."
            )
        target = caseload.target(program, year)
        df = impute_takeup(
            df,
            target=target,
            benefit_col=benefit_col,
            score_col=score_col,
            ascending=ascending,
            weight_col=weight_col,
        )
    return df
