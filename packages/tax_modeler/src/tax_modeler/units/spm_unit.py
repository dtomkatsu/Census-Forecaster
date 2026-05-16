"""Pool tax units into SPM units (Tier 2 follow-up).

SPM units pool cohabiting unmarried partners with shared children into a
single unit with one threshold; tax units do not. Without pooling, two
cohabiting parents — each filing as single/HOH with some of the kids —
appear as two filing units with two thresholds, double-counting against
poverty totals (~10-20% upward bias in absolute persons-in-poverty per
the module-level NOTES on :mod:`tax_modeler.poverty.impact`).

This module implements a conservative heuristic that catches the named
bias case without over-pooling unrelated multi-family households:

  * pool tax units sharing an ``hh_id`` when **none** is filed jointly
    and **at least two** have ``num_dependents > 0``

That captures cohabiting parents with shared kids. It does **not** pool:

  * multigenerational households where only one filer has kids
  * roommate households with no dependents
  * a household where one filer is already MFJ (the partners are
    married and the second adult is already covered by the joint unit)

Pooling sums dollar columns (income, credits, benefits, MOOP, work and
childcare expenses), sums counts (dependents, qualifying children),
flips ``filing_status`` to ``married_filing_jointly`` so downstream
threshold and persons-per-unit logic pick up ``n_adults=2``, and
preserves geography from the highest-income partner.

Default-OFF wiring is intentional: this is an architectural change to
the unit of analysis; the user should validate magnitudes against
unpooled output before flipping the default.
"""
from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd


# Columns to sum when pooling tax units into one SPM unit.
# NOTE: ``weight`` is *not* in this list. PUMS weights for two filers in
# the same household are each ~equal to the household weight; summing
# them would double-count person-equivalents downstream. Pooling keeps
# the primary partner's weight (a single representative household-level
# weight).
_SUM_COLS: tuple[str, ...] = (
    "income",
    "total_cash_income",
    "earned_income",
    "wage_income",
    "num_dependents",
    "num_qualifying_children",
    "hi_tax_liability",
    "eitc_amount",
    "ctc_total",
    "ctc_refundable",
    "ctc_nonrefundable",
    "hi_eitc_amount",
    "arpa_ctc_refundable",
    "snap_amount",
    "ssi_amount",
    "ssi_hi_amount",
    "aca_ptc_amount",
    "wic_amount",
    "housing_subsidy_amount",
    "liheap_amount",
    "childcare_amount",
    "hi_food_excise_amount",
    "hi_renters_amount",
    "moop_amount",
    "childcare_expense_amount",
    "work_expense_amount",
)

# Columns to keep from the "primary" (highest-income) tax unit.
_PRIMARY_COLS: tuple[str, ...] = (
    "hh_id",
    "PUMA",
    "PUMA10",
    "SERIALNO",
    "tenure",
    "county",
    "house_district",
    "senate_district",
    "primary_agep",
    "weight",
)


def _pool_candidates(group: pd.DataFrame) -> bool:
    """Return True if this hh_id group looks like cohabiting partners + kids."""
    if len(group) < 2:
        return False
    if (group["filing_status"] == "married_filing_jointly").any():
        return False
    n_with_kids = (group["num_dependents"].fillna(0) > 0).sum()
    return n_with_kids >= 2


def build_spm_units(
    units: pd.DataFrame,
    *,
    sum_cols: Optional[Iterable[str]] = None,
    primary_cols: Optional[Iterable[str]] = None,
    pooled_flag_col: str = "is_spm_pooled",
) -> pd.DataFrame:
    """Pool cohabiting unmarried partners + shared kids into one SPM unit per row.

    Tax units that do not match the pooling heuristic pass through
    unchanged. Pooled rows have:

      * ``filing_status = "married_filing_jointly"`` (so threshold and
        persons-per-unit derive ``n_adults = 2``)
      * Dollar columns summed across partners
      * ``num_dependents`` and ``num_qualifying_children`` summed
      * Geography + tenure from the primary (highest-income) partner

    A boolean ``is_spm_pooled`` column flags which rows were pooled,
    for downstream audit. The original tax-unit frame's row count is
    not preserved when pooling occurs (two tax units → one SPM unit).

    Parameters
    ----------
    units:
        Tax-unit DataFrame. Must carry ``hh_id``, ``filing_status``,
        ``num_dependents``.
    sum_cols / primary_cols:
        Optional overrides on which columns are summed vs. kept from
        the primary partner. Defaults cover the dollar / count columns
        the SPM resource and threshold code reads.
    pooled_flag_col:
        Boolean column written on the output frame.
    """
    required = {"hh_id", "filing_status", "num_dependents"}
    missing = required - set(units.columns)
    if missing:
        raise KeyError(
            f"build_spm_units requires columns {sorted(missing)} on the input frame"
        )

    sum_cols_set = set(sum_cols) if sum_cols is not None else set(_SUM_COLS)
    primary_cols_set = set(primary_cols) if primary_cols is not None else set(_PRIMARY_COLS)

    df = units.copy()
    df[pooled_flag_col] = False

    pooled_rows: list[pd.Series] = []
    untouched_idx: list = []

    for hh_id, group in df.groupby("hh_id", sort=False):
        if not _pool_candidates(group):
            untouched_idx.extend(group.index.tolist())
            continue
        # Pick the highest-income tax unit as the "primary" for geography.
        primary = group.sort_values("income", ascending=False).iloc[0]
        merged = primary.copy()
        for col in df.columns:
            if col in sum_cols_set and col in group.columns:
                merged[col] = float(group[col].fillna(0).sum())
            elif col in primary_cols_set and col in group.columns:
                merged[col] = primary[col]
            # other columns: keep primary's value as fallback
        merged["filing_status"] = "married_filing_jointly"
        merged[pooled_flag_col] = True
        pooled_rows.append(merged)

    untouched = df.loc[untouched_idx]
    if pooled_rows:
        pooled_df = pd.DataFrame(pooled_rows)
        # Match dtypes from the untouched slice (pandas may upcast on Series concat).
        for col in untouched.columns:
            if col in pooled_df.columns:
                try:
                    pooled_df[col] = pooled_df[col].astype(untouched[col].dtype)
                except (TypeError, ValueError):
                    pass
        out = pd.concat([untouched, pooled_df], ignore_index=True)
    else:
        out = untouched.reset_index(drop=True)
    return out


__all__ = ["build_spm_units"]
