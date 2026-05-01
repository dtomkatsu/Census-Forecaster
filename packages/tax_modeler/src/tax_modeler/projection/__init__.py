"""
Ensemble growth projection system for Hawaii tax revenue forecasting.

This module provides income projection capabilities that combine:
- ACS demographic and income trends
- BLS OES occupation-specific wage growth
- Hierarchical matching strategies with confidence scoring
"""

from __future__ import annotations

from .ensemble import EnsembleProjector
from .occupation_matcher import OccupationMatcher
from .tax_unit_projector import project_tax_units_forward
from .acs_supplement_forecast import AcsSupplement, project_acs_supplement, scale_mortgage_deductions

__all__ = [
    'EnsembleProjector',
    'OccupationMatcher',
    'project_tax_units_forward',
    'AcsSupplement',
    'project_acs_supplement',
    'scale_mortgage_deductions',
]
