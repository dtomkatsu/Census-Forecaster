"""SPM resource calculation and Hawaii-specific poverty thresholds.

The :func:`compute_spm_resources` function aggregates post-tax-and-transfer
resources at the SPM unit level using the components ``tax_modeler``
already computes (Hawaii income tax, federal EITC/CTC). Components not
yet modeled (SNAP, housing, MOOP, childcare expenses) are accepted as
input columns or scalars; they default to zero and the function
documents the resulting bias.

Phase 2 ships the *resource calculation*; Phase 3 wires SNAP/SSI into
it as those benefit modules land. MOOP / childcare / work-expense
imputation is a later phase (the synthetic fixture cannot exercise it).
"""
from __future__ import annotations

from .impact import PovertyImpactResult, compute_poverty_impact
from .spm import compute_spm_resources
from .thresholds import hawaii_spm_threshold, spm_threshold_table, threshold_for_units

__all__ = [
    "compute_spm_resources",
    "compute_poverty_impact",
    "PovertyImpactResult",
    "hawaii_spm_threshold",
    "spm_threshold_table",
    "threshold_for_units",
]
