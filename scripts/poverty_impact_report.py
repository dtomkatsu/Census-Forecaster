#!/usr/bin/env python3
"""Hawaii anti-poverty impact of EITC, CTC, and HI state EITC by geography.

Emits four CSVs per run at state, county, House district, and Senate
district granularity, comparing baseline SPM poverty rates against
seven counterfactuals (four removal, three expansion/new-credit).

    by_state.csv             — single-row state totals
    by_county.csv            — 4 Hawaii counties
    by_house_district.csv    — up to 51 HD rows
    by_senate_district.csv   — up to 25 SD rows

Scenarios:
  Removal — what would poverty look like without each credit?
    no_eitc, no_ctc, no_hi_eitc, no_credits
  Expansion — how much additional poverty reduction from policy changes?
    expanded_ctc_2021 (ARPA-style fully-refundable CTC),
    hi_eitc_100pct    (HI state EITC raised from 40% → 100% of federal),
    hi_ctc_650        (new HI state CTC at $650/qualifying-child, refundable)

Examples
--------
    # TY 2024 baseline + all seven scenarios on real PUMS, with SNAP
    python scripts/poverty_impact_report.py --tax-year 2024 --apply-snap \\
        --pums-data-dir packages/data/raw/pums \\
        --out reports/poverty_impact_2024/

    # TY 2025 projection
    python scripts/poverty_impact_report.py --tax-year 2025 --apply-snap \\
        --pums-data-dir packages/data/raw/pums \\
        --out reports/poverty_impact_2025/

    # Sweep alternative HI state CTC amounts
    python scripts/poverty_impact_report.py --tax-year 2024 --apply-snap \\
        --hi-ctc-per-child 1000 \\
        --out reports/poverty_impact_2024_hi_ctc_1000/

Notes
-----
* SNAP imputation is recommended for poverty-impact runs (without it,
  low-income units' SPM resources are understated by ~$500M/yr in
  Hawaii, biasing baseline poverty rates upward).
* See the module-level docstring of ``tax_modeler.poverty.impact`` for
  the full list of methodological caveats (static counterfactual,
  marginal-attribution non-additivity, unit-of-analysis bias).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

LOG = logging.getLogger("poverty_impact_report")

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_DIR = REPO_ROOT / "tests" / "tax_modeler" / "fixtures"


# ---------------------------------------------------------------------------
# Pipeline glue (mirrors scripts/eitc_ctc_geo_report.py; intentionally
# duplicated — scripts/ has no shared helpers module)
# ---------------------------------------------------------------------------


def _load_units(pums_data_dir: Optional[Path], use_fixture: bool) -> pd.DataFrame:
    """Build enriched, taxed tax units with HI EITC + geography assigned."""
    from tax_modeler.pipeline import enrich_for_credits
    from tax_modeler.units.constructor import TaxUnitConstructor
    from tax_modeler.analysis.puma_crosswalk import assign_geography

    if use_fixture or pums_data_dir is None:
        persons_path = DEFAULT_FIXTURE_DIR / "synthetic_pums_persons.parquet"
        households_path = DEFAULT_FIXTURE_DIR / "synthetic_pums_households.parquet"
        if not persons_path.exists() or not households_path.exists():
            raise FileNotFoundError(
                f"Synthetic PUMS fixture missing at {DEFAULT_FIXTURE_DIR}."
            )
        persons = pd.read_parquet(persons_path)
        households = pd.read_parquet(households_path)
        LOG.info("Loaded synthetic PUMS fixture: %d persons, %d households",
                 len(persons), len(households))
    else:
        for ext in ("parquet", "csv"):
            p = pums_data_dir / f"psam_p15.{ext}"
            h = pums_data_dir / f"psam_h15.{ext}"
            if p.exists() and h.exists():
                reader = pd.read_parquet if ext == "parquet" else pd.read_csv
                persons = reader(p)
                households = reader(h)
                LOG.info("Loaded PUMS from %s (%s): %d persons, %d hhs",
                         pums_data_dir, ext, len(persons), len(households))
                break
        else:
            raise FileNotFoundError(
                f"No psam_p15.{{parquet,csv}} found in {pums_data_dir}"
            )
        from tax_modeler.loaders.pums_loader import PUMSDataLoader
        _coalesce = PUMSDataLoader(data_dir=pums_data_dir)._coalesce_puma
        households = _coalesce(households)
        persons = _coalesce(persons)

    ctor = TaxUnitConstructor(
        persons.copy(), households.copy(),
        use_soi_calibration=False, progress_bar=False,
    )
    units = ctor.create_rule_based_units(parallel=False)
    units = enrich_for_credits(units)
    units = assign_geography(units)
    return units


def _build_units_for_tax_year(units: pd.DataFrame, tax_year: int, project: bool) -> pd.DataFrame:
    """Compute base tax + HI EITC for a given year."""
    from tax_modeler.pipeline import compute_base_tax
    from tax_modeler.credits.hi_eitc import compute_hi_eitc_for_units

    if project:
        from tax_modeler.projection.tax_unit_projector import project_tax_units_forward
        out = project_tax_units_forward(units, target_year=tax_year)
    else:
        out = compute_base_tax(units, tax_year=tax_year)
    out = compute_hi_eitc_for_units(out)
    return out


def _apply_snap(units: pd.DataFrame, *, tax_year: int) -> pd.DataFrame:
    """Compute SNAP benefits then take-up-adjust against admin caseload anchor."""
    from tax_modeler.benefits.snap import compute_snap_for_units
    from tax_modeler.calibration.admin_caseload import AdminCaseload
    from tax_modeler.calibration.takeup_imputation import impute_takeup

    LOG.info("Computing SNAP benefits + take-up imputation for TY %d", tax_year)
    out = compute_snap_for_units(units)
    try:
        target = AdminCaseload.load().target("snap", tax_year)
    except Exception as exc:
        LOG.warning(
            "SNAP admin caseload target unavailable for year=%d (%s); "
            "skipping take-up calibration. SNAP amounts reflect simulated "
            "eligibility only.", tax_year, exc,
        )
        return out
    out = impute_takeup(
        out, target=target, benefit_col="snap_amount", score_col="income",
        ascending=True, weight_col="weight",
    )
    return out


def _apply_arpa_ctc(units: pd.DataFrame) -> pd.DataFrame:
    from tax_modeler.credits.arpa_ctc import arpa_ctc_for_tax_units
    return arpa_ctc_for_tax_units(units)


def _apply_credit_takeup(
    units: pd.DataFrame,
    *,
    tax_year: int,
    programs: tuple[str, ...] = ("eitc", "actc"),
) -> pd.DataFrame:
    """Rank-and-truncate EITC/ACTC eligibles to IRS SOI take-up targets.

    Without this, ``eitc_amount`` and ``ctc_refundable`` reflect *eligibility*
    (~105k EITC-eligible filers in Hawaii), not *receipt* (~84k claimed per
    IRS SOI). Baseline poverty lifts for the no_eitc / no_ctc scenarios are
    overstated by ~25% / ~15% respectively when this step is skipped.
    """
    from tax_modeler.pipeline import apply_credit_takeup
    LOG.info(
        "Applying IRS-anchored take-up imputation for %s at year=%d",
        ",".join(programs), tax_year,
    )
    try:
        return apply_credit_takeup(units, year=tax_year, programs=programs)
    except Exception as exc:
        LOG.warning(
            "apply_credit_takeup failed for year=%d (%s); falling back to "
            "TY2022 IRS SOI anchor. Eligibility totals will be partially "
            "scaled but the IRS rate is treated as behavioral and constant.",
            tax_year, exc,
        )
        return apply_credit_takeup(units, year=2022, programs=programs)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--tax-year", type=int, required=True,
                   help="Tax year (2022, 2023, 2024, or 2025).")
    p.add_argument("--out", type=Path, required=True,
                   help="Output directory.")
    p.add_argument("--pums-data-dir", type=Path, default=None,
                   help="Directory with psam_h15.{parquet,csv} + psam_p15.*. "
                        "Defaults to the synthetic fixture.")
    p.add_argument("--use-fixture", action="store_true",
                   help="Force use of the synthetic PUMS fixture.")
    p.add_argument("--apply-snap", action="store_true", default=True,
                   help="(Default ON.) Compute + take-up-impute SNAP before "
                        "the SPM computation. Use --no-apply-snap to disable.")
    p.add_argument("--no-apply-snap", dest="apply_snap", action="store_false",
                   help=argparse.SUPPRESS)
    p.add_argument("--apply-credit-takeup", action="store_true", default=True,
                   help="(Default ON.) Rank-and-truncate EITC/ACTC eligibles "
                        "to the IRS SOI take-up target so baseline reflects "
                        "*receipt*, not *eligibility*. Use "
                        "--no-apply-credit-takeup to disable.")
    p.add_argument("--no-apply-credit-takeup", dest="apply_credit_takeup",
                   action="store_false", help=argparse.SUPPRESS)
    p.add_argument("--apply-moop", action="store_true", default=True,
                   help="(Default ON.) Impute MOOP (medical out-of-pocket) "
                        "from CPS ASEC Hawaii donors before SPM resource "
                        "calculation. Use --no-apply-moop to disable.")
    p.add_argument("--no-apply-moop", dest="apply_moop", action="store_false",
                   help=argparse.SUPPRESS)
    p.add_argument("--hi-ctc-takeup-rate", type=float, default=0.80,
                   help="Take-up rate applied to the hi_ctc_650 expansion "
                        "increment. Default 0.80 (year-1 ramp consistent with "
                        "MN 2023 / VT 2022 enacted state CTCs).")
    p.add_argument("--hi-eitc-100pct-takeup-rate", type=float, default=0.95,
                   help="Take-up rate applied to the hi_eitc_100pct "
                        "expansion *increment* (existing HI EITC claimers "
                        "continue claiming automatically since HI EITC "
                        "attaches to federal). Default 0.95.")
    p.add_argument("--arpa-ctc-takeup-rate", type=float, default=0.95,
                   help="Take-up rate applied to the expanded_ctc_2021 "
                        "(ARPA) increment. Default 0.95 (federal CTC steady "
                        "state).")
    p.add_argument("--scenarios", type=str, default=None,
                   help="Comma-separated subset of "
                        "no_eitc,no_ctc,no_hi_eitc,no_credits,"
                        "expanded_ctc_2021,hi_eitc_100pct,hi_ctc_650. "
                        "Default = all seven.")
    p.add_argument("--hi-ctc-per-child", type=float, default=650.0,
                   help="Per-qualifying-child amount for the hi_ctc_650 "
                        "scenario. Default $650.")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def _print_summary(*, tax_year: int, by_state: pd.DataFrame, scenarios: tuple[str, ...]) -> None:
    s = by_state.iloc[0]
    print()
    print(f"=== TY {tax_year} Hawaii poverty impact ===")
    rate = s["poverty_rate_baseline"]
    persons_total = s["weighted_persons"]
    persons_poor = s["persons_in_poverty_baseline"]
    print(f"  Baseline SPM poverty rate         : {rate * 100:>14.2f}%")
    print(f"  Persons in poverty (baseline)     : {persons_poor:>15,.0f}")
    print(f"  Weighted persons (state)          : {persons_total:>15,.0f}")
    print()
    label_map = {
        "no_eitc":           "Persons lifted by EITC",
        "no_ctc":            "Persons lifted by CTC",
        "no_hi_eitc":        "Persons lifted by HI EITC",
        "no_credits":        "Persons lifted by ALL three credits (joint)",
        "expanded_ctc_2021": "Additional lift if ARPA-style CTC restored",
        "hi_eitc_100pct":    "Additional lift if HI EITC → 100% of federal",
        "hi_ctc_650":        "Additional lift if HI enacts $650/child CTC",
    }
    for scn in scenarios:
        col = f"persons_lifted_{scn}"
        if col not in s.index:
            continue
        label = label_map.get(scn, scn)
        sign = "+" if not scn.startswith("no_") else ""
        print(f"  {label:<48} : {sign}{s[col]:>14,.0f}")
    print()
    gap_baseline_m = s["poverty_gap_baseline_$"] / 1e6
    print(f"  Baseline poverty gap              : ${gap_baseline_m:>14,.1f}M")
    for scn in scenarios:
        col = f"gap_closed_{scn}_$"
        if col not in s.index:
            continue
        label = label_map.get(scn, scn).replace("Persons lifted by", "Gap closed by").replace("Additional lift", "Additional gap closed")
        sign = "+" if not scn.startswith("no_") else ""
        print(f"  {label:<48} : {sign}${s[col] / 1e6:>13,.1f}M")
    print()


def main(argv: Optional[list] = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.tax_year not in {2022, 2023, 2024, 2025}:
        LOG.error("--tax-year must be one of {2022, 2023, 2024, 2025}; got %d", args.tax_year)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)

    # 1. Build base units.
    base_units = _load_units(args.pums_data_dir, args.use_fixture)

    # 2. Compute tax + credits for the requested year.
    PUMS_CONSTRUCTION_YEAR = 2022
    project_required = args.tax_year != PUMS_CONSTRUCTION_YEAR
    units = _build_units_for_tax_year(base_units, args.tax_year, project=project_required)

    # 3. IRS-anchored take-up: rank-and-truncate EITC/ACTC eligibles to
    #    actual SOI claim counts. Must run *before* ARPA CTC counterfactual
    #    column is computed so the ARPA column reflects parameter changes
    #    only and not take-up calibration of the baseline.
    if args.apply_credit_takeup:
        units = _apply_credit_takeup(units, tax_year=args.tax_year)

    # 4. ARPA CTC counterfactual column (required for expanded_ctc_2021 scenario).
    units = _apply_arpa_ctc(units)

    # 5. SNAP wiring (default ON for poverty-impact reports).
    if args.apply_snap:
        units = _apply_snap(units, tax_year=args.tax_year)

    # 6. MOOP imputation from CPS ASEC Hawaii donors. Required to bring the
    #    baseline SPM rate in line with Census-published Hawaii SPM (~10-12%);
    #    without it the baseline rate runs ~10pp high.
    if args.apply_moop:
        from tax_modeler.benefits.moop import compute_moop_for_units
        units = compute_moop_for_units(units)

    # 7. Resolve scenarios.
    from tax_modeler.poverty.impact import compute_poverty_impact, _DEFAULT_SCENARIOS

    if args.scenarios:
        scenarios = tuple(s.strip() for s in args.scenarios.split(",") if s.strip())
    else:
        scenarios = _DEFAULT_SCENARIOS

    # 8. Compute impact.
    result = compute_poverty_impact(
        units, tax_year=args.tax_year, scenarios=scenarios,
        hi_ctc_per_child=args.hi_ctc_per_child,
        hi_ctc_takeup_rate=args.hi_ctc_takeup_rate,
        hi_eitc_100pct_takeup_rate=args.hi_eitc_100pct_takeup_rate,
        arpa_ctc_takeup_rate=args.arpa_ctc_takeup_rate,
    )

    # 9. Write CSVs.
    result.by_state.to_csv(args.out / "by_state.csv", index=False)
    result.by_county.to_csv(args.out / "by_county.csv", index=False)
    result.by_house_district.to_csv(args.out / "by_house_district.csv", index=False)
    result.by_senate_district.to_csv(args.out / "by_senate_district.csv", index=False)
    LOG.info("Wrote 4 poverty-impact CSVs to %s", args.out)

    # 10. Summary block.
    _print_summary(tax_year=args.tax_year, by_state=result.by_state, scenarios=result.scenarios)

    if result.notes:
        print("Notes:")
        for n in result.notes:
            print(f"  - {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
