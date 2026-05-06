"""Year-forward DOTAX-shaped calibration targets for Hawaii income tax microsim.

Constructs filer-count, tax, and filing-status targets for any TY in 2025-2031
from three inputs:
    1. DOTAX TY2022 baseline (filer counts, tax, filing status)
    2. Hawaii Council on Revenues IIT projection (FY27 anchor + back-cast)
    3. Top-bracket differential growth assumption (1pp/yr above general)

Used by ``year_recalibrator.project_and_recalibrate`` to layer ITEP-style
year-by-year IRS target matching on top of the existing B19013 + top-income
premium projection. The forward targets re-anchor projected incomes each year
so total revenue tracks COR and top-bracket distribution tracks IRS empirical
patterns (top 1% growing 2-3pp/yr above median).

Methodology
-----------
For target year Y:

* **Aggregate tax target T_Y**: lookup in COR projections (default
  ``DEFAULT_COR_IIT_PROJECTIONS_M``). For Y < 2027, back-cast from the FY27
  anchor at 2.5% nominal growth.

* **Filer migration**: apply piecewise growth ``g_b(Y)`` per bracket:
    - Below $200K: ``g_low = 1.025^(Y-2022)``
    - At/above $200K: ``g_high = g_low * 1.010^(Y-2022)``  (top differential)
  Build a CDF over TY2022 brackets, scale cut-points by ``g_b``, then
  re-bucket onto the fixed 15-bracket nominal schema. Total filer count is
  held constant at 618,423 (Hawaii's filer base is near-stable).

* **Tax targets**: per-filer effective rate from TY2022 (``r_b = Tax_b / N_b``)
  applied to the *forward* counts, with a small ``rate_drift`` uplift for
  bracket-creep into higher marginal rates. Then uniformly scaled so the sum
  exactly equals T_Y (consistency with COR).

* **Filing status**: TY2022 totals scaled by ``total_Y / 618_423`` (≈1.0).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# COR Sep 2025 forecast for Hawaii Individual Income Tax (FY27 anchor; FY28+
# at the council's long-run 2.5% nominal growth). Source of truth for the
# aggregate revenue target each year.
DEFAULT_COR_IIT_PROJECTIONS_M: Dict[int, float] = {
    2027: 3050.0,
    2028: 3127.0,
    2029: 3205.0,
    2030: 3285.0,
    2031: 3367.0,
}

# DOTAX TY2022 baseline (Table A8, resident-only). Mirrors the constants in
# ``simultaneous_calibrator.py`` — defined here too so this module is
# self-contained for forward target construction.
_DOTAX_FILER_TARGETS_2022: Dict[Tuple[float, float], int] = {
    (0,         10_000):    115_285,
    (10_000,    20_000):     64_160,
    (20_000,    30_000):     57_835,
    (30_000,    40_000):     58_135,
    (40_000,    50_000):     53_555,
    (50_000,    75_000):     91_459,
    (75_000,   100_000):     54_976,
    (100_000,  150_000):     62_065,
    (150_000,  200_000):     27_976,
    (200_000,  300_000):     19_015,
    (300_000,  400_000):      5_729,
    (400_000,  500_000):      2_856,
    (500_000,  750_000):      2_549,
    (750_000, 1_000_000):     1_004,
    (1_000_000, np.inf):      1_824,
}

_DOTAX_TAX_TARGETS_2022: Dict[Tuple[float, float], float] = {
    (0,         10_000):     3.0,
    (10_000,    20_000):    21.0,
    (20_000,    30_000):    51.0,
    (30_000,    40_000):    92.0,
    (40_000,    50_000):   116.0,
    (50_000,    75_000):   293.0,
    (75_000,   100_000):   261.0,
    (100_000,  150_000):   438.0,
    (150_000,  200_000):   294.0,
    (200_000,  300_000):   310.0,
    (300_000,  400_000):   153.0,
    (400_000,  500_000):   101.0,
    (500_000,  750_000):   149.0,
    (750_000, 1_000_000):   85.0,
    (1_000_000, np.inf):   663.0,
}

_DOTAX_STATUS_TARGETS_2022: Dict[str, int] = {
    "single":                     326_470,
    "married_filing_jointly":     210_724,
    "head_of_household":           65_638,
    "married_filing_separately":   15_591,
}

_TY2022_TOTAL_TAX_M = sum(_DOTAX_TAX_TARGETS_2022.values())     # 3030.0
_TY2022_TOTAL_FILERS = sum(_DOTAX_FILER_TARGETS_2022.values())  # 618,423


@dataclass(frozen=True)
class ForwardTargets:
    """Year-parameterized DOTAX-shaped calibration targets.

    Attributes
    ----------
    year:
        Target tax year (e.g. 2027).
    filer_targets:
        ``{(agi_lo, agi_hi): filer_count}`` for the 15 nominal AGI brackets.
    tax_targets:
        ``{(agi_lo, agi_hi): tax_M}`` summing to the COR aggregate for ``year``.
    status_targets:
        ``{filing_status: count}`` totals.
    aggregate_tax_M:
        Convenience: sum of ``tax_targets.values()``.
    """
    year: int
    filer_targets: Dict[Tuple[float, float], int]
    tax_targets:   Dict[Tuple[float, float], float]
    status_targets: Dict[str, int]
    aggregate_tax_M: float


def _back_cast_cor(year: int, cor_projections_M: Dict[int, float]) -> float:
    """Return the COR aggregate tax target for *year*.

    For years already in the table, return the value directly. For years
    before the earliest entry, back-cast at 2.5% nominal annual growth from
    the earliest anchor (typically FY27 = $3,050M).
    """
    if year in cor_projections_M:
        return cor_projections_M[year]
    earliest = min(cor_projections_M)
    if year > max(cor_projections_M):
        # Forward extrapolation also at 2.5% (rare; COR usually publishes 5+ yrs)
        anchor = cor_projections_M[max(cor_projections_M)]
        return anchor * (1.025 ** (year - max(cor_projections_M)))
    # Back-cast: anchor / 1.025^(anchor_year - year)
    anchor = cor_projections_M[earliest]
    return anchor / (1.025 ** (earliest - year))


def _migrate_filer_counts(
    base_counts: Dict[Tuple[float, float], int],
    g_low: float,
    g_high: float,
    threshold: float = 200_000.0,
) -> Dict[Tuple[float, float], int]:
    """Migrate TY2022 filer counts to a forward year via bracket-shift.

    Each TY2022 bracket ``(lo, hi)`` is treated as a uniform mass of filers
    on ``[lo, hi)``. We scale every cut-point by ``g_low`` (below threshold)
    or ``g_high`` (at/above threshold) and re-bucket onto the fixed nominal
    boundaries. Total mass is preserved.

    For the open-ended top bracket ``(1_000_000, inf)``, mass is preserved
    in place (scaling shifts the lower edge but the bucket remains the top).
    """
    nominal_brackets = sorted(base_counts.keys())
    # Build "shifted" sub-pieces from each TY2022 bracket
    shifted_pieces = []  # list of (lo_new, hi_new, count_density_per_dollar)
    for (lo, hi), count in base_counts.items():
        g = g_low if lo < threshold else g_high
        new_lo = lo * g
        if hi == np.inf:
            new_hi = np.inf
        else:
            new_hi = hi * g
        # Density per dollar (uniform within bracket) — for finite top bracket;
        # for open bracket, treat as point mass at new_lo (scaling preserves count).
        if new_hi == np.inf:
            shifted_pieces.append(("point", new_lo, np.inf, count))
        else:
            density = count / (new_hi - new_lo) if new_hi > new_lo else 0.0
            shifted_pieces.append(("uniform", new_lo, new_hi, density))

    # Now bucket shifted pieces onto the fixed nominal schema
    forward = {b: 0.0 for b in nominal_brackets}
    for kind, plo, phi, val in shifted_pieces:
        if kind == "point":
            # Mass goes entirely into whichever nominal bracket contains plo
            for (nlo, nhi) in nominal_brackets:
                if nlo <= plo < nhi:
                    forward[(nlo, nhi)] += val
                    break
            else:
                forward[nominal_brackets[-1]] += val
        else:  # uniform
            density = val
            for (nlo, nhi) in nominal_brackets:
                # Overlap of [plo, phi) with [nlo, nhi)
                if nhi == np.inf:
                    overlap_lo = max(plo, nlo)
                    overlap_hi = phi
                else:
                    overlap_lo = max(plo, nlo)
                    overlap_hi = min(phi, nhi)
                if overlap_hi > overlap_lo:
                    forward[(nlo, nhi)] += density * (overlap_hi - overlap_lo)

    # Round to integers; rounding noise will be absorbed by the renormalization
    # step in build_targets.
    return {b: int(round(v)) for b, v in forward.items()}


def build_targets(
    year: int,
    *,
    cor_projections_M: Optional[Dict[int, float]] = None,
    low_growth: float = 0.025,
    top_differential: float = 0.010,
    rate_drift: float = 0.005,
    base_counts: Optional[Dict[Tuple[float, float], int]] = None,
    base_tax: Optional[Dict[Tuple[float, float], float]] = None,
    base_status: Optional[Dict[str, int]] = None,
    base_year: int = 2022,
) -> ForwardTargets:
    """Construct ``ForwardTargets`` for the given year.

    Parameters
    ----------
    year:
        Target tax year (2022..2031 supported).
    cor_projections_M:
        Override for the COR projection table. Default uses
        ``DEFAULT_COR_IIT_PROJECTIONS_M``.
    low_growth:
        Annual income growth factor applied to brackets below $200K.
    top_differential:
        Extra annual growth for brackets at/above $200K (compounded with
        ``low_growth``). Captures top-1% empirical premium.
    rate_drift:
        Per-year effective-rate uplift reflecting bracket-creep into higher
        marginal rates as nominal incomes rise.
    base_counts, base_tax, base_status:
        Override the TY2022 baseline (mainly for testing the round-trip).
    base_year:
        Calendar year of the baseline; default 2022.
    """
    cor = dict(cor_projections_M or DEFAULT_COR_IIT_PROJECTIONS_M)
    bc = dict(base_counts or _DOTAX_FILER_TARGETS_2022)
    bt = dict(base_tax    or _DOTAX_TAX_TARGETS_2022)
    bs = dict(base_status or _DOTAX_STATUS_TARGETS_2022)

    years = year - base_year
    g_low  = (1 + low_growth) ** years
    g_high = g_low * (1 + top_differential) ** years
    drift  = 1 + rate_drift * years

    # ── 1. Filer counts: bracket migration ────────────────────────────────────
    forward_counts = _migrate_filer_counts(bc, g_low, g_high)

    # ── 2. Tax targets: per-filer effective rate × new counts × drift ─────────
    raw_tax: Dict[Tuple[float, float], float] = {}
    for bracket, base_n in bc.items():
        base_t = bt[bracket]
        eff_rate = base_t / base_n if base_n > 0 else 0.0
        new_n = forward_counts.get(bracket, 0)
        raw_tax[bracket] = eff_rate * new_n * drift

    # Scale uniformly so sum matches COR aggregate
    aggregate = _back_cast_cor(year, cor)
    raw_sum = sum(raw_tax.values())
    if raw_sum > 0:
        scale = aggregate / raw_sum
    else:
        scale = 1.0
    forward_tax = {b: v * scale for b, v in raw_tax.items()}

    # ── 3. Filing status: scale TY2022 totals by total filer growth ─────────
    base_total = sum(bc.values())
    new_total = sum(forward_counts.values())
    status_scale = new_total / base_total if base_total > 0 else 1.0
    forward_status = {s: int(round(v * status_scale)) for s, v in bs.items()}

    return ForwardTargets(
        year=year,
        filer_targets=forward_counts,
        tax_targets=forward_tax,
        status_targets=forward_status,
        aggregate_tax_M=aggregate,
    )


def summarize(target: ForwardTargets) -> str:
    """One-line summary for logging."""
    n = sum(target.filer_targets.values())
    top = sum(v for (lo, _), v in target.filer_targets.items() if lo >= 500_000)
    return (
        f"ForwardTargets[{target.year}]: {n:,} filers (≥$500K: {top:,}), "
        f"${target.aggregate_tax_M:,.0f}M aggregate tax"
    )
