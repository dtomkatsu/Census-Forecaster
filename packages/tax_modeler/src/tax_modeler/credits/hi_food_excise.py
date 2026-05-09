"""Hawaii Refundable Food/Excise Tax Credit (HRS §235-55.85).

The Food/Excise Tax Credit offsets the regressive burden of the Hawaii
General Excise Tax (GET) on food and basic goods. It is the largest
state-level refundable credit and is claimed per qualifying exemption
with an AGI-based phase-out by filing status.

This module is a deterministic re-implementation of the existing
:meth:`HawaiiTaxCredits.food_excise_tax_credit` in
:mod:`tax_modeler.adjustments.hawaii_credits`, exposed via the
Reform DSL with parameter overrides. Computation::

    base_credit  = per_exemption × n_exemptions
    if agi <= phase_out_start: credit = base_credit
    elif agi >= phase_out_end:  credit = 0
    else: credit = base_credit × (1 − (agi − start) / (end − start))

Number of exemptions = filer + (spouse if MFJ) + dependents.

Reform DSL (``Reform.benefit_overrides["hi_food_excise"]``):

  * ``per_exemption``         dollars per exemption (default 110)
  * ``amount_pct``            multiplier on final credit (default 1.0)
  * ``income_threshold_factor`` multiplier on phase-out boundaries (default 1.0)
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping, Optional

import numpy as np
import pandas as pd

from tax_modeler.errors import ConfigError


_DEFAULT_PHASE_OUT_START = {
    "single": 30_000,
    "married_filing_jointly": 50_000,
    "head_of_household": 40_000,
    "married_filing_separately": 25_000,
}
_DEFAULT_PHASE_OUT_END = {
    "single": 50_000,
    "married_filing_jointly": 70_000,
    "head_of_household": 60_000,
    "married_filing_separately": 35_000,
}


@dataclass(frozen=True)
class HawaiiFoodExciseParameters:
    per_exemption: float = 110.0
    phase_out_start: Mapping[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_PHASE_OUT_START)
    )
    phase_out_end: Mapping[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_PHASE_OUT_END)
    )
    amount_pct: float = 1.0
    income_threshold_factor: float = 1.0


def hawaii_food_excise_parameters() -> HawaiiFoodExciseParameters:
    return HawaiiFoodExciseParameters()


def with_food_excise_overrides(
    base: HawaiiFoodExciseParameters, overrides: Optional[Mapping[str, object]]
) -> HawaiiFoodExciseParameters:
    if not overrides:
        return base
    valid = set(base.__dataclass_fields__)
    bad = set(overrides) - valid
    if bad:
        raise ConfigError(
            f"unknown HI food/excise override keys: {sorted(bad)}",
            available=sorted(valid),
        )
    return replace(base, **dict(overrides))


def compute_hi_food_excise_for_units(
    units: pd.DataFrame,
    *,
    params: Optional[HawaiiFoodExciseParameters] = None,
    overrides: Optional[Mapping[str, object]] = None,
    out_col: str = "hi_food_excise_amount",
) -> pd.DataFrame:
    """Compute the HI Food/Excise Tax Credit annual amount per tax unit."""
    p = with_food_excise_overrides(
        params or hawaii_food_excise_parameters(), overrides
    )
    df = units.copy()

    income = df["income"].fillna(0).astype(float).to_numpy()
    is_joint = (df["filing_status"] == "married_filing_jointly").to_numpy()
    n_dep = df["num_dependents"].fillna(0).astype(int).to_numpy()
    n_exemptions = 1 + is_joint.astype(int) + n_dep
    base_credit = n_exemptions * p.per_exemption * p.amount_pct

    starts = df["filing_status"].map(p.phase_out_start).fillna(
        p.phase_out_start.get("single", 30_000)
    ).to_numpy() * p.income_threshold_factor
    ends = df["filing_status"].map(p.phase_out_end).fillna(
        p.phase_out_end.get("single", 50_000)
    ).to_numpy() * p.income_threshold_factor

    # Linear phase-out
    phase_pct = np.clip((income - starts) / np.maximum(ends - starts, 1e-9), 0.0, 1.0)
    credit = base_credit * (1.0 - phase_pct)
    credit = np.where(income >= ends, 0.0, credit)

    df[out_col] = credit
    return df
