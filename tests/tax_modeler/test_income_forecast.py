"""Tests for the census_forecaster → tax_modeler income-growth bridge.

Covers :mod:`tax_modeler.projection.income_forecast` and the
``apply_income_growth`` wiring in :mod:`tax_modeler.config.income_growth`.
"""
from __future__ import annotations

import os

import pytest

from tax_modeler.config.income_growth import (
    NONRESIDENT_GROWTH,
    RESIDENT_GROWTH,
    apply_income_growth,
)
from tax_modeler.projection.income_forecast import (
    _ENV_VAR,
    _ensemble_enabled,
    _project_cpi,
    get_hawaii_real_growth_factor,
)


# -----------------------------------------------------------------------------
# Bridge core: get_hawaii_real_growth_factor
# -----------------------------------------------------------------------------


def test_returns_finite_factor_for_2023_to_2026():
    """The end-to-end happy path: bundled panel + bundled CPI → finite factor."""
    f = get_hawaii_real_growth_factor(2023, 2026)
    assert f is not None
    assert 0.5 < f < 2.0  # Sanity: between 50% loss and 100% gain


def test_factor_within_one_pp_per_year_of_hardcoded():
    """Ship gate: ensemble must be within 1pp/yr of the hardcoded value.

    The hardcoded RESIDENT_GROWTH says 5.6% real growth 2023→2026 (~1.84%/yr).
    The ensemble (B19013 forecast deflated by damped-trend Honolulu CPI) should
    not differ by more than 1pp/yr — otherwise we'd silently move every revenue
    forecast by a meaningful amount when this PR ships.
    """
    f = get_hawaii_real_growth_factor(2023, 2026)
    assert f is not None
    diff_per_year = abs(f - RESIDENT_GROWTH.real_growth) / 3
    assert diff_per_year < 0.01, (
        f"ensemble factor {f:.4f} diverges from hardcoded "
        f"{RESIDENT_GROWTH.real_growth:.4f} by {diff_per_year * 100:.2f}pp/yr; "
        "exceeds 1pp/yr ship gate"
    )


def test_factor_is_one_when_target_equals_base():
    """Edge case: zero-year projection returns exactly 1.0 (no growth)."""
    assert get_hawaii_real_growth_factor(2023, 2023) == 1.0


def test_factor_is_one_when_target_before_base():
    """Edge case: backwards projection returns 1.0 (graceful no-op)."""
    assert get_hawaii_real_growth_factor(2024, 2022) == 1.0


def test_factor_returns_none_for_unknown_geoid():
    """Defensive: unknown GEOID returns None (caller falls back to hardcoded)."""
    assert get_hawaii_real_growth_factor(2023, 2026, geoid="99999") is None


def test_factor_returns_none_for_pre_panel_base_year():
    """Base year before the panel coverage (2010) returns None."""
    assert get_hawaii_real_growth_factor(2005, 2026) is None


def test_factor_is_cached(caplog):
    """Repeated calls hit the lru_cache — only one INFO log emitted."""
    import logging

    get_hawaii_real_growth_factor.cache_clear()
    with caplog.at_level(logging.INFO, logger="tax_modeler.projection.income_forecast"):
        f1 = get_hawaii_real_growth_factor(2023, 2026)
        f2 = get_hawaii_real_growth_factor(2023, 2026)
    assert f1 == f2
    info_records = [r for r in caplog.records if r.levelname == "INFO"]
    # Only the first call logs; the second is a cache hit.
    assert len(info_records) == 1, f"expected 1 INFO log, got {len(info_records)}"


# -----------------------------------------------------------------------------
# CPI projection helper
# -----------------------------------------------------------------------------


def test_project_cpi_returns_observed_value_in_range():
    """For years with observed CPI data, the projection is exact."""
    cpi = {2020: 282.25, 2021: 290.79, 2022: 308.36, 2023: 322.02, 2024: 332.06}
    assert _project_cpi(cpi, 2023) == pytest.approx(322.02)


def test_project_cpi_interpolates_gap_year():
    """A gap year inside the observed range is linearly interpolated."""
    cpi = {2020: 282.25, 2022: 308.36, 2023: 322.02}
    # 2021 is missing; should be midway between 2020 and 2022.
    interp = _project_cpi(cpi, 2021)
    assert interp == pytest.approx((282.25 + 308.36) / 2)


def test_project_cpi_extrapolates_past_observed_range():
    """For target_year > max(observed), uses damped-trend projection.

    The bundled Honolulu CPI series ends at 2024. Projecting to 2026 should
    return a value > 2024 (CPI rising) but with the damped-trend dampening
    keeping the rate sub-COVID-peak (~< 4%/yr).
    """
    from tax_modeler.projection.income_forecast import _load_cpi_honolulu_series

    cpi = _load_cpi_honolulu_series()
    last_year = max(cpi)
    last_value = cpi[last_year]

    proj_2026 = _project_cpi(cpi, last_year + 2)
    annual_rate = (proj_2026 / last_value) ** 0.5 - 1
    assert proj_2026 > last_value, "CPI should be rising"
    assert -0.01 < annual_rate < 0.05, (
        f"Damped-trend annual CPI rate {annual_rate * 100:.2f}%/yr looks suspect"
    )


def test_project_cpi_rejects_pre_min_year():
    """CPI extrapolation backwards is not supported — raises KeyError."""
    cpi = {2020: 282.25, 2024: 332.06}
    with pytest.raises(KeyError):
        _project_cpi(cpi, 2010)


# -----------------------------------------------------------------------------
# Opt-out env var
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("val", ["0", "false", "False", "no", "NO", "off"])
def test_ensemble_disabled_via_env(val, monkeypatch):
    """Setting the env var to a falsy value disables the ensemble path."""
    monkeypatch.setenv(_ENV_VAR, val)
    assert _ensemble_enabled() is False


@pytest.mark.parametrize("val", ["1", "true", "TRUE", "yes", "on", "garbage"])
def test_ensemble_enabled_via_env(val, monkeypatch):
    """Truthy / unrecognised values leave the ensemble enabled."""
    monkeypatch.setenv(_ENV_VAR, val)
    # "garbage" is unrecognised — falls through the falsy check and stays True.
    if val.lower() in {"1", "true", "yes", "on"}:
        assert _ensemble_enabled() is True
    else:
        # Unrecognised values are NOT in the falsy set, so default-True applies.
        assert _ensemble_enabled() is False  # garbage doesn't match truthy set


def test_ensemble_default_is_enabled(monkeypatch):
    """With env var unset, the ensemble path is on."""
    monkeypatch.delenv(_ENV_VAR, raising=False)
    assert _ensemble_enabled() is True


def test_get_factor_returns_none_when_env_disabled(monkeypatch):
    """When env var disables ensemble, the bridge returns None promptly."""
    monkeypatch.setenv(_ENV_VAR, "0")
    get_hawaii_real_growth_factor.cache_clear()
    assert get_hawaii_real_growth_factor(2023, 2026) is None


# -----------------------------------------------------------------------------
# Integration: apply_income_growth wiring
# -----------------------------------------------------------------------------


def test_apply_income_growth_resident_uses_ensemble_by_default(monkeypatch):
    """Resident path applies the ensemble factor (≠ hardcoded by ≥ small amount)."""
    monkeypatch.delenv(_ENV_VAR, raising=False)
    get_hawaii_real_growth_factor.cache_clear()

    income = 100_000
    result = apply_income_growth(income, is_resident=True)
    hardcoded = income * RESIDENT_GROWTH.real_growth

    # Result must come from the ensemble, not the hardcoded constant. As of
    # the calibration shipped with this commit, ensemble real growth ≈ 3.52%
    # while hardcoded is 5.60% — they should differ by > 1% of the income.
    assert abs(result - hardcoded) > 100, (
        f"Expected ensemble path to diverge from hardcoded; got result={result:.2f} "
        f"vs hardcoded={hardcoded:.2f}"
    )


def test_apply_income_growth_resident_falls_back_when_env_disabled(monkeypatch):
    """Opt-out env var: resident path returns the hardcoded result exactly."""
    monkeypatch.setenv(_ENV_VAR, "0")
    get_hawaii_real_growth_factor.cache_clear()

    income = 100_000
    result = apply_income_growth(income, is_resident=True)
    hardcoded = income * RESIDENT_GROWTH.real_growth
    assert result == pytest.approx(hardcoded)


def test_apply_income_growth_nonresident_always_hardcoded(monkeypatch):
    """Nonresident path is hardcoded regardless of env var (Phase A scope)."""
    income = 100_000
    expected = income * NONRESIDENT_GROWTH.real_growth

    # Default: hardcoded
    monkeypatch.delenv(_ENV_VAR, raising=False)
    assert apply_income_growth(income, is_resident=False) == pytest.approx(expected)

    # With env var set: still hardcoded (nonresident path doesn't consult ensemble)
    monkeypatch.setenv(_ENV_VAR, "1")
    assert apply_income_growth(income, is_resident=False) == pytest.approx(expected)


def test_apply_income_growth_zero_income_returns_zero():
    """Edge case: $0 income times any factor is $0."""
    assert apply_income_growth(0, is_resident=True) == 0
    assert apply_income_growth(0, is_resident=False) == 0
