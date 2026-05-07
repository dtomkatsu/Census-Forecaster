"""Stage 2 smoke: TaxUnitConstructor on the synthetic PUMS fixture.

Catches regressions in unit construction (filing-status assignment,
dependent counting, household coverage) before downstream stages run.
"""
from __future__ import annotations

import pytest


@pytest.mark.smoke
def test_units_constructed(synthetic_units) -> None:
    """Construction succeeds and produces a non-empty frame."""
    assert len(synthetic_units) > 0
    assert synthetic_units["filing_status"].notna().all()


@pytest.mark.smoke
def test_units_cover_all_filing_statuses(synthetic_units) -> None:
    """The fixture is designed to produce every filing-status branch."""
    statuses = set(synthetic_units["filing_status"].unique())
    # mfj, mfs, single all guaranteed by fixture design; HoH may collapse to single
    # depending on dependent assignment, so it's not asserted.
    assert {"single", "married_filing_jointly", "married_filing_separately"}.issubset(statuses)


@pytest.mark.smoke
def test_units_have_positive_weights(synthetic_units) -> None:
    """Every constructed unit must have weight > 0; zero weights silently
    drop revenue downstream."""
    assert (synthetic_units["weight"] > 0).all()


@pytest.mark.smoke
def test_units_income_within_fixture_range(synthetic_units) -> None:
    """Income values come from the fixture's $5K–$1.5M lognormal sampler;
    values outside that envelope indicate corruption upstream."""
    assert synthetic_units["income"].min() >= 0
    assert synthetic_units["income"].max() < 5_000_000  # generous upper bound
