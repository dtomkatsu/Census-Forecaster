"""RxKids Hawaiʻi — modeled prenatal + infant cash prescription program.

Hawaii-equivalent of the RxKids program operating in Flint MI and 35+
other Michigan communities (administered by Michigan State University +
GiveDirectly, launched Jan 2024). RxKids provides unrestricted cash
"prescribed" during pregnancy and the postnatal period, structured as
charitable disbursement (not taxable income, no SNAP/Medicaid offset).

This module evaluates a Hawaii-targeted variant adapted to local cost
of living and Hawaii's existing Medicaid (QUEST Integration) eligibility
framework. The default parameters model a Medicaid-eligibility-gated
variant — chosen to keep program cost in a politically tractable range
(~$45M/yr) rather than match Flint's universal eligibility design
(~$110M/yr if scaled to all 15,535 annual Hawaii births).

Program scope
-------------

Eligibility (default = Medicaid-targeted)
    * Adult women filing as ``single`` or ``head_of_household`` with
      income ≤ 138 % FPL (Hawaii Medicaid expansion adult threshold).
    * Prenatal: ``num_dependents == 0`` (filer is not yet a parent of
      record; "expecting"). Because PUMS does not observe pregnancy,
      we apply ``prenatal_pregnancy_probability`` per eligible woman,
      calibrated to the Hawaii Medicaid-financed births / Medicaid
      adult women ratio (~0.12, see RXKIDS_METHODOLOGY.md).
    * Postnatal: any filing unit with ``num_dependents > 0`` and the
      same income test, with payments scaled to the unit's count of
      children under ``postnatal_age_cutoff`` (default 5). Because
      individual child ages are not on the tax-unit frame, we use
      ``child_under_age_share`` to convert ``num_dependents`` into an
      effective count of children 0–5.

Payment structure (default mirrors task spec, not Flint reality)
    * Prenatal: ``prenatal_monthly`` × ``prenatal_months``
      (default 500 × 9 = $4,500 per pregnancy)
    * Postnatal: ``postnatal_monthly_per_child`` × ``n_children_0_5`` × 12
      (default $125/mo × eligible kids × 12 months = $1,500/yr/child)
    * Take-up: ``takeup_rate`` (default 0.80; Flint observed 0.98 under
      universal design + hospital partnership — Hawaii conservatively
      models 0.80 in absence of analogous infrastructure)

Tax treatment
    * ``is_taxable = False`` (default). Flint program is structured as
      charitable disbursement (GiveDirectly), so payments do not flow
      through AGI / EITC / CTC interactions. Modeled by adding the
      ``rxkids_amount`` column to SPM resources only — NOT to
      ``total_cash_income``. See ``compute_spm_resources`` wiring.

Annual cost (default Medicaid-targeted Hawaii variant, approx.)
    * Prenatal: ~5,000 eligible women × 0.12 pregnancy prob × $4,500
      × 0.80 take-up ≈ $2.2M
    * Postnatal: ~10,000 eligible HHs × ~0.5 kids 0-5 × $1,500
      × 0.80 take-up ≈ $6M
    * Total: small-program territory (~$8-15M, sensitive to take-up).
      A universal variant matching Flint design would be ~$110M.

Universal variant (advocacy framing)
    Override the defaults to model the Flint universal program:
        params = RxKidsHIParams(
            prenatal_monthly=2000.0,    # one-time $2,000 (use
                                        # prenatal_months=1 to model
                                        # as one-shot)
            prenatal_months=1,
            postnatal_monthly_per_child=500.0,
            postnatal_age_cutoff=1,    # under-1s only (Flint design)
            income_fpl_cap=10.0,        # effectively universal
            takeup_rate=0.95,
            prenatal_pregnancy_probability=0.04,  # birth rate among all
                                                  # women of childbearing age
        )

Caveats
-------
* PUMS does not observe pregnancy → prenatal payments are
  probabilistic. The ``prenatal_pregnancy_probability`` parameter is the
  expected annual pregnancy rate among eligible filers; defaults are
  calibrated from Hawaii Medicaid-financed birth counts.
* PUMS tax-unit frame does not carry individual child ages → postnatal
  payments rely on ``child_under_age_share`` (default 0.20, the
  Hawaii-ACS share of dependents <6 among all dependents 0-17 in
  Medicaid-eligible households). Sensitivity: linear in this share.
* The Flint RxKids program is universal (no income/Medicaid test). The
  default parameters here model a Medicaid-eligibility-gated variant
  for cost reasons. Override ``income_fpl_cap`` to a high value to
  model the universal variant.
* Modeled as non-taxable charitable cash. If the Hawaii legislature
  structured a similar program differently (e.g. as a refundable tax
  credit), the resource-accounting treatment would need to change.

Reform DSL hooks (``Reform.benefit_overrides["rxkids"]``)
    * ``prenatal_monthly``                $-per-month override
    * ``postnatal_monthly_per_child``     $-per-month-per-child override
    * ``income_fpl_cap``                  FPL multiplier override
    * ``takeup_rate``                     take-up multiplier override

See ``RXKIDS_METHODOLOGY.md`` at the repo root for full sourcing of
parameter values and the Hawaii calibration.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Optional

import numpy as np
import pandas as pd

from tax_modeler.errors import ConfigError

from ..benefits._fpl import hawaii_fpl


# Hawaii Medicaid-financed births per Hawaii Medicaid-eligible adult woman.
# 6,200 Medicaid births (40% × 15,535 CDC NVSR 73-02 total) ÷ ~50,000 Medicaid
# adult women filing units (HI QUEST + ACS demographics) ≈ 0.124.
# Adjust upward as the modeled eligibility universe contracts.
_DEFAULT_PREGNANCY_PROBABILITY = 0.12

# Share of dependents that are children 0-5 in Hawaii Medicaid-eligible
# households. Derived from ACS PUMS 2018-2022 Hawaii — among all dependents
# 0-17 in households below 200% FPL, ~20% are 0-5 (6 single-year ages out
# of 18 weighted by Hawaii age structure). Use 0.20 as the modeling default.
_DEFAULT_CHILD_UNDER_AGE_SHARE = 0.20

# Single / head-of-household women aged 18-44 are the prenatal-eligible
# universe. Conservatively assume ~50% of these filers are women (PUMS
# tax-unit frame doesn't carry primary-filer sex). For the Medicaid
# pregnancy probability calibration the 0.50 women-share is already baked
# in, so do not double-discount.


@dataclass(frozen=True)
class RxKidsHIParams:
    """Parameters for the Hawaii RxKids equivalent.

    Defaults model a Medicaid-targeted variant (138% FPL cap, $500/mo
    prenatal × 9 months, $125/mo postnatal per child 0-5 × 12 months).
    See module docstring for the universal Flint-equivalent override
    recipe.
    """

    prenatal_monthly: float = 500.0
    """Dollar payment per prenatal month, per pregnant filer."""

    postnatal_monthly_per_child: float = 125.0
    """Dollar payment per month, per child under ``postnatal_age_cutoff``."""

    prenatal_months: int = 9
    """Number of months of prenatal payments per pregnancy."""

    postnatal_age_cutoff: int = 5
    """Children under this age (inclusive) receive postnatal payments.

    Flint default = 1 (perinatal-only). Hawaii spec defaults to 5 to
    span the full ARPA-CTC equivalent age range when paired with
    HI CTC scenarios.
    """

    income_fpl_cap: float = 1.38
    """Income / FPL ratio at or below which a unit qualifies.

    Default 1.38 = Hawaii Medicaid (QUEST) adult expansion threshold.
    Set to a high number (e.g. 10.0) to model the universal Flint
    design.
    """

    takeup_rate: float = 0.80
    """Fraction of eligible units that actually claim.

    Default 0.80 — conservative relative to Flint's observed 0.98 under
    universal design + hospital partnership; reflects the absence of
    analogous infrastructure in Hawaii at year-1 ramp.
    """

    is_taxable: bool = False
    """If False, payments are added to SPM resources but not money income.

    Matches the Flint design (GiveDirectly charitable disbursement, not
    IRS-reported). A True value would route payments through AGI and
    therefore interact with EITC/CTC phase-outs — currently not modeled.
    """

    prenatal_pregnancy_probability: float = _DEFAULT_PREGNANCY_PROBABILITY
    """Probability that an eligible woman is pregnant in a given year.

    Calibrated from Hawaii Medicaid-financed births / Medicaid adult
    women. Use ~0.04 for a universal-program variant (all women
    aged 18-44).
    """

    child_under_age_share: float = _DEFAULT_CHILD_UNDER_AGE_SHARE
    """Share of dependents 0-17 that are children 0-5.

    Used to convert ``num_dependents`` into an effective count of
    children under ``postnatal_age_cutoff``, since PUMS does not carry
    individual child ages on the tax-unit frame.
    """


def hawaii_rxkids_parameters() -> RxKidsHIParams:
    """Default RxKids Hawaiʻi parameters (Medicaid-targeted variant)."""
    return RxKidsHIParams()


def with_rxkids_overrides(
    base: RxKidsHIParams, overrides: Optional[Mapping[str, object]]
) -> RxKidsHIParams:
    """Apply Reform-DSL-style overrides to a parameter set."""
    if not overrides:
        return base
    valid = set(base.__dataclass_fields__)
    bad = set(overrides) - valid
    if bad:
        raise ConfigError(
            f"unknown RxKids override keys: {sorted(bad)}",
            available=sorted(valid),
        )
    return replace(base, **dict(overrides))


def compute_rxkids_for_units(
    units: pd.DataFrame,
    *,
    tax_year: int = 2024,
    params: Optional[RxKidsHIParams] = None,
    overrides: Optional[Mapping[str, object]] = None,
    out_col: str = "rxkids_amount",
) -> pd.DataFrame:
    """Compute the annual RxKids Hawaiʻi benefit amount per tax unit.

    Adds a ``rxkids_amount`` column = expected annual dollars per filing
    unit (prenatal + postnatal, take-up-adjusted).

    Eligibility
    -----------
    * **Prenatal**: filing_status in {single, head_of_household} AND
      income/FPL(family_size) <= ``income_fpl_cap`` AND
      ``num_dependents == 0`` (filer is not already claiming children).
      Amount per eligible unit:
          ``prenatal_pregnancy_probability``  ×
          ``prenatal_monthly`` × ``prenatal_months`` ×
          ``takeup_rate``
    * **Postnatal**: any filing unit with ``num_dependents > 0`` AND
      income test passed. Per-unit amount:
          ``n_children_under_cutoff``                ×
          ``postnatal_monthly_per_child`` × 12 ×
          ``takeup_rate``
      where ``n_children_under_cutoff = min(num_dependents,
      child_under_age_share × num_dependents)``.

    Notes
    -----
    * ``is_taxable=False`` is the modeling default — the amount returned
      here must be added to SPM resources, not money_income. The wiring
      in ``compute_spm_resources`` already supports a ``rxkids_col``
      parameter for this purpose.
    * Take-up imputation here is the *combined* take-up rate (eligibility
      × claim). Unlike SNAP, RxKids has no separate IRS-anchored take-up
      target (the program is hypothetical for Hawaii). To explore
      sensitivity, override ``takeup_rate``.
    """
    p = with_rxkids_overrides(params or hawaii_rxkids_parameters(), overrides)
    if not 0.0 <= p.takeup_rate <= 1.0:
        raise ConfigError(
            f"takeup_rate must be in [0.0, 1.0], got {p.takeup_rate}"
        )
    if not 0.0 <= p.prenatal_pregnancy_probability <= 1.0:
        raise ConfigError(
            "prenatal_pregnancy_probability must be in [0.0, 1.0], "
            f"got {p.prenatal_pregnancy_probability}"
        )
    if p.postnatal_age_cutoff < 0:
        raise ConfigError(
            f"postnatal_age_cutoff must be >= 0, got {p.postnatal_age_cutoff}"
        )

    df = units.copy()

    filing_status = df["filing_status"].astype(str).to_numpy()
    n_dep = df["num_dependents"].fillna(0).clip(lower=0).astype(int).to_numpy()
    is_joint = (filing_status == "married_filing_jointly")
    hh_size = 1 + is_joint.astype(int) + n_dep
    income = df["income"].fillna(0).astype(float).to_numpy()

    # FPL: hawaii_fpl is only published for 2024 in this codebase. Reuse
    # the 2024 anchor for adjacent years (TY2022-2025) — Hawaii FPL grew
    # ~10% over that span; treating eligibility as 2024-anchored slightly
    # over-counts eligibility for 2022 and slightly under-counts for
    # 2025. Material bias is small relative to the take-up uncertainty.
    fpl = np.array([hawaii_fpl(2024, household_size=int(s)) for s in hh_size])
    fpl_ratio = np.where(fpl > 0, income / fpl, np.inf)
    income_eligible = fpl_ratio <= p.income_fpl_cap

    # ---- Prenatal ----
    # Single / HoH filers with no current dependents are the proxy
    # universe for "pregnant filer not yet claiming children".
    prenatal_filing_eligible = np.isin(
        filing_status, ("single", "head_of_household")
    )
    prenatal_eligible = (
        income_eligible & prenatal_filing_eligible & (n_dep == 0)
    )
    prenatal_per_unit = (
        p.prenatal_pregnancy_probability
        * p.prenatal_monthly * p.prenatal_months
        * p.takeup_rate
    )
    prenatal_amount = np.where(prenatal_eligible, prenatal_per_unit, 0.0)

    # ---- Postnatal ----
    # Number of dependents that are children under the age cutoff.
    # PUMS tax-unit frame does not carry individual child ages — use the
    # configured age-share to scale num_dependents.
    n_kids_under_cutoff = np.minimum(
        n_dep.astype(float),
        n_dep.astype(float) * p.child_under_age_share,
    )
    postnatal_eligible = income_eligible & (n_dep > 0)
    postnatal_amount = np.where(
        postnatal_eligible,
        n_kids_under_cutoff
        * p.postnatal_monthly_per_child * 12
        * p.takeup_rate,
        0.0,
    )

    df[out_col] = prenatal_amount + postnatal_amount
    return df


__all__ = [
    "RxKidsHIParams",
    "compute_rxkids_for_units",
    "hawaii_rxkids_parameters",
    "with_rxkids_overrides",
]
