"""
Poverty-impact entry point for Hawaii tax microsimulation.

Computes the number of persons, families, and children lifted above the
Hawaii SPM poverty threshold under each credit scenario.

Empirical anchors
-----------------
Federal effective tax rates: IRS SOI TY2022 national Table 1.4
HI EITC take-up (base): 84,010 claims / ~120,000 eligible (IRS SOI 2022) = 0.70
HI EITC take-up (100% scenario): 0.95 (marginal-claimant rate among federal filers)
ARPA CTC take-up: Treasury monthly CTC data for Hawaii, 2021 = 0.82
HI CTC take-up (hypothetical): 0.70 (conservative, matches HI EITC base)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .spm_aggregation import (
    compute_spm_resources,
    compute_spm_threshold,
    flag_spm_poor,
    SPM_THRESHOLD_BASE_4PERSON_2022,
    SPM_HI_RPP_2022,
)

# ---------------------------------------------------------------------------
# IRS SOI TY2022 bracket-aware effective federal tax rates
# Source: IRS SOI Table 1.4, TY2022
# (income_low, income_high, effective_rate)
# ---------------------------------------------------------------------------

_SOI_EFFECTIVE_RATE_TABLE: List[Tuple[float, float, float]] = [
    (0,        5_000,   0.0025),
    (5_000,    10_000,  0.0012),
    (10_000,   15_000,  0.0030),
    (15_000,   20_000,  0.0156),
    (20_000,   25_000,  0.0290),
    (25_000,   30_000,  0.0407),
    (30_000,   40_000,  0.0548),
    (40_000,   50_000,  0.0672),
    (50_000,   75_000,  0.0832),
    (75_000,   100_000, 0.0999),
    (100_000,  200_000, 0.1233),
    (200_000,  500_000, 0.1731),
    (500_000,  float("inf"), 0.2316),
]

# Precompute breakpoints and rates for vectorized lookup
_SOI_BREAKPOINTS: np.ndarray = np.array(
    [row[0] for row in _SOI_EFFECTIVE_RATE_TABLE], dtype=float
)
_SOI_RATES: np.ndarray = np.array(
    [row[2] for row in _SOI_EFFECTIVE_RATE_TABLE], dtype=float
)

# ---------------------------------------------------------------------------
# Take-up rate constants (empirically anchored)
# ---------------------------------------------------------------------------

# HI EITC take-up at 100%-of-federal scenario (marginal claimant rate)
# Source: IRS SOI TY2022 Hawaii (col 129); DOTAX Annual Report 2022
HI_EITC_100PCT_TAKEUP: float = 0.95

# HI EITC base take-up: 84,010 / 120,000 ≈ 0.70
# Source: IRS SOI TY2022 Hawaii; PUMS 2022 eligibility estimate
HI_EITC_BASE_TAKEUP: float = 0.70

# ARPA CTC take-up: Treasury monthly CTC data for Hawaii, 2021
# Source: Treasury.gov, "Monthly Advance Child Tax Credit Payments by State", 2021
ARPA_CTC_TAKEUP: float = 0.82

# HI CTC take-up (hypothetical $300/$650/$1000 scenarios)
# Conservative: matches HI EITC base take-up
HI_CTC_300_TAKEUP: float = 0.70
HI_CTC_650_TAKEUP: float = 0.70
HI_CTC_1000_TAKEUP: float = 0.70

# ---------------------------------------------------------------------------
# Default scenario list
# ---------------------------------------------------------------------------

_DEFAULT_SCENARIOS: List[str] = [
    "federal_eitc",
    "federal_ctc",
    "hi_eitc",
    "hi_ctc_300",
    "hi_ctc_650",
    "hi_ctc_1000",
    "hi_eitc_100pct",
    "expanded_ctc_2021",
]


# ---------------------------------------------------------------------------
# Federal tax fallback
# ---------------------------------------------------------------------------


def _apply_federal_tax_fallback(df: pd.DataFrame) -> pd.Series:
    """Compute estimated federal income tax via IRS SOI TY2022 bracket rates.

    Uses vectorized np.searchsorted on the AGI breakpoints to assign each
    tax unit to a bracket, then multiplies income by the bracket's effective
    rate.  Replaces the old "10% of positive money income" placeholder.

    Source: IRS SOI Table 1.4, TY2022 (national).

    Args:
        df: Tax-unit DataFrame. Must contain 'income' column.

    Returns:
        pd.Series of estimated federal tax (dollars), same index as df.
    """
    income = df["income"].fillna(0.0).astype(float).clip(lower=0.0)
    income_arr = income.to_numpy()

    # searchsorted returns index of the FIRST breakpoint >= income;
    # subtract 1 to get the bracket whose lower bound <= income.
    # Clip to valid range [0, len-1].
    idx = np.searchsorted(_SOI_BREAKPOINTS, income_arr, side="right") - 1
    idx = np.clip(idx, 0, len(_SOI_RATES) - 1)

    rates = _SOI_RATES[idx]
    fed_tax = income_arr * rates

    return pd.Series(fed_tax, index=df.index, name="federal_tax_estimated")


# ---------------------------------------------------------------------------
# Credit computation helpers
# ---------------------------------------------------------------------------


def _get_col(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    """Return a column from df, or a constant series if column is absent."""
    if col in df.columns:
        return df[col].fillna(default).astype(float)
    return pd.Series(default, index=df.index, dtype=float)


def _family_size(df: pd.DataFrame) -> pd.Series:
    """Resolve family/household size column."""
    if "num_people" in df.columns:
        return df["num_people"].fillna(1).astype(int)
    if "family_size" in df.columns:
        return df["family_size"].fillna(1).astype(int)
    return pd.Series(1, index=df.index, dtype=int)


def _weight(df: pd.DataFrame) -> pd.Series:
    """Resolve person-weight column (default 1.0)."""
    for col in ("weight", "PWGTP", "WGTP"):
        if col in df.columns:
            return df[col].fillna(1.0).astype(float)
    return pd.Series(1.0, index=df.index)


def _num_children(df: pd.DataFrame) -> pd.Series:
    """Resolve number-of-children column."""
    for col in ("num_children", "qualifying_children", "eitc_qualifying_children"):
        if col in df.columns:
            return df[col].fillna(0).astype(int)
    return pd.Series(0, index=df.index, dtype=int)


def _num_persons(df: pd.DataFrame) -> pd.Series:
    """Persons per tax unit (family size)."""
    return _family_size(df)


# ---------------------------------------------------------------------------
# Scenario credit vectors
# ---------------------------------------------------------------------------


def _scenario_credit(df: pd.DataFrame, scenario: str) -> pd.Series:
    """Return the per-tax-unit credit amount (before take-up) for a scenario.

    For population-weighted expected-value counting:
        effective_credit = credit_amount × takeup_rate

    Args:
        df: Tax-unit DataFrame.
        scenario: Scenario name from _DEFAULT_SCENARIOS.

    Returns:
        pd.Series of credit amounts (dollars, before take-up scaling).
    """
    if scenario == "federal_eitc":
        return _get_col(df, "eitc_amount").clip(lower=0.0)

    elif scenario == "federal_ctc":
        return _get_col(df, "ctc_refundable").clip(lower=0.0)

    elif scenario == "hi_eitc":
        # HI EITC = 40% of federal EITC, subject to base take-up
        return (_get_col(df, "eitc_amount").clip(lower=0.0) * 0.40)

    elif scenario == "hi_ctc_300":
        return (_num_children(df).astype(float) * 300.0)

    elif scenario == "hi_ctc_650":
        return (_num_children(df).astype(float) * 650.0)

    elif scenario == "hi_ctc_1000":
        return (_num_children(df).astype(float) * 1000.0)

    elif scenario == "hi_eitc_100pct":
        # HI EITC at 100% of federal (vs. 40% current law)
        return _get_col(df, "eitc_amount").clip(lower=0.0)

    elif scenario == "expanded_ctc_2021":
        # ARPA 2021 CTC — prefer pre-computed column, else use num_children
        if "arpa_ctc_refundable" in df.columns:
            return _get_col(df, "arpa_ctc_refundable").clip(lower=0.0)
        # Fallback: $3,000 per qualifying child (conservative: ignores under-6 bump)
        return (_num_children(df).astype(float) * 3_000.0)

    else:
        raise ValueError(f"Unknown scenario: {scenario!r}")


def _scenario_takeup(scenario: str) -> float:
    """Return the take-up rate for a scenario."""
    takeup_map: Dict[str, float] = {
        "federal_eitc": 1.0,       # Already in data (IRS-reported)
        "federal_ctc": 1.0,        # Already in data
        "hi_eitc": HI_EITC_BASE_TAKEUP,
        "hi_ctc_300": HI_CTC_300_TAKEUP,
        "hi_ctc_650": HI_CTC_650_TAKEUP,
        "hi_ctc_1000": HI_CTC_1000_TAKEUP,
        "hi_eitc_100pct": HI_EITC_100PCT_TAKEUP,
        "expanded_ctc_2021": ARPA_CTC_TAKEUP,
    }
    return takeup_map.get(scenario, 1.0)


# ---------------------------------------------------------------------------
# Core poverty-impact calculation
# ---------------------------------------------------------------------------


def _build_baseline_resources(df: pd.DataFrame) -> pd.Series:
    """Compute SPM resources *before* any credit (income minus taxes only).

    If federal_tax_effective is not present, falls back to SOI-bracketed
    rate estimation.
    """
    income = df["income"].fillna(0.0).astype(float)
    resources = income.copy()

    # Federal tax
    if "federal_tax_effective" in df.columns:
        fed_tax = df["federal_tax_effective"].fillna(0.0).astype(float).clip(lower=0.0)
    else:
        fed_tax = _apply_federal_tax_fallback(df).clip(lower=0.0)

    resources -= fed_tax

    # State tax
    if "hi_tax_liability" in df.columns:
        resources -= df["hi_tax_liability"].fillna(0.0).astype(float).clip(lower=0.0)

    return resources


def compute_poverty_impact(
    tax_units_df: pd.DataFrame,
    year: int = 2022,
    scenarios: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Compute persons lifted above SPM poverty threshold per credit scenario.

    For each scenario, adds the credit amount (scaled by take-up rate) to
    the *baseline* SPM resources (income minus taxes, no credits) and counts
    how many weighted persons are moved above the SPM threshold.

    The baseline intentionally omits credits so that each scenario's lift is
    measured as the marginal effect of that credit alone.

    Args:
        tax_units_df: DataFrame of tax units. Required column: 'income'.
            Optional columns: 'eitc_amount', 'ctc_refundable',
            'arpa_ctc_refundable', 'federal_tax_effective', 'hi_tax_liability',
            'num_people' / 'family_size', 'num_children', 'weight'.
        year: Tax year for SPM threshold CPI adjustment (default 2022).
        scenarios: List of scenario names to compute; defaults to
            _DEFAULT_SCENARIOS (all 8 scenarios).

    Returns:
        pd.DataFrame with columns:
            scenario, persons_lifted, families_lifted, children_lifted,
            pct_poor_baseline, pct_poor_with_credit, poverty_reduction_pp
        One row per scenario.
    """
    if scenarios is None:
        scenarios = _DEFAULT_SCENARIOS

    df = tax_units_df.reset_index(drop=True)

    weights = _weight(df)
    n_persons = _num_persons(df)
    n_children = _num_children(df)
    family_size = _family_size(df)

    threshold = compute_spm_threshold(family_size, year=year)
    baseline_resources = _build_baseline_resources(df)

    # Baseline poverty flag
    poor_baseline = baseline_resources < threshold

    total_persons_weighted = (weights * n_persons).sum()

    rows = []
    for scenario in scenarios:
        credit = _scenario_credit(df, scenario)
        takeup = _scenario_takeup(scenario)

        # Expected-value approach: scale the credit by the take-up rate
        # before comparing to threshold
        resources_with_credit = baseline_resources + credit * takeup
        poor_with_credit = resources_with_credit < threshold

        # Units lifted = were poor in baseline and no longer poor with credit
        lifted_mask = poor_baseline & ~poor_with_credit

        persons_lifted = float((weights * n_persons * lifted_mask).sum())
        families_lifted = float((weights * lifted_mask).sum())
        children_lifted = float((weights * n_children * lifted_mask).sum())

        pct_poor_baseline = float(
            (weights * n_persons * poor_baseline).sum() / total_persons_weighted
            if total_persons_weighted > 0 else 0.0
        )
        pct_poor_with_credit = float(
            (weights * n_persons * poor_with_credit).sum() / total_persons_weighted
            if total_persons_weighted > 0 else 0.0
        )
        poverty_reduction_pp = pct_poor_baseline - pct_poor_with_credit

        rows.append(
            {
                "scenario": scenario,
                "persons_lifted": persons_lifted,
                "families_lifted": families_lifted,
                "children_lifted": children_lifted,
                "pct_poor_baseline": pct_poor_baseline,
                "pct_poor_with_credit": pct_poor_with_credit,
                "poverty_reduction_pp": poverty_reduction_pp,
            }
        )

    return pd.DataFrame(rows)


def compute_poverty_impact_with_se(
    tax_units_df: pd.DataFrame,
    year: int = 2022,
    scenarios: Optional[List[str]] = None,
    n_bootstrap: int = 0,
) -> pd.DataFrame:
    """Same as compute_poverty_impact but adds standard-error columns.

    If the DataFrame contains PUMS replicate weight columns
    (weight_r01 .. weight_r80), uses the successive-difference replicate
    (SDR) variance estimator.  Otherwise falls back to a ±10% one-at-a-time
    (OAT) parameter sweep as a parameter-range SE proxy.

    Args:
        tax_units_df: Tax-unit DataFrame (same as compute_poverty_impact).
        year: Tax year for threshold CPI adjustment.
        scenarios: Scenario list (default: all 8).
        n_bootstrap: Unused; present for API consistency with future
            bootstrap implementation.

    Returns:
        pd.DataFrame with all columns from compute_poverty_impact plus:
            se_persons_lifted, se_families_lifted, se_children_lifted.
    """
    if scenarios is None:
        scenarios = _DEFAULT_SCENARIOS

    base_result = compute_poverty_impact(tax_units_df, year=year, scenarios=scenarios)

    # Check for PUMS replicate weights (weight_r01 .. weight_r80)
    replicate_cols = [c for c in tax_units_df.columns if c.startswith("weight_r")]

    if replicate_cols:
        se_rows = _se_from_replicates(tax_units_df, replicate_cols, year, scenarios)
    else:
        se_rows = _se_from_oat_sweep(tax_units_df, year, scenarios)

    se_df = pd.DataFrame(se_rows).set_index("scenario")
    result = base_result.set_index("scenario").join(se_df, how="left").reset_index()
    return result


# ---------------------------------------------------------------------------
# SE helpers
# ---------------------------------------------------------------------------


def _se_from_replicates(
    df: pd.DataFrame,
    replicate_cols: List[str],
    year: int,
    scenarios: List[str],
) -> List[Dict]:
    """Successive-difference replicate (SDR) variance for persons_lifted."""
    n_rep = len(replicate_cols)
    sdr_factor = 4.0 / n_rep  # SDR formula constant

    # Base estimate
    base = compute_poverty_impact(df, year=year, scenarios=scenarios)
    base_vals = base.set_index("scenario")["persons_lifted"].to_dict()

    # Per-replicate estimates
    rep_vals: Dict[str, List[float]] = {s: [] for s in scenarios}
    df_work = df.copy()
    for rc in replicate_cols:
        df_work = df_work.copy()
        df_work["weight"] = df[rc]
        rep_result = compute_poverty_impact(df_work, year=year, scenarios=scenarios)
        for _, row in rep_result.iterrows():
            rep_vals[row["scenario"]].append(row["persons_lifted"])

    rows = []
    for s in scenarios:
        diffs_sq = [(v - base_vals[s]) ** 2 for v in rep_vals[s]]
        variance = sdr_factor * sum(diffs_sq)
        rows.append(
            {
                "scenario": s,
                "se_persons_lifted": variance ** 0.5,
                "se_families_lifted": float("nan"),
                "se_children_lifted": float("nan"),
            }
        )
    return rows


def _se_from_oat_sweep(
    df: pd.DataFrame,
    year: int,
    scenarios: List[str],
    sweep_pct: float = 0.10,
) -> List[Dict]:
    """±10% one-at-a-time income sweep as a parameter-range SE proxy."""
    rows = []
    for s in scenarios:
        df_hi = df.copy()
        df_hi["income"] = df["income"] * (1 + sweep_pct)
        df_lo = df.copy()
        df_lo["income"] = df["income"] * (1 - sweep_pct)

        hi_val = (
            compute_poverty_impact(df_hi, year=year, scenarios=[s])
            .iloc[0]["persons_lifted"]
        )
        lo_val = (
            compute_poverty_impact(df_lo, year=year, scenarios=[s])
            .iloc[0]["persons_lifted"]
        )
        # Half-range as a conservative SE proxy
        se = abs(hi_val - lo_val) / 2.0
        rows.append(
            {
                "scenario": s,
                "se_persons_lifted": se,
                "se_families_lifted": float("nan"),
                "se_children_lifted": float("nan"),
            }
        )
    return rows
