"""tax_modeler — Hawaii income-tax + federal EITC microsimulation.

A self-contained microsimulation package for state-level income-tax
forecasting.  Currently configured for Hawaii (Act 46, SB 3125 CD1, HB 2306,
etc.) but structured so a future state plug-in is a config-file change, not
a refactor (see :class:`StateConfig`).

Quick start
-----------

::

    from tax_modeler import run_pipeline

    result = run_pipeline(target_year=2026)
    print(result.state_summary["hi_net_tax_revenue"])
    print(result.by_county)

Stable public API
-----------------

Use :data:`PUBLIC_API` to discover the supported surface.  Anything not in
that list is internal and may change without notice.  The most common
entry points:

- :func:`run_pipeline` — end-to-end, returns :class:`PipelineResult`
- :func:`enrich_for_credits` / :func:`compute_base_tax` / :func:`calibrate`
  — individual stages for advanced workflows
- :class:`TaxCalculator`, :class:`TaxSystemRegistry`, :func:`compare_systems`
  — bracket-comparison primitives
- :class:`RevenueEstimator` — population-weighted aggregation
- :class:`StateConfig`, :data:`HAWAII` — state-level constants

Errors
------

Boundary failures raise typed exceptions from :mod:`tax_modeler.errors`:
:class:`MissingDataError`, :class:`DataValidationError`, :class:`ConfigError`,
:class:`CalibrationError`.  All inherit from :class:`TaxModelerError` and
the appropriate Python builtin (``FileNotFoundError`` / ``ValueError`` /
``RuntimeError``) for backwards-compatible ``except`` blocks.
"""
from __future__ import annotations

# --- Errors -----------------------------------------------------------------
from .errors import (
    CalibrationError,
    ConfigError,
    DataValidationError,
    MissingDataError,
    TaxModelerError,
)

# --- Core domain types -------------------------------------------------------
from .units.base import FILING_STATUS, TaxUnitConstructor
from .liability.hawaii import HawaiiTaxParameters

# --- Tax liability + credits + deductions ------------------------------------
from .liability import calculate_hawaii_tax, calculate_hawaii_tax_for_units
from .credits import calculate_eitc, calculate_eitc_for_tax_units
from .brackets import HawaiiTaxCalculator, load_tax_data
from .deductions import (
    DeductionPolicy,
    TaxableIncomeCalculator,
    parse_deduction_benchmarks,
    parse_exemption_benchmarks,
)

# --- Tax-system orchestration ------------------------------------------------
from .config import (
    HAWAII,
    StateConfig,
    TaxCalculator,
    TaxSystemConfig,
    TaxSystemRegistry,
    compare_systems,
)

# --- Calibration -------------------------------------------------------------
from .calibration import (
    CalibrationOrchestrator,
    DOTAXSOIParser,
    IPFCalibrationOrchestrator,
    IPFCalibrator,
    apply_ipf_calibration,
    apply_ipf_calibration_via_rake,
    apply_systematic_calibration,
)

# --- Adjustments / credits ---------------------------------------------------
from .adjustments import (
    calculate_hawaii_credits,
    estimate_agi_from_total_income,
    estimate_deduction,
    scale_deduction_params_for_target_year,
    scale_eitc_for_poverty,
)
from .adjustments.hawaii_credits import HawaiiTaxCredits
from .adjustments.pareto_calibration import ParetoIncomeCalibrator
from .adjustments.ultra_high_income_synthesizer import UltraHighIncomeSynthesizer

# --- Validation --------------------------------------------------------------
from .validation import (
    DotaxTable12AValidator,
    apply_hybrid_tax_calibration,
    validate_against_table_12a,
    validate_hybrid_calibration,
)

# --- Revenue / analysis ------------------------------------------------------
from .revenue import RevenueEstimator, estimate_revenue
from .analysis import GeographicAnalyzer, assign_geography, load_crosswalk

# --- End-to-end pipeline -----------------------------------------------------
from .pipeline import (
    PipelineResult,
    calibrate,
    compute_base_tax,
    enrich_for_credits,
    run_pipeline,
)

# --- PUMS / projection (two entry points each) ------------------------------
# Simple "scalar / DataFrame" helpers — bridge to monorepo workspace packages.
from .pums_adapter import load_hawaii_pums
from .projection_adapter import project_income_growth

# Full-fat loaders kept from the original ctc-and-eitc — needed for batched
# population loading and tax-unit-vectorized income projection.
from .loaders.pums_loader import PUMSDataLoader, load_pums_data
from .projection import (
    AcsSupplement,
    EnsembleProjector,
    OccupationMatcher,
    project_acs_supplement,
    project_tax_units_forward,
    scale_mortgage_deductions,
)


__version__ = "0.2.0"


# ----------------------------------------------------------------------------
# Public API surface
#
# These are the symbols users should import.  They have stable signatures and
# documented behavior.  Everything else re-exported below is "internal but
# importable" — fine for power users who pin a version, but no compatibility
# guarantee across releases.
# ----------------------------------------------------------------------------

PUBLIC_API = (
    # End-to-end entry point
    "run_pipeline",
    "PipelineResult",
    # Pipeline stages (formerly underscore-private; underscore aliases remain
    # as deprecated shims in tax_modeler.pipeline).
    "enrich_for_credits",
    "compute_base_tax",
    "calibrate",
    # Tax math primitives
    "TaxUnitConstructor",
    "TaxCalculator",
    "TaxSystemConfig",
    "TaxSystemRegistry",
    "compare_systems",
    # Aggregation
    "RevenueEstimator",
    # State configuration
    "StateConfig",
    "HAWAII",
    # Errors (catch by intent)
    "TaxModelerError",
    "MissingDataError",
    "DataValidationError",
    "ConfigError",
    "CalibrationError",
)


__all__ = [
    # ── Stable public surface ─────────────────────────────────────────────
    *PUBLIC_API,
    # ── Internal but importable (no stability guarantee) ─────────────────
    "FILING_STATUS",
    "HawaiiTaxParameters",
    "calculate_hawaii_tax",
    "calculate_hawaii_tax_for_units",
    "calculate_eitc",
    "calculate_eitc_for_tax_units",
    "HawaiiTaxCalculator",
    "load_tax_data",
    "DeductionPolicy",
    "TaxableIncomeCalculator",
    "parse_deduction_benchmarks",
    "parse_exemption_benchmarks",
    "CalibrationOrchestrator",
    "apply_systematic_calibration",
    "IPFCalibrationOrchestrator",
    "apply_ipf_calibration",
    "apply_ipf_calibration_via_rake",
    "DOTAXSOIParser",
    "IPFCalibrator",
    "estimate_agi_from_total_income",
    "calculate_hawaii_credits",
    "estimate_deduction",
    "scale_deduction_params_for_target_year",
    "scale_eitc_for_poverty",
    "HawaiiTaxCredits",
    "ParetoIncomeCalibrator",
    "UltraHighIncomeSynthesizer",
    "DotaxTable12AValidator",
    "validate_against_table_12a",
    "apply_hybrid_tax_calibration",
    "validate_hybrid_calibration",
    "estimate_revenue",
    "GeographicAnalyzer",
    "assign_geography",
    "load_crosswalk",
    "load_hawaii_pums",
    "PUMSDataLoader",
    "load_pums_data",
    "project_income_growth",
    "EnsembleProjector",
    "OccupationMatcher",
    "project_tax_units_forward",
    "AcsSupplement",
    "project_acs_supplement",
    "scale_mortgage_deductions",
]
