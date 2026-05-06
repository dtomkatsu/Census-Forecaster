"""Non-resident filer uplift for resident-only Hawaii microsim.

Our microsim is anchored on PUMS Hawaii residents and DOTAX resident-filer
statistics, so it captures resident liability only. Non-residents (Form
N-15) and composite returns (S-corp / partnership pass-throughs) add a
material layer of HI-source income tax that ITEP-style fiscal scoring
includes by default.

Source: DOTAX *Hawaiʻi Individual Income Tax Statistics, Tax Year 2022*
(https://files.hawaii.gov/tax/stats/stats/indinc/2022indinc.pdf)

TY2022 anchor figures (before credits):
  - 107,992 N-15 returns
  - $300M total NR liability                  (vs $3,029M resident → 9.0%)
  - $134M from ≥$400K HI AGI bin              (44.7% of NR total)
  - 1,530 NR returns + 1,504 composite returns at ≥$400K HI AGI
  - 56% of NR top-bracket taxable income is LTCG (vs 21% for residents)
  - NR liability CAGR 2012-2022: ~11%/yr (vs 6.3% for residents)

Statutory facts:
  - HRS §235-51 imposes the same rate schedule on residents and non-residents
  - §235-51(f) 7.25% LTCG alt-tax IS available to non-residents
  - SB 3125 CD1's 13% top bracket applies to NR HI-source income above $1M
    (no statutory carve-out)
  - Composite returns pay at the highest marginal rate by statute → captured
    automatically at 13% under SB 3125 CD1

Caveats:
  - DOTAX Table A-3 stops at ≥$400K HI AGI; finer NR granularity at $1M+
    not published.  Allocation between $400K-$1M and $1M+ uses the same
    proportion as the resident population (proxy).
  - 34.4% of N-15 returns are non-taxable; uplift applies to taxable returns
    only (exclude from positive-liability scaling).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


# DOTAX TY2022 anchor (before credits, $M)
NR_TOTAL_LIABILITY_2022_M: float = 300.0
NR_TOP_BRACKET_LIABILITY_2022_M: float = 134.0   # NR ≥$400K HI AGI

# Resident TY2022 reference (DOTAX, before credits)
RES_TOTAL_LIABILITY_2022_M: float = 3_029.0

# 10-year CAGRs from DOTAX time series (2012-2022)
NR_GROWTH_RATE_PCT: float = 0.11
RES_GROWTH_RATE_PCT: float = 0.063

# Bracket-weighted uplift factors derived from DOTAX Table A-3.
# Multiply resident liability per bracket by (1 + uplift) to add NR layer.
#   below_350K : low NR exposure (mostly mainland income, doesn't hit HI brackets)
#   350K_to_1M : moderate NR uplift; NR composite returns dominant
#   1M_plus    : NR uplift via large landlords + high-LTCG nonresidents
DEFAULT_BRACKET_UPLIFT: Dict[str, float] = {
    "below_350K": 0.030,
    "350K_to_1M": 0.130,
    "1M_plus":    0.100,
}


@dataclass(frozen=True)
class NRUpliftConfig:
    """Configuration for NR uplift application."""

    bracket_uplift: Dict[str, float]
    growth_rate_pct: float = NR_GROWTH_RATE_PCT
    base_year: int = 2022


DEFAULT_CONFIG = NRUpliftConfig(bracket_uplift=DEFAULT_BRACKET_UPLIFT)


def estimate_nr_total_liability_M(
    year: int, *, config: NRUpliftConfig = DEFAULT_CONFIG,
) -> float:
    """Total NR tax liability for ``year`` (before credits, $M).

    Anchors at TY2022 ($300M) and grows at ``config.growth_rate_pct``/yr.
    """
    growth = (1 + config.growth_rate_pct) ** (year - config.base_year)
    return NR_TOTAL_LIABILITY_2022_M * growth


def bracket_for_agi(agi: float) -> str:
    """Return the bracket key for an AGI value."""
    if agi < 350_000:
        return "below_350K"
    if agi < 1_000_000:
        return "350K_to_1M"
    return "1M_plus"


def apply_uplift_to_bracket_delta(
    resident_delta_by_bracket_M: Dict[str, float],
    *,
    config: NRUpliftConfig = DEFAULT_CONFIG,
) -> Dict[str, float]:
    """Add NR layer to resident-only bracket deltas.

    Parameters
    ----------
    resident_delta_by_bracket_M:
        Mapping like ``{"below_350K": 50.0, "350K_to_1M": 30.0, "1M_plus": 100.0}``
        — the resident-only revenue delta in $M for each bracket.

    Returns
    -------
    Same dict shape with NR uplift added to each bracket.
    """
    uplift = config.bracket_uplift
    return {k: v * (1 + uplift[k]) for k, v in resident_delta_by_bracket_M.items()}


def total_with_nr_uplift_M(
    resident_delta_by_bracket_M: Dict[str, float],
    *,
    config: NRUpliftConfig = DEFAULT_CONFIG,
) -> float:
    """Sum of resident + NR delta across all brackets ($M)."""
    return sum(apply_uplift_to_bracket_delta(
        resident_delta_by_bracket_M, config=config,
    ).values())
