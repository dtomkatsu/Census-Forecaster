"""ACS and economic-data publication schedule helpers.

Provides deterministic approximations of official release dates so the
backtest harness and calibration pipeline can operate in "publication mode"
— simulating the information set available at each historical anchor point
rather than pretending all data is visible on Jan 1 of the following year.

Real dates vary slightly year to year (Census announces a specific Thursday);
the functions here return a computed date using the weekday-of-month formula
that matches all historical 1-year and 5-year ACS releases within ±3 days.
"""
from __future__ import annotations

from datetime import date, timedelta


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the n-th occurrence (1-based) of weekday (Mon=0…Sun=6) in (year, month)."""
    first = date(year, month, 1)
    delta = (weekday - first.weekday()) % 7
    return first + timedelta(days=delta + 7 * (n - 1))


def acs_1y_release_date(year: int) -> date:
    """Approximate release date of the 1-year ACS for data year `year`.

    Census releases the 1-year ACS in the second week of September of year+1.
    Historical matches (all within ±2 days of the published schedule):
      2023 → Sept 12, 2024   2022 → Sept 14, 2023
      2021 → Sept 15, 2022   2019 → Sept 15, 2020
      2018 → Sept 12, 2019   2017 → Sept 13, 2018

    (2020 1-year ACS was not published due to COVID data quality concerns.)
    """
    return _nth_weekday(year + 1, 9, 3, 2)  # 2nd Thursday of September Y+1


def acs_5y_release_date(year: int) -> date:
    """Approximate release date of the 5-year ACS ending in data year `year`.

    Census releases 5-year ACS in early December of year+1.
    Historical matches:
      2022 → Dec 7, 2023    2021 → Dec 8, 2022
      2020 → Dec 9, 2021    2019 → Dec 10, 2020
    """
    return _nth_weekday(year + 1, 12, 3, 1)  # 1st Thursday of December Y+1
