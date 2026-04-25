"""Typed dataclasses for ACS observations, BLS series, and forecast outputs.

These are pure data containers. No I/O, no model logic — keeps the
projection and back-test code easy to test with hand-built inputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class AcsObservation:
    """A single ACS estimate for one (geography, indicator, vintage).

    Fields
    ------
    estimate : float
        Published point estimate (in native units — dollars, count, etc.).
    moe : float
        90% margin of error as published by ACS. Negative values are the
        Census sentinel for suppressed/unreliable; the MOE module returns
        NaN SE for those so they don't poison downstream math.
    year : int
        For 1-year ACS, the calendar year of collection. For 5-year ACS,
        the *end* year of the rolling window (e.g. 2024 for 2020-2024).
        The projection module treats the effective time index for 5-year
        estimates as `year - 2` (the window midpoint).
    vintage : str
        "1y" or "5y". Determines effective time index and noise floor.
    geoid : str
        Census GEOID. State = 2 chars, county = 5 chars (state+county).
    indicator : str
        ACS table-cell ID (e.g. "B19013_001E"). Suffix `E` is the estimate;
        the corresponding `M` cell holds the MOE.
    """
    estimate: float
    moe: float
    year: int
    vintage: str
    geoid: str
    indicator: str

    def __post_init__(self) -> None:
        if self.vintage not in ("1y", "5y"):
            raise ValueError(f"vintage must be '1y' or '5y', got {self.vintage!r}")


@dataclass(frozen=True)
class BlsObservation:
    """A single observation from a BLS time series.

    Fields
    ------
    series_id : str
        BLS series identifier (e.g. "CUURS49ASA0" for Honolulu all-items CPI).
    year : int
        Calendar year of observation.
    period : str
        BLS period code: "M01"-"M12" for monthly, "Q01"-"Q05" for quarterly,
        "S01"/"S02" for semi-annual, "A01" for annual.
    value : float
        The published index value.
    """
    series_id: str
    year: int
    period: str
    value: float

    @property
    def month(self) -> int:
        """Month number (1-12) if this is a monthly observation; else 0."""
        if self.period.startswith("M") and len(self.period) == 3:
            try:
                return int(self.period[1:])
            except ValueError:
                return 0
        return 0


@dataclass(frozen=True)
class ForecastPoint:
    """One projected value for a target period, with uncertainty.

    Fields
    ------
    point : float
        Best estimate at the target period.
    se_total : float
        Combined 1-sigma standard error (sample + forecast model).
    se_sample : float
        Sample component (propagated ACS MOE; 0 for BLS-only forecasts).
    se_forecast : float
        Model component (residual variance × horizon scaling).
    ci90_low / ci90_high : float
        90% prediction interval bounds. Symmetric Gaussian; matches the
        Z=1.645 convention ACS itself uses.
    method : str
        Which model produced this row — `damped_log_trend`, `ar1`,
        `macro_anchor`, `ensemble`, etc. Lets back-test reports drill in.
    target_year : int
    geoid : str
        Empty string when the forecast is not geo-specific (e.g. national CPI).
    indicator : str
        ACS variable for ACS forecasts; BLS series_id for BLS forecasts.
    horizon : int
        Periods (years for ACS, months for BLS) from latest observation
        to the target.
    notes : str
        Free-form audit string (e.g. "capped at +10%/yr momentum ceiling").
    """
    point: float
    se_total: float
    se_sample: float
    se_forecast: float
    ci90_low: float
    ci90_high: float
    method: str
    target_year: int
    geoid: str
    indicator: str
    horizon: int
    notes: str = ""


@dataclass
class GeographySeries:
    """Sorted time series for a (geography, indicator) pair, mixed vintages.

    Holds the chronological observations the projection model consumes.
    The factory `from_observations` validates monotonic year ordering and
    rejects duplicate (year, vintage) pairs — duplicates would break the
    weighted-trend math silently.
    """
    geoid: str
    indicator: str
    observations: list[AcsObservation] = field(default_factory=list)

    @classmethod
    def from_observations(
        cls, geoid: str, indicator: str, obs: list[AcsObservation]
    ) -> "GeographySeries":
        for o in obs:
            if o.geoid != geoid or o.indicator != indicator:
                raise ValueError(
                    f"observation {o.geoid}/{o.indicator} does not match "
                    f"series {geoid}/{indicator}"
                )
        seen: set[tuple[int, str]] = set()
        for o in obs:
            key = (o.year, o.vintage)
            if key in seen:
                raise ValueError(f"duplicate observation for {key}")
            seen.add(key)
        ordered = sorted(obs, key=lambda x: (x.year, x.vintage))
        return cls(geoid=geoid, indicator=indicator, observations=ordered)

    def one_year(self) -> list[AcsObservation]:
        """1-year observations only, sorted by year."""
        return [o for o in self.observations if o.vintage == "1y"]

    def five_year(self) -> list[AcsObservation]:
        """5-year observations only, sorted by end year."""
        return [o for o in self.observations if o.vintage == "5y"]

    def latest(self, vintage: Optional[str] = None) -> Optional[AcsObservation]:
        """Most recent observation (optionally filtered by vintage)."""
        pool = self.observations if vintage is None else [
            o for o in self.observations if o.vintage == vintage
        ]
        return pool[-1] if pool else None
