"""Tests for year-specific EITC/CTC parameters.

Each EITC year asserts the IRS Rev. Proc. max-credit value to the dollar
for the 2-child bracket at the saturation point (earned income at
``phase_in_ends`` for that bracket, single filer). CTC tests verify the
year-specific refundable-per-child cap.
"""

from __future__ import annotations

import pytest

from tax_modeler.credits.eitc import (
    EITCParameters,
    calculate_eitc,
    eitc_parameters_for_year,
)
from tax_modeler.credits.ctc import (
    CTCParameters,
    calculate_ctc,
    ctc_parameters_for_year,
)


# Two qualifying children, valid PUMS-style relationship + citizenship codes.
_TWO_KID_DEPS = [
    {'age': 8, 'relationship': 25, 'citizenship': 1},
    {'age': 12, 'relationship': 25, 'citizenship': 1},
]


@pytest.mark.parametrize(
    "tax_year,expected_max",
    [
        (2022, 6_164),
        (2023, 6_604),
        (2024, 6_960),
        (2025, 7_152),
    ],
)
def test_eitc_max_credit_2_kids_matches_irs_table(tax_year, expected_max):
    """At the saturation point, EITC = max credit per the year's IRS table."""
    params = eitc_parameters_for_year(tax_year)
    bracket = params.by_children[2]
    # Earned income at the saturation point gives the max credit.
    unit = {
        'filing_status': 'single',
        'income': bracket.phase_in_ends,
        'earned_income': bracket.phase_in_ends,
        'investment_income': 0,
        'dependents_details': _TWO_KID_DEPS,
        'num_dependents': 2,
    }
    result = calculate_eitc(unit, tax_year=tax_year)
    assert result['eitc_eligible'] is True
    assert result['eitc_qualifying_children'] == 2
    assert result['eitc_amount'] == pytest.approx(expected_max, abs=1.0)


@pytest.mark.parametrize(
    "tax_year,expected_zero_kid_max",
    [
        (2022, 560),
        (2023, 600),
        (2024, 632),
        (2025, 649),
    ],
)
def test_eitc_zero_kid_max_matches_irs_table(tax_year, expected_zero_kid_max):
    params = eitc_parameters_for_year(tax_year)
    assert params.by_children[0].max_credit == expected_zero_kid_max


@pytest.mark.parametrize(
    "tax_year,one_kid,three_kid",
    [
        (2022, 3_733, 6_935),
        (2023, 3_995, 7_430),
        (2024, 4_213, 7_830),
        (2025, 4_328, 8_046),
    ],
)
def test_eitc_one_and_three_kid_max_match_irs_table(tax_year, one_kid, three_kid):
    params = eitc_parameters_for_year(tax_year)
    assert params.by_children[1].max_credit == one_kid
    assert params.by_children[3].max_credit == three_kid


def test_eitc_unsupported_year_raises():
    with pytest.raises(KeyError):
        eitc_parameters_for_year(2019)


def test_eitc_default_remains_2023():
    """Default no-arg EITCParameters must still reflect TY 2023 (back-compat)."""
    default = EITCParameters()
    assert default.investment_income_limit == 11_000
    assert default.by_children[2].max_credit == 6_604
    assert default.by_children[3].max_credit == 7_430


@pytest.mark.parametrize(
    "tax_year,refundable_cap",
    [
        (2022, 1_500),
        (2023, 1_600),
        (2024, 1_700),
        (2025, 1_700),
    ],
)
def test_ctc_refundable_cap_by_year(tax_year, refundable_cap):
    params = ctc_parameters_for_year(tax_year)
    assert params.refundable_limit_per_child == refundable_cap
    assert params.max_credit_per_child == 2_000  # TCJA statutory cap unchanged


def test_ctc_unsupported_year_raises():
    with pytest.raises(KeyError):
        ctc_parameters_for_year(2017)


def test_ctc_default_remains_2023():
    """Default no-arg CTCParameters must still reflect TY 2023."""
    default = CTCParameters()
    assert default.refundable_limit_per_child == 1_600
    assert default.max_credit_per_child == 2_000


# ---------------------------------------------------------------------------
# CPI extrapolation past the last published Rev. Proc. (F5)
# ---------------------------------------------------------------------------

def test_eitc_extrapolation_off_by_default():
    with pytest.raises(KeyError):
        eitc_parameters_for_year(2027)


def test_eitc_extrapolated_params_grow_and_round():
    from tax_modeler.credits.eitc import CREDIT_PARAM_CPI_GROWTH

    base = eitc_parameters_for_year(2025)
    p2027 = eitc_parameters_for_year(2027, extrapolate=True)
    factor = (1.0 + CREDIT_PARAM_CPI_GROWTH) ** 2

    # Dollar params scale by the CPI factor with statutory rounding.
    assert p2027.by_children[2].max_credit == pytest.approx(
        base.by_children[2].max_credit * factor, abs=5.0
    )
    assert p2027.by_children[2].max_credit % 10 == 0          # IRC §32(j): nearest $10
    assert p2027.investment_income_limit % 50 == 0            # invest limit: nearest $50
    assert p2027.investment_income_limit > base.investment_income_limit
    assert p2027.by_children[1].phaseout_start_joint > base.by_children[1].phaseout_start_joint

    # Statutory rates do NOT scale.
    for n in (0, 1, 2, 3):
        assert p2027.by_children[n].phase_in_rate == base.by_children[n].phase_in_rate
        assert p2027.by_children[n].phaseout_rate == base.by_children[n].phaseout_rate


def test_eitc_extrapolation_published_year_unchanged():
    """extrapolate=True must not alter published years."""
    assert (
        eitc_parameters_for_year(2024, extrapolate=True).by_children[2].max_credit
        == eitc_parameters_for_year(2024).by_children[2].max_credit
    )


def test_eitc_extrapolation_does_not_backfill_early_years():
    with pytest.raises(KeyError):
        eitc_parameters_for_year(2019, extrapolate=True)


def test_eitc_extrapolation_monotone_over_horizon():
    prev = eitc_parameters_for_year(2025).by_children[2].max_credit
    for yr in range(2026, 2032):
        cur = eitc_parameters_for_year(yr, extrapolate=True).by_children[2].max_credit
        assert cur >= prev
        prev = cur


def test_ctc_extrapolation_off_by_default():
    with pytest.raises(KeyError):
        ctc_parameters_for_year(2027)


def test_ctc_extrapolated_cap_floors_to_100_and_respects_max():
    p2027 = ctc_parameters_for_year(2027, extrapolate=True)
    # 1_700 × 1.021² ≈ 1_772 → floor to $1,700 per §24(d)(4)(B).
    assert p2027.refundable_limit_per_child == 1_700
    p2031 = ctc_parameters_for_year(2031, extrapolate=True)
    # 1_700 × 1.021⁶ ≈ 1_925 → floor to $1,900.
    assert p2031.refundable_limit_per_child == 1_900
    assert p2031.refundable_limit_per_child % 100 == 0
    # Statutory TCJA values never move.
    assert p2031.max_credit_per_child == 2_000
    assert p2031.phaseout_threshold_single == 200_000
    assert p2031.phaseout_threshold_joint == 400_000
    # And the cap can never exceed the $2,000 max credit.
    far = ctc_parameters_for_year(2045, extrapolate=True)
    assert far.refundable_limit_per_child <= 2_000


def test_eitc_calculate_with_extrapolation_keeps_real_value():
    """A unit at the TY2025 saturation point scaled forward by CPI should
    still receive (approximately) the scaled max credit — the F5 regression
    was credits phasing out early because params stayed at TY2025."""
    from tax_modeler.credits.eitc import CREDIT_PARAM_CPI_GROWTH

    base = eitc_parameters_for_year(2025).by_children[2]
    factor = (1.0 + CREDIT_PARAM_CPI_GROWTH) ** 6  # TY2031
    unit = {
        'filing_status': 'single',
        'income': base.phase_in_ends * factor,
        'earned_income': base.phase_in_ends * factor,
        'investment_income': 0,
        'dependents_details': _TWO_KID_DEPS,
        'num_dependents': 2,
    }
    result = calculate_eitc(unit, tax_year=2031, extrapolate=True)
    assert result['eitc_eligible'] is True
    assert result['eitc_amount'] == pytest.approx(base.max_credit * factor, rel=0.01)


def test_ctc_actc_uses_year_refundable_cap_2_kids():
    """ACTC cap differs by year: $1,500 (2022) vs $1,700 (2025) per child."""
    # Earned income high enough that 15% × (EI − 2_500) saturates the
    # refundable cap for both kids.
    unit = {
        'filing_status': 'single',
        'income': 60_000,
        'earned_income': 60_000,
        'dependents': [
            {'age': 8, 'relationship': '22', 'citizenship': '1'},
            {'age': 12, 'relationship': '22', 'citizenship': '1'},
        ],
        'num_dependents': 2,
    }

    r2022 = calculate_ctc(unit, tax_year=2022)
    r2025 = calculate_ctc(unit, tax_year=2025)

    assert r2022['qualifying_children'] == 2
    assert r2025['qualifying_children'] == 2
    # 15% × (60_000 − 2_500) = 8_625 → saturates each year's cap.
    assert r2022['ctc_refundable'] == pytest.approx(2 * 1_500)
    assert r2025['ctc_refundable'] == pytest.approx(2 * 1_700)
    # Total CTC capped at $2,000/child either way (no phaseout at $60K).
    assert r2022['ctc_total'] == 4_000
    assert r2025['ctc_total'] == 4_000
