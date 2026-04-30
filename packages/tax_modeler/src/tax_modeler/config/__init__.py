"""Tax system configuration package."""

from __future__ import annotations

from .tax_system_config import (
    TaxSystemConfig,
    TaxSystemRegistry,
    TaxCalculator,
    compare_systems
)

__all__ = [
    'TaxSystemConfig',
    'TaxSystemRegistry',
    'TaxCalculator',
    'compare_systems'
]
