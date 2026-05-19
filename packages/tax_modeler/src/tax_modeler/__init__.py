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
from .credits import (
    HawaiiEitcParameters,
    HawaiiFoodExciseParameters,
    HawaiiRentersCreditParameters,
    calculate_eitc,
    calculate_eitc_for_tax_units,
    compute_hi_eitc_for_units,
    compute_hi_food_excise_for_units,
    compute_hi_renters_for_units,
    hawaii_eitc_parameters,
    hawaii_food_excise_parameters,
    hawaii_renters_credit_parameters,
)
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
    AdminCaseload,
    CalibrationOrchestrator,
    CaseloadTarget,
    DOTAXSOIParser,
    Dimension,
    DonorMatcher,
    IPFCalibrationOrchestrator,
    IPFCalibrator,
    JointDistributionDrift,
    JointIpfResult,
    apply_ipf_calibration,
    apply_ipf_calibration_via_rake,
    apply_systematic_calibration,
    calibrate_benefits,
    impute_childcare_expense,
    impute_moop,
    impute_takeup,
    impute_work_expense,
    joint_ipf,
    validate_joint_distribution,
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
    enrich_for_benefits,
    enrich_for_credits,
    enrich_with_spm_unit_id,
    run_pipeline,
)

# --- Policy-impact extension (Phase 1: entities + reform DSL) ----------------
from .entities import EntityGraph, Household, Person, SPMUnit, TaxUnit
from .reform import (
    TAX_SYSTEM_FACTORY_REGISTRY,
    Reform,
    ReformResult,
    apply_reform,
    register_tax_system,
)
from .scenarios import (
    BehavioralParams,
    ForecastScenario,
    MacroScenario,
    TopIncomeParams,
)

# --- Policy-impact extension (Phase 2: distribution + poverty metrics) -------
from .metrics import (
    atkinson,
    decile_summary,
    distribution_by_geography,
    gini,
    palma,
    poverty_by_geography,
    poverty_depth,
    poverty_gap,
    poverty_rate,
    weighted_ntile_labels,
)
from .poverty import (
    compute_spm_resources,
    hawaii_spm_threshold,
    spm_threshold_table,
    threshold_for_units,
)

# --- Policy-impact extension (Phase 3 + 5: benefit modules) ------------------
from .benefits import (
    # Phase 3
    HawaiiSsiSupplementParameters,
    SnapParameters,
    SsiParameters,
    compute_snap_for_units,
    compute_ssi_for_units,
    compute_ssi_hi_supplement_for_units,
    federal_ssi_parameters,
    hawaii_snap_parameters,
    hawaii_ssi_supplement_parameters,
    # Phase 5
    AcaPtcParameters,
    ChildcareParameters,
    HousingParameters,
    LiheapParameters,
    MedicaidParameters,
    WicParameters,
    aca_ptc_parameters,
    compute_aca_ptc_for_units,
    compute_childcare_for_units,
    compute_housing_for_units,
    compute_liheap_for_units,
    compute_medicaid_for_units,
    compute_wic_for_units,
    hawaii_childcare_parameters,
    hawaii_housing_parameters,
    hawaii_liheap_parameters,
    hawaii_medicaid_parameters,
    hawaii_wic_parameters,
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
    DemographicProjectionResult,
    EnsembleProjector,
    OccupationMatcher,
    hawaii_demographic_targets,
    hawaii_disability_share,
    hawaii_hh_size_dist,
    hawaii_senior_share,
    project_acs_supplement,
    project_demographics_forward,
    project_tax_units_forward,
    scale_mortgage_deductions,
)


__version__ = "0.3.0.dev0"


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
    "enrich_for_benefits",
    "enrich_with_spm_unit_id",
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
    # Policy-impact: reform DSL + entity layer (v0.3.0+)
    "Reform",
    "ReformResult",
    "apply_reform",
    "register_tax_system",
    "TAX_SYSTEM_FACTORY_REGISTRY",
    "EntityGraph",
    "Person",
    "TaxUnit",
    "SPMUnit",
    "Household",
    # Phase 11: typed scenario-parameter dataclasses
    "BehavioralParams",
    "TopIncomeParams",
    "MacroScenario",
    "ForecastScenario",
    # Policy-impact: distribution + poverty metrics (v0.3.0+)
    "decile_summary",
    "gini",
    "palma",
    "atkinson",
    "weighted_ntile_labels",
    "poverty_rate",
    "poverty_depth",
    "poverty_gap",
    "compute_spm_resources",
    "hawaii_spm_threshold",
    "spm_threshold_table",
    "threshold_for_units",
    # Policy-impact: SNAP + SSI benefit modules (v0.3.0+)
    "compute_snap_for_units",
    "compute_ssi_for_units",
    "compute_ssi_hi_supplement_for_units",
    "SnapParameters",
    "SsiParameters",
    "HawaiiSsiSupplementParameters",
    "hawaii_snap_parameters",
    "federal_ssi_parameters",
    "hawaii_ssi_supplement_parameters",
    # Policy-impact: take-up imputation against administrative caseload (Phase 4)
    "AdminCaseload",
    "CaseloadTarget",
    "calibrate_benefits",
    "impute_takeup",
    # Phase 8: ACS demographic projection + donor-match + geographic stratification
    "project_demographics_forward",
    "hawaii_senior_share",
    "hawaii_hh_size_dist",
    "hawaii_disability_share",
    "hawaii_demographic_targets",
    "DemographicProjectionResult",
    "DonorMatcher",
    "impute_moop",
    "impute_childcare_expense",
    "impute_work_expense",
    "poverty_by_geography",
    "distribution_by_geography",
    # Phase 10: joint multi-dim IPF
    "Dimension",
    "JointIpfResult",
    "JointDistributionDrift",
    "joint_ipf",
    "validate_joint_distribution",
    # Policy-impact: Phase 5 federal-cost-share + in-kind programs
    "compute_aca_ptc_for_units",
    "compute_medicaid_for_units",
    "compute_wic_for_units",
    "compute_liheap_for_units",
    "compute_childcare_for_units",
    "compute_housing_for_units",
    "AcaPtcParameters",
    "MedicaidParameters",
    "WicParameters",
    "LiheapParameters",
    "ChildcareParameters",
    "HousingParameters",
    "aca_ptc_parameters",
    "hawaii_medicaid_parameters",
    "hawaii_wic_parameters",
    "hawaii_liheap_parameters",
    "hawaii_childcare_parameters",
    "hawaii_housing_parameters",
    # Hawaii state-level refundable credits
    "compute_hi_eitc_for_units",
    "compute_hi_food_excise_for_units",
    "compute_hi_renters_for_units",
    "HawaiiEitcParameters",
    "HawaiiFoodExciseParameters",
    "HawaiiRentersCreditParameters",
    "hawaii_eitc_parameters",
    "hawaii_food_excise_parameters",
    "hawaii_renters_credit_parameters",
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
