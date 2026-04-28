"""PUMS microdata fetcher via the Census Data API.

Endpoint
--------
    https://api.census.gov/data/{year}/acs/acs{vintage}/pums

Documentation
-------------
    https://www.census.gov/data/developers/data-sets/acs-1year/
    https://www.census.gov/data/developers/data-sets/acs-5year/

Variables commonly requested
-----------------------------
    SERIALNO  — housing-unit serial number (always fetched)
    PUMA      — Public Use Microdata Area code (always fetched)
    WGTP      — housing-unit weight (always fetched)
    VEH       — vehicles available (0-6)
    HINCP     — household income past 12 months
    TEN       — tenure (owned/rented)
    BDSP      — number of bedrooms
"""
from __future__ import annotations

import os
from typing import Optional

import requests

from ..models import PumsRecord

CENSUS_API_BASE = "https://api.census.gov/data"


def fetch_pums(
    state_fips: str,
    variables: list[str],
    year: int = 2022,
    vintage: str = "1",
    api_key: Optional[str] = None,
    timeout: int = 60,
) -> list[PumsRecord]:
    """Fetch PUMS microdata records for a state.

    Parameters
    ----------
    state_fips : str
        2-digit state FIPS code (e.g. "15" for Hawaii).
    variables : list[str]
        PUMS variable names to fetch in addition to SERIALNO, PUMA, WGTP
        which are always included.  Example: ["VEH", "TEN"].
    year : int
        ACS data year (e.g. 2022).
    vintage : str
        "1" for 1-year PUMS, "5" for 5-year PUMS.
    api_key : str, optional
        Census API key.  Falls back to the ``CENSUS_API_KEY`` environment
        variable.  Without a key, requests are rate-limited to ~500/day.
    timeout : int
        HTTP request timeout in seconds (default 60).

    Returns
    -------
    list[PumsRecord]
        One ``PumsRecord`` per housing unit.  Records with weight ≤ 0 or
        a missing PUMA are silently excluded.

    Raises
    ------
    requests.HTTPError
        On non-200 responses from the Census API.
    """
    key = api_key or os.environ.get("CENSUS_API_KEY", "")
    url = f"{CENSUS_API_BASE}/{year}/acs/acs{vintage}/pums"

    always_fetch = ["SERIALNO", "PUMA", "WGTP"]
    get_vars = list(dict.fromkeys(always_fetch + variables))

    params: dict = {
        "get": ",".join(get_vars),
        "for": "public use microdata area:*",
        "in": f"state:{state_fips}",
    }
    if key:
        params["key"] = key

    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()

    rows = resp.json()
    headers = rows[0]
    records: list[PumsRecord] = []

    for row in rows[1:]:
        d = dict(zip(headers, row))

        # PUMA may appear as "PUMA" or as the geo field "public use microdata area"
        puma_raw = d.get("PUMA") or d.get("public use microdata area", "")
        if not puma_raw:
            continue

        puma = f"{state_fips}{puma_raw.zfill(5)}"

        weight_raw = d.get("WGTP", "0") or "0"
        try:
            weight = float(weight_raw)
        except ValueError:
            weight = 0.0
        if weight <= 0:
            continue

        var_values: dict[str, float] = {}
        for v in variables:
            raw = d.get(v)
            if raw is not None:
                try:
                    var_values[v] = float(raw)
                except ValueError:
                    pass

        records.append(PumsRecord(
            serial=d.get("SERIALNO", ""),
            puma=puma,
            weight=weight,
            variables=var_values,
        ))

    return records
