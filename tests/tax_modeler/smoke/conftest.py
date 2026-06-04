"""Shared fixtures for tax_modeler smoke tests.

Smoke tests run on the deterministic 50-household synthetic PUMS at
``tests/tax_modeler/fixtures/synthetic_pums_*.parquet``.  No real PUMS,
DOTAX, or IRS data is required — anything missing should be caught by
:class:`tax_modeler.errors.MissingDataError` long before a smoke test
hits it.

To regenerate the fixture (e.g. after a schema change), run::

    python tests/tax_modeler/fixtures/_build_fixture.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
PERSONS_PATH = FIXTURE_DIR / "synthetic_pums_persons.parquet"
HOUSEHOLDS_PATH = FIXTURE_DIR / "synthetic_pums_households.parquet"


def pytest_addoption(parser):  # noqa: D401  (pytest hook)
    """Add ``--update-golden`` so the golden-revenue test can refresh its
    checked-in baseline when math changes intentionally."""
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Regenerate golden_revenue.json from the current run instead of asserting.",
    )


@pytest.fixture(scope="session")
def synthetic_persons() -> pd.DataFrame:
    if not PERSONS_PATH.exists():
        pytest.fail(
            f"Synthetic person fixture missing at {PERSONS_PATH}.\n"
            "Regenerate with `python tests/tax_modeler/fixtures/_build_fixture.py`."
        )
    return pd.read_parquet(PERSONS_PATH)


@pytest.fixture(scope="session")
def synthetic_households() -> pd.DataFrame:
    if not HOUSEHOLDS_PATH.exists():
        pytest.fail(
            f"Synthetic household fixture missing at {HOUSEHOLDS_PATH}.\n"
            "Regenerate with `python tests/tax_modeler/fixtures/_build_fixture.py`."
        )
    return pd.read_parquet(HOUSEHOLDS_PATH)


@pytest.fixture(scope="session")
def synthetic_units(synthetic_persons, synthetic_households) -> pd.DataFrame:
    """Tax units produced by ``TaxUnitConstructor`` on the synthetic PUMS.

    Session-scoped because construction is the slowest single step in the
    smoke pipeline (~0.5-1.0s on a laptop) and downstream stages all need
    the same starting frame.
    """
    from tax_modeler.units.constructor import TaxUnitConstructor

    ctor = TaxUnitConstructor(
        synthetic_persons.copy(),
        synthetic_households.copy(),
        use_soi_calibration=False,
        progress_bar=False,
    )
    return ctor.create_rule_based_units(parallel=False)


@pytest.fixture(scope="session")
def enriched_units(synthetic_units) -> pd.DataFrame:
    from tax_modeler.pipeline import enrich_for_credits

    return enrich_for_credits(synthetic_units)


@pytest.fixture(scope="session")
def taxed_units(enriched_units) -> pd.DataFrame:
    from tax_modeler.pipeline import compute_base_tax

    return compute_base_tax(enriched_units)
