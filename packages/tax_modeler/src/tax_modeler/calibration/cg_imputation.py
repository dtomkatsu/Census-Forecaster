"""Capital gains share imputation for PUMS filers in the $100K–$1M range.

Extends ``synthetic_cg_share`` (set by top_income_synthesis for $1M+ filers
via Pareto synthesis) to the $100K–$200K and $200K–$1M SOI income bins using
bin-level CG/AGI ratios from IRS SOI Hawaii Table 2.

Why this matters
----------------
PUMS ACS data does not separately survey capital gains realizations. The
``income`` field (PINCP) nominally includes them, but we have no per-filer
signal for how much of a $150K filer's income is CG. Without a CG share,
``calculate_hawaii_tax_for_units`` and ``per_unit_tax`` treat all income as
ordinary, applying full bracket rates. For filers who actually have CG
(IRS SOI shows ~45% of $100K–$200K filers; ~65% of $200K–$1M), this
overstates Hawaii tax — the state caps CG tax at 7.25% (HRS §235-16).

What this does NOT do
---------------------
CG imputation does NOT add income. It recharacterizes an SOI-consistent
fraction of each filer's existing ``income`` as capital gains so that the
tax calculators apply the cap correctly. TCI (total_cash_income) is
therefore unchanged — PUMS income already nominally contains CG.

Scope
-----
- $100K–$200K SOI bin: direct SOI capgain_M / agi_M ratio applied uniformly.
- $200K–$1M: SOI $200K+ total less the synthesized $1M+ contribution gives
  the residual CG/AGI ratio for the $200K–$1M PUMS sub-population.
- $0–$100K: excluded (IRS SOI <1% of AGI is CG).
- $1M+: excluded (Pareto synthesis already sets tier-specific CG shares).
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Income thresholds that bound the imputation range
_LOWER_BOUND = 100_000.0   # below this: no imputation
_UPPER_BOUND = 1_000_000.0  # at/above this: handled by synthesis


def impute_capital_gains_from_soi(
    df: pd.DataFrame,
    soi_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Set ``synthetic_cg_share`` for PUMS filers in the $100K–$1M range.

    Parameters
    ----------
    df:
        Tax units DataFrame with at least ``income`` and ``weight``.
        Rows already having ``synthetic_cg_share > 0`` (Pareto synthesis)
        are skipped.
    soi_df:
        Output of ``load_soi_state_targets()``. Loaded automatically from
        the default CSV path if *None*.

    Returns
    -------
    pd.DataFrame — copy of *df* with ``synthetic_cg_share`` updated for the
    two mid-tier income bins.
    """
    from tax_modeler.calibration.irs_soi_state_targets import (
        load_soi_state_targets, SOI_AGI_BINS,
    )

    out = df.copy()

    if soi_df is None:
        try:
            soi_df = load_soi_state_targets()
        except FileNotFoundError as exc:
            logger.warning("SOI CSV not found — CG imputation skipped: %s", exc)
            return out

    # Normalise the CG share column
    if "synthetic_cg_share" not in out.columns:
        out["synthetic_cg_share"] = 0.0
    else:
        out["synthetic_cg_share"] = out["synthetic_cg_share"].fillna(0.0)

    incomes  = out["income"].to_numpy(dtype=float)
    weights  = out["weight"].to_numpy(dtype=float)
    cg_arr   = out["synthetic_cg_share"].to_numpy(dtype=float).copy()

    # Rows already assigned by Pareto synthesis — do not overwrite.
    already_synthesized = cg_arr > 0

    # Look up the actual bin tuples from SOI_AGI_BINS to avoid float/int
    # mismatch in MultiIndex lookup.
    bin_100_200 = next(b for b in SOI_AGI_BINS if b[0] == 100_000)
    bin_200_plus = next(b for b in SOI_AGI_BINS if b[0] == 200_000)

    # ── $100K–$200K bin ──────────────────────────────────────────────────────
    row_100_200 = soi_df.loc[bin_100_200]
    cg_100_200_M  = float(row_100_200["capgain_M"])
    agi_100_200_M = float(row_100_200["agi_M"])
    share_100_200 = cg_100_200_M / agi_100_200_M if agi_100_200_M > 0 else 0.0

    mask_100_200 = (
        (incomes >= 100_000) & (incomes < 200_000) & ~already_synthesized
    )

    # ── $200K–$1M residual ───────────────────────────────────────────────────
    # SOI bins $200K+ lumps $200K-$1M with $1M+. Subtract the synthesis
    # filers' weighted CG and AGI to get the $200K-$1M sub-population share.
    row_200_plus = soi_df.loc[bin_200_plus]
    soi_cg_200p_M  = float(row_200_plus["capgain_M"])
    soi_agi_200p_M = float(row_200_plus["agi_M"])

    synth_200p = already_synthesized & (incomes >= 200_000)
    synth_cg_M  = float(
        (incomes[synth_200p] * cg_arr[synth_200p] * weights[synth_200p]).sum()
    ) / 1e6
    synth_agi_M = float(
        (incomes[synth_200p] * weights[synth_200p]).sum()
    ) / 1e6

    residual_cg_M  = max(0.0, soi_cg_200p_M  - synth_cg_M)
    residual_agi_M = max(0.0, soi_agi_200p_M - synth_agi_M)
    share_200k_1m  = residual_cg_M / residual_agi_M if residual_agi_M > 0 else 0.0

    mask_200k_1m = (
        (incomes >= 200_000) & (incomes < 1_000_000) & ~already_synthesized
    )

    # Apply
    cg_arr[mask_100_200] = share_100_200
    cg_arr[mask_200k_1m] = share_200k_1m
    out["synthetic_cg_share"] = cg_arr

    logger.info(
        "CG imputation: "
        "$100K–$200K share=%.3f (wt filers=%.0f), "
        "$200K–$1M share=%.3f (wt filers=%.0f) | "
        "SOI $200K+ total: CG $%.1fM AGI $%.1fM; "
        "synthesis absorbed: CG $%.1fM AGI $%.1fM",
        share_100_200, weights[mask_100_200].sum(),
        share_200k_1m, weights[mask_200k_1m].sum(),
        soi_cg_200p_M, soi_agi_200p_M,
        synth_cg_M, synth_agi_M,
    )

    return out
