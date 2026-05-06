"""HB 2306 HD1 quintile distributional analysis (MID scenario, TY 2027-2031).

Uses the same MID synthesis + projection assumptions as
forecast_sb3125_cd1_enhanced.py.  Compares Act 46 (baseline) vs
HB 2306 HD1 (top 3 bracket rates +1pp, enhanced refundable CDCC,
brackets frozen — no 2027/2029 phase-ins).

No REEC credit overlay: HB 2306 does not cap or restrict REEC.
CDCC enhancement is captured per-filer via HawaiiTaxCredits.calculate_total_credits
(credit_scenario='hb2306_hd1').

Outputs:
  /tmp/hb2306_quintile_mid_2027_2031.csv
  /tmp/hb2306_bracket_mid_2027_2031.csv
  /tmp/hb2306_quintile_distributional_report.pdf
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
from tax_modeler.scenarios.behavioral_response import apply_top_income_growth_premium
from tax_modeler.projection.tax_unit_projector import project_tax_units_forward
from tax_modeler.calibration.year_recalibrator import project_and_recalibrate
from tax_modeler.scenarios.quintile_analysis import (
    generate_quintile_report, compute_quintile_breaks,
    cor_scale_factor_for_year, per_unit_tax,
)

# MID scenario assumptions (matches forecast_sb3125_cd1_enhanced.py MID)
MID_ALPHA       = 1.5
MID_TOP_PREMIUM = 0.010
TARGET_YEARS    = [2027, 2028, 2029, 2030, 2031]

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
    # $500K-$1M income redistribution: rewrite each filer's income via
    # truncated Pareto inverse-CDF mapped to weighted percentile. Preserves
    # PUMS demographics (filing status mix stays ~62% MFJ / 26% MFS / 10%
    # Single / 2.5% HoH) so the surcharge-relevant Single+MFS share isn't
    # diluted. Capped just below $1M; no overlap with $1M+ synthesis.
    units = redistribute_mid_high_incomes(base, pareto_alpha=MID_ALPHA)
    # $1M+ Pareto synthesis (existing flow, replaces $1M+ rows)
    units = synthesize_top_filers(units, pareto_alpha=MID_ALPHA)
    units = _enrich_for_credits(units)              # adds total_cash_income for TCI quintile binning
    units = impute_capital_gains_from_soi(units)    # Phase 3: CG rate cap for $100K-$1M filers
    units = _compute_base_tax(units)
    units, tail_k = rescale_synthetic_tail_to_tax_target(units)
    units = _compute_base_tax(units)
    print(f"  tail_k={tail_k:.4f}", flush=True)

    calc = TaxCalculator()

    # Anchor quintile boundaries to 2026 household-income distribution
    base_2026_breaks = compute_quintile_breaks(units)
    print(
        f"  2026 quintile breaks: "
        f"${base_2026_breaks[0]:,.0f} / ${base_2026_breaks[1]:,.0f} / "
        f"${base_2026_breaks[2]:,.0f} / ${base_2026_breaks[3]:,.0f}",
        flush=True,
    )

    quintile_frames, bracket_frames = [], []

    for yr in TARGET_YEARS:
        print(f"  TY {yr}...", flush=True)
        # ITEP-style year-by-year IRS target matching: re-rake weights to
        # forward DOTAX-shaped filer counts BEFORE the premium, then re-anchor
        # aggregate tax to COR's annual IIT projection AFTER premium + tax
        # recompute. Closes ~$66M HB 2306 surcharge gap with ITEP's analysis.
        # Methodology stack (ITEP-aligned):
        #   - use_forward_targets: rake to forward DOTAX-shaped filer counts
        #     and re-anchor aggregate tax to COR projection per year.
        #   - use_soi_anchor: anchor $1M+ tier composition (CG / wages /
        #     business / dividends) on national IRS SOI Table 1.4.
        #   - use_cbo_aging: age each filer's income components at CBO
        #     Outlook nominal rates (wages 4.4%/yr, CG 5-9%/yr, etc.) instead
        #     of uniform B19013 county-median growth.
        # Default Hawaii calibration factors apply (DEFAULT_HAWAII_FACTORS):
        # wages 0.85× national, business 0.90×, capital_gains 1.00×, others
        # 1.00×. Pass cbo_hawaii_factors={c: 1.0 ...} for pure CBO-national
        # aging — that variant lands HB 2306 TY2027 at $367M, matching ITEP.
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
        hb2306_cfg   = TaxSystemRegistry.get_hb2306_hd1_system(yr)

        # COR scaling: ratio of official COR FY{yr} IIT projection to our
        # microsim Act 46 baseline. Brings totals into ITEP/COR comparable units.
        act46_M = float(
            (per_unit_tax(projected, baseline_cfg, calc, "hi_standard_deduction")
             * projected["weight"].to_numpy(dtype=float)).sum() / 1e6
        )
        cor_factor = cor_scale_factor_for_year(yr, act46_M)

        # No REEC credit overlay for HB 2306 — bill does not restrict REEC.
        # Pass empty credit_overlay dict so generate_quintile_report skips distribution.
        empty_overlay = {}

        q_df, b_df, _ = generate_quintile_report(
            projected, baseline_cfg, hb2306_cfg,
            credit_overlay=empty_overlay,
            calc=calc,
            deduction_col="hi_standard_deduction",
            scenario_params=None,        # no REEC loss to distribute
            quintile_breaks=base_2026_breaks,
            cor_scale_factor=cor_factor,
        )
        q_df.insert(0, "tax_year", yr)
        b_df.insert(0, "tax_year", yr)
        quintile_frames.append(q_df)
        bracket_frames.append(b_df)

    all_quintiles = pd.concat(quintile_frames, ignore_index=True)
    all_brackets  = pd.concat(bracket_frames,  ignore_index=True)

    Q_CSV = Path("/tmp/hb2306_quintile_mid_2027_2031.csv")
    B_CSV = Path("/tmp/hb2306_bracket_mid_2027_2031.csv")
    all_quintiles.to_csv(Q_CSV, index=False)
    all_brackets.to_csv(B_CSV, index=False)
    print(f"Saved: {Q_CSV}", flush=True)
    print(f"Saved: {B_CSV}", flush=True)

    # Print TY 2027 summary
    q27 = all_quintiles[all_quintiles["tax_year"] == 2027]
    pd.set_option("display.float_format", "{:,.1f}".format)
    print("\n" + "=" * 90, flush=True)
    print("HB 2306 HD1 vs Act 46 — MID Scenario, TY 2027", flush=True)
    print("=" * 90, flush=True)
    print(q27[[
        "quintile", "household_count",
        "avg_per_hh_bracket_change", "avg_per_hh_credit_loss", "avg_per_hh_total_change",
        "total_bracket_$M", "total_change_$M",
        "pct_pay_more", "pct_pay_less",
    ]].to_string(index=False), flush=True)

    total_act46 = (all_quintiles[all_quintiles["tax_year"]==2027]["total_act46_$M"]).sum()
    total_hb    = (all_quintiles[all_quintiles["tax_year"]==2027]["total_cd1_$M"]).sum()
    print(f"\nTY 2027 total: Act 46=${total_act46:.1f}M  HB2306=${total_hb:.1f}M  "
          f"delta=${total_hb-total_act46:+.1f}M", flush=True)

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

    PDF_OUT = Path("/tmp/hb2306_quintile_distributional_report.pdf")

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
    TEAL     = "#2c8c87"
    PILL_BG  = "#e8eef7"
    PILL_FG  = "#1e3a5f"
    TXT_GREY = "#4a5568"
    RULE     = "#cbd5e0"
    GREEN    = "#276749"   # distinct color for HB 2306 bars

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

    # ── Page 1: tables ─────────────────────────────────────────────────────────
    def table_page(pdf):
        fig = plt.figure(figsize=(11, 11))
        fig.suptitle(
            "HB 2306 HD1 vs Act 46 — Distributional Impact (MID Scenario)",
            fontsize=15, fontweight="bold", y=0.97, color=NAVY,
        )
        fig.text(
            0.5, 0.935,
            "Per-household impact by ITEP-anchored 2026 household-income quintile, TY 2027 – 2031",
            ha="center", fontsize=10, style="italic", color=TXT_GREY,
        )
        specs = [
            (avg_label,                            avg_col,          "dollar"),
            ("Share of Households with Tax Increase", "pct_pay_more", "pct"),
            (tot_label,                            tot_col,          "millions"),
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
                     "official Council on Revenues IIT baseline to account for population-coverage "
                     "gaps (PTE filers, non-resident withholding, withholding-only filers).",
                     ha="left", fontsize=7, style="italic", color=TXT_GREY)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    # ── Chart pages ─────────────────────────────────────────────────────────────
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
                   "HB 2306 HD1 vs Act 46 — MID Scenario",
                   avg_col, "dollar", GREEN)
        chart_page(pdf, "Share of Households with a Tax Increase",
                   "HB 2306 HD1 vs Act 46 — MID Scenario",
                   "pct_pay_more", "pct", NAVY)
        chart_page(pdf, "Total Tax Change by Quintile",
                   "HB 2306 HD1 vs Act 46 — MID Scenario",
                   tot_col, "millions", GREEN)
        m = pdf.infodict()
        m["Title"] = "HB 2306 HD1 Distributional Analysis"
        m["Author"] = "Census-Forecaster"

    print(f"Saved: {PDF_OUT}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
