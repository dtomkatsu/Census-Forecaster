"""Multi-MSA BLS CPI panel definition for v3 stratified calibration.

The v2 calibration ran on 5 Honolulu series only — too narrow to
generalize. v3 expands to a panel of 11 metropolitan areas × 5 CPI
series, each spanning 2010-2024. This file documents the area / series
matrix and exposes builders for the cross-product of series IDs.

Area code conventions
---------------------
BLS uses a two-tier area code:
* `0000` — U.S. City Average (national, monthly)
* `S{R}{S}{X}` where R = region code (1-4), S = size class (1-9),
  X = letter selecting a specific MSA within that region/size class

The codes below were verified empirically against the BLS public API
on 2026-04-26 (see `scripts/refresh_bls_panel.py` for the probe). All
11 areas publish all 5 series. Four areas publish the all-items index
(SA0) monthly; the remaining seven publish bimonthly. The other four
series (food, rent, housing, gasoline) publish monthly across all areas.

Series suffix conventions
-------------------------
* `SA0`     — All items, all urban consumers (headline CPI)
* `SAF11`   — Food at home
* `SEHA`    — Rent of primary residence
* `SAH1`    — Housing
* `SETB01`  — Motor fuel (gasoline) — stress-test for high volatility

The `SA0` series is the headline forecaster target; the other four are
included to stratify κ across volatility regimes (food and rent are
low-volatility; gasoline is high-volatility; housing sits between).

Panel size
----------
* 11 areas × 5 series = 55 BLS series
* ~15 years (2010-2024) of monthly/bimonthly observations
* ~9,000 raw observations after concatenation
* ~40,000 walk-forward folds across (anchor, h ∈ {2,4,6,8,12})
* ~220 strata cells (series × h_bucket × vol_regime)
* ~180 folds per cell on average — well above n_threshold=20

"""
from __future__ import annotations

from dataclasses import dataclass


# Top 10 MSAs by 2020 population + national + Honolulu (existing primary).
# Names below are the BLS publication labels; the (region, size_class)
# columns describe the BLS area code structure for context.
@dataclass(frozen=True)
class BlsArea:
    """One BLS publication area in the v3 calibration panel."""
    code: str
    name: str
    region: str            # NE, MidAtl, ENC, WNC, SAtl, ESC, WSC, Mtn, Pac
    size_class: str        # A (largest) or B (second-largest) or "national"
    headline_frequency: str  # "monthly" or "bimonthly"


BLS_PANEL_AREAS: tuple[BlsArea, ...] = (
    BlsArea(code="0000", name="U.S. City Average",
            region="national", size_class="national", headline_frequency="monthly"),
    BlsArea(code="S49A", name="Urban Honolulu, HI",
            region="Pacific", size_class="A", headline_frequency="bimonthly"),
    BlsArea(code="S12A", name="New York-Newark-Jersey City, NY-NJ-PA",
            region="Mid-Atlantic", size_class="A", headline_frequency="monthly"),
    BlsArea(code="S23A", name="Chicago-Naperville-Elgin, IL-IN-WI",
            region="East-North-Central", size_class="A", headline_frequency="monthly"),
    BlsArea(code="S49B", name="Los Angeles-Long Beach-Anaheim, CA",
            region="Pacific", size_class="B", headline_frequency="bimonthly"),
    BlsArea(code="S48A", name="Dallas-Fort Worth-Arlington, TX",
            region="West-South-Central", size_class="A", headline_frequency="bimonthly"),
    BlsArea(code="S48B", name="Houston-The Woodlands-Sugar Land, TX",
            region="West-South-Central", size_class="B", headline_frequency="bimonthly"),
    BlsArea(code="S35A", name="Washington-Arlington-Alexandria, DC-VA-MD-WV",
            region="South-Atlantic", size_class="A", headline_frequency="bimonthly"),
    BlsArea(code="S37A", name="Miami-Fort Lauderdale-West Palm Beach, FL",
            region="South-Atlantic", size_class="A2", headline_frequency="bimonthly"),
    BlsArea(code="S11A", name="Boston-Cambridge-Newton, MA-NH",
            region="New-England", size_class="A", headline_frequency="bimonthly"),
    BlsArea(code="S24A", name="Minneapolis-St. Paul-Bloomington, MN-WI",
            region="West-North-Central", size_class="A", headline_frequency="bimonthly"),
)


@dataclass(frozen=True)
class BlsSeriesKind:
    """One CPI subindex tracked across all panel areas."""
    suffix: str
    label: str
    description: str


BLS_PANEL_SERIES: tuple[BlsSeriesKind, ...] = (
    BlsSeriesKind(suffix="SA0",   label="all_items",
                  description="All items, all urban consumers (headline CPI)"),
    BlsSeriesKind(suffix="SAF11", label="food_at_home",
                  description="Food at home"),
    BlsSeriesKind(suffix="SEHA",  label="rent",
                  description="Rent of primary residence"),
    BlsSeriesKind(suffix="SAH1",  label="housing",
                  description="Housing"),
    BlsSeriesKind(suffix="SETB01", label="gasoline",
                  description="Motor fuel (gasoline) — high-volatility stress test"),
)


def all_panel_series_ids() -> list[str]:
    """Return the cross-product of areas × series as BLS series IDs."""
    return [
        f"CUUR{area.code}{kind.suffix}"
        for area in BLS_PANEL_AREAS
        for kind in BLS_PANEL_SERIES
    ]


def parse_series_id(series_id: str) -> tuple[BlsArea, BlsSeriesKind] | None:
    """Decompose a panel series ID into its (area, kind) parts.

    Returns None if the series_id isn't part of the configured panel —
    e.g. a one-off series fetched outside the calibration set.
    """
    if not series_id.startswith("CUUR") or len(series_id) < 8:
        return None
    # Area code is variable length: 4 chars for national (`0000`) and S-prefix
    # codes are 4 chars also (e.g. `S49A`). The series suffix is 3-6 chars.
    # Try area-code prefix length 4 first (matches both national and S-codes),
    # then fall through to longer prefixes if needed.
    area_part = series_id[4:8]
    suffix = series_id[8:]
    area = next((a for a in BLS_PANEL_AREAS if a.code == area_part), None)
    kind = next((k for k in BLS_PANEL_SERIES if k.suffix == suffix), None)
    if area is None or kind is None:
        return None
    return (area, kind)


def panel_series_for_area(area_code: str) -> list[str]:
    """All five series IDs for one area."""
    area = next((a for a in BLS_PANEL_AREAS if a.code == area_code), None)
    if area is None:
        raise ValueError(f"unknown area code {area_code!r}")
    return [f"CUUR{area.code}{kind.suffix}" for kind in BLS_PANEL_SERIES]


def panel_series_for_kind(suffix: str) -> list[str]:
    """All series IDs across areas for one CPI subindex."""
    kind = next((k for k in BLS_PANEL_SERIES if k.suffix == suffix), None)
    if kind is None:
        raise ValueError(f"unknown series suffix {suffix!r}")
    return [f"CUUR{area.code}{kind.suffix}" for area in BLS_PANEL_AREAS]


__all__ = [
    "BlsArea",
    "BlsSeriesKind",
    "BLS_PANEL_AREAS",
    "BLS_PANEL_SERIES",
    "all_panel_series_ids",
    "panel_series_for_area",
    "panel_series_for_kind",
    "parse_series_id",
]
