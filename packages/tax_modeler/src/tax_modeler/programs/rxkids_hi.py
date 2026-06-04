"""RxKids Hawaiʻi — modeled prenatal + infant cash prescription program.

Hawaii-equivalent of the RxKids program operating in Flint MI and 35+
other Michigan communities (administered by Michigan State University +
GiveDirectly, launched Jan 2024). RxKids provides unrestricted cash
"prescribed" during pregnancy and the postnatal period, structured as
charitable disbursement (not taxable income, no SNAP/Medicaid offset).

This module evaluates a Hawaii-targeted variant adapted to local cost
of living and Hawaii's existing Medicaid (QUEST Integration) eligibility
framework. The default parameters model the **statutory** eligibility:
a unit qualifies if it satisfies EITHER of two clauses (see "Eligibility"
below). This is a substantially broader gate than a Medicaid-only design
and sits between the Medicaid-targeted (~$8-15M) and fully-universal
(~$110M) cost poles described in RXKIDS_METHODOLOGY.md.

Program scope
-------------

Eligibility (statutory — clause 1 OR clause 2)
    * **Clause 1 — Medicaid.** Any unit whose member qualifies for
      benefits under the State's Medicaid (Med-QUEST) program. Reuses the
      ``medicaid_receives`` boolean from
      ``tax_modeler.benefits.compute_medicaid_for_units``; the caller
      pre-attaches that column. (If absent, the module falls back to
      clause 2 only and warns.)
    * **Clause 2 — 300% FPL.** Family income ≤ 300% FPL for a family of
      applicable size *including the expected unborn child(ren)*. The
      unborn increment (``prenatal_unborn_count``, default +1) raises the
      FPL family size — and therefore the dollar threshold — for the
      prenatal arm ONLY. The postnatal arm uses the plain family size.
    * Prenatal arm: ``single`` / ``head_of_household`` filers with
      ``num_dependents == 0`` (filer is "expecting", not yet a parent of
      record). Because PUMS does not observe pregnancy, we apply
      ``prenatal_pregnancy_probability`` per eligible filer.
    * Postnatal arm: units with ``num_dependents > 0``. Because individual
      child ages are not on the tax-unit frame, ``child_under_age_share``
      converts ``num_dependents`` into an effective count of children
      under ``postnatal_age_cutoff``.

Payment structure (defaults below; override for alternative designs)
    * Prenatal: ``prenatal_monthly`` × ``prenatal_months``
      (default $1,500 × 1 = $1,500 per pregnancy)
    * Postnatal: ``postnatal_monthly_per_child`` × ``n_children`` ×
      ``postnatal_months`` (default $500/mo × eligible kids × 6 = $3,000)
    * Take-up: ``takeup_rate`` (default 0.80; Flint observed 0.98 under
      universal design + hospital partnership — Hawaii conservatively
      models 0.80 in absence of analogous infrastructure)

Tax treatment
    * ``is_taxable = False`` (default). Flint program is structured as
      charitable disbursement (GiveDirectly), so payments do not flow
      through AGI / EITC / CTC interactions. Modeled by adding the
      ``rxkids_amount`` column to SPM resources only — NOT to
      ``total_cash_income``. See ``compute_spm_resources`` wiring.

Outputs
    * ``rxkids_amount`` — combined expected annual benefit per unit.
    * ``rxkids_prenatal_amount`` / ``rxkids_postnatal_amount`` — the two
      arm subtotals, for splitting program outlay in the cost report.

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
  payments rely on ``child_under_age_share`` (default 0.066 = Hawaii
  annual births ÷ dependents 0-17). This is the annual birth FLOW per
  dependent, matched to the full per-birth postnatal entitlement.
  Sensitivity: linear in this share.
* The Flint RxKids program is universal (no income/Medicaid test). The
  default parameters here model a Medicaid-eligibility-gated variant
  for cost reasons. Override ``income_fpl_cap`` to a high value to
  model the universal variant.
* Modeled as non-taxable charitable cash. If the Hawaii legislature
  structured a similar program differently (e.g. as a refundable tax
  credit), the resource-accounting treatment would need to change.

Reform DSL hooks (``Reform.benefit_overrides["rxkids"]``)
    * ``prenatal_monthly``                $-per-payment override (one-time)
    * ``prenatal_months``                 number of prenatal payments (1 = one-time)
    * ``postnatal_monthly_per_child``     $-per-month-per-child override
    * ``postnatal_months``                number of postnatal monthly payments
    * ``income_fpl_cap``                  FPL multiplier override (10.0 = universal)
    * ``takeup_rate``                     take-up rate override

See ``RXKIDS_METHODOLOGY.md`` at the repo root for full sourcing of
parameter values and the Hawaii calibration.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Mapping, Optional

import numpy as np
import pandas as pd

from tax_modeler.errors import ConfigError

from ..benefits._fpl import fpl_year_for, hawaii_fpl

LOG = logging.getLogger(__name__)


# All-Hawaii birth rate among single/HoH filers with no dependents.
# 15,535 total births (CDC NVSR 73-02) ÷ ~155,000 single+HoH filers with
# no current dependents (ACS PUMS Hawaii) × 50% women-share ≈ 0.10.
# Used for the universal (unconditional) variant where all expectant
# mothers are eligible regardless of income.
_DEFAULT_PREGNANCY_PROBABILITY = 0.10

# Annual qualifying-birth rate per dependent (FLOW, not a point-in-time
# stock). The postnatal payment is the full per-birth entitlement
# (postnatal_monthly_per_child × postnatal_months, e.g. $500 × 6 = $3,000),
# so the correct annual-cost basis is the full annual birth cohort, not the
# <6-month snapshot. Using a half-year stock here would understate the
# postnatal arm by ~2× (see RXKIDS_METHODOLOGY.md §3).
#   Hawaii annual births 15,535 (CDC NVSR 73-02)
#   ÷ ACS PUMS Hawaii dependents 0-17 ≈ 233,000 (5-yr sample)
#   ≈ 0.066.
# Interpretation: n_dep × this rate ≈ the family's expected qualifying
# births this year; summed over the population it recovers total births.
_DEFAULT_CHILD_UNDER_AGE_SHARE = 0.066

# Single / head-of-household women aged 18-44 are the prenatal-eligible
# universe. Conservatively assume ~50% of these filers are women (PUMS
# tax-unit frame doesn't carry primary-filer sex). The 0.50 women-share
# is already baked into _DEFAULT_PREGNANCY_PROBABILITY above.


@dataclass(frozen=True)
class RxKidsHIParams:
    """Parameters for the Hawaii RxKids equivalent.

    Defaults model the statutory eligibility (Medicaid OR ≤300% FPL incl.
    unborn child) with this payment design:
      * Prenatal: one-time $1,500 payment per pregnancy.
      * Postnatal: $500/month for 6 months beginning at birth ($3,000 total
        per child).

    Eligibility is set by ``income_fpl_cap`` (default 3.00 = 300% FPL) plus
    the Medicaid clause evaluated in ``compute_rxkids_for_units``. Set
    ``income_fpl_cap=1.38`` for a Medicaid-adult-expansion-only income test,
    or a high value (e.g. 10.0) for an effectively-universal variant.
    """

    prenatal_monthly: float = 1500.0
    """Dollar payment per prenatal month, per pregnant filer."""

    postnatal_monthly_per_child: float = 500.0
    """Dollar payment per month, per child under ``postnatal_age_cutoff``."""

    prenatal_months: int = 1
    """Number of months of prenatal payments per pregnancy (1 = one-time)."""

    postnatal_months: int = 6
    """Number of months of postnatal payments per eligible child."""

    postnatal_age_cutoff: int = 1
    """Children under this age (years) receive postnatal payments.

    Default 1 = infants in their first year of life, approximating the
    0–6-month window. PUMS does not carry sub-year ages, so age=0 is
    the closest proxy.
    """

    income_fpl_cap: float = 3.00
    """Income / FPL ratio at or below which a unit qualifies (clause 2).

    Default 3.00 = the statutory 300% FPL income test. A unit also
    qualifies via clause 1 (Medicaid receipt) regardless of this cap;
    see ``compute_rxkids_for_units``. Set higher (e.g. 10.0) to model an
    effectively-universal income variant, or to 1.38 for a Medicaid-
    adult-expansion-only income test.
    """

    prenatal_unborn_count: int = 1
    """Expected unborn children added to family size for the prenatal test.

    The statute sizes the family "including the expected unborn child or
    children." For the prenatal arm only, the FPL family size is
    incremented by this count (default 1), raising the dollar threshold
    and expanding eligibility for expectant filers. The postnatal arm
    leaves family size unchanged (the child is already in num_dependents).
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
    """Annual qualifying-birth rate per dependent (a FLOW, default 0.066).

    Converts ``num_dependents`` into the family's expected number of
    qualifying births this year, since PUMS does not carry individual
    child ages on the tax-unit frame. Because the postnatal payment is the
    full per-birth entitlement (``postnatal_monthly_per_child`` ×
    ``postnatal_months``), this must be the full annual birth cohort per
    dependent (≈ births ÷ dependents 0-17), NOT a <6-month stock share —
    otherwise the postnatal arm is understated ~2×. Sensitivity: linear.
    """


def hawaii_rxkids_parameters() -> RxKidsHIParams:
    """Default RxKids Hawaiʻi parameters (statutory eligibility variant)."""
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
    medicaid_col: str = "medicaid_receives",
    family_income_col: Optional[str] = None,
    family_size_col: Optional[str] = None,
) -> pd.DataFrame:
    """Compute the annual RxKids Hawaiʻi benefit amount per tax unit.

    Adds ``rxkids_amount`` (= prenatal + postnatal, take-up-adjusted) plus
    the two arm subtotals ``rxkids_prenatal_amount`` and
    ``rxkids_postnatal_amount`` (derived from ``out_col``'s stem).

    Statutory eligibility (clause 1 OR clause 2)
    --------------------------------------------
    * **Clause 1 — Medicaid**: ``medicaid_col`` (default
      ``"medicaid_receives"``) is True. The caller must pre-attach this
      column via ``tax_modeler.benefits.compute_medicaid_for_units``; if it
      is missing the function falls back to clause 2 only and logs a
      warning.
    * **Clause 2 — 300% FPL**: ``income / FPL(applicable_size) <=
      income_fpl_cap`` (default 3.00). For the prenatal arm the applicable
      family size includes the expected unborn child(ren)
      (``prenatal_unborn_count``, default +1); the postnatal arm uses the
      plain family size. ``tax_year`` selects the FPL table.

    Arms
    ----
    * **Prenatal**: filing_status in {single, head_of_household} AND
      ``num_dependents == 0`` AND (clause 1 OR clause 2 at prenatal size).
      Amount = ``prenatal_pregnancy_probability × prenatal_monthly ×
      prenatal_months × takeup_rate``.
    * **Postnatal**: ``num_dependents > 0`` AND (clause 1 OR clause 2 at
      postnatal size). Amount = ``n_children_under_cutoff ×
      postnatal_monthly_per_child × postnatal_months × takeup_rate`` where
      ``n_children_under_cutoff = child_under_age_share × num_dependents``.

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

    # Income/size basis for the FPL test. The statute uses *family* income for
    # a *family* of applicable size. If the caller supplies family-grain columns
    # (income and persons summed across the tax units that share a household /
    # SPM unit), use those — testing per tax unit at tax-unit size would split a
    # household's income across small units and overstate eligibility. Falls
    # back to tax-unit grain when the columns are absent.
    if (
        family_income_col is not None and family_size_col is not None
        and family_income_col in df.columns and family_size_col in df.columns
    ):
        test_income = df[family_income_col].fillna(0).astype(float).to_numpy()
        base_size = df[family_size_col].fillna(0).clip(lower=1).astype(int).to_numpy()
    else:
        test_income = income
        base_size = hh_size

    # ---- Clause 1: Medicaid receipt ----
    # The statute makes anyone who "qualifies for benefits under the
    # State's Medicaid program" eligible, independent of the 300% FPL
    # income test. We reuse the medicaid_receives boolean produced by
    # tax_modeler.benefits.compute_medicaid_for_units; the caller must
    # pre-attach it (keeps this hypothetical-program module decoupled
    # from the benefits assembly). If it is absent we fall back to the
    # income test alone and warn.
    if medicaid_col in df.columns:
        medicaid_eligible = df[medicaid_col].fillna(False).to_numpy(dtype=bool)
    else:
        LOG.warning(
            "compute_rxkids_for_units: %r column not found; applying the "
            "300%% FPL income test only (clause 2). Run "
            "compute_medicaid_for_units(units) first to honor the Medicaid "
            "eligibility clause.",
            medicaid_col,
        )
        medicaid_eligible = np.zeros(len(df), dtype=bool)

    # ---- Clause 2: 300% FPL income test ----
    # The family is sized "including the expected unborn child(ren)" for
    # the prenatal arm only — a larger family size raises the FPL dollar
    # threshold and expands eligibility for expectant filers. The
    # postnatal arm uses the plain family size (the child is already
    # counted in num_dependents). Hence two separate FPL ratios. The
    # run's tax_year selects the FPL table so forward-projected incomes
    # are tested against same-year thresholds.
    postnatal_size = base_size
    prenatal_size = base_size + max(0, int(p.prenatal_unborn_count))

    fpl_yr = fpl_year_for(tax_year)
    fpl_postnatal = np.array(
        [hawaii_fpl(fpl_yr, household_size=int(s)) for s in postnatal_size]
    )
    fpl_prenatal = np.array(
        [hawaii_fpl(fpl_yr, household_size=int(s)) for s in prenatal_size]
    )
    income_eligible_postnatal = (
        np.where(fpl_postnatal > 0, test_income / fpl_postnatal, np.inf)
        <= p.income_fpl_cap
    )
    income_eligible_prenatal = (
        np.where(fpl_prenatal > 0, test_income / fpl_prenatal, np.inf)
        <= p.income_fpl_cap
    )

    # ---- Prenatal ----
    # Single / HoH filers with no current dependents are the proxy
    # universe for "pregnant filer not yet claiming children". Eligible
    # via Medicaid (clause 1) OR the 300% FPL test sized with the unborn
    # child (clause 2).
    prenatal_filing_eligible = np.isin(
        filing_status, ("single", "head_of_household")
    )
    prenatal_eligible = (
        prenatal_filing_eligible
        & (n_dep == 0)
        & (medicaid_eligible | income_eligible_prenatal)
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
    # configured age-share to scale num_dependents. Eligible via Medicaid
    # (clause 1) OR the 300% FPL test (clause 2).
    n_kids_under_cutoff = np.minimum(
        n_dep.astype(float),
        n_dep.astype(float) * p.child_under_age_share,
    )
    postnatal_eligible = (medicaid_eligible | income_eligible_postnatal) & (n_dep > 0)
    postnatal_amount = np.where(
        postnatal_eligible,
        n_kids_under_cutoff
        * p.postnatal_monthly_per_child * p.postnatal_months
        * p.takeup_rate,
        0.0,
    )

    # Emit prenatal / postnatal subtotals alongside the combined amount so
    # the fiscal-cost report can split program outlay by arm.
    stem = out_col[:-len("_amount")] if out_col.endswith("_amount") else out_col
    df[f"{stem}_prenatal_amount"] = prenatal_amount
    df[f"{stem}_postnatal_amount"] = postnatal_amount
    df[out_col] = prenatal_amount + postnatal_amount
    return df


__all__ = [
    "RxKidsHIParams",
    "compute_rxkids_for_units",
    "hawaii_rxkids_parameters",
    "with_rxkids_overrides",
]
