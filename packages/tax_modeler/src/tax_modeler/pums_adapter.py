"""Bridge from tax_modeler's PUMS API onto :mod:`pums_estimator.fetch_pums`.

This module exposes a **simple** PUMS-as-DataFrame helper that delegates
to :func:`pums_estimator.fetch_pums` (the workspace's canonical PUMS
fetcher). It re-shapes :class:`pums_estimator.PumsRecord` instances into
the wide pandas DataFrame layout that ``tax_modeler.units`` expects.

When to use which PUMS entry point:

  - **Use this adapter** for typical needs: "give me Hawaii PUMS for
    year Y as a DataFrame I can pass to tax-unit construction." It's
    one function call, no batching machinery to reason about, and
    delegates caching to ``pums_estimator``.

  - **Use** :class:`tax_modeler.loaders.pums_loader.PUMSDataLoader`
    when you need its specific features that don't exist in
    ``pums_estimator``: incremental batched loading
    (``load_households_batch``), explicit person-vs-household column
    splits, PUMS vintage column-rename handling (``STATE`` →
    ``ST``), and the ``create_tax_units`` shortcut. These are
    important for full-population pipeline runs but overkill for
    most analysis.

The two paths coexist intentionally — they cover different use cases.
Both are exported at the package level via :mod:`tax_modeler.__init__`.
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
