"""Hawaii Low-Income Household Renters Credit (HRS §235-55.7).

A small refundable credit for renting low-income filers. The existing
:meth:`HawaiiTaxCredits.low_income_renters_credit` uses random sampling
(``np.random.random() < 0.30``) to imitate the share of low-income
filers who actually claim. That non-determinism is incompatible with
the Reform DSL's "compare baseline vs counterfactual" semantics — the
RNG state would scramble per call.

This module re-implements the credit deterministically:

  * Income test (AGI by filing status) — same as the existing module
  * Take-up rate ``takeup_pct`` (default 0.30) is applied as a *uniform
    multiplier* on the credit amount rather than a per-unit Bernoulli
    coin flip. Aggregate dollar flow is identical; per-unit values are
    smoothed (every eligible unit gets 30% of the full credit instead
    of 30% getting the full credit).

The smoothed approach is standard in microsimulation aggregate
analysis — we lose nothing for fiscal-impact work, and the Reform DSL
remains deterministic.

Reform DSL (``Reform.benefit_overrides["hi_renters"]``):

  * ``takeup_pct``           share of eligible filers receiving (default 0.30)
  * ``amount_pct``           multiplier on final credit (default 1.0)
  * ``income_threshold_factor`` multiplier on AGI ceilings (default 1.0)
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping, Optional

import numpy as np
import pandas as pd

from tax_modeler.errors import ConfigError


_DEFAULT_INCOME_CAP = {
    "single": 30_000,
    "married_filing_jointly": 40_000,
    "head_of_household": 35_000,
    "married_filing_separately": 20_000,
}


@dataclass(frozen=True)
class HawaiiRentersCreditParameters:
    income_cap_by_status: Mapping[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_INCOME_CAP)
    )
    # Tiered credit by AGI (matches existing hawaii_credits.py)
    credit_under_15k: float = 150.0
    credit_15k_to_25k: float = 100.0
    credit_above_25k: float = 50.0
    takeup_pct: float = 0.30
    amount_pct: float = 1.0
    income_threshold_factor: float = 1.0


def hawaii_renters_credit_parameters() -> HawaiiRentersCreditParameters:
    return HawaiiRentersCreditParameters()


def with_renters_overrides(
    base: HawaiiRentersCreditParameters, overrides: Optional[Mapping[str, object]]
) -> HawaiiRentersCreditParameters:
    if not overrides:
        return base
    valid = set(base.__dataclass_fields__)
    bad = set(overrides) - valid
    if bad:
        raise ConfigError(
            f"unknown HI renters override keys: {sorted(bad)}",
            available=sorted(valid),
        )
    return replace(base, **dict(overrides))


def compute_hi_renters_for_units(
    units: pd.DataFrame,
    *,
    params: Optional[HawaiiRentersCreditParameters] = None,
    overrides: Optional[Mapping[str, object]] = None,
    out_col: str = "hi_renters_amount",
) -> pd.DataFrame:
    """Compute the HI Low-Income Household Renters Credit per tax unit."""
    p = with_renters_overrides(
        params or hawaii_renters_credit_parameters(), overrides
    )
    df = units.copy()

    income = df["income"].fillna(0).astype(float).to_numpy()
    income_caps = df["filing_status"].map(p.income_cap_by_status).fillna(
        p.income_cap_by_status.get("single", 30_000)
    ).to_numpy() * p.income_threshold_factor

    # Tiered credit by AGI
    tier_credit = np.where(
        income < 15_000, p.credit_under_15k,
        np.where(income < 25_000, p.credit_15k_to_25k, p.credit_above_25k),
    )

    eligible = income < income_caps
    credit = np.where(eligible, tier_credit, 0.0)
    credit = credit * p.takeup_pct * p.amount_pct
    df[out_col] = credit
    return df
