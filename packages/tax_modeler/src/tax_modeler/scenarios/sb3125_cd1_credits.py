"""Static-scoring overlay for SB 3125 CD1 credit changes.

Three credit changes in the bill have material fiscal impact but are not
captured by the individual-income-tax microsimulation:

  1. §235-12.5 Renewable Energy Technologies Income Tax Credit
     - Capped at $40M aggregate per year for TY 2027-2030
     - Set to $0 from TY 2031 onward
     - Adds AGI eligibility limits ($175K single/HoH/MFS, $350K MFJ)
       Per §235-12.5(a) as amended: "$175,000 if filing as an individual,
       or $350,000 if filing jointly". HoH and MFS treated as "individual"
       (single category) per user direction.

  2. §235-110.7 Capital Goods Excise Tax Credit
     - Sunsets effective Dec 31, 2027 (applies TY 2028+)

  3. §235-110.91 Tax Credit for Research Activities (via Act 261 amendment)
     - Bill accelerates Part II of Act 261 from 1/1/2030 to 1/1/2029
     - Net effect: credit eliminated 1 year earlier (TY 2029 instead of 2030)
     - Bill impact = TY 2029 only; TY 2030+ baseline already has it sunset

DOTAX TY2023 baselines (in $M, from "Tax Credits Claimed by Hawai`i
Taxpayers — Tax Year 2023", Dec 2025):

  Renewable Energy Tax Credit (Table A-1, line 1854; A-5, line 2067):
    Total: $100.1M
    By taxpayer type:
      Individuals:   $58.3M  (subject to AGI limit)
      Corporations:  $38.6M  (NOT subject to AGI limit)
      Other (other):  $3.2M  (financial corp, fiduciaries, exempt orgs)
    Individual claims by AGI bin:
      <$10K:      $4.7M  (100% eligible — below threshold)
      $10-30K:    $2.5M  (100% eligible)
      $30-60K:    $3.1M  (100% eligible)
      $60-100K:   $5.8M  (100% eligible)
      $100-200K: $16.2M  (~97.2% eligible per PUMS — most below $175K)
      $200K+:    $26.0M  (~56.1% eligible per PUMS — MFJ at $200-350K still in)
    Eligibility shares derived from Hawaii calibrated tax units (cached at
    /tmp/tax_units_cache.parquet, weighted-filer counts).

  Capital Goods Excise Tax Credit (Table A-1, line 1862):
    Total: $34.6M

  Tax Credit for Research Activities (Table A-1, line 1857):
    Total: $7.0M  ($1.0M individuals + $6.0M corporations)

Growth assumption: Hawaii nominal income growth from
``get_hawaii_real_growth_factor(2023, year) * cpi_honolulu_factor``,
matching the methodology used for tax unit projections.

This overlay does NOT model:
  - Behavioral response to the cap (pro-rata allocation under §235-12.5(h)
    means filers have minimal incentive to time claims — appropriate to
    treat as static)
  - Carryover dynamics (carry-forwards from prior years post-cap)
  - Non-individual REEC claimants other than corporate (~$3.2M "other"
    treated as not subject to AGI limits but counted in cap)
"""
from __future__ import annotations

from typing import Dict
import logging

logger = logging.getLogger(__name__)

BASE_YEAR = 2023

# ---------------------------------------------------------------------------
# DOTAX TY2023 baselines (in $ millions)
# ---------------------------------------------------------------------------

# §235-12.5 Renewable Energy Tax Credit (REEC)
REEC_INDIVIDUAL_TOTAL_M = 58.293
REEC_CORPORATE_TOTAL_M  = 38.565
REEC_OTHER_TOTAL_M      =  3.217   # financial corp, fiduciaries, exempt orgs (not subject to AGI limit)
# Sanity: 58.293 + 38.565 + 3.217 = $100.075M, matches DOTAX Table A-1 line 1854.

# Individual REEC claims by AGI bin (DOTAX Table A-5, line 2067)
# Each entry: (bin_label, claim_$M, eligible_share_after_AGI_limit)
# Eligibility shares derived from Hawaii calibrated tax units (PUMS):
# fraction of weighted filers in each bin with AGI <= threshold
# ($175K single/HoH/MFS, $350K MFJ).
REEC_INDIVIDUAL_BY_AGI_BIN = [
    ("<$10K",        4.731, 1.000),
    ("$10K-$30K",    2.522, 1.000),
    ("$30K-$60K",    3.121, 1.000),
    ("$60K-$100K",   5.752, 1.000),
    ("$100K-$200K", 16.150, 0.972),
    ("$200K+",      26.018, 0.561),
]
# Sanity: sum of claims = $58.294M (matches REEC_INDIVIDUAL_TOTAL_M to rounding)

# §235-110.7 Capital Goods Excise Tax Credit (CGEC)
CGEC_TOTAL_M = 34.608

# §235-110.91 Tax Credit for Research Activities (TCRA)
TCRA_TOTAL_M = 7.034

# ---------------------------------------------------------------------------
# Bill provisions
# ---------------------------------------------------------------------------
REEC_CAP_2027_2030_M = 40.0
REEC_CAP_2031_PLUS_M =  0.0
CGEC_SUNSET_YEAR     = 2027   # Sunsets after Dec 31, 2027 -> applies TY 2028+
TCRA_BILL_REPEAL_YEAR = 2029  # Bill: Act 261 Part II takes effect 1/1/2029
TCRA_ACT46_REPEAL_YEAR = 2030 # Baseline (Act 46): repeal was 1/1/2030

# ---------------------------------------------------------------------------
# Growth factors
# ---------------------------------------------------------------------------


def _hawaii_nominal_growth(target_year: int) -> float:
    """Cumulative Hawaii nominal income growth from BASE_YEAR (2023) to target_year.

    nominal = real(B19013, CPI-deflated) * Honolulu CPI growth.

    Falls back to flat 4%/yr if the bundled forecast machinery is unavailable.
    """
    try:
        from tax_modeler.projection.income_forecast import (
            get_hawaii_real_growth_factor, _load_cpi_honolulu_series, _project_cpi,
        )
        real = get_hawaii_real_growth_factor(BASE_YEAR, target_year)
        if real is None:
            raise ValueError("real growth factor unavailable")
        cpi = _load_cpi_honolulu_series()
        cpi_factor = _project_cpi(cpi, target_year) / _project_cpi(cpi, BASE_YEAR)
        return real * cpi_factor
    except Exception as e:
        years = target_year - BASE_YEAR
        fallback = (1.04) ** years
        logger.warning(
            "Hawaii nominal growth unavailable (%s); falling back to 4%%/yr -> factor=%.4f",
            e, fallback,
        )
        return fallback


# ---------------------------------------------------------------------------
# Credit overlay
# ---------------------------------------------------------------------------


def _reec_eligible_individual_M() -> float:
    """REEC individual-side eligible demand (TY2023 $) after AGI limits.

    Sums DOTAX TY2023 individual claims weighted by per-bin AGI eligibility
    share (from PUMS). Assumes within-bin uniformity (filer-share ≈ dollar-share).
    """
    return sum(claim * elig for _, claim, elig in REEC_INDIVIDUAL_BY_AGI_BIN)


def _reec_baseline_M(target_year: int) -> Dict[str, float]:
    """REEC projected demand for target_year, with eligibility breakdown."""
    g = _hawaii_nominal_growth(target_year)
    individual_eligible_2023  = _reec_eligible_individual_M()
    individual_ineligible_2023 = REEC_INDIVIDUAL_TOTAL_M - individual_eligible_2023
    return {
        "growth":               g,
        "individual_eligible":  individual_eligible_2023 * g,
        "individual_ineligible": individual_ineligible_2023 * g,  # AGI-excluded
        "corporate":            REEC_CORPORATE_TOTAL_M * g,
        "other":                REEC_OTHER_TOTAL_M * g,
        "total_baseline":       (REEC_INDIVIDUAL_TOTAL_M + REEC_CORPORATE_TOTAL_M + REEC_OTHER_TOTAL_M) * g,
        "total_eligible":       (individual_eligible_2023 + REEC_CORPORATE_TOTAL_M + REEC_OTHER_TOTAL_M) * g,
    }


def compute_credit_overlay(target_year: int) -> Dict[str, float]:
    """Compute SB 3125 CD1 credit-cap fiscal impact for ``target_year``.

    Positive values = revenue gained by the State.

    Returns a dict with the breakdown described in the module docstring.
    """
    if target_year < BASE_YEAR:
        raise ValueError(f"target_year must be >= {BASE_YEAR}, got {target_year}")

    growth = _hawaii_nominal_growth(target_year)

    # ---- Renewable Energy Tax Credit ------------------------------------
    reec = _reec_baseline_M(target_year)
    if 2027 <= target_year <= 2030:
        # Cap binds on the eligible portion. Total revenue gain =
        # ineligible-by-AGI demand (filtered out entirely) +
        # excess of eligible demand over the cap.
        reec_after_bill = min(reec["total_eligible"], REEC_CAP_2027_2030_M)
    elif target_year >= 2031:
        reec_after_bill = REEC_CAP_2031_PLUS_M
    else:
        reec_after_bill = reec["total_baseline"]
    reec_savings = max(0.0, reec["total_baseline"] - reec_after_bill)

    # ---- Capital Goods Excise Tax Credit --------------------------------
    cgec_baseline = CGEC_TOTAL_M * growth
    cgec_savings = cgec_baseline if target_year > CGEC_SUNSET_YEAR else 0.0

    # ---- Research Activities Credit -------------------------------------
    tcra_baseline = TCRA_TOTAL_M * growth
    # Bill accelerates repeal by 1 year. Difference applies in TY 2029 only.
    if target_year == TCRA_BILL_REPEAL_YEAR:  # 2029: bill repeals, baseline keeps
        tcra_savings = tcra_baseline
    else:
        tcra_savings = 0.0   # 2027-2028: both keep; 2030+: both repealed

    total_credit_savings = reec_savings + cgec_savings + tcra_savings

    return {
        "growth_factor":         round(growth, 4),
        # REEC breakdown
        "reec_individual_eligible_$M":   round(reec["individual_eligible"], 2),
        "reec_individual_ineligible_$M": round(reec["individual_ineligible"], 2),
        "reec_corporate_$M":             round(reec["corporate"], 2),
        "reec_other_$M":                 round(reec["other"], 2),
        "reec_baseline_$M":              round(reec["total_baseline"], 2),
        "reec_eligible_$M":              round(reec["total_eligible"], 2),
        "reec_after_bill_$M":            round(reec_after_bill, 2),
        "reec_savings_$M":               round(reec_savings, 2),
        # CGEC
        "cgec_baseline_$M":              round(cgec_baseline, 2),
        "cgec_savings_$M":               round(cgec_savings, 2),
        # TCRA
        "tcra_baseline_$M":              round(tcra_baseline, 2),
        "tcra_savings_$M":               round(tcra_savings, 2),
        # Totals
        "total_credit_savings_$M":       round(total_credit_savings, 2),
    }
