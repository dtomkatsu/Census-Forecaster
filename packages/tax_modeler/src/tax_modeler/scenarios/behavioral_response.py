"""Behavioral response module for SB 3125 CD1's new 13% top bracket.

Static-scoring forecasts overstate the revenue gain from a top-bracket rate
hike because high earners respond on multiple margins:

  1. **Taxable-income elasticity (ETI)** — They shift compensation
     (deferred comp, fringe benefits), realize fewer capital gains
     ("lock-in"), restructure pass-through income, and shelter via
     deductions / charitable giving. Standard ETI for top earners
     ranges 0.20-0.50 (Saez/Slemrod/Giertz 2012; Hawaii has limited
     state-level evidence).

  2. **Migration / domicile change** — They move to states with lower
     or no income tax. Hawaii has the worst net out-migration of high
     earners in the country (IRS SOI migration data). Young & Varner
     (2011) estimate top-1% migration elasticity ≈ 0.10-0.15 per
     percentage-point top-rate increase, with effects concentrated
     among the very highest earners and growing over time.

  3. **Pass-through entity (PTE) election** — Hawaii's PTE election
     under HRS §235-110.93 lets pass-through businesses pay Hawaii
     tax at the entity level (currently 11%, the top individual
     rate) and SALT-deduct it federally. SB 3125 CD1's 13% individual
     rate creates a 2pp incentive to shift income through PTE. Most
     S-corps and partnerships with $1M+ owners would elect.

This module applies these three responses on top of the static
microsimulation. They reduce the bracket-revenue estimate by an amount
that scales with: (a) the size of the marginal rate change, (b) the
income above the new threshold, and (c) the chosen elasticity values.

Three scenarios bracket the literature:
    LOW       — eti=0.15, migration_elast=0.05, pte_capture=0.20  (modest)
    MID       — eti=0.25, migration_elast=0.10, pte_capture=0.35  (default)
    HIGH      — eti=0.40, migration_elast=0.15, pte_capture=0.50  (aggressive)

References:
  - Saez, Slemrod, Giertz (2012) "The Elasticity of Taxable Income with
    Respect to Marginal Tax Rates" J. Econ. Lit.
  - Young, Varner, Lurie, Prisinzano (2016) "Millionaire Migration and
    Taxation of the Elite" American Sociological Review.
  - Cohen, Lai, Steindel (2014) "State income taxes and team performance"
    NJ Treasury working paper on millionaire migration.
  - Hawaii DOTAX "Tax Credits Claimed by Hawai`i Taxpayers — Tax Year
    2023" (Dec 2025) for PTE base.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bill parameters
# ---------------------------------------------------------------------------
# SB 3125 CD1 new top bracket thresholds (taxable income)
SB3125_TOP_THRESHOLDS = {
    "married_filing_jointly":      1_000_000,
    "qualifying_widow":            1_000_000,
    "head_of_household":             750_000,
    "single":                        500_000,
    "married_filing_separately":     500_000,
}
# Top marginal rate under each system
ACT46_TOP_RATE = 0.11      # current top rate under Act 46
SB3125_CD1_TOP_RATE = 0.13 # new top rate under bill

# Hawaii PTE election rate (HRS §235-110.93). Currently 11% (the top
# individual rate); the PTE election was pegged to the top individual
# bracket so it tracks Act 46. SB 3125 CD1 does NOT amend §235-110.93,
# so PTE rate stays at 11% even when individual top hits 13%.
PTE_RATE = 0.11


# ---------------------------------------------------------------------------
# Behavioral parameter scenarios
# ---------------------------------------------------------------------------
@dataclass
class BehavioralParams:
    """Behavioral elasticity parameters."""
    eti: float                 # Taxable income elasticity (Saez/Slemrod/Giertz range: 0.15-0.50)
    migration_elast: float     # Top-1% migration elasticity per pp rate change (Young/Varner: 0.05-0.15)
    pte_capture: float         # Share of $1M+ pass-through income that elects PTE under bill
    migration_phase_in_years: int = 5  # Years to fully realize migration response

    @classmethod
    def low(cls) -> "BehavioralParams":
        return cls(eti=0.15, migration_elast=0.05, pte_capture=0.20)

    @classmethod
    def mid(cls) -> "BehavioralParams":
        return cls(eti=0.25, migration_elast=0.10, pte_capture=0.35)

    @classmethod
    def high(cls) -> "BehavioralParams":
        return cls(eti=0.40, migration_elast=0.15, pte_capture=0.50)

    @classmethod
    def static(cls) -> "BehavioralParams":
        """All zeros — replicates the original static-scoring estimate."""
        return cls(eti=0.0, migration_elast=0.0, pte_capture=0.0)

    @classmethod
    def named(cls, name: str) -> "BehavioralParams":
        m = {"low": cls.low, "mid": cls.mid, "high": cls.high, "static": cls.static}
        if name not in m:
            raise ValueError(f"Unknown behavioral scenario {name!r}; "
                             f"valid: {list(m.keys())}")
        return m[name]()


# ---------------------------------------------------------------------------
# ETI: taxable-income response to marginal rate change
# ---------------------------------------------------------------------------

def _income_response_factor(
    baseline_mtr: float, scenario_mtr: float, eti: float
) -> float:
    """Return the multiplicative income adjustment for an ETI response.

    Standard form: %ΔTI = ETI × %Δ(1-MTR)
        new_TI / old_TI = ((1 - scenario_mtr) / (1 - baseline_mtr)) ** eti

    For a rate increase (scenario_mtr > baseline_mtr), this is < 1.
    """
    if baseline_mtr >= 1.0 or scenario_mtr >= 1.0:
        return 1.0
    return ((1.0 - scenario_mtr) / (1.0 - baseline_mtr)) ** eti


def apply_eti_response(
    df: pd.DataFrame,
    params: BehavioralParams,
    *,
    income_col: str = "income",
    fs_col: str = "filing_status",
    inplace: bool = False,
) -> pd.DataFrame:
    """Reduce incomes of filers above the new 13% threshold per ETI.

    Only the *marginal* income above the threshold gets the rate change
    11% → 13% — but standard ETI literature applies the response to
    the entire taxable income of the filer (since they re-optimize
    overall labor supply / shelter use). We follow the literature and
    apply the factor to total income for filers above threshold.

    For filers below threshold under both systems, no response.
    """
    if params.eti <= 0:
        return df if inplace else df.copy()

    out = df if inplace else df.copy()
    out[income_col] = out[income_col].astype(float)
    out["_eti_factor"] = 1.0

    for fs, threshold in SB3125_TOP_THRESHOLDS.items():
        mask = (out[fs_col] == fs) & (out[income_col] > threshold)
        if not mask.any():
            continue
        # Marginal rate moved from ACT46_TOP_RATE to SB3125_CD1_TOP_RATE
        # for the portion above the threshold. ETI literature treats
        # the response as proportional to the change in the marginal
        # net-of-tax rate at the filer's top dollar.
        factor = _income_response_factor(
            ACT46_TOP_RATE, SB3125_CD1_TOP_RATE, params.eti
        )
        out.loc[mask, income_col] = out.loc[mask, income_col] * factor
        out.loc[mask, "_eti_factor"] = factor

    return out


# ---------------------------------------------------------------------------
# Migration: weight-reduction for top filers leaving Hawaii
# ---------------------------------------------------------------------------

def apply_migration_response(
    df: pd.DataFrame,
    params: BehavioralParams,
    *,
    target_year: int,
    bill_effective_year: int = 2027,
    income_col: str = "income",
    fs_col: str = "filing_status",
    weight_col: str = "weight",
    inplace: bool = False,
) -> pd.DataFrame:
    """Reduce weights of $1M+ filers per migration elasticity, phased in.

    The Young & Varner migration elasticity is per percentage-point top-rate
    change. SB 3125 CD1 raises the top from 11% to 13% (2pp), so the long-run
    out-migration share is 2 × migration_elast. We phase this in linearly
    over `migration_phase_in_years` from `bill_effective_year`.

    Migration applies to filers above the *MFJ* threshold ($1M) since
    that's where the literature's top-1% estimates apply. Lower thresholds
    (HoH $750K, Single $500K) mostly capture upper-middle earners with
    weaker migration response — we apply a discounted rate (50%) for
    those between the lower threshold and $1M.
    """
    if params.migration_elast <= 0:
        return df if inplace else df.copy()

    out = df if inplace else df.copy()
    out[weight_col] = out[weight_col].astype(float)
    out["_migration_factor"] = 1.0

    rate_change_pp = (SB3125_CD1_TOP_RATE - ACT46_TOP_RATE) * 100.0  # 2.0
    long_run_loss = params.migration_elast * rate_change_pp           # e.g. 0.10 × 2.0 = 0.20

    # Phase-in: linear from year 1 of effect to year N
    years_since_effect = max(0, target_year - bill_effective_year)
    phase_frac = min(1.0, (years_since_effect + 1) / params.migration_phase_in_years)
    realised_loss = long_run_loss * phase_frac                        # e.g. 0.20 × 0.6 = 0.12

    # Top tier ($1M+): full migration loss
    mask_top = out[income_col] >= 1_000_000
    out.loc[mask_top, weight_col] = out.loc[mask_top, weight_col] * (1.0 - realised_loss)
    out.loc[mask_top, "_migration_factor"] = 1.0 - realised_loss

    # Upper tier ($500K-$1M MFJ etc): half the migration response
    upper_loss = realised_loss * 0.5
    for fs, threshold in SB3125_TOP_THRESHOLDS.items():
        if threshold >= 1_000_000:
            continue
        mask_upper = ((out[fs_col] == fs) & (out[income_col] >= threshold)
                      & (out[income_col] < 1_000_000))
        if not mask_upper.any():
            continue
        out.loc[mask_upper, weight_col] = (
            out.loc[mask_upper, weight_col] * (1.0 - upper_loss)
        )
        out.loc[mask_upper, "_migration_factor"] = 1.0 - upper_loss

    return out


# ---------------------------------------------------------------------------
# PTE election shift: revenue moves from individual to PTE form
# ---------------------------------------------------------------------------

def estimate_pte_election_shift_M(
    df: pd.DataFrame,
    params: BehavioralParams,
    *,
    income_col: str = "income",
    fs_col: str = "filing_status",
    weight_col: str = "weight",
) -> Dict[str, float]:
    """Estimate revenue *reduction* from PTE election under SB 3125 CD1.

    Mechanism: Pass-through owners with income above the new 13% threshold
    have a 2pp incentive (13% → 11%) to elect the PTE. We assume:

      - Share of $1M+ income that is pass-through-eligible: 40%
        (national IRS SOI 2022: pass-through is ~35-50% of top-1% income;
        Hawaii skews slightly lower due to wage-heavy economy)
      - Of eligible pass-through income, `pte_capture` share elects
      - Revenue lost = (captured income above threshold) × (13% - 11%)
        = captured income × 0.02

    Returns:
      pte_eligible_income_$M:    pass-through income above threshold (pre-election)
      pte_elected_income_$M:     income that actually elects ( × pte_capture)
      pte_revenue_loss_$M:       revenue moving from individual to PTE form
    """
    if params.pte_capture <= 0:
        return {
            "pte_eligible_income_$M": 0.0,
            "pte_elected_income_$M":  0.0,
            "pte_revenue_loss_$M":    0.0,
        }

    PASS_THROUGH_SHARE = 0.40  # national IRS SOI 2022 average for top 1%
    RATE_DIFFERENTIAL = SB3125_CD1_TOP_RATE - PTE_RATE  # 0.02

    excess_income_total = 0.0
    for fs, threshold in SB3125_TOP_THRESHOLDS.items():
        mask = (df[fs_col] == fs) & (df[income_col] > threshold)
        if not mask.any():
            continue
        excess = (df.loc[mask, income_col] - threshold) * df.loc[mask, weight_col]
        excess_income_total += float(excess.sum())

    pte_eligible = excess_income_total * PASS_THROUGH_SHARE
    pte_elected = pte_eligible * params.pte_capture
    pte_loss_dollars = pte_elected * RATE_DIFFERENTIAL

    return {
        "pte_eligible_income_$M": pte_eligible / 1e6,
        "pte_elected_income_$M":  pte_elected / 1e6,
        "pte_revenue_loss_$M":    pte_loss_dollars / 1e6,
    }


# ---------------------------------------------------------------------------
# Top-income growth premium
# ---------------------------------------------------------------------------
# B19013 (median household income) under-projects top-earner growth.
# US data 1979-2019 (Piketty-Saez-Zucman): top-1% real income grew
# ~2.3pp/yr faster than median; top-0.1% grew ~3.5pp/yr faster.
# Hawaii state-level data is thin, but we conservatively assume top
# incomes grow 1.5pp/yr faster than the median-anchored projection.
# This corrects a systematic under-projection of 13%-bracket revenue.
TOP_INCOME_PREMIUM_BASE_YEAR = 2023
TOP_INCOME_PREMIUM_THRESHOLD = 500_000   # apply above this AGI
TOP_INCOME_PREMIUM_RATE = 0.015          # 1.5pp/yr above median


def apply_top_income_growth_premium(
    df: pd.DataFrame,
    *,
    target_year: int,
    base_year: int = TOP_INCOME_PREMIUM_BASE_YEAR,
    annual_premium: float = TOP_INCOME_PREMIUM_RATE,
    threshold: float = TOP_INCOME_PREMIUM_THRESHOLD,
    income_col: str = "income",
    inplace: bool = False,
) -> pd.DataFrame:
    """Scale top-earner incomes by a compounding premium over median growth.

    The base projection uses county-level B19013 (median household income),
    which under-projects top earners. This function applies a separate
    multiplier to filers above ``threshold`` to reflect top-quintile / top-1%
    income growth differential.

    Multiplier = (1 + annual_premium) ** (target_year - base_year)
    For default 1.5pp/yr from 2023 to 2027: 1.015^4 = 1.061 (+6.1%)
    """
    if annual_premium <= 0 or target_year <= base_year:
        return df if inplace else df.copy()
    years = target_year - base_year
    multiplier = (1.0 + annual_premium) ** years
    out = df if inplace else df.copy()
    # Ensure income column accepts float multiplications without dtype-upcast errors
    out[income_col] = out[income_col].astype(float)
    mask = out[income_col] >= threshold
    out.loc[mask, income_col] = out.loc[mask, income_col] * multiplier
    out["_top_income_premium"] = 1.0
    out.loc[mask, "_top_income_premium"] = multiplier
    return out


# ---------------------------------------------------------------------------
# Combined behavioral response
# ---------------------------------------------------------------------------

def apply_behavioral_response(
    df: pd.DataFrame,
    params: BehavioralParams,
    *,
    target_year: int,
    bill_effective_year: int = 2027,
    income_col: str = "income",
    fs_col: str = "filing_status",
    weight_col: str = "weight",
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """Apply ETI + migration adjustments and report the PTE shift.

    Returns (adjusted_df, diagnostics_dict).

    The PTE shift is reported separately because it represents revenue
    that moves to a different tax base (the PTE entity-level tax), not
    revenue that disappears. The caller subtracts it from the bracket
    delta as a correction.
    """
    out = df.copy()
    out = apply_eti_response(out, params, income_col=income_col, fs_col=fs_col, inplace=True)
    out = apply_migration_response(
        out, params, target_year=target_year,
        bill_effective_year=bill_effective_year,
        income_col=income_col, fs_col=fs_col, weight_col=weight_col, inplace=True,
    )

    # PTE shift estimated on the post-ETI / post-migration income base
    # (so we don't double-count income that already left)
    pte = estimate_pte_election_shift_M(
        out, params, income_col=income_col, fs_col=fs_col, weight_col=weight_col,
    )

    # Report top-bracket diagnostics
    mask_top = out[income_col] >= 1_000_000
    diag = {
        "scenario_eti":              params.eti,
        "scenario_migration_elast":  params.migration_elast,
        "scenario_pte_capture":      params.pte_capture,
        "filers_1m_post_response":   float(out.loc[mask_top, weight_col].sum()),
        "income_1m_post_response_$M": float(
            (out.loc[mask_top, income_col] * out.loc[mask_top, weight_col]).sum()
        ) / 1e6,
        **pte,
    }
    return out, diag
