"""SB 3125 CD1 fiscal forecast with behavioral response and growth corrections.

Improvements over forecast_sb3125_cd1.py:

  1. **ETI behavioral response** — taxable-income elasticity reduces top-bracket
     income for filers above the 13% threshold. Saez/Slemrod/Giertz range:
     ETI=0.15 (low) / 0.25 (mid) / 0.40 (high).

  2. **Migration response** — Young/Varner top-1% migration elasticity per pp
     top-rate change. Phased in over 5 years from 2027.

  3. **PTE election shift** — Bill creates 2pp incentive for $1M+ pass-through
     income to elect PTE (11%) vs face individual 13%. Reported as a
     deduction from gross bracket revenue.

  4. **Top-income growth premium** — Top earners (>$500K) get an additional
     1.5pp/yr growth above the median-anchored projection (Piketty-Saez-Zucman
     top-1% > median differential, conservatively halved for state level).

  5. **Corporate growth proxy for CGEC** — Capital Goods Excise Credit
     ($34.6M, 90% corporate) now grows with Hawaii nominal GDP (5%/yr),
     not median household income (3.5%/yr).

  6. **Corporate REEC AGI eligibility option** — Bill text is ambiguous on
     whether AGI limits bind to corporations. Default False (no limit), but
     a sensitivity scenario sets True (treat as $200K+ bin).

  7. **Baseline-scaling diagnostic** — Reports both raw and COR-scaled
     bracket delta (microsim baseline = $2,282M; COR FY27 = $3,050M).

Three integrated scenarios:
    LOW       — eti=0.15, migration=0.05, pte=0.20, alpha=1.6, reec=obbba_severe
    MID       — eti=0.25, migration=0.10, pte=0.35, alpha=1.5, reec=obbba_mid
    HIGH      — eti=0.40, migration=0.15, pte=0.50, alpha=1.4, reec=pre_obbba

Output:
  /tmp/sb3125_cd1_enhanced_2027_2031.csv
"""
from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path

DATA_DIR = Path("/Users/dtomkatsu/ctc-and-eitc/data/raw/pums")
CACHE_FILE = Path("/tmp/tax_units_cache.parquet")
OUT_CSV = Path("/tmp/sb3125_cd1_enhanced_2027_2031.csv")
TARGET_YEARS = [2027, 2028, 2029, 2030, 2031]

# COR FY27 individual-income tax projection (Sep 2025 forecast)
COR_FY27_IIT_PROJ_M = 3050.0

# Three calibrated scenarios. Calibration is anchored to (a) the official
# 5yr fiscal-impact estimate of ~$680M, (b) state-level ETI literature
# (Rauh/Shyu 2024 California 13.3% study), (c) PTE rate 9% (Act 50, Hawaii)
# vs bill's 13% individual top → 4pp arbitrage gap, and (d) REEC nonrefundable
# utilization considerations + Hawaii solar saturation.
SCENARIOS = [
    {
        "label":  "LOW",
        "alpha":  1.7,                # steeper top tail (less concentration)
        "reec":   "obbba_severe",
        "behav":  "high",             # strong behavioral response (low revenue gain)
        "corp_agi_limit": True,
        "top_premium":     0.003,     # +0.3%/yr: MID – 1.0pp (strong outmigration)
        "reec_eff_share":  0.65,      # only 65% of claims actually offset tax
        "cgec_growth":     0.020,     # 2%/yr business growth
        "itemized_adj":    True,
    },
    {
        "label":  "MID",
        "alpha":  1.5,
        "reec":   "obbba_mid",
        "behav":  "mid",              # ETI=0.40, migr=0.10, pte=0.70
        "corp_agi_limit": False,
        "top_premium":     0.013,     # +1.3%/yr: IRS SOI 1.8pp differential – 0.5pp Hawaii haircut
        "reec_eff_share":  0.80,      # 80% utilization (literature midpoint)
        "cgec_growth":     0.030,     # 3%/yr (calibrated down from 5%)
        "itemized_adj":    True,
    },
    {
        "label":  "HIGH",
        "alpha":  1.4,
        "reec":   "pre_obbba",
        "behav":  "low",              # weak behavioral (high revenue gain)
        "corp_agi_limit": False,
        "top_premium":     0.023,     # +2.3%/yr: MID + 1.0pp (national-rate convergence)
        "reec_eff_share":  1.00,      # full claim utilization
        "cgec_growth":     0.040,     # 4%/yr business growth
        "itemized_adj":    False,     # no itemized adjustment (overstates 13% base)
    },
]

REPO = Path(__file__).parent
sys.path.insert(0, str(REPO / "packages" / "tax_modeler" / "src"))
sys.path.insert(0, str(REPO / "packages" / "census_forecaster" / "src"))
sys.path.insert(0, str(REPO / "packages" / "pums_estimator" / "src"))
sys.path.insert(0, str(REPO / "packages" / "common" / "src"))


def run_one_scenario(
    base_calibrated, *, scenario, target_years,
    _compute_base_tax,
    project_tax_units_forward,
    TaxCalculator, TaxSystemRegistry, compare_systems,
    compute_credit_overlay,
    synthesize_top_filers, validate_top_synthesis,
    BehavioralParams, apply_behavioral_response,
    apply_top_income_growth_premium,
    apply_itemized_deduction_adjustment,
):
    import time
    label  = scenario["label"]
    alpha  = scenario["alpha"]
    reec   = scenario["reec"]
    behav  = scenario["behav"]
    corp_agi = scenario["corp_agi_limit"]
    top_premium = scenario["top_premium"]
    reec_eff = scenario["reec_eff_share"]
    cgec_g   = scenario["cgec_growth"]
    do_item  = scenario["itemized_adj"]
    print(f"\n{'='*78}\nSCENARIO {label}: alpha={alpha} reec={reec} behav={behav} "
          f"corp_agi={corp_agi} top_premium={top_premium:+.3f}\n"
          f"  reec_eff_share={reec_eff} cgec_growth={cgec_g:.3f} itemized_adj={do_item}\n"
          f"{'='*78}", flush=True)

    # Synthesize fresh from the calibrated (no-synthesis) base
    units = synthesize_top_filers(base_calibrated, pareto_alpha=alpha)
    units = _compute_base_tax(units)
    units, tail_k = rescale_synthetic_tail_to_tax_target(units)
    units = _compute_base_tax(units)
    v = validate_top_synthesis(units)
    print(f"  Synthesis: {v['filers_1m_plus']:,.0f} filers @ $1M+ "
          f"({100*v['filer_target_ratio']:.1f}%), ${v['tax_1m_plus_$M']:,.1f}M tax "
          f"({100*v['tax_target_ratio']:.1f}%), tail_k={tail_k:.4f}", flush=True)

    behav_params = BehavioralParams.named(behav)
    print(f"  Behavioral: ETI={behav_params.eti}, migration_elast="
          f"{behav_params.migration_elast}, pte_capture={behav_params.pte_capture}",
          flush=True)

    calc = TaxCalculator()
    rows = []
    for year in target_years:
        t0 = time.perf_counter()
        # 1) Standard projection (county B19013 income growth)
        projected = project_tax_units_forward(units, target_year=year, method="ensemble")

        # 2) Top-income growth premium (corrects under-projection of top-1%)
        projected = apply_top_income_growth_premium(
            projected, target_year=year, annual_premium=top_premium,
        )

        # 2b) Itemized-deduction adjustment for top filers
        if do_item:
            projected = apply_itemized_deduction_adjustment(projected)

        # 3) Pre-behavioral baseline + scenario revenue (static)
        baseline_cfg = TaxSystemRegistry.get_act46_system(year)
        scenario_cfg = TaxSystemRegistry.get_sb3125_cd1_system(year)
        cmp_static = compare_systems(projected, baseline_cfg, scenario_cfg, calculator=calc)
        diff_static = float(cmp_static[cmp_static["system"] == "Difference"].iloc[0]["revenue_millions"])
        baseline_static = float(cmp_static[cmp_static["system"] == baseline_cfg.name].iloc[0]["revenue_millions"])

        # 4) Apply behavioral response (ETI + migration), recompute scenario revenue
        adjusted, behav_diag = apply_behavioral_response(
            projected, behav_params, target_year=year,
        )
        cmp_behav = compare_systems(adjusted, baseline_cfg, scenario_cfg, calculator=calc)
        diff_behav = float(cmp_behav[cmp_behav["system"] == "Difference"].iloc[0]["revenue_millions"])

        # 5) PTE election shift (revenue moves from individual to PTE form)
        pte_shift = behav_diag["pte_revenue_loss_$M"]
        bracket_delta_after_response = diff_behav - pte_shift

        # 6) Credit-cap overlay (with corp AGI + utilization + cgec growth)
        credit = compute_credit_overlay(
            year, reec_demand_scenario=reec,
            corp_subject_to_agi_limit=corp_agi,
            reec_effective_claim_share=reec_eff,
            cgec_annual_growth=cgec_g,
        )
        credit_total = credit["total_credit_savings_$M"]

        total = bracket_delta_after_response + credit_total

        # 7) COR-scaled diagnostic: scale bracket delta to match COR baseline
        cor_scale_factor = COR_FY27_IIT_PROJ_M / baseline_static if baseline_static > 0 else 1.0
        bracket_delta_cor_scaled = bracket_delta_after_response * cor_scale_factor

        rows.append({
            "scenario":                       label,
            "tax_year":                       year,
            "act46_baseline_$M":              round(baseline_static, 2),
            "bracket_delta_static_$M":        round(diff_static, 2),
            "eti_response_$M":                round(diff_behav - diff_static, 2),
            "pte_shift_$M":                   round(-pte_shift, 2),
            "bracket_delta_post_$M":          round(bracket_delta_after_response, 2),
            "bracket_delta_cor_scaled_$M":    round(bracket_delta_cor_scaled, 2),
            "reec_savings_$M":                credit["reec_savings_$M"],
            "cgec_savings_$M":                credit["cgec_savings_$M"],
            "tcra_savings_$M":                credit["tcra_savings_$M"],
            "credit_total_$M":                credit_total,
            "total_impact_$M":                round(total, 2),
            "filers_1m_post_response":        round(behav_diag["filers_1m_post_response"], 0),
        })
        print(f"  TY {year}: static={diff_static:+.1f}M  "
              f"ETI={diff_behav-diff_static:+.1f}M  "
              f"PTE={-pte_shift:+.1f}M  "
              f"-> bracket={bracket_delta_after_response:+.1f}M  "
              f"credit={credit_total:+.1f}M  "
              f"TOTAL={total:+.1f}M  ({time.perf_counter()-t0:.1f}s)", flush=True)
    return rows


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)

    try:
        import time
        import pandas as pd

        print("Importing modules...", flush=True)
        from tax_modeler.pipeline import _enrich_for_credits, _compute_base_tax, _calibrate
        from tax_modeler.projection.tax_unit_projector import project_tax_units_forward
        from tax_modeler.config.tax_system_config import (
            TaxCalculator, TaxSystemRegistry, compare_systems,
        )
        from tax_modeler.scenarios.sb3125_cd1_credits import compute_credit_overlay
        from tax_modeler.scenarios.top_income_synthesis import (
            synthesize_top_filers, validate_top_synthesis,
            rescale_synthetic_tail_to_tax_target,
        )
        from tax_modeler.scenarios.behavioral_response import (
            BehavioralParams,
            apply_behavioral_response,
            apply_top_income_growth_premium,
            apply_itemized_deduction_adjustment,
        )

        wall_start = time.perf_counter()

        if not CACHE_FILE.exists():
            print(f"ERROR: tax-unit cache not found at {CACHE_FILE}", flush=True)
            print("Run forecast_sb3125_cd1.py first to populate the cache.", flush=True)
            sys.exit(1)

        print(f"Loading cached units from {CACHE_FILE}...", flush=True)
        units = pd.read_parquet(CACHE_FILE)
        print(f"  {len(units):,} units loaded", flush=True)

        print("Enriching + base tax + calibrating (one-time)...", flush=True)
        units = _enrich_for_credits(units)
        units = _compute_base_tax(units)
        calibrated_base = _calibrate(units)

        all_rows = []
        for sc in SCENARIOS:
            all_rows.extend(run_one_scenario(
                calibrated_base, scenario=sc, target_years=TARGET_YEARS,
                _compute_base_tax=_compute_base_tax,
                project_tax_units_forward=project_tax_units_forward,
                TaxCalculator=TaxCalculator,
                TaxSystemRegistry=TaxSystemRegistry,
                compare_systems=compare_systems,
                compute_credit_overlay=compute_credit_overlay,
                synthesize_top_filers=synthesize_top_filers,
                validate_top_synthesis=validate_top_synthesis,
                BehavioralParams=BehavioralParams,
                apply_behavioral_response=apply_behavioral_response,
                apply_top_income_growth_premium=apply_top_income_growth_premium,
                apply_itemized_deduction_adjustment=apply_itemized_deduction_adjustment,
            ))

        df = pd.DataFrame(all_rows)
        df.to_csv(OUT_CSV, index=False)

        # ---- Summary tables -------------------------------------------------
        print("\n" + "=" * 100, flush=True)
        print("SB 3125 CD1 ENHANCED FISCAL IMPACT  ($M, vs Act 46 baseline, with behavioral response)",
              flush=True)
        print("=" * 100, flush=True)

        # Total impact pivot
        pv = df.pivot(index="tax_year", columns="scenario", values="total_impact_$M")
        pv = pv[["LOW", "MID", "HIGH"]]
        pv.loc["5yr cum"] = pv.sum()
        print("\nTotal annual fiscal impact ($M, post-behavioral):")
        print(pv.to_string(float_format=lambda x: f"{x:>9,.1f}"), flush=True)

        # Bracket-only (post-response) pivot
        pv_b = df.pivot(index="tax_year", columns="scenario", values="bracket_delta_post_$M")[["LOW","MID","HIGH"]]
        pv_b.loc["5yr cum"] = pv_b.sum()
        print("\nBracket-change impact (post-ETI/migration/PTE) ($M):")
        print(pv_b.to_string(float_format=lambda x: f"{x:>9,.1f}"), flush=True)

        # COR-scaled pivot
        pv_cs = df.pivot(index="tax_year", columns="scenario", values="bracket_delta_cor_scaled_$M")[["LOW","MID","HIGH"]]
        pv_cs.loc["5yr cum"] = pv_cs.sum()
        print("\nBracket-change impact, COR-scaled to actual revenue base ($M):")
        print(pv_cs.to_string(float_format=lambda x: f"{x:>9,.1f}"), flush=True)

        # Credit pivot
        pv_c = df.pivot(index="tax_year", columns="scenario", values="credit_total_$M")[["LOW","MID","HIGH"]]
        pv_c.loc["5yr cum"] = pv_c.sum()
        print("\nCredit-cap impact ($M):")
        print(pv_c.to_string(float_format=lambda x: f"{x:>9,.1f}"), flush=True)

        # Behavioral decomposition for MID at TY 2027
        mid27 = df[(df["scenario"] == "MID") & (df["tax_year"] == 2027)].iloc[0]
        print("\n" + "-" * 100, flush=True)
        print("BEHAVIORAL DECOMPOSITION (MID scenario, TY 2027):", flush=True)
        print("-" * 100, flush=True)
        print(f"  Static bracket delta:                   ${mid27['bracket_delta_static_$M']:>+8.2f}M", flush=True)
        print(f"  ETI/migration response (income shrink): ${mid27['eti_response_$M']:>+8.2f}M", flush=True)
        print(f"  PTE election shift to entity tax:       ${mid27['pte_shift_$M']:>+8.2f}M", flush=True)
        print(f"  Post-behavioral bracket delta:          ${mid27['bracket_delta_post_$M']:>+8.2f}M", flush=True)
        print(f"  COR-scaled (×{COR_FY27_IIT_PROJ_M/mid27['act46_baseline_$M']:.3f}):                "
              f"${mid27['bracket_delta_cor_scaled_$M']:>+8.2f}M", flush=True)

        print(f"\nSaved: {OUT_CSV}", flush=True)
        print(f"Total elapsed: {time.perf_counter() - wall_start:.1f}s", flush=True)

    except Exception as e:
        print(f"\nERROR: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
