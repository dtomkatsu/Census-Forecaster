"""Entity layer: Person, TaxUnit, SPMUnit, Household.

This module provides a thin abstraction over the column-oriented unit
DataFrames produced by ``TaxUnitConstructor``. Tax-modeling code keeps
operating on DataFrames; benefit-modeling code (SNAP, SSI, TANF, ACA-PTC,
etc.) operates on entity views because eligibility and resource pooling
happen at different aggregations than tax filing.

Identifier conventions (preserved from PUMS / TaxUnitConstructor):

  - ``SERIALNO``                household identifier (string)
  - ``hh_id``                   alias of SERIALNO
  - ``primary_filer_id``        ``SERIALNO_SPORDER`` of primary filer
  - ``secondary_filer_id``      ``SERIALNO_SPORDER`` of spouse on joint
                                returns; otherwise ``"0"``
  - ``dependent_person_ids``    list of ``SERIALNO_SPORDER`` strings
                                (preserved by ``enrich_for_credits``)

The :class:`EntityGraph` constructs lookup indexes once and exposes
accessors for iterating people, tax units, SPM units, and households.
Each entity dataclass is a *view* — the underlying truth is the
DataFrame held by the graph.

For SPM unit assignment, Phase 1 ships a conservative default:
*one SPMUnit per Household*. The Census P60-280 cohabitor-and-unrelated-
children logic is a Phase 2 refinement; the placeholder works fine for
households that look like single SPM units (most), and the API does not
change when it is upgraded.
"""
from __future__ import annotations

from .graph import (
    EntityGraph,
    Household,
    Person,
    SPMUnit,
    TaxUnit,
)

__all__ = [
    "EntityGraph",
    "Household",
    "Person",
    "SPMUnit",
    "TaxUnit",
]
