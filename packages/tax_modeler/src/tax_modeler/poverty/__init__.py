"""Poverty-impact module for Hawaii tax microsimulation."""

from __future__ import annotations

from .spm_aggregation import (
    compute_spm_resources,
    compute_spm_threshold,
    flag_spm_poor,
    SPM_THRESHOLD_BASE_4PERSON_2022,
    SPM_HI_RPP_2022,
)
from .impact import (
    compute_poverty_impact,
    compute_poverty_impact_with_se,
    _apply_federal_tax_fallback,
    HI_EITC_BASE_TAKEUP,
    HI_EITC_100PCT_TAKEUP,
    ARPA_CTC_TAKEUP,
)

__all__: list[str] = [
    "compute_spm_resources",
    "compute_spm_threshold",
    "flag_spm_poor",
    "SPM_THRESHOLD_BASE_4PERSON_2022",
    "SPM_HI_RPP_2022",
    "compute_poverty_impact",
    "compute_poverty_impact_with_se",
    "_apply_federal_tax_fallback",
    "HI_EITC_BASE_TAKEUP",
    "HI_EITC_100PCT_TAKEUP",
    "ARPA_CTC_TAKEUP",
]
