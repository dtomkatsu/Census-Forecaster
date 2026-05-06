"""SB 3125 CD1 quintile distributional analysis (MID scenario, TY 2027-2031).

Uses the full revised pipeline:
  - use_forward_targets:  rake to forward DOTAX-shaped filer counts;
                          Phase 2 anchors aggregate tax to COR projection.
  - use_soi_anchor:       SOI Table 1.4 tier composition for $1M+ filers
                          (CG/wages/business shares from administrative data).
  - use_cbo_aging:        per-component CBO Outlook nominal aging (wages 4.4%/yr,
                          CG 5-9%/yr, business 4.8%/yr) instead of uniform B19013
                          county-median growth. With default Hawaii calibration
                          (DEFAULT_HAWAII_FACTORS) on by default.

REEC credit overlay applied via compute_credit_overlay (REEC §235-12.5,
CGEC §235-110.31, TCRA §235-15) at MID scenario parameters:
    obbba_mid REEC demand, eff_share=0.65, cgec_growth=1.5%/yr, reec_cf_m=$6M.

Outputs:
  /tmp/sb3125_quintile_revised_2027_2031.csv
  /tmp/sb3125_bracket_revised_2027_2031.csv
  /tmp/sb3125_quintile_distributional_report.pdf
"""
from __future__ import annotations

import logging
import sys
import traceback
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

REPO = Path(__file__).parent
for p in (
    REPO / "packages" / "tax_modeler" / "src",
    REPO / "packages" / "census_forecaster" / "src",
    REPO / "packages" / "pums_estimator" / "src",
    REPO / "packages" / "common" / "src",
):
    sys.path.insert(0, str(p))

import pandas as pd

from tax_modeler.pipeline import _compute_base_tax, _enrich_for_credits
from tax_modeler.calibration.cg_imputation import impute_capital_gains_from_soi
from tax_modeler.config.tax_system_config import TaxCalculator, TaxSystemRegistry
from tax_modeler.scenarios.top_income_synthesis import (
    synthesize_top_filers, rescale_synthetic_tail_to_tax_target,
    redistribute_mid_high_incomes,
)
from tax_modeler.calibration.year_recalibrator import project_and_recalibrate
from tax_modeler.scenarios.sb3125_cd1_credits import compute_credit_overlay
from tax_modeler.scenarios.quintile_analysis import (
    generate_quintile_report, compute_quintile_breaks,
    cor_scale_factor_for_year, per_unit_tax,
)

# MID scenario parameters (matches forecast_sb3125_cd1_enhanced.py MID).
MID_ALPHA           = 1.5
MID_TOP_PREMIUM     = 0.010
MID_REEC            = "obbba_mid"
MID_REEC_EFF_SHARE  = 0.65
MID_CGEC_GROWTH     = 0.015
MID_REEC_CF_M       = 6.0
MID_CORP_AGI_LIMIT  = False
TARGET_YEARS        = [2027, 2028, 2029, 2030, 2031]

CALIBRATED_PKL = Path("/tmp/sb3125_calibrated_base.pkl")


def main() -> None:
    if not CALIBRATED_PKL.exists():
        print(f"ERROR: {CALIBRATED_PKL} not found. Run forecast_sb3125_cd1_enhanced.py first.")
        sys.exit(1)

    import time
    wall = time.perf_counter()

    print("Loading calibrated base...", flush=True)
    base = pd.read_pickle(CALIBRATED_PKL)

    print(f"Synthesizing top filers (MID alpha={MID_ALPHA})...", flush=True)
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

    quintile_frames, bracket_frames = [], []

    # MID scenario dict for REEC distribution inside generate_quintile_report
    mid_scenario_params = {
        "label":          "MID",
        "alpha":          MID_ALPHA,
        "reec":           MID_REEC,
        "behav":          "mid",
        "corp_agi_limit": MID_CORP_AGI_LIMIT,
        "top_premium":    MID_TOP_PREMIUM,
        "reec_eff_share": MID_REEC_EFF_SHARE,
        "cgec_growth":    MID_CGEC_GROWTH,
        "reec_cf_m":      MID_REEC_CF_M,
    }

    for yr in TARGET_YEARS:
        print(f"  TY {yr}...", flush=True)
        # Methodology stack (same as forecast_hb2306_quintile.py):
        #   - forward_targets re-rake + COR anchor at Phase 2
        #   - SOI Table 1.4 anchor for $1M+ tier composition
        #   - CBO component aging with default Hawaii calibration factors
        # Pass cbo_hawaii_factors={c: 1.0 ...} to disable HI calibration
        # (pure CBO-national aging, matches ITEP methodology by construction).
        projected, _forward = project_and_recalibrate(
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

        baseline_cfg = TaxSystemRegistry.get_act46_system(yr)
        sb3125_cfg   = TaxSystemRegistry.get_sb3125_cd1_system(yr)

        # COR scaling: ratio of official COR FY{yr} IIT projection to our
        # microsim Act 46 baseline. Brings totals into ITEP/COR comparable units.
        act46_M = float(
            (per_unit_tax(projected, baseline_cfg, calc)
             * projected["weight"].to_numpy(dtype=float)).sum() / 1e6
        )
        cor_factor = cor_scale_factor_for_year(yr, act46_M)

        # REEC + CGEC + TCRA credit overlay for this year
        credit_overlay = compute_credit_overlay(
            yr,
            reec_demand_scenario=MID_REEC,
            corp_subject_to_agi_limit=MID_CORP_AGI_LIMIT,
            reec_effective_claim_share=MID_REEC_EFF_SHARE,
            cgec_annual_growth=MID_CGEC_GROWTH,
            reec_carryforward_utilization_m=MID_REEC_CF_M,
        )

        q_df, b_df, _ = generate_quintile_report(
            projected, baseline_cfg, sb3125_cfg,
            credit_overlay=credit_overlay,
            calc=calc,
            scenario_params=mid_scenario_params,
            quintile_breaks=base_2026_breaks,
            cor_scale_factor=cor_factor,
        )
        q_df.insert(0, "tax_year", yr)
        b_df.insert(0, "tax_year", yr)
        quintile_frames.append(q_df)
        bracket_frames.append(b_df)

    all_quintiles = pd.concat(quintile_frames, ignore_index=True)
    all_brackets  = pd.concat(bracket_frames,  ignore_index=True)

    Q_CSV = Path("/tmp/sb3125_quintile_revised_2027_2031.csv")
    B_CSV = Path("/tmp/sb3125_bracket_revised_2027_2031.csv")
    all_quintiles.to_csv(Q_CSV, index=False)
    all_brackets.to_csv(B_CSV, index=False)
    print(f"Saved: {Q_CSV}", flush=True)
    print(f"Saved: {B_CSV}", flush=True)

    # Print TY 2027 summary
    q27 = all_quintiles[all_quintiles["tax_year"] == 2027]
    pd.set_option("display.float_format", "{:,.1f}".format)
    print("\n" + "=" * 100, flush=True)
    print("SB 3125 CD1 vs Act 46 — MID Scenario, TY 2027 (full revised pipeline)", flush=True)
    print("=" * 100, flush=True)
    print(q27[[
        "quintile", "household_count",
        "avg_per_hh_bracket_change", "avg_per_hh_credit_loss", "avg_per_hh_total_change",
        "total_bracket_$M", "total_credit_loss_$M", "total_change_$M",
        "pct_pay_more", "pct_pay_less",
    ]].to_string(index=False), flush=True)

    total_act46 = (all_quintiles[all_quintiles["tax_year"]==2027]["total_act46_$M"]).sum()
    total_sb    = (all_quintiles[all_quintiles["tax_year"]==2027]["total_cd1_$M"]).sum()
    total_brk   = (all_quintiles[all_quintiles["tax_year"]==2027]["total_bracket_$M"]).sum()
    total_crd   = (all_quintiles[all_quintiles["tax_year"]==2027]["total_credit_loss_$M"]).sum()
    print(
        f"\nTY 2027 totals:"
        f"\n  Act 46 baseline:        ${total_act46:>9.1f}M"
        f"\n  SB 3125 CD1 scenario:   ${total_sb:>9.1f}M"
        f"\n  Bracket delta:          ${total_brk:>+9.1f}M"
        f"\n  Credit-loss overlay:    ${total_crd:>+9.1f}M"
        f"\n  Total fiscal impact:    ${total_sb-total_act46+total_crd:>+9.1f}M",
        flush=True,
    )

    # 5-year cumulative
    cum_brk = all_quintiles["total_bracket_$M"].sum()
    cum_crd = all_quintiles["total_credit_loss_$M"].sum()
    cum_total = all_quintiles["total_change_$M"].sum()
    print(
        f"\n5-year cumulative (TY27-31):"
        f"\n  Bracket delta:          ${cum_brk:>+9.1f}M"
        f"\n  Credit-loss overlay:    ${cum_crd:>+9.1f}M"
        f"\n  Total fiscal impact:    ${cum_total:>+9.1f}M",
        flush=True,
    )

    # Year-by-year totals
    print("\n" + "-" * 100, flush=True)
    print("Annual totals by year ($M):", flush=True)
    print("-" * 100, flush=True)
    yearly = all_quintiles.groupby("tax_year")[
        ["total_bracket_$M", "total_credit_loss_$M", "total_change_$M"]
    ].sum()
    print(yearly.to_string(float_format=lambda x: f"{x:>+9.1f}"), flush=True)

    # Generate PDF
    print("\nGenerating PDF...", flush=True)
    _make_pdf(all_quintiles)

    print(f"Total elapsed: {time.perf_counter()-wall:.1f}s", flush=True)


def _make_pdf(df: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.rcParams["text.parse_math"] = False
    matplotlib.rcParams["font.family"] = ["DejaVu Sans"]
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.backends.backend_pdf import PdfPages

    PDF_OUT = Path("/tmp/sb3125_quintile_distributional_report.pdf")

    HH_BREAKS = [28_336, 60_915, 100_510, 168_638]
    Q_LABELS  = ["Q1 (bottom 20%)", "Q2", "Q3", "Q4", "Q5 (top 20%)"]
    Q_NAMES   = ["Bottom 20%", "2nd 20%", "3rd 20%", "4th 20%", "Top 20%"]
    Q_RANGES  = [
        f"under ${HH_BREAKS[0]//1000}K",
        f"${HH_BREAKS[0]//1000}K – ${HH_BREAKS[1]//1000}K",
        f"${HH_BREAKS[1]//1000}K – ${HH_BREAKS[2]//1000}K",
        f"${HH_BREAKS[2]//1000}K – ${HH_BREAKS[3]//1000}K",
        f"${HH_BREAKS[3]//1000}K+",
    ]

    NAVY     = "#1e3a5f"
    PILL_BG  = "#e8eef7"
    PILL_FG  = "#1e3a5f"
    TXT_GREY = "#4a5568"
    RULE     = "#cbd5e0"
    BLUE     = "#2b6cb0"   # SB 3125 bar color (distinct from HB 2306 green)

    def _fmt(val, fmt):
        if fmt == "dollar":
            return f"{'+' if val>=0 else '-'}${abs(val):,.0f}"
        if fmt == "pct":
            return f"{val:.1f}%"
        if fmt == "millions":
            return f"{'+' if val>=0 else '-'}${abs(val):,.1f}M"
        return str(val)

    years = sorted(df["tax_year"].unique())

    has_hh    = "avg_per_hh_total_change" in df.columns
    has_cor   = "total_change_cor_$M" in df.columns
    avg_col   = "avg_per_hh_total_change" if has_hh else "avg_total_change"
    tot_col   = "total_change_$M"
    avg_label = "Avg Tax Change per Household" if has_hh else "Avg Per-Filer Tax Change"
    tot_label = "Total Tax Change for Quintile"

    def table_page(pdf):
        fig = plt.figure(figsize=(11, 11))
        fig.suptitle(
            "SB 3125 CD1 vs Act 46 — Distributional Impact (MID Scenario)",
            fontsize=15, fontweight="bold", y=0.97, color=NAVY,
        )
        fig.text(
            0.5, 0.935,
            "Per-household impact (bracket change + REEC/CGEC/TCRA credit overlay), "
            "ITEP-anchored 2026 household-income quintiles, TY 2027 – 2031",
            ha="center", fontsize=10, style="italic", color=TXT_GREY,
        )
        specs = [
            (avg_label,                              avg_col,          "dollar"),
            ("Share of Households with Tax Increase", "pct_pay_more",  "pct"),
            (tot_label,                              tot_col,          "millions"),
        ]
        n = len(specs)
        top, bot, pad = 0.90, 0.03, 0.025
        ph = (top - bot - (n-1)*pad) / n
        for i, (title, col, fmt) in enumerate(specs):
            y0 = top - i*(ph+pad)
            ax = fig.add_axes([0.05, y0-ph, 0.90, ph])
            ax.axis("off")
            ax.text(0, 1.0, title, transform=ax.transAxes,
                    fontsize=11.5, fontweight="bold", color=NAVY, va="top")
            rows = []
            for ql, qn, qr in zip(Q_LABELS, Q_NAMES, Q_RANGES):
                row = [qn, qr]
                for yr in years:
                    v = float(df[(df["tax_year"]==yr)&(df["quintile"]==ql)].iloc[0][col])
                    row.append(_fmt(v, fmt))
                rows.append(row)
            col_labels = ["Quintile", "Household income"] + [str(y) for y in years]
            col_widths = [0.16, 0.22] + [0.124]*len(years)
            tbl = ax.table(cellText=rows, colLabels=col_labels,
                           colWidths=col_widths, loc="upper left",
                           bbox=[0,0,1,0.85], cellLoc="center")
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(9)
            for j in range(len(col_labels)):
                c = tbl[(0,j)]; c.set_facecolor(NAVY)
                c.set_text_props(color="white", fontweight="bold"); c.set_edgecolor("white")
            for r in range(1, len(rows)+1):
                for j in range(len(col_labels)):
                    c = tbl[(r,j)]; c.set_edgecolor(RULE)
                    if j == 0:
                        c.set_text_props(fontweight="bold", color=NAVY); c.set_facecolor(PILL_BG)
                    elif j == 1:
                        c.set_text_props(color=TXT_GREY); c.set_facecolor(PILL_BG)
                    if r == len(rows) and j >= 2:
                        c.set_facecolor("#fff5f5")
        if has_cor:
            diag_lines = []
            for yr in years:
                sub = df[df["tax_year"] == yr]
                raw = sub["total_change_$M"].sum()
                scl = sub["total_change_cor_$M"].sum()
                diag_lines.append(f"TY {yr}: raw ${raw:+,.0f}M / COR-anchored ${scl:+,.0f}M")
            fig.text(0.05, 0.018,
                     "Aggregate impact (raw / COR-anchored statewide):  "
                     + "  |  ".join(diag_lines),
                     ha="left", fontsize=7.5, color=TXT_GREY)
            fig.text(0.05, 0.005,
                     "Per-quintile values are RAW microsim. COR-anchored totals scale to the "
                     "official Council on Revenues IIT baseline.",
                     ha="left", fontsize=7, style="italic", color=TXT_GREY)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    def _panel(ax, yr, col, fmt, bar_color):
        vals = [float(df[(df["tax_year"]==yr)&(df["quintile"]==ql)].iloc[0][col])
                for ql in Q_LABELS]
        yp = np.arange(len(Q_LABELS))[::-1]
        ax.barh(yp, vals, height=0.55, color=bar_color, edgecolor="none")
        vmax = max(abs(min(vals)), abs(max(vals))) or 1.0
        pad  = vmax * 0.04
        for i, (y, v) in enumerate(zip(yp, vals)):
            lbl = _fmt(v, fmt)
            if v >= 0:
                ax.text(v+pad, y, lbl, va="center", ha="left",
                        fontsize=10, fontweight="bold", color="#2d3748")
            else:
                ax.text(v-pad, y, lbl, va="center", ha="right",
                        fontsize=10, fontweight="bold", color="#2d3748")
        ax.set_yticks(yp); ax.set_yticklabels([])
        for y, name, rng in zip(yp, Q_NAMES, Q_RANGES):
            ax.text(-0.01, y+0.12, name, transform=ax.get_yaxis_transform(),
                    ha="right", va="center", fontsize=9.5, fontweight="bold", color=PILL_FG,
                    bbox=dict(boxstyle="round,pad=0.35", facecolor=PILL_BG, edgecolor="none"))
            ax.text(-0.01, y-0.22, rng, transform=ax.get_yaxis_transform(),
                    ha="right", va="center", fontsize=8.5, color=TXT_GREY)
        ax.set_title(f"Tax Year {yr}", loc="left", fontsize=12, fontweight="bold", color=NAVY)
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False); ax.spines["bottom"].set_color(RULE)
        ax.tick_params(axis="y", length=0); ax.tick_params(axis="x", colors=TXT_GREY, labelsize=8)
        ax.grid(axis="x", linestyle=":", alpha=0.35, color=RULE); ax.axvline(0, color=RULE, lw=0.7)
        if min(vals) < 0:
            ax.set_xlim(min(vals)-vmax*0.30, max(vals)+vmax*0.30)
        else:
            ax.set_xlim(0, max(vals)*1.30)

    def chart_page(pdf, title, subtitle, col, fmt, bar_color):
        fig = plt.figure(figsize=(11, 10))
        fig.suptitle(title, fontsize=14, fontweight="bold", y=0.965, color=NAVY)
        fig.text(0.5, 0.93, subtitle, ha="center", fontsize=10, style="italic", color=TXT_GREY)
        for i, yr in enumerate([2027, 2031]):
            ax = fig.add_axes([0.22, 0.50-i*0.42, 0.72, 0.36])
            _panel(ax, yr, col, fmt, bar_color)
        fig.text(0.5, 0.02,
                 "Source: Census-Forecaster microsim. Quintiles defined on 2026 household income.",
                 ha="center", fontsize=8, style="italic", color=TXT_GREY)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    avg_chart_title = ("Average Tax Change per Household by Quintile" if has_hh
                       else "Average Per-Filer Tax Change by Quintile")
    with PdfPages(PDF_OUT) as pdf:
        table_page(pdf)
        chart_page(pdf, avg_chart_title,
                   "SB 3125 CD1 vs Act 46 — MID Scenario",
                   avg_col, "dollar", BLUE)
        chart_page(pdf, "Share of Households with a Tax Increase",
                   "SB 3125 CD1 vs Act 46 — MID Scenario",
                   "pct_pay_more", "pct", NAVY)
        chart_page(pdf, "Total Tax Change by Quintile",
                   "SB 3125 CD1 vs Act 46 — MID Scenario",
                   tot_col, "millions", BLUE)
        m = pdf.infodict()
        m["Title"] = "SB 3125 CD1 Distributional Analysis (Revised Pipeline)"
        m["Author"] = "Census-Forecaster"

    print(f"Saved: {PDF_OUT}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
