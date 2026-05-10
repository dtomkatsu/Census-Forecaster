"""Reform-as-data: a small DSL for tax + benefit policy counterfactuals.

A :class:`Reform` is a frozen description of what to change relative to a
baseline. Today it supports two payloads:

* ``tax_system_factory`` — a callable ``year -> TaxSystemConfig`` that
  produces the *scenario* tax system. The existing
  :class:`tax_modeler.config.tax_system_config.TaxSystemRegistry` factory
  methods (``get_act46_system``, ``get_sb3125_cd1_system``, etc.) plug
  in directly.
* ``benefit_overrides`` — a mapping like
  ``{"snap": {"max_benefit_pct": 0.90}, "ssi": {"federal_payment_pct": 0.95}}``
  that the Phase 3 benefit modules will read. Phase 1 stores it but has
  no benefit machinery to apply it; reforms with ``benefit_overrides``
  emit a :class:`UserWarning` until those modules land.

:func:`apply_reform` runs the comparison and returns a
:class:`ReformResult` with both worlds and the summary deltas.
"""
from __future__ import annotations

from .reform import (
    TAX_SYSTEM_FACTORY_REGISTRY,
    Reform,
    ReformResult,
    apply_reform,
    register_tax_system,
)

__all__ = [
    "Reform",
    "ReformResult",
    "apply_reform",
    "register_tax_system",
    "TAX_SYSTEM_FACTORY_REGISTRY",
]
