"""tax_modeler — Hawaii income tax + federal EITC microsimulation.

Imported from `ctc-and-eitc` and integrated into the Census-Forecaster
monorepo as a fourth workspace package alongside `common`,
`census_forecaster`, and `pums_estimator`.

The public API below re-exports the most commonly-used symbols from each
submodule. For lower-level access, import directly from the submodule
(e.g. `from tax_modeler.calibration.ipf_calibration import IPFCalibrator`).
"""
from __future__ import annotations

# --- Core domain types -------------------------------------------------------
from .units.base import TaxUnitConstructor, FILING_STATUS
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
    TaxSystemConfig,
    TaxSystemRegistry,
    TaxCalculator,
    compare_systems,
)

# --- Calibration -------------------------------------------------------------
from .calibration import (
    CalibrationOrchestrator,
    apply_systematic_calibration,
    IPFCalibrationOrchestrator,
    apply_ipf_calibration,
    apply_ipf_calibration_via_rake,
    DOTAXSOIParser,
    IPFCalibrator,
)

# --- Adjustments / credits ---------------------------------------------------
from .adjustments import (
    estimate_agi_from_total_income,
    calculate_hawaii_credits,
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
    validate_against_table_12a,
    apply_hybrid_tax_calibration,
    validate_hybrid_calibration,
)

# --- Revenue / analysis ------------------------------------------------------
from .revenue import RevenueEstimator, estimate_revenue
from .analysis import GeographicAnalyzer, assign_geography, load_crosswalk

# --- End-to-end pipeline -----------------------------------------------------
from .pipeline import run_pipeline, PipelineResult

# --- PUMS / projection (two entry points each) ------------------------------
# Simple "scalar / DataFrame" helpers — bridge to monorepo workspace packages.
from .pums_adapter import load_hawaii_pums
from .projection_adapter import project_income_growth
# Full-fat loaders kept from the original ctc-and-eitc — needed for batched
# population loading and tax-unit-vectorized income projection.
from .loaders.pums_loader import PUMSDataLoader, load_pums_data
from .projection import (
    EnsembleProjector,
    OccupationMatcher,
    project_tax_units_forward,
    AcsSupplement,
    project_acs_supplement,
    scale_mortgage_deductions,
)

__version__ = "0.1.0"

__all__ = [
    # Core types
    "TaxUnitConstructor",
    "FILING_STATUS",
    "HawaiiTaxParameters",
    # Liability + credits + deductions
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
    # Tax-system orchestration
    "TaxSystemConfig",
    "TaxSystemRegistry",
    "TaxCalculator",
    "compare_systems",
    # Calibration
    "CalibrationOrchestrator",
    "apply_systematic_calibration",
    "IPFCalibrationOrchestrator",
    "apply_ipf_calibration",
    "apply_ipf_calibration_via_rake",
    "DOTAXSOIParser",
    "IPFCalibrator",
    # Adjustments
    "estimate_agi_from_total_income",
    "calculate_hawaii_credits",
    "estimate_deduction",
    "scale_deduction_params_for_target_year",
    "scale_eitc_for_poverty",
    "HawaiiTaxCredits",
    "ParetoIncomeCalibrator",
    "UltraHighIncomeSynthesizer",
    # Validation
    "DotaxTable12AValidator",
    "validate_against_table_12a",
    "apply_hybrid_tax_calibration",
    "validate_hybrid_calibration",
    # Revenue / analysis
    "RevenueEstimator",
    "estimate_revenue",
    # End-to-end pipeline
    "run_pipeline",
    "PipelineResult",
    # Geography — PUMA crosswalk and analysis
    "GeographicAnalyzer",
    "assign_geography",
    "load_crosswalk",
    # PUMS — simple adapter (preferred for one-shot loads)
    "load_hawaii_pums",
    # PUMS — full-fat loader (use for batched / full-population pipelines)
    "PUMSDataLoader",
    "load_pums_data",
    # Projection — simple scalar growth factor
    "project_income_growth",
    # Projection — full ensemble (BLS OES + occupation matching)
    "EnsembleProjector",
    "OccupationMatcher",
    # Projection — forward micro-simulation (census_forecaster → scaled tax units)
    "project_tax_units_forward",
    # Projection — ACS housing/poverty supplement (B25064/B25077/S1701)
    "AcsSupplement",
    "project_acs_supplement",
    "scale_mortgage_deductions",
]
