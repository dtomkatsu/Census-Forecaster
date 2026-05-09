"""Hawaii Federal Poverty Level (FPL) guidelines.

HHS publishes annual poverty guidelines separately for the contiguous
48 states + DC, Alaska, and Hawaii. Hawaii is ~11-12% above contiguous
US. The numbers below are the 2024 HHS guidelines (Federal Register,
Jan 2024). Update annually when HHS publishes new tables.

Used by SNAP gross/net income tests (Phase 3, separate USDA tables),
Medicaid eligibility (Phase 5), WIC eligibility (Phase 5), ACA Premium
Tax Credit (Phase 5).
"""
from __future__ import annotations

from tax_modeler.errors import ConfigError


# 2024 HHS Hawaii poverty guidelines (annual, by household size)
_HI_FPL_BASE_2024 = {
    1: 16_770, 2: 22_680, 3: 28_590, 4: 34_500,
    5: 40_410, 6: 46_320, 7: 52_230, 8: 58_140,
}
_HI_FPL_INCREMENT_PER_EXTRA_PERSON_2024 = 5_910


def hawaii_fpl(year: int = 2024, *, household_size: int = 1) -> float:
    """Annual HHS Hawaii poverty guideline for a household of ``household_size``."""
    if year != 2024:
        raise ConfigError(
            f"hawaii_fpl: only 2024 published; got year={year}",
            available=[2024],
        )
    if household_size <= 0:
        raise ConfigError("household_size must be >= 1")
    if household_size <= max(_HI_FPL_BASE_2024):
        return float(_HI_FPL_BASE_2024[household_size])
    extra = household_size - max(_HI_FPL_BASE_2024)
    return float(
        _HI_FPL_BASE_2024[max(_HI_FPL_BASE_2024)]
        + extra * _HI_FPL_INCREMENT_PER_EXTRA_PERSON_2024
    )


__all__ = ["hawaii_fpl"]
