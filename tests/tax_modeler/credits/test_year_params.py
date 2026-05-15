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
    {'age': 8, 'relationship': 22, 'citizenship': 1},
    {'age': 12, 'relationship': 22, 'citizenship': 1},
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
