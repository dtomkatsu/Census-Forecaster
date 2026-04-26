"""Operational scripts shipped with the package.

These are CLI entry points that operate on bundled or freshly fetched
data. Distinct from the library API in `census_forecaster` proper —
these scripts have side effects (network calls, file writes) and are
meant to be invoked manually via `python -m census_forecaster.scripts.<name>`.
"""
