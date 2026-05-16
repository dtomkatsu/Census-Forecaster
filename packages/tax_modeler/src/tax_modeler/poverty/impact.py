"""Anti-poverty impact of federal CTC, federal EITC, and Hawaii state EITC.

Computes Hawaii SPM poverty rates *with* the relevant credits (baseline)
and re-computes them under one or more counterfactual scenarios:

  Removal scenarios (the credit is set to $0):
    * ``no_eitc``       — federal EITC removed
    * ``no_ctc``        — federal CTC refundable portion removed
    * ``no_hi_eitc``    — Hawaii state EITC removed
    * ``no_credits``    — all three credits removed

  Expansion / new-credit scenarios:
    * ``expanded_ctc_2021`` — federal CTC replaced with the ARPA 2021
      design (see :mod:`tax_modeler.credits.arpa_ctc`).
    * ``hi_eitc_100pct`` — Hawaii state EITC rate raised from 40% to
      100% of federal (i.e. ``hi_eitc_amount × 2.5``).
    * ``hi_ctc_650`` — Hawaii enacts a state CTC at $650 per qualifying
      child, fully refundable, no AGI phase-out.

For each scenario the module reports:

  * Per-geography poverty rate (state, county, House district, Senate
    district).
  * **Persons lifted out of poverty** by each scenario, computed at the
    tax-unit level and scaled by SPM-unit-equivalent person count
    (``adults + num_dependents``).
  * Total poverty gap ($) and dollars-closed by each scenario.

Static counterfactual — no labor supply / marriage / fertility / filing
response. See module-level NOTES at the bottom for full caveats.

The math relies on the fact that :func:`compute_spm_resources` is
*linear* in the credit columns. The counterfactual SPM resources are
therefore obtained by simple subtraction (or addition for expansions),
which is ~5× faster than re-running :func:`compute_spm_resources` once
per scenario.

NOTES (also surfaced via :class:`PovertyImpactResult.notes`):

  * **Static counterfactual**: holds labor supply, marriage, fertility,
    and filing behavior constant. Empirical EITC elasticities suggest
    single-mother LFP would fall 2–7 pp under repeal; this module does
    not model that.
  * **Marginal attribution is non-additive**: ``lifted_eitc + lifted_ctc
    + lifted_hi_eitc ≠ lifted_combined`` because EITC and CTC phase-outs
    interact. Use ``lifted_combined`` for headline claims; marginals for
    relative ranking.
  * **Unit-of-analysis** (Tier 2 — opt-in fix available): frame is
    *tax-unit*-grained by default; pass the units through
    :func:`tax_modeler.units.spm_unit.build_spm_units` (or set
    ``--pool-spm-units`` on ``scripts/poverty_impact_report.py``) to
    pool cohabiting unmarried partners with shared kids into one SPM
    unit. The default remains tax-unit-grained pending user validation.
  * **SPM resource gaps** (Tier 2 — closed): MOOP, housing subsidies,
    CCSP childcare subsidies, work-related childcare expense, and
    other work expenses are now wired into the resource calculation
    via the ``--apply-moop``, ``--apply-housing-subsidy``,
    ``--apply-childcare-subsidy``, and ``--apply-spm-expenses`` flags
    on ``scripts/poverty_impact_report.py`` (all default ON). Residual
    direction of bias: small and ambiguous.
  * **District assignment** (Tier 2 — partial): within-PUMA HD/SD via
    deterministic SERIALNO hash by default. A biproportional IPF raking
    function (:func:`tax_modeler.analysis.district_raking.rake_biproportional`)
    is now shipped; the high-level wrapper picks up IRS SOI ZIP filer
    totals + ZIP→HD crosswalk when bundled (data files pending).
    District-level point estimates still carry roughly ±20% uncertainty
    until those data files land.
  * **Expansion take-up**: ``hi_ctc_650`` scales its $650/child increment
    by ``hi_ctc_takeup_rate`` (default 0.80, MN 2023 / VT 2022 first-year
    ramp); ``hi_eitc_100pct`` scales its 60-pp HI EITC increment by
    ``hi_eitc_100pct_takeup_rate`` (default 0.95, since the rate
    auto-attaches to federal claims); ``expanded_ctc_2021`` scales the
    ARPA delta by ``arpa_ctc_takeup_rate`` (default 0.95). Removal
    scenarios are unscaled — receipt is encoded by IRS take-up
    calibration upstream on the baseline credit columns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from tax_modeler.metrics.poverty import poverty_gap, poverty_rate

from .spm import SPMResourceMeta, compute_spm_resources
from .thresholds import threshold_for_units


_DEFAULT_SCENARIOS: tuple[str, ...] = (
    "no_eitc",
    "no_ctc",
    "no_hi_eitc",
    "no_credits",
    "expanded_ctc_2021",
    "hi_eitc_100pct",
    "hi_ctc_650",
)

_HI_EITC_CURRENT_RATE = 0.40  # Act 209 (2023) — 40% of federal, refundable.

# Filing-status values used for the by_household_type disaggregation.
# ``head_of_household`` is the closest tax-unit proxy for "single mother"
# (a parent or guardian filing without a spouse with at least one
# qualifying dependent). ``single`` filers without dependents and married
# filers are reported alongside for context.
_HOUSEHOLD_TYPES: tuple[str, ...] = (
    "single",
    "head_of_household",
    "married_filing_jointly",
    "married_filing_separately",
)


@dataclass(frozen=True)
class PovertyImpactResult:
    """Per-geography baseline + counterfactual poverty metrics.

    ``by_household_type`` disaggregates the same metrics by filing
    status (single / head_of_household / married_filing_jointly /
    married_filing_separately). The ``head_of_household`` row is the
    closest tax-unit proxy for single-mother households — used by the
    RxKids analysis to estimate single-mother poverty impact.
    """

    units: pd.DataFrame  # augmented with scenario resource + poor columns
    by_state: pd.DataFrame
    by_county: pd.DataFrame
    by_house_district: pd.DataFrame
    by_senate_district: pd.DataFrame
    by_household_type: pd.DataFrame
    tax_year: int
    spm_meta: SPMResourceMeta
    scenarios: tuple[str, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)


def _persons_per_unit(units: pd.DataFrame) -> np.ndarray:
    """SPM-unit-equivalent person count per filing unit.

    `n_adults = 2 if MFJ else 1` (mirrors threshold_for_units convention).
    `+ num_dependents` (clipped to >= 0).
    """
    is_joint = (units["filing_status"] == "married_filing_jointly").to_numpy()
    n_adults = 1 + is_joint.astype(int)
    n_children = units["num_dependents"].fillna(0).clip(lower=0).astype(int).to_numpy()
    return (n_adults + n_children).astype(float)


def _scenario_resources(
    *,
    baseline_resources: np.ndarray,
    units: pd.DataFrame,
    scenario: str,
    eitc_col: str,
    ctc_col: str,
    hi_eitc_col: str,
    arpa_ctc_col: str,
    qualifying_children_col: str,
    hi_ctc_per_child: float,
    hi_ctc_takeup_rate: float,
    hi_eitc_100pct_takeup_rate: float,
    arpa_ctc_takeup_rate: float,
    rxkids_col: str,
) -> np.ndarray:
    """Counterfactual SPM resources via linear arithmetic on credit columns.

    Expansion scenarios' *increments* are scaled by an empirically grounded
    take-up rate. Removal scenarios are not — receipt is already encoded
    via upstream IRS take-up calibration on the baseline credit columns.
    """
    eitc = units[eitc_col].fillna(0).to_numpy(dtype=float)
    ctc = units[ctc_col].fillna(0).to_numpy(dtype=float)
    hi_eitc = units[hi_eitc_col].fillna(0).to_numpy(dtype=float)
    if scenario == "no_eitc":
        return baseline_resources - eitc
    if scenario == "no_ctc":
        return baseline_resources - ctc
    if scenario == "no_hi_eitc":
        return baseline_resources - hi_eitc
    if scenario == "no_credits":
        return baseline_resources - (eitc + ctc + hi_eitc)
    if scenario == "expanded_ctc_2021":
        if arpa_ctc_col not in units.columns:
            raise KeyError(
                f"scenario={scenario!r} requires column {arpa_ctc_col!r}; "
                "call tax_modeler.credits.arpa_ctc_for_tax_units(units) first."
            )
        arpa = units[arpa_ctc_col].fillna(0).to_numpy(dtype=float)
        increment = (arpa - ctc) * arpa_ctc_takeup_rate
        return baseline_resources + increment
    if scenario == "hi_eitc_100pct":
        # Going from 40% to 100% of federal = +60pp = +1.5× the current
        # HI EITC dollars. (current = 0.40 × federal; new = 1.00 × federal;
        # increment = 0.60 × federal = 1.5 × current.)
        # The increment is scaled by take-up; existing HI EITC claimers
        # continue claiming automatically (HI attaches to federal) so the
        # default 0.95 captures the new-claim friction on the marginal
        # 60-pp band rather than re-applying take-up to existing receipt.
        increment = (
            hi_eitc * (1.0 - _HI_EITC_CURRENT_RATE) / _HI_EITC_CURRENT_RATE
            * hi_eitc_100pct_takeup_rate
        )
        return baseline_resources + increment
    if scenario == "hi_ctc_650":
        if qualifying_children_col not in units.columns:
            raise KeyError(
                f"scenario={scenario!r} requires column {qualifying_children_col!r}."
            )
        n_kids = units[qualifying_children_col].fillna(0).clip(lower=0).to_numpy(dtype=float)
        return baseline_resources + hi_ctc_per_child * n_kids * hi_ctc_takeup_rate
    if scenario == "rxkids_hi":
        if rxkids_col not in units.columns:
            raise KeyError(
                f"scenario={scenario!r} requires column {rxkids_col!r}; "
                "call tax_modeler.programs.compute_rxkids_for_units(units) first."
            )
        # The rxkids_amount column is already take-up-adjusted inside
        # compute_rxkids_for_units (the program's overall takeup_rate
        # parameter scales both prenatal and postnatal). Adding it
        # directly to baseline resources gives the expansion lift.
        rxk = units[rxkids_col].fillna(0).to_numpy(dtype=float)
        return baseline_resources + rxk
    raise ValueError(f"unknown scenario: {scenario!r}")


def _aggregate(
    units: pd.DataFrame,
    *,
    group_col: Optional[str],
    threshold: np.ndarray,
    person_weight: np.ndarray,
    filer_weight: np.ndarray,
    scenarios: Sequence[str],
) -> pd.DataFrame:
    """Per-geography aggregation for baseline + every scenario."""
    if group_col is None:
        groups: list[tuple[object, pd.Index]] = [("__state__", units.index)]
    else:
        groups = [(k, g.index) for k, g in units.groupby(group_col, observed=True, dropna=False)]

    rows = []
    for key, idx in groups:
        pos = units.index.get_indexer(idx)
        pw = person_weight[pos]
        fw = filer_weight[pos]
        thr = threshold[pos]
        baseline_r = units.loc[idx, "spm_resources"].to_numpy(dtype=float)

        # Persons in poverty baseline (using person weights).
        poor_baseline = baseline_r < thr
        persons_in_poverty_baseline = float(pw[poor_baseline].sum())
        weighted_persons = float(pw.sum())
        weighted_filers = float(fw.sum())
        pov_rate_baseline = (
            persons_in_poverty_baseline / weighted_persons if weighted_persons > 0 else 0.0
        )
        gap_baseline = float(np.maximum(thr - baseline_r, 0.0).dot(fw))

        row: dict[str, float | str] = {
            "weighted_persons": weighted_persons,
            "weighted_filers": weighted_filers,
            "poverty_rate_baseline": pov_rate_baseline,
            "persons_in_poverty_baseline": persons_in_poverty_baseline,
            "poverty_gap_baseline_$": gap_baseline,
        }
        if group_col is not None:
            row[group_col] = key

        for scn in scenarios:
            scn_r = units.loc[idx, f"spm_resources_{scn}"].to_numpy(dtype=float)
            poor_scn = scn_r < thr
            persons_in_poverty_scn = float(pw[poor_scn].sum())
            pov_rate_scn = (
                persons_in_poverty_scn / weighted_persons if weighted_persons > 0 else 0.0
            )
            gap_scn = float(np.maximum(thr - scn_r, 0.0).dot(fw))

            # For removal scenarios: persons lifted = persons_in_poverty_scn - baseline.
            # Positive ⇒ credit lifts people out of poverty (counterfactual poorer).
            # For expansion scenarios: persons lifted = baseline - scn (counterfactual richer).
            if scn.startswith("no_"):
                persons_lifted = persons_in_poverty_scn - persons_in_poverty_baseline
                gap_closed = gap_scn - gap_baseline
            else:
                persons_lifted = persons_in_poverty_baseline - persons_in_poverty_scn
                gap_closed = gap_baseline - gap_scn

            row[f"poverty_rate_{scn}"] = pov_rate_scn
            row[f"persons_lifted_{scn}"] = persons_lifted
            row[f"gap_closed_{scn}_$"] = gap_closed

        rows.append(row)

    df = pd.DataFrame(rows)
    if group_col is not None:
        df = df.sort_values(group_col).reset_index(drop=True)
    return df


def compute_poverty_impact(
    units: pd.DataFrame,
    *,
    tax_year: int,
    scenarios: Sequence[str] = _DEFAULT_SCENARIOS,
    eitc_col: str = "eitc_amount",
    ctc_col: str = "ctc_refundable",
    hi_eitc_col: str = "hi_eitc_amount",
    arpa_ctc_col: str = "arpa_ctc_refundable",
    qualifying_children_col: str = "num_qualifying_children",
    hi_ctc_per_child: float = 650.0,
    hi_ctc_takeup_rate: float = 0.80,
    hi_eitc_100pct_takeup_rate: float = 0.95,
    arpa_ctc_takeup_rate: float = 0.95,
    rxkids_col: str = "rxkids_amount",
    household_type_col: str = "filing_status",
    weight_col: str = "weight",
    tenure_col: str = "tenure",
) -> PovertyImpactResult:
    """Compute SPM poverty impact of EITC, CTC, and HI state EITC, plus expansions.

    See module docstring for the scenario catalog.

    Parameters
    ----------
    units:
        Tax-unit DataFrame, post-:func:`compute_base_tax` and
        :func:`assign_geography`. Must carry the geography columns
        ``county``, ``house_district``, ``senate_district`` (added by
        :func:`tax_modeler.analysis.puma_crosswalk.assign_geography`).
    tax_year:
        Year for threshold lookup and (informational) for credit
        parameters. The credit *values* are already baked into the
        ``eitc_col`` / ``ctc_col`` / ``hi_eitc_col`` columns at compute
        time — this argument does not recompute them.
    scenarios:
        Which counterfactuals to evaluate. Default = all seven.
    hi_ctc_per_child:
        Dollar value of the hypothetical Hawaii state CTC per
        qualifying child (default $650). Used only when ``"hi_ctc_650"``
        is in ``scenarios``.
    hi_ctc_takeup_rate:
        Take-up rate applied to the hi_ctc_650 expansion increment.
        Default 0.80 — consistent with enacted state CTCs (MN 2023, VT
        2022 first-year ramp). Setting this to 0.0 zeroes the lift.
    hi_eitc_100pct_takeup_rate:
        Take-up rate applied to the hi_eitc_100pct expansion increment.
        Default 0.95 — existing HI EITC claimers continue claiming
        automatically (HI attaches to federal), so this captures the
        new-claim friction on the marginal 60-pp band.
    arpa_ctc_takeup_rate:
        Take-up rate applied to the expanded_ctc_2021 increment.
        Default 0.95 — federal CTC steady-state participation rate.
    """
    required = {"filing_status", "num_dependents", "county",
                "house_district", "senate_district", weight_col, eitc_col,
                ctc_col, hi_eitc_col}
    missing = required - set(units.columns)
    if missing:
        raise KeyError(
            f"compute_poverty_impact missing required columns: {sorted(missing)}"
        )

    df = units.copy()

    # 1. Baseline SPM resources (with all credits intact).
    # NOTE: ``rxkids_col`` is wired with ``rxkids_col=None`` here so
    # baseline resources reflect the *current* policy (RxKids does not
    # exist in Hawaii). The ``rxkids_hi`` scenario adds the amount as
    # a counterfactual expansion in ``_scenario_resources`` below.
    df, spm_meta = compute_spm_resources(
        df,
        eitc_col=eitc_col,
        refundable_ctc_col=ctc_col,
        hi_eitc_col=hi_eitc_col,
        rxkids_col=None,
    )

    # 2. Per-unit Hawaii SPM threshold.
    df["spm_threshold"] = threshold_for_units(df, year=tax_year, tenure_col=tenure_col)
    threshold = df["spm_threshold"].to_numpy(dtype=float)

    # 3. Person-equivalent weight (for "persons lifted" metric).
    df["person_weight"] = df[weight_col].astype(float).to_numpy() * _persons_per_unit(df)
    person_w = df["person_weight"].to_numpy(dtype=float)
    filer_w = df[weight_col].astype(float).to_numpy()

    # 4. Counterfactual resources per scenario.
    baseline_r = df["spm_resources"].to_numpy(dtype=float)
    for scn in scenarios:
        df[f"spm_resources_{scn}"] = _scenario_resources(
            baseline_resources=baseline_r,
            units=df,
            scenario=scn,
            eitc_col=eitc_col,
            ctc_col=ctc_col,
            hi_eitc_col=hi_eitc_col,
            arpa_ctc_col=arpa_ctc_col,
            qualifying_children_col=qualifying_children_col,
            hi_ctc_per_child=hi_ctc_per_child,
            hi_ctc_takeup_rate=hi_ctc_takeup_rate,
            hi_eitc_100pct_takeup_rate=hi_eitc_100pct_takeup_rate,
            arpa_ctc_takeup_rate=arpa_ctc_takeup_rate,
            rxkids_col=rxkids_col,
        )

    # 5. Aggregate at each geography level.
    by_state = _aggregate(
        df, group_col=None, threshold=threshold,
        person_weight=person_w, filer_weight=filer_w, scenarios=scenarios,
    )
    by_county = _aggregate(
        df, group_col="county", threshold=threshold,
        person_weight=person_w, filer_weight=filer_w, scenarios=scenarios,
    )
    by_hd = _aggregate(
        df, group_col="house_district", threshold=threshold,
        person_weight=person_w, filer_weight=filer_w, scenarios=scenarios,
    )
    by_sd = _aggregate(
        df, group_col="senate_district", threshold=threshold,
        person_weight=person_w, filer_weight=filer_w, scenarios=scenarios,
    )

    # 5a. Household-type disaggregation (single / HoH / MFJ / MFS).
    # HoH = single-mother proxy for RxKids analysis.
    if household_type_col not in df.columns:
        raise KeyError(
            f"household_type_col={household_type_col!r} not in units; "
            "expected one of the filing_status columns."
        )
    by_ht = _aggregate(
        df, group_col=household_type_col, threshold=threshold,
        person_weight=person_w, filer_weight=filer_w, scenarios=scenarios,
    )
    # Restrict to the canonical filing-status set so downstream consumers
    # can rely on the row labels even if the input frame has stray values.
    by_ht = by_ht[by_ht[household_type_col].isin(_HOUSEHOLD_TYPES)].reset_index(drop=True)

    # 5b. Augment by_state with HoH-specific poverty metrics. This is the
    # single-mother summary advocates need to cite when discussing RxKids
    # poverty impact.
    hoh = by_ht[by_ht[household_type_col] == "head_of_household"]
    state_row_extras: dict[str, float] = {}
    if not hoh.empty:
        hoh_row = hoh.iloc[0]
        state_row_extras["poverty_rate_hoh_baseline"] = float(hoh_row["poverty_rate_baseline"])
        state_row_extras["persons_in_poverty_hoh_baseline"] = float(
            hoh_row["persons_in_poverty_baseline"]
        )
        state_row_extras["weighted_persons_hoh"] = float(hoh_row["weighted_persons"])
        for scn in scenarios:
            col = f"persons_lifted_{scn}"
            if col in hoh_row.index:
                state_row_extras[f"persons_lifted_{scn}_hoh"] = float(hoh_row[col])
            rate_col = f"poverty_rate_{scn}"
            if rate_col in hoh_row.index:
                state_row_extras[f"poverty_rate_{scn}_hoh"] = float(hoh_row[rate_col])
    else:
        # No HoH filers in the frame — zero out HoH summary fields so
        # downstream report code can rely on the columns existing.
        state_row_extras["poverty_rate_hoh_baseline"] = 0.0
        state_row_extras["persons_in_poverty_hoh_baseline"] = 0.0
        state_row_extras["weighted_persons_hoh"] = 0.0
        for scn in scenarios:
            state_row_extras[f"persons_lifted_{scn}_hoh"] = 0.0
            state_row_extras[f"poverty_rate_{scn}_hoh"] = 0.0
    for k, v in state_row_extras.items():
        by_state[k] = v

    notes: list[str] = list(spm_meta.notes)
    notes.append(
        "Static counterfactual: no labor supply / marriage / fertility / "
        "filing response modeled. Persons-lifted figures are upper bounds for "
        "removal scenarios and lower bounds for expansion scenarios."
    )
    notes.append(
        f"hi_ctc_650 scenario applies a {hi_ctc_takeup_rate:.0%} take-up rate "
        f"to a hypothetical ${int(hi_ctc_per_child)}/child Hawaii state CTC. "
        "Pass --hi-ctc-takeup-rate (or hi_ctc_takeup_rate=) to sweep."
    )
    notes.append(
        f"hi_eitc_100pct applies {hi_eitc_100pct_takeup_rate:.0%} take-up on "
        "the 60-pp HI EITC increment; existing 40%-band receipt is unchanged. "
        f"expanded_ctc_2021 applies {arpa_ctc_takeup_rate:.0%} take-up on the "
        "ARPA-CTC delta."
    )

    if "rxkids_hi" in scenarios:
        notes.append(
            "rxkids_hi scenario adds the rxkids_amount column as a "
            "non-taxable cash transfer to SPM resources. Defaults model "
            "a Medicaid-eligibility-gated variant ($500/mo prenatal × 9, "
            "$125/mo postnatal per child 0-5 × 12, 80% take-up). See "
            "RXKIDS_METHODOLOGY.md for parameter sourcing and the "
            "universal-variant override recipe."
        )

    return PovertyImpactResult(
        units=df,
        by_state=by_state,
        by_county=by_county,
        by_house_district=by_hd,
        by_senate_district=by_sd,
        by_household_type=by_ht,
        tax_year=tax_year,
        spm_meta=spm_meta,
        scenarios=tuple(scenarios),
        notes=tuple(notes),
    )


__all__ = ["compute_poverty_impact", "PovertyImpactResult"]
