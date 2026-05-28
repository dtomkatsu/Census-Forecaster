"""
Tests for EITC calculations, including IRC §32(c)(1)(A)(ii) age 25-64 rule
for childless filers.
"""

from __future__ import annotations

import pytest

from tax_modeler.credits.eitc import calculate_eitc


def _childless_unit(age: int, earned_income: float = 15_000) -> dict:
    return {
        'filing_status': 'single',
        'income': earned_income,
        'earned_income': earned_income,
        'investment_income': 0.0,
        'dependents_details': [],
        'primary_agep': age,
    }


def _parent_unit(primary_age: int, earned_income: float = 20_000) -> dict:
    return {
        'filing_status': 'single',
        'income': earned_income,
        'earned_income': earned_income,
        'investment_income': 0.0,
        'dependents_details': [
            {'age': 5, 'relationship': 22, 'citizenship': 1},
        ],
        'primary_agep': primary_age,
    }


# --- IRC §32(c)(1)(A)(ii) age rule for childless filers ---

def test_childless_age_24_gets_no_eitc():
    result = calculate_eitc(_childless_unit(age=24))
    assert result['eitc_amount'] == 0.0
    assert result['eitc_eligible'] is False


def test_childless_age_25_gets_eitc():
    result = calculate_eitc(_childless_unit(age=25))
    assert result['eitc_amount'] > 0
    assert result['eitc_eligible'] is True


def test_childless_age_64_gets_eitc():
    result = calculate_eitc(_childless_unit(age=64))
    assert result['eitc_amount'] > 0
    assert result['eitc_eligible'] is True


def test_childless_age_65_gets_no_eitc():
    result = calculate_eitc(_childless_unit(age=65))
    assert result['eitc_amount'] == 0.0
    assert result['eitc_eligible'] is False


def test_parent_age_20_unaffected_by_age_rule():
    """A 20-year-old with a qualifying child is still eligible."""
    result = calculate_eitc(_parent_unit(primary_age=20))
    assert result['eitc_amount'] > 0
    assert result['eitc_eligible'] is True
    assert result['eitc_qualifying_children'] == 1


def test_missing_age_defaults_eligible():
    """If primary_agep is absent, default to 40 (assume eligible)."""
    unit = {
        'filing_status': 'single',
        'income': 15_000,
        'earned_income': 15_000,
        'investment_income': 0.0,
        'dependents_details': [],
    }
    result = calculate_eitc(unit)
    assert result['eitc_amount'] > 0


# --- Coupling guard: attached adult relatives are not EITC qualifying children ---

def test_attached_adult_relative_not_eitc_qualifying_child():
    """A filer who claims an elderly parent (or other adult relative) as a
    dependent must NOT count that adult as an EITC qualifying child. Guards the
    Part 2 coupling: once dependents carry real ages, the qualifying-child
    count excludes adult dependents."""
    unit = {
        'filing_status': 'single',
        'income': 15_000,
        'earned_income': 15_000,
        'investment_income': 0.0,
        'primary_agep': 45,
        'dependents_details': [
            {'age': 70, 'relationship': 27, 'citizenship': 1},  # elderly parent
        ],
    }
    result = calculate_eitc(unit)
    assert result['eitc_qualifying_children'] == 0


def test_mixed_dependents_counts_only_qualifying_child():
    """With one young child and one elderly parent, only the child counts as an
    EITC qualifying child."""
    unit = {
        'filing_status': 'head_of_household',
        'income': 20_000,
        'earned_income': 20_000,
        'investment_income': 0.0,
        'primary_agep': 40,
        'dependents_details': [
            {'age': 8, 'relationship': 22, 'citizenship': 1},   # qualifying child
            {'age': 72, 'relationship': 27, 'citizenship': 1},  # elderly parent
        ],
    }
    result = calculate_eitc(unit)
    assert result['eitc_qualifying_children'] == 1
