"""Stage 7 smoke: RevenueEstimator aggregates without losing dollars.

The estimator is a pure aggregation layer.  This test guards against
weight-vs-tax-column mismatches and the classic "summary doesn't match
breakdown" bug.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def estimator(taxed_units):
    from tax_modeler.revenue.estimator import RevenueEstimator

    return RevenueEstimator(taxed_units)


@pytest.mark.smoke
def test_state_summary_revenue_positive(estimator) -> None:
    summary = estimator.state_summary()
    assert summary["total_weighted_filers"] > 0
    # Revenue is non-negative; on the synthetic fixture it must be > 0
    # because the income mix includes $200K+ units.
    assert summary.get("hi_net_tax_revenue", 0) > 0


@pytest.mark.smoke
def test_breakdowns_return_dataframes(estimator, taxed_units) -> None:
    """Each cut returns a non-empty DataFrame so consumers can iterate.

    ``by_county`` requires geographic assignment (PUMA→county crosswalk)
    that the synthetic fixture skips; tested via filing-status and
    quintile cuts instead.
    """
    by_filing = estimator.by_filing_status()
    by_quintile = estimator.by_income_quintile()
    assert len(by_filing) > 0
    assert len(by_quintile) > 0
    # Only assert by_county when geography has been assigned upstream.
    if "county" in taxed_units.columns:
        by_county = estimator.by_county()
        assert len(by_county) > 0


@pytest.mark.smoke
def test_filing_status_breakdown_sums_to_state(estimator) -> None:
    """Filing-status revenue should sum to (within a tight tolerance of)
    the state-level total.  If not, weights are being dropped somewhere."""
    summary = estimator.state_summary()
    by_filing = estimator.by_filing_status()
    state_total = summary["hi_net_tax_revenue"]

    # Find the revenue column (estimator may name it differently across versions)
    rev_col = next(
        (c for c in by_filing.columns if "revenue" in c.lower() or "tax" in c.lower()),
        None,
    )
    assert rev_col is not None, f"No revenue column in {list(by_filing.columns)}"

    breakdown_total = float(by_filing[rev_col].sum())
    # Allow 1% drift for binning rounding; bigger gaps indicate a real bug
    assert abs(breakdown_total - state_total) / max(abs(state_total), 1.0) < 0.01, \
        f"Filing-status breakdown {breakdown_total:,.0f} != state total {state_total:,.0f}"
