"""Hypothetical / proposed cash-transfer programs evaluated by the modeler.

Distinct from :mod:`tax_modeler.benefits` (programs that exist today and
need to be modeled to reproduce the current SPM baseline). Modules here
represent *policy proposals* — programs that don't yet exist in Hawaii
but that the modeler can evaluate as anti-poverty interventions.

Each module exports:
  * a frozen ``...Params`` dataclass
  * a default-parameters factory (``hawaii_*_parameters``)
  * a ``compute_*_for_units(units, ...)`` function that adds an amount
    column suitable for adding to ``spm_resources``
"""
from __future__ import annotations

from .rxkids_hi import (
    RxKidsHIParams,
    compute_rxkids_for_units,
    hawaii_rxkids_parameters,
)

__all__ = [
    "RxKidsHIParams",
    "compute_rxkids_for_units",
    "hawaii_rxkids_parameters",
]
