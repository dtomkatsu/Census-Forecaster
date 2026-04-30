"""Bridge from tax_modeler's PUMS API onto :mod:`pums_estimator.fetch_pums`.

The original ctc-and-eitc project shipped its own ``src/data/pums_loader.py``
(now living at :mod:`tax_modeler.loaders.pums_loader`) which fetched PUMS
files directly from the Census API and applied tax-specific column renames.

Inside the Census-Forecaster monorepo, PUMS fetching is owned by the
:mod:`pums_estimator` package, which provides a leaner :func:`fetch_pums`
helper plus a :class:`PumsRecord` value object. This adapter re-shapes
``PumsRecord`` instances into the wide pandas DataFrame layout that
``tax_modeler.units`` expects, so callers can migrate off the legacy
``PUMSDataLoader`` class incrementally.

Use this module as the **preferred new API**. The legacy
``tax_modeler.loaders.pums_loader.PUMSDataLoader`` is still importable for
back-compat but will be removed in a future tax_modeler release.
"""
from __future__ import annotations

from typing import Sequence

try:
    import pandas as pd
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "pandas is required for tax_modeler.pums_adapter; "
        "install with `uv sync --package tax-modeler`."
    ) from e

from pums_estimator import PumsRecord, fetch_pums


def load_hawaii_pums(
    year: int = 2022,
    variables: Sequence[str] = (),
    api_key: str | None = None,
) -> pd.DataFrame:
    """Fetch Hawaii (state FIPS 15) PUMS records as a flat DataFrame.

    Each row is one ``PumsRecord`` flattened so its ``variables`` dict is
    expanded into top-level columns. The first three columns are always
    ``serial``, ``puma``, ``weight``; the rest are whatever variables the
    caller asked for.

    Parameters
    ----------
    year:
        Survey year (1-year ACS PUMS). Default 2022.
    variables:
        PUMS variable codes to include. Empty tuple returns the default set
        chosen by :func:`pums_estimator.fetch_pums`.
    api_key:
        Optional Census API key (override / supplement the
        ``CENSUS_API_KEY`` environment variable).

    Returns
    -------
    pd.DataFrame
        One row per PUMS housing unit; columns ``serial``, ``puma``,
        ``weight`` plus each requested variable.
    """
    records: list[PumsRecord] = fetch_pums(
        state_fips="15",
        variables=tuple(variables),
        year=year,
        api_key=api_key,
    )
    rows = [
        {"serial": r.serial, "puma": r.puma, "weight": r.weight, **r.variables}
        for r in records
    ]
    return pd.DataFrame(rows)
