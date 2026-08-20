"""Council on Revenues (COR) official projections bundled with the package.

The data file is refreshed by
``python -m census_forecaster.scripts.refresh_cor_iit`` and committed, so
reading it needs no network access and no optional dependency.

Consumers should call :func:`load_cor_iit_projections` rather than hardcoding a
vintage — COR meets on no fixed cadence (~4-5 times a year), and a transcribed
dict silently goes stale between meetings.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "cor" / "cor_iit_projections.json"


class CorDataUnavailable(RuntimeError):
    """The bundled COR data file is missing or unreadable."""


@lru_cache(maxsize=1)
def _load_raw() -> dict:
    if not DATA_PATH.exists():
        raise CorDataUnavailable(
            f"{DATA_PATH} not found — run "
            "`python -m census_forecaster.scripts.refresh_cor_iit`"
        )
    try:
        return json.loads(DATA_PATH.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise CorDataUnavailable(f"could not read {DATA_PATH}: {exc}") from exc


def load_cor_iit_projections(by: str = "tax_year") -> dict[int, float]:
    """Return {year: individual income tax projection in $M}.

    Parameters
    ----------
    by:
        ``"tax_year"`` (default) applies the repo's ``FY(n+1) = TY(n)``
        convention; ``"fiscal_year"`` returns the raw source keys.
    """
    key = {
        "tax_year": "projections_by_tax_year",
        "fiscal_year": "projections_by_fiscal_year",
    }.get(by)
    if key is None:
        raise ValueError(f"by must be 'tax_year' or 'fiscal_year', got {by!r}")
    return {int(k): float(v) for k, v in _load_raw()[key].items()}


def cor_vintage() -> str:
    """Meeting date (ISO) of the COR forecast the bundled data came from."""
    return str(_load_raw()["meeting_date"])


def cor_source_url() -> str:
    """URL of the attachment the bundled data was parsed from."""
    return str(_load_raw()["source_url"])
