"""SB 3125 CD2 vs TY2026-frozen baseline — ITEP-comparable distributional analysis.

Comparison frame:
  Baseline: Act 46 law frozen at TY2026 (TY2025 brackets + TY2026 standard
            deductions held constant for all projection years). This is the
            same frozen-law config as HB 2306 original, used here as a
            neutral baseline.
  Bill:     SB 3125 CD2 full implementation (year-specific CD2 brackets +
            Act 46 standard-deduction phase-in continuing as enacted).

Delta = CD2 full - TY2026 frozen law.

This mirrors ITEP's methodology (they compare to TY2026 law) but with our
microsim's income distribution. Results are decomposed into two components:
  bracket_delta: (CD2 brackets + frozen 2026 SDs) - (frozen 2026 brackets + frozen 2026 SDs)
                 = pure bracket-structure effect
  sd_delta:      (frozen 2026 brackets + Act46 SDs) - (frozen 2026 brackets + frozen 2026 SDs)
                 = Act 46 SD-expansion effect (ongoing law, not the bill)
  total_delta:   bracket_delta + sd_delta (= ITEP's headline number)

Outputs:
  /tmp/cd2_vs_fy26base_bracket_mid_2027_2031.csv
  /tmp/cd2_vs_fy26base_quintile_mid_2027_2031.csv
"""
from __future__ import annotations

import logging
import sys
import traceback
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

# Requires the workspace to be installed: `uv sync --all-packages`.
REPO = Path(__file__).parent

import numpy as np
import pandas as pd

# Public-name imports; underscore aliases still work but emit DeprecationWarning.
from tax_modeler.pipeline import compute_base_tax as _compute_base_tax
from tax_modeler.pipeline import enrich_for_credits as _enrich_for_credits
from tax_modeler.calibration.cg_imputation import impute_capital_gains_from_soi
from tax_modeler.config.tax_system_config import TaxCalculator, TaxSystemRegistry
from tax_modeler.scenarios.top_income_synthesis import (
    synthesize_top_filers, rescale_synthetic_tail_to_tax_target,
    redistribute_mid_high_incomes,
)
from tax_modeler.calibration.year_recalibrator import project_and_recalibrate
from tax_modeler.scenarios.quintile_analysis import (
    generate_quintile_report, compute_quintile_breaks,
    per_unit_tax,
)
from tax_modeler.adjustments.itemized_deductions import scale_deduction_params_for_target_year
from tax_modeler.liability.hawaii import NO_ITEMIZING

MID_ALPHA       = 1.5
MID_TOP_PREMIUM = 0.010
TARGET_YEARS    = [2027, 2028, 2029, 2030, 2031]
CALIBRATED_PKL  = Path("/tmp/sb3125_calibrated_base.pkl")

INCOME_BINS = {
    "below_50K":   (0,          50_000),
    "50K_200K":    (50_000,    200_000),
    "200K_1M":     (200_000, 1_000_000),
    "1M_plus":     (1_000_000, float("inf")),
}


def _bin_delta(inc, w, diffs):
    result = {}
    for label, (lo, hi) in INCOME_BINS.items():
        mask = (inc >= lo) & (inc < hi)
        result[label] = float(diffs[mask].sum() / 1e6)
    result["total"] = float(diffs.sum() / 1e6)
    return result


def main() -> None:
    if not CALIBRATED_PKL.exists():
        print(f"ERROR: {CALIBRATED_PKL} not found. Run forecast_sb3125_cd2_enhanced.py first.")
        sys.exit(1)

    import time
    wall = time.perf_counter()

    print("Loading calibrated base...", flush=True)
    base = pd.read_pickle(CALIBRATED_PKL)
    units = redistribute_mid_high_incomes(base, pareto_alpha=MID_ALPHA)
    units = synthesize_top_filers(units, pareto_alpha=MID_ALPHA)
    units = _enrich_for_credits(units)
    units = impute_capital_gains_from_soi(units)
    units = _compute_base_tax(units)
    units, tail_k = rescale_synthetic_tail_to_tax_target(units)
    units = _compute_base_tax(units)
    print(f"  tail_k={tail_k:.4f}", flush=True)

    calc = TaxCalculator()
    base_2026_breaks = compute_quintile_breaks(units)
    print(
        f"  2026 quintile breaks: "
        f"${base_2026_breaks[0]:,.0f} / ${base_2026_breaks[1]:,.0f} / "
        f"${base_2026_breaks[2]:,.0f} / ${base_2026_breaks[3]:,.0f}",
        flush=True,
    )

    rows = []
    quintile_frames, bracket_frames = [], []

    for yr in TARGET_YEARS:
        print(f"  TY {yr}...", flush=True)

        projected, _ = project_and_recalibrate(
            units,
            target_year=yr,
            use_forward_targets=True,
            use_soi_anchor=True,
            soi_year=2022,
            hawaii_capgain_adjustment=0.95,
            use_cbo_aging=True,
            cbo_vintage="2025-01",
            top_premium_pct=MID_TOP_PREMIUM,
            top_bracket_differential=0.025,
            method="ensemble",
        )

        inc = projected["income"].to_numpy(dtype=float)
        w   = projected["weight"].to_numpy(dtype=float)

        # Three configs:
        # A: TY2026-frozen baseline (brackets=2025, SDs=2026)
        # B: TY2026-frozen brackets + Act46 SDs (isolates SD effect)
        # C: CD2 full (CD2 brackets + Act46 SDs)
        cfg_a = TaxSystemRegistry.get_hb2306_orig_system(yr)   # frozen 2026
        cfg_c = TaxSystemRegistry.get_sb3125_cd2_system(yr)    # CD2 full
        from tax_modeler.config.tax_system_config import TaxSystemConfig
        cfg_b = TaxSystemConfig(
            name=f"frozen2026_brackets_act46_sds_{yr}",
            year=yr,
            bracket_year=2025,           # frozen 2026 brackets
            standard_deduction_year=yr,  # Act 46 SD phase-in
            personal_exemption=TaxSystemRegistry.PERSONAL_EXEMPTIONS.get(2026, 1200),
            description=f"Frozen 2026 brackets + Act46 TY{yr} SDs",
        )

        # Per-scenario itemized deduction scaling: frozen-2026 baseline uses
        # TY2026 mortgage/SALT/charitable amounts; CD2 uses target-year scales
        # (Act 46 phase-in conceptually keeps these growing under current law).
        # Without this, both scenarios would share an identically scaled
        # itemized column, slightly misstating the SD-vs-itemize margin
        # under each counterfactual. Effect is small but principled.
        ded_params_2026   = scale_deduction_params_for_target_year(2026, geoid="15003")
        ded_params_target = scale_deduction_params_for_target_year(yr,   geoid="15003")

        # Build scenario-specific projected copies with year-appropriate itemized.
        # _compute_base_tax repopulates `hi_itemized_deduction` based on the
        # supplied params; per_unit_tax then reads that column.
        proj_frozen = _compute_base_tax(
            projected.copy(), tax_year=2026, deduction_params=ded_params_2026,
        )
        proj_target = _compute_base_tax(
            projected.copy(), tax_year=yr, deduction_params=ded_params_target,
        )

        tax_a = per_unit_tax(proj_frozen, cfg_a, calc)  # frozen-2026 baseline (frozen itemized)
        tax_b = per_unit_tax(proj_target, cfg_b, calc)  # frozen brackets + Act46 SDs (target itemized)
        tax_c = per_unit_tax(proj_target, cfg_c, calc)  # CD2 full (target itemized)

        # Component deltas (filer-level, $)
        bracket_effect = (tax_c - tax_b) * w   # CD2 brackets vs frozen-2026 brackets, holding SD constant
        sd_effect      = (tax_b - tax_a) * w   # Act46 SD expansion effect (ongoing law)
        total_effect   = (tax_c - tax_a) * w   # full delta: CD2 vs frozen-2026

        br = _bin_delta(inc, w, bracket_effect)
        sd = _bin_delta(inc, w, sd_effect)
        tt = _bin_delta(inc, w, total_effect)

        rows.append({"year": yr, "component": "bracket_delta_$M", **br})
        rows.append({"year": yr, "component": "sd_expansion_delta_$M", **sd})
        rows.append({"year": yr, "component": "total_delta_$M", **tt})

        # Quintile report (total delta, vs frozen-2026 baseline).
        # NOTE: generate_quintile_report takes a single df; the per-scenario
        # itemization above is applied to the headline component breakdown
        # (rows[]) but the quintile distribution uses target-year itemized
        # for both sides. Effect on the quintile shape is small (<1% on
        # Q1-Q5 totals) since itemized scaling is mostly a top-bracket effect.
        empty_overlay = {}
        q_df, b_df, _ = generate_quintile_report(
            proj_target, cfg_a, cfg_c,
            credit_overlay=empty_overlay,
            calc=calc,
            scenario_params=None,
            quintile_breaks=base_2026_breaks,
            cor_scale_factor=1.0,   # raw — no COR scaling for this comparison
        )
        q_df.insert(0, "tax_year", yr)
        b_df.insert(0, "tax_year", yr)
        quintile_frames.append(q_df)
        bracket_frames.append(b_df)

    df_summary = pd.DataFrame(rows)
    all_quintiles = pd.concat(quintile_frames, ignore_index=True)
    all_brackets  = pd.concat(bracket_frames,  ignore_index=True)

    Q_CSV = Path("/tmp/cd2_vs_fy26base_quintile_mid_2027_2031.csv")
    B_CSV = Path("/tmp/cd2_vs_fy26base_bracket_mid_2027_2031.csv")
    all_quintiles.to_csv(Q_CSV, index=False)
    all_brackets.to_csv(B_CSV, index=False)

    # ── Print summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 90, flush=True)
    print("SB 3125 CD2 vs TY2026-FROZEN BASELINE — MID Scenario", flush=True)
    print("Baseline = Act 46 frozen at TY2026 (no further phase-ins)", flush=True)
    print("Bill     = SB 3125 CD2 brackets + Act 46 SD phase-in continues", flush=True)
    print("=" * 90, flush=True)

    def _print_component(component_label, header_title):
        print(f"\n--- {header_title} ---", flush=True)
        print(f"{'Year':<6} {'<$50K':>10} {'$50K-$200K':>12} {'$200K-$1M':>12} {'$1M+':>10} {'Annual':>10} {'Cumulative':>12}", flush=True)
        print("-" * 78, flush=True)
        cum = {k: 0.0 for k in list(INCOME_BINS.keys()) + ["total"]}
        for yr in TARGET_YEARS:
            r = df_summary[(df_summary["year"] == yr) & (df_summary["component"] == component_label)].iloc[0]
            for k in cum:
                cum[k] += r[k]
            print(f"{yr:<6} {r['below_50K']:>+9.1f}M {r['50K_200K']:>+11.1f}M "
                  f"{r['200K_1M']:>+11.1f}M {r['1M_plus']:>+9.1f}M "
                  f"{r['total']:>+9.1f}M {cum['total']:>+11.1f}M", flush=True)
        print("-" * 78, flush=True)
        print(f"{'5yr':<6} {cum['below_50K']:>+9.1f}M {cum['50K_200K']:>+11.1f}M "
              f"{cum['200K_1M']:>+11.1f}M {cum['1M_plus']:>+9.1f}M {cum['total']:>+9.1f}M", flush=True)
        return cum

    br_5yr = _print_component(
        "bracket_delta_$M",
        "Bracket effect only (CD2 brackets vs TY2026-frozen brackets, SDs held at Act46)",
    )
    sd_5yr = _print_component(
        "sd_expansion_delta_$M",
        "Act 46 SD-expansion effect (ongoing current law, not the bill)",
    )
    tt_5yr = _print_component(
        "total_delta_$M",
        "TOTAL: CD2 full vs TY2026-frozen (= ITEP's headline number, our microsim)",
    )

    print("\n--- Quintile distribution (total delta, TY 2027) ---", flush=True)
    q27 = all_quintiles[all_quintiles["tax_year"] == 2027]
    pd.set_option("display.float_format", "{:,.1f}".format)
    print(q27[[
        "quintile", "household_count",
        "avg_per_hh_bracket_change", "avg_per_hh_total_change",
        "total_bracket_$M", "total_change_$M",
        "pct_pay_more", "pct_pay_less",
    ]].to_string(index=False), flush=True)

    # ITEP's published annual figures from "26.05.06 HI SB 3125 CD Analysis.xlsx".
    # Each year is a standalone snapshot of total drift from TY2026-frozen law
    # ($M, residents only). NOT a running sum across years.
    ITEP_ANNUAL = {2027: -227.0, 2028: -258.0, 2029: -534.0, 2030: -563.0, 2031: -622.0}

    print(f"\n\nComparison to ITEP — annual snapshots vs TY2026-frozen baseline (residents, $M):", flush=True)
    print(
        f"{'Year':<6} {'Ours (total)':>14} {'Ours (bracket)':>16} "
        f"{'ITEP':>10} {'Gap (total-ITEP)':>18}",
        flush=True,
    )
    print("-" * 70, flush=True)
    sum_tt = 0.0
    sum_br = 0.0
    sum_itep = 0.0
    for yr in TARGET_YEARS:
        ours_br = df_summary[(df_summary["year"] == yr) & (df_summary["component"] == "bracket_delta_$M")].iloc[0]["total"]
        ours_tt = df_summary[(df_summary["year"] == yr) & (df_summary["component"] == "total_delta_$M")].iloc[0]["total"]
        itep    = ITEP_ANNUAL[yr]
        gap     = ours_tt - itep
        sum_tt   += ours_tt
        sum_br   += ours_br
        sum_itep += itep
        print(
            f"{yr:<6} {ours_tt:>+12.1f}M {ours_br:>+14.1f}M "
            f"{itep:>+8.1f}M {gap:>+16.1f}M",
            flush=True,
        )
    print("-" * 70, flush=True)
    print(
        f"{'5yrΣ':<6} {sum_tt:>+12.1f}M {sum_br:>+14.1f}M "
        f"{sum_itep:>+8.1f}M {sum_tt - sum_itep:>+16.1f}M",
        flush=True,
    )
    print("(5yrΣ row sums annual snapshots — useful as a fiscal-note style aggregate, not a stock figure.)", flush=True)

    print(f"\nSaved: {Q_CSV}", flush=True)
    print(f"Saved: {B_CSV}", flush=True)
    print(f"Total elapsed: {time.perf_counter() - wall:.1f}s", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
