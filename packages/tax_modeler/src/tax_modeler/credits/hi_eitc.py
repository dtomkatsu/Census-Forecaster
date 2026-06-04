"""Hawaii State Earned Income Tax Credit (HRS §235-55.75).

Hawaii enacted a state EITC effective TY 2018 (Act 107, 2017) at 20% of
the federal EITC, **non-refundable**. Act 209 (2023, HB 954) made the
credit **refundable** and increased the rate to **40% of federal EITC**
for tax years beginning after December 31, 2022.

Calculation::

    hi_eitc = max(0, federal_eitc) × rate_of_federal

When ``refundable=True`` the credit is paid out in full (added to SPM
resources). When ``refundable=False`` (TY 2018-2022 vintage) it is
limited to remaining state tax liability after other non-refundable
credits.

Reform DSL (``Reform.benefit_overrides["hi_eitc"]``):

  * ``rate_of_federal``    fraction of federal EITC (default 0.40 for TY 2023+)
  * ``refundable``         True/False (default True for TY 2023+)
  * ``amount_pct``         multiplier on final credit (default 1.0)
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Optional

import numpy as np
import pandas as pd

from tax_modeler.errors import ConfigError


@dataclass(frozen=True)
class HawaiiEitcParameters:
    """HI EITC parameters. Defaults reflect TY 2023+ law."""

    rate_of_federal: float = 0.40
    refundable: bool = True
    amount_pct: float = 1.0


def hawaii_eitc_parameters(tax_year: Optional[int] = None) -> HawaiiEitcParameters:
    """Year-aware HI EITC parameters.

    Act 107 (2017) introduced the credit at 20% of federal, non-refundable,
    effective TY 2018. Act 209 (2023) raised the rate to 40% and made the
    credit refundable, effective for "tax years beginning after December 31,
    2022" — i.e. TY 2023 onward.

    When ``tax_year`` is omitted, the function returns the post-Act 209
    parameters (TY 2023+). Pre-2023 callers must pass an explicit year so
    backtests don't overstate the credit.
    """
    if tax_year is None or tax_year >= 2023:
        return HawaiiEitcParameters(rate_of_federal=0.40, refundable=True)
    return HawaiiEitcParameters(rate_of_federal=0.20, refundable=False)


def with_hi_eitc_overrides(
    base: HawaiiEitcParameters, overrides: Optional[Mapping[str, object]]
) -> HawaiiEitcParameters:
    if not overrides:
        return base
    valid = set(base.__dataclass_fields__)
    bad = set(overrides) - valid
    if bad:
        raise ConfigError(
            f"unknown HI EITC override keys: {sorted(bad)}",
            available=sorted(valid),
        )
    return replace(base, **dict(overrides))


def compute_hi_eitc_for_units(
    units: pd.DataFrame,
    *,
    tax_year: Optional[int] = None,
    params: Optional[HawaiiEitcParameters] = None,
    overrides: Optional[Mapping[str, object]] = None,
    federal_eitc_col: str = "eitc_amount",
    tax_before_credits_col: str = "hi_tax_before_credits",
    out_col: str = "hi_eitc_amount",
) -> pd.DataFrame:
    """Compute the Hawaii state EITC per tax unit.

    Adds ``out_col`` to a copy of ``units``. If the federal EITC column
    is missing (e.g. baseline didn't run ``compute_base_tax``), the
    output is zero everywhere.

    For non-refundable mode, the credit is capped at remaining state tax
    liability (``hi_tax_before_credits`` minus other already-applied
    non-refundable credits). When that column is missing the function
    falls back to the full credit — slightly overstates the
    non-refundable case for taxpayers whose tax is below the credit.
    """
    p = with_hi_eitc_overrides(
        params or hawaii_eitc_parameters(tax_year), overrides
    )
    df = units.copy()

    if federal_eitc_col not in df.columns:
        df[out_col] = 0.0
        return df

    fed = df[federal_eitc_col].fillna(0).astype(float).to_numpy()
    raw = np.maximum(fed, 0.0) * p.rate_of_federal * p.amount_pct

    if p.refundable or tax_before_credits_col not in df.columns:
        df[out_col] = raw
    else:
        tax_cap = df[tax_before_credits_col].fillna(0).astype(float).to_numpy()
        df[out_col] = np.minimum(raw, np.maximum(tax_cap, 0.0))

    return df
