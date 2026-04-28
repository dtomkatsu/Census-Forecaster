"""pums-estimator: county-level distribution estimation via PUMS microdata reweighting.

Estimates statistics not directly published by the Census Bureau — such as
the distribution of vehicle types by county — by reweighting ACS PUMS
microdata to match county-level control totals from census_forecaster.

Quick start
-----------
    >>> from pums_estimator import PumsRecord, CountyControls, SyntheticEstimatePoint
    >>> from pums_estimator.pums.client import fetch_pums
    >>> from pums_estimator.pums.crosswalk import load_crosswalk
    >>> from pums_estimator.estimation.synthetic import estimate_county_distribution

Statistical contract
--------------------
Results are *model-based estimates*, not direct survey estimates.  They
carry the uncertainty of both the PUMS sampling design and the raking
assumptions.  Do not treat them as equivalent to published ACS tables.
"""
from .models import PumsRecord, CountyControls, SyntheticEstimatePoint

__version__ = "0.1.0"

__all__ = [
    "PumsRecord",
    "CountyControls",
    "SyntheticEstimatePoint",
]
