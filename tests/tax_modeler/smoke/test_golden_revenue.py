"""Golden-output regression: revenue totals on the synthetic fixture.

Compares aggregate revenue against checked-in expected values within a
±2% tolerance.  This catches accidental drift in bracket math, credit
overlay, or aggregation that wouldn't surface in the type/shape checks
of the per-stage smoke tests.

When the underlying math changes intentionally (e.g. new bracket
schedule, credit-overlay update), regenerate the baseline::

    pytest tests/tax_modeler/smoke/test_golden_revenue.py --update-golden

The ``--update-golden`` flag is wired up via :func:`pytest_addoption`
in this file's :func:`pytest_configure`-adjacent hook.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "golden_revenue.json"


def _load_golden() -> dict:
    with GOLDEN_PATH.open() as f:
        return json.load(f)


def _save_golden(payload: dict) -> None:
    payload.setdefault(
        "_comment",
        "Golden revenue values; regenerate with `pytest --update-golden`.",
    )
    payload["tolerance_pct"] = payload.get("tolerance_pct", 2.0)
    with GOLDEN_PATH.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def _within_tol(actual: float, expected: float, tol_pct: float) -> bool:
    if expected == 0:
        return abs(actual) <= tol_pct
    return abs(actual - expected) / abs(expected) <= tol_pct / 100.0


@pytest.mark.smoke
def test_golden_state_summary(taxed_units, request) -> None:
    """State-level totals must match committed values within tolerance."""
    from tax_modeler.revenue.estimator import RevenueEstimator

    estimator = RevenueEstimator(taxed_units)
    summary = estimator.state_summary()
    quintile = estimator.by_income_quintile()

    actual = {
        "hi_net_tax_revenue": float(summary["hi_net_tax_revenue"]),
        "total_weighted_filers": float(summary["total_weighted_filers"]),
        "quintile_hi_gross_tax": [float(x) for x in quintile["hi_gross_tax"].tolist()],
    }

    if request.config.getoption("--update-golden"):
        _save_golden(actual)
        pytest.skip("Golden values regenerated; rerun without --update-golden to assert.")

    golden = _load_golden()
    tol = float(golden.get("tolerance_pct", 2.0))

    assert _within_tol(
        actual["hi_net_tax_revenue"], golden["hi_net_tax_revenue"], tol
    ), (
        f"hi_net_tax_revenue drift: {actual['hi_net_tax_revenue']:,.0f} "
        f"vs golden {golden['hi_net_tax_revenue']:,.0f} (tol ±{tol}%)"
    )
    assert _within_tol(
        actual["total_weighted_filers"], golden["total_weighted_filers"], tol
    ), (
        f"total_weighted_filers drift: {actual['total_weighted_filers']:,.0f} "
        f"vs golden {golden['total_weighted_filers']:,.0f}"
    )

    expected_q = golden["quintile_hi_gross_tax"]
    actual_q = actual["quintile_hi_gross_tax"]
    assert len(actual_q) == len(expected_q), (
        f"Quintile count changed: {len(actual_q)} vs {len(expected_q)}"
    )
    for i, (a, e) in enumerate(zip(actual_q, expected_q)):
        assert _within_tol(a, e, tol), (
            f"Q{i+1} hi_gross_tax drift: {a:,.0f} vs golden {e:,.0f} (tol ±{tol}%)"
        )
