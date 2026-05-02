"""End-to-end Hawaii tax microsimulation pipeline.

Chains six stages into a single callable:

  1. **Load** — PUMSDataLoader reads local parquet/CSV files.
  2. **Construct** — TaxUnitConstructor builds tax filing units from person +
     household records.
  3. **Enrich** — Derives earned/investment income and creates credit-ready
     dependent dicts from the TaxUnitConstructor output schema.
  4. **Tax** — calculate_hawaii_tax_for_units computes baseline Hawaii
     liability + credits.
  5. **Calibrate** — apply_ipf_calibration_via_rake adjusts unit weights to
     match DOTAX aggregate benchmarks.
  6. **Project** — project_tax_units_forward scales income to target year,
     recalculates Hawaii tax + federal credits + poverty correction.
  7. **Estimate** — RevenueEstimator wraps the projected units for revenue
     queries.

Quick start (PUMS files required at the default data path)::

    from tax_modeler.pipeline import run_pipeline

    result = run_pipeline(target_year=2026)
    print(result.state_summary["hi_net_tax_revenue"])
    print(result.by_county)

Skip PUMS loading by supplying pre-built calibrated units::

    result = run_pipeline(target_year=2026, tax_units_df=my_calibrated_df)

Approximations
--------------
Without a person-level join, dependent ages are not available from
TaxUnitConstructor alone.  The enrichment step creates synthetic dependent
dicts with ``age=10`` for every counted dependent, so all dependents are
treated as qualifying children under 17.  This slightly overestimates CTC
for non-child dependents (e.g. elderly relatives) but is conservative for
EITC (which has a broader age cap).  Supply a pre-enriched ``tax_units_df``
to bypass this approximation.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """Output of :func:`run_pipeline`.

    All revenue figures are population-weighted dollar totals.  Use
    ``estimator`` for additional queries not pre-computed here.
    """

    tax_units: pd.DataFrame          # calibrated base-year units (post-IPF)
    projected_units: pd.DataFrame    # projected target-year units
    estimator: object                # RevenueEstimator instance

    state_summary: Dict              # estimator.state_summary()
    by_county: pd.DataFrame          # estimator.by_county()
    by_filing_status: pd.DataFrame   # estimator.by_filing_status()
    by_income_quintile: pd.DataFrame # estimator.by_income_quintile()

    base_year: int
    target_year: int
    n_units: int                     # number of tax-unit rows
    n_weighted_filers: float         # population-weighted filer count
    elapsed_seconds: float           # wall-clock time for the full run

    timings: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------


def _load_pums(data_dir: Path, state: str, pums_type: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Stage 1: load person + household PUMS DataFrames."""
    from tax_modeler.loaders.pums_loader import PUMSDataLoader

    loader = PUMSDataLoader(data_dir=data_dir)
    hh_file = loader._hh_file_path(state, pums_type)
    if not hh_file.exists():
        raise FileNotFoundError(
            f"PUMS household file not found: {hh_file}\n"
            "Download the Hawaii ACS PUMS files and place them at:\n"
            f"  {data_dir}/psam_h{state}.parquet  (or .csv)\n"
            f"  {data_dir}/psam_p{state}.parquet  (or .csv)"
        )
    person_df, hh_df = loader.load_data(state=state, pums_type=pums_type)
    logger.info("PUMS loaded: %d persons, %d households", len(person_df), len(hh_df))
    return person_df, hh_df


def _construct_units(person_df: pd.DataFrame, hh_df: pd.DataFrame) -> pd.DataFrame:
    """Stage 2: build tax filing units."""
    from tax_modeler.units.constructor import TaxUnitConstructor

    constructor = TaxUnitConstructor(
        person_df,
        hh_df,
        use_soi_calibration=False,  # defer calibration to explicit IPF step
        progress_bar=False,
    )
    units = constructor.create_rule_based_units(parallel=True)
    logger.info("Tax units constructed: %d units", len(units))
    return units


def _enrich_for_credits(df: pd.DataFrame) -> pd.DataFrame:
    """Stage 3: derive credit-calculation inputs from TaxUnitConstructor columns.

    TaxUnitConstructor stores dependent person IDs in ``dependents``
    (list[str]).  Credit calculations expect ``dependents`` to be a list of
    dicts with ``age``, ``relationship``, ``citizenship``, ``months_in_home``.
    This step replaces the person-ID list with synthetic dicts using
    ``num_dependents`` as the count, assuming each is a qualifying child aged 10.

    Derived columns added (skipped if already present):
      - ``earned_income``          wages + self-employment income
      - ``investment_income``      interest/dividend income
      - ``num_qualifying_children`` capped copy of num_dependents
      - ``dependents``             list of credit-ready dicts (overwrites str list)
      - ``dependents_details``     alias of dependents (for EITC code path)
    """
    df = df.copy()

    # Preserve original person-ID list before overwriting
    if "dependents" in df.columns:
        df["dependent_person_ids"] = df["dependents"]

    def _make_dep_dicts(n: int):
        return [
            {"age": 10, "relationship": 22, "citizenship": 1, "months_in_home": 12}
        ] * max(0, int(n))

    df["dependents"] = df["num_dependents"].apply(_make_dep_dicts)
    df["dependents_details"] = df["dependents"]

    # Qualifying children count (proxy: all dependents, capped at 3 for EITC)
    if "num_qualifying_children" not in df.columns:
        df["num_qualifying_children"] = df["num_dependents"].clip(upper=3).astype(int)

    def _col(name: str) -> pd.Series:
        return df[name].fillna(0) if name in df.columns else pd.Series(0.0, index=df.index)

    if "earned_income" not in df.columns:
        earned = (
            _col("primary_wagp") + _col("primary_semp")
            + _col("secondary_wagp") + _col("secondary_semp")
        )
        df["earned_income"] = earned.clip(lower=0)

    if "investment_income" not in df.columns:
        invest = _col("primary_intp") + _col("secondary_intp")
        df["investment_income"] = invest.clip(lower=0)

    return df


def _compute_base_tax(df: pd.DataFrame) -> pd.DataFrame:
    """Stage 4: compute baseline Hawaii tax + federal credits."""
    from tax_modeler.liability.hawaii import calculate_hawaii_tax_for_units
    from tax_modeler.credits.eitc import calculate_eitc_for_tax_units
    from tax_modeler.projection.tax_unit_projector import _recalculate_ctc

    df = calculate_hawaii_tax_for_units(df)
    df = _recalculate_ctc(df)
    df = calculate_eitc_for_tax_units(df)
    return df


def _calibrate(df: pd.DataFrame) -> pd.DataFrame:
    """Stage 5: IPF rake calibration against DOTAX aggregate benchmarks."""
    from tax_modeler.calibration import apply_ipf_calibration_via_rake

    calibrated = apply_ipf_calibration_via_rake(df)
    logger.info(
        "IPF calibration complete: weight sum %.0f → %.0f",
        df["weight"].sum(),
        calibrated["weight"].sum(),
    )
    return calibrated


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_pipeline(
    target_year: int,
    base_year: Optional[int] = None,
    pums_data_dir: Optional[Path] = None,
    state: str = "15",
    pums_type: str = "5yr",
    method: str = "ensemble",
    tax_units_df: Optional[pd.DataFrame] = None,
    skip_calibration: bool = False,
) -> PipelineResult:
    """Run the full Hawaii tax microsimulation pipeline.

    Parameters
    ----------
    target_year:
        Year to project forward to (e.g. 2026).
    base_year:
        ACS anchor year for income growth factors.  Defaults to
        ``None`` — census_forecaster picks the most recent panel vintage.
    pums_data_dir:
        Directory containing ``psam_h15.parquet`` and ``psam_p15.parquet``
        (or ``.csv`` equivalents).  Ignored when ``tax_units_df`` is supplied.
        Defaults to the standard monorepo path
        (``<repo_root>/data/raw/pums``).
    state:
        State FIPS code (default ``"15"`` for Hawaii).
    pums_type:
        ``"5yr"`` (default) or ``"1yr"`` — selects the PUMS vintage.
    method:
        census_forecaster projector method: ``"ensemble"`` (default),
        ``"damped_log_trend"``, ``"ar1_log_diff"``, or ``"carry_forward"``.
    tax_units_df:
        Pre-built calibrated base-year tax units.  When provided, stages
        1–5 (PUMS loading, construction, enrichment, tax, calibration) are
        skipped and projection begins immediately from this DataFrame.
        The caller is responsible for ensuring ``hi_tax_liability``,
        ``earned_income``, ``investment_income``, ``dependents``, and
        ``num_qualifying_children`` are present.
    skip_calibration:
        When ``True``, skip the IPF rake step even when building from PUMS.
        Useful for debugging the construction and projection stages in isolation.

    Returns
    -------
    PipelineResult
        Contains calibrated base units, projected units, a RevenueEstimator
        instance, and pre-computed summary tables.
    """
    from tax_modeler.projection.tax_unit_projector import project_tax_units_forward
    from tax_modeler.revenue.estimator import RevenueEstimator

    wall_start = time.perf_counter()
    timings: Dict[str, float] = {}

    # ------------------------------------------------------------------ #
    # Stages 1–5: build calibrated base-year units (skipped if supplied)  #
    # ------------------------------------------------------------------ #
    if tax_units_df is not None:
        logger.info("run_pipeline: using caller-supplied tax_units_df (%d rows)", len(tax_units_df))
        calibrated = tax_units_df
    else:
        _data_dir = pums_data_dir or (
            Path(__file__).resolve().parents[5] / "data" / "raw" / "pums"
        )

        t0 = time.perf_counter()
        person_df, hh_df = _load_pums(_data_dir, state, pums_type)
        timings["load_pums"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        units = _construct_units(person_df, hh_df)
        timings["construct"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        units = _enrich_for_credits(units)
        timings["enrich"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        units = _compute_base_tax(units)
        timings["base_tax"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        calibrated = _calibrate(units) if not skip_calibration else units
        timings["calibrate"] = time.perf_counter() - t0

    # ------------------------------------------------------------------ #
    # Stage 6: project forward                                             #
    # ------------------------------------------------------------------ #
    t0 = time.perf_counter()
    projected = project_tax_units_forward(
        calibrated,
        target_year=target_year,
        base_year=base_year,
        method=method,
    )
    timings["project"] = time.perf_counter() - t0
    logger.info(
        "Projection complete: %d units, median income %.0f → %.0f",
        len(projected),
        projected["income_base_year"].median(),
        projected["income"].median(),
    )

    # ------------------------------------------------------------------ #
    # Stage 7: revenue estimation                                          #
    # ------------------------------------------------------------------ #
    t0 = time.perf_counter()
    estimator = RevenueEstimator(projected)
    state_summary = estimator.state_summary()
    by_county = estimator.by_county()
    by_filing = estimator.by_filing_status()
    by_quintile = estimator.by_income_quintile()
    timings["estimate"] = time.perf_counter() - t0

    elapsed = time.perf_counter() - wall_start

    logger.info(
        "Pipeline complete in %.1fs: %d units, %.0f weighted filers, "
        "hi_net_tax_revenue=%.0f",
        elapsed,
        len(projected),
        state_summary["total_weighted_filers"],
        state_summary["hi_net_tax_revenue"],
    )

    return PipelineResult(
        tax_units=calibrated,
        projected_units=projected,
        estimator=estimator,
        state_summary=state_summary,
        by_county=by_county,
        by_filing_status=by_filing,
        by_income_quintile=by_quintile,
        base_year=base_year or projected["projection_base_year"].iloc[0],
        target_year=target_year,
        n_units=len(projected),
        n_weighted_filers=state_summary["total_weighted_filers"],
        elapsed_seconds=elapsed,
        timings=timings,
    )
