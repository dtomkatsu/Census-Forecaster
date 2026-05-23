"""
SPM (Supplemental Poverty Measure) aggregation for Hawaii tax microsimulation.

Builds a simplified SPM poverty flag on a tax-unit DataFrame.

SPM threshold methodology
--------------------------
Federal SPM threshold (2022 base): 4-person renter ~$32,000
(Source: Census SPM Research File, 2022)

Family-size scaling:
  Single (1):     0.52 × $32,000 = $16,640
  Two-person (2): 0.68 × $32,000 = $21,760
  Three-person (3): 0.84 × $32,000 = $26,880
  Four-person (4):  $32,000  (reference)
  Five+ (n):        $32,000 × (1 + 0.15 × (n-4))

Hawaii RPP adjustment: BEA Honolulu All-items RPP 2022 = 113.093 (national=100)
→ factor = 1.131

Hawaii SPM threshold for 4-person (2022) = $32,000 × 1.131 = $36,192

Annual update: BLS CPI-U Honolulu (CUUSA426SA0) growth from 2022 base.
Data loaded from:
  packages/census_forecaster/src/census_forecaster/data/anchors/cpi_honolulu_allitems.json

SPM resources counted
---------------------
+ cash income            (income column)
+ EITC refundable        (eitc_amount when positive)
+ CTC refundable         (ctc_refundable column)
- federal tax            (federal_tax_effective column, if present)
- state tax              (hi_tax_liability column, if present)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

SPM_THRESHOLD_BASE_4PERSON_2022: int = 32_000  # Census SPM Research File (2022)
SPM_HI_RPP_2022: float = 1.131  # BEA Honolulu All-items RPP / 100

# Family-size scale factors (relative to 4-person reference)
_SIZE_SCALE: dict[int, float] = {
    1: 0.52,
    2: 0.68,
    3: 0.84,
    4: 1.00,
}

_CPI_BASE_YEAR: int = 2022
_CPI_BASE_VALUE: float = 308.358  # BLS CUUSA426SA0 H2 2022

# ---------------------------------------------------------------------------
# CPI data loader (lazy, cached at module level)
# ---------------------------------------------------------------------------

_CPI_DATA: Optional[dict[int, float]] = None


def _load_cpi_data() -> dict[int, float]:
    """Load Honolulu CPI-U data from the census_forecaster anchor file."""
    global _CPI_DATA
    if _CPI_DATA is not None:
        return _CPI_DATA

    # Resolve path relative to this file's location in the monorepo
    this_file = Path(__file__).resolve()
    # packages/tax_modeler/src/tax_modeler/poverty/spm_aggregation.py
    # -> go up to packages/, then into census_forecaster
    packages_dir = this_file.parents[4]  # packages/
    cpi_path = (
        packages_dir
        / "census_forecaster"
        / "src"
        / "census_forecaster"
        / "data"
        / "anchors"
        / "cpi_honolulu_allitems.json"
    )

    if cpi_path.exists():
        with open(cpi_path, "r") as f:
            raw = json.load(f)
        _CPI_DATA = {int(k): float(v) for k, v in raw["values_by_year"].items()}
    else:
        # Fallback: use only the known 2022 base — other years will use base
        _CPI_DATA = {_CPI_BASE_YEAR: _CPI_BASE_VALUE}

    return _CPI_DATA


def _cpi_adjustment_factor(year: int) -> float:
    """Return CPI ratio (target_year / 2022) for threshold inflation adjustment."""
    if year == _CPI_BASE_YEAR:
        return 1.0

    cpi_data = _load_cpi_data()
    base_cpi = cpi_data.get(_CPI_BASE_YEAR, _CPI_BASE_VALUE)
    target_cpi = cpi_data.get(year)

    if target_cpi is None:
        # Extrapolate from the nearest available year using last known value
        available_years = sorted(cpi_data.keys())
        if year > max(available_years):
            target_cpi = cpi_data[max(available_years)]
        else:
            target_cpi = cpi_data[min(available_years)]

    return target_cpi / base_cpi


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def compute_spm_resources(df: pd.DataFrame) -> pd.Series:
    """
    Compute SPM resources for each tax unit.

    SPM resources = cash income
                  + refundable EITC (eitc_amount if positive)
                  + refundable CTC  (ctc_refundable if present)
                  - federal income tax (federal_tax_effective if present)
                  - Hawaii state tax  (hi_tax_liability if present)

    Args:
        df: DataFrame of tax units. Expected columns:
            - income: float  (cash income)
            - eitc_amount: float  (optional; EITC credit, positive = refundable)
            - ctc_refundable: float  (optional)
            - federal_tax_effective: float  (optional; already-computed federal tax)
            - hi_tax_liability: float  (optional)

    Returns:
        pd.Series of SPM resource amounts (dollars), same index as df.
    """
    resources = df["income"].fillna(0.0).astype(float).copy()

    # Add refundable credits
    if "eitc_amount" in df.columns:
        eitc = df["eitc_amount"].fillna(0.0).astype(float)
        resources += eitc.clip(lower=0.0)

    if "ctc_refundable" in df.columns:
        resources += df["ctc_refundable"].fillna(0.0).astype(float).clip(lower=0.0)

    # Subtract taxes
    if "federal_tax_effective" in df.columns:
        resources -= df["federal_tax_effective"].fillna(0.0).astype(float).clip(lower=0.0)

    if "hi_tax_liability" in df.columns:
        resources -= df["hi_tax_liability"].fillna(0.0).astype(float).clip(lower=0.0)

    return resources


def compute_spm_threshold(num_people: pd.Series, year: int = 2022) -> pd.Series:
    """
    Compute the family-size- and year-adjusted Hawaii SPM threshold per tax unit.

    Threshold = SPM_THRESHOLD_BASE_4PERSON_2022
              × Hawaii_RPP_factor
              × family_size_scale(n)
              × CPI_adjustment(year)

    Args:
        num_people: pd.Series of integers (household/family size).
        year: Tax year for CPI inflation adjustment (default 2022).

    Returns:
        pd.Series of dollar thresholds, same index as num_people.
    """
    n = num_people.fillna(1).astype(int)

    # Vectorized size scale
    def _scale(size: int) -> float:
        if size <= 0:
            size = 1
        if size in _SIZE_SCALE:
            return _SIZE_SCALE[size]
        # Five or more: 1 + 0.15 × (n - 4)
        return 1.0 + 0.15 * (size - 4)

    size_scale = n.map(_scale)

    cpi_factor = _cpi_adjustment_factor(year)

    threshold = (
        SPM_THRESHOLD_BASE_4PERSON_2022
        * SPM_HI_RPP_2022
        * size_scale
        * cpi_factor
    )

    return threshold.rename("spm_threshold")


def flag_spm_poor(df: pd.DataFrame, year: int = 2022) -> pd.Series:
    """
    Return a boolean Series: True if SPM resources < SPM threshold.

    The DataFrame must contain an 'income' column and optionally:
    eitc_amount, ctc_refundable, federal_tax_effective, hi_tax_liability,
    num_people.

    Args:
        df: Tax-unit DataFrame.
        year: Tax year (default 2022).

    Returns:
        pd.Series[bool] with True meaning "in SPM poverty", same index as df.
    """
    resources = compute_spm_resources(df)

    # Household size: prefer num_people, fall back to family_size, then 1
    if "num_people" in df.columns:
        size = df["num_people"]
    elif "family_size" in df.columns:
        size = df["family_size"]
    else:
        size = pd.Series(1, index=df.index)

    threshold = compute_spm_threshold(size, year=year)

    return (resources < threshold).rename("spm_poor")
