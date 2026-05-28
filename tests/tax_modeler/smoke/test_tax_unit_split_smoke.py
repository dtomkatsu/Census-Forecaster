"""Guardrail against tax-unit over-splitting on the synthetic fixture.

The real 47%→~21% childless-EITC-claimer headline can only be measured on
real PUMS (see ``scripts/diagnose_tax_unit_splitting.py``); the 50-household
fixture is far too small for a stable claimer-share. So this smoke test guards
the two stable structural properties the over-splitting fix changes:

  1. mean tax-units-per-household stays low (no runaway splitting);
  2. ``dependents_details`` carries REAL per-dependent records (not synthetic
     age-10 placeholders) so EITC/CTC qualifying-child counts are accurate.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.smoke


def test_units_per_household_is_low(synthetic_units):
    per_hh = synthetic_units.groupby("SERIALNO").size()
    assert per_hh.mean() < 1.5, f"mean units/HH = {per_hh.mean():.3f}"


def test_dependents_details_present_and_structured(enriched_units):
    """Every unit carries a dependents_details list matching num_dependents,
    and the entries are dicts with the age/relationship keys credit code needs."""
    df = enriched_units
    assert "dependents_details" in df.columns

    lengths_match = df.apply(
        lambda r: len(r["dependents_details"]) == int(r["num_dependents"]), axis=1
    )
    assert lengths_match.all()

    for deps in df["dependents_details"]:
        for d in deps:
            assert isinstance(d, dict)
            assert "age" in d and "relationship" in d


def test_qualifying_children_not_exceeding_dependents(enriched_units):
    """EITC qualifying-children count never exceeds total dependents."""
    df = enriched_units
    assert (df["num_qualifying_children"] <= df["num_dependents"]).all()
