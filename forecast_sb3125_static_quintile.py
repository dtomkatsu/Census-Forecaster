"""SB 3125 distributional analysis by income quintile, TY 2027–2031.

Usage:
  python forecast_sb3125_static_quintile.py --cd 1   # SB 3125 CD1 (default)
  python forecast_sb3125_static_quintile.py --cd 2   # SB 3125 CD2

Replaces:
  forecast_sb3125_cd1_quintile.py
  forecast_sb3125_cd2_quintile.py

"Static" reflects the scoring methodology: per-unit tax is computed at projected
income before ETI/migration adjustments, consistent with standard distributional
analysis (CBO / Tax Policy Center methodology). Distinguishes this script from
the dynamic forecast_sb3125_quintile.py which uses the full project_and_recalibrate
pipeline.

For each tax year, computes the per-filer bracket-change impact (SB 3125 CD{N}
vs Act 46 baseline) and aggregates into five equal-population income quintiles.

Scope: bracket change only (§235-51). REEC/CGEC/TCRA credit components are
aggregate static-scoring overlays not attributable to individual filers and are
excluded from the quintile breakdown (CD2: shown in a separate REEC section of
the PDF).

Scenario: MID (Pareto α=1.5, itemized_adj=True) — calibrated best-estimate.

Output (--cd 1):
  /tmp/sb3125_cd1_quintile_2027_2031.csv

Output (--cd 2):
  /tmp/sb3125_cd2_quintile_2027_2031.csv
  /tmp/sb3125_cd2_quintile_distributional_report.pdf
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback
from pathlib import Path

DATA_DIR = Path(
    os.environ.get("HAWAII_PUMS_DIR")
    or Path.home() / "ctc-and-eitc" / "data" / "raw" / "pums"
)
CACHE_FILE = Path("/tmp/tax_units_cache.parquet")
TARGET_YEARS = [2027, 2028, 2029, 2030, 2031]

# MID scenario parameters (calibrated best-estimate)
PARETO_ALPHA   = 1.5
ITEMIZED_ADJ   = True
TOP_PREMIUM    = 0.0   # no additional top-income growth premium for MID

# Requires the workspace to be installed: `uv sync --all-packages`.
REPO = Path(__file__).parent

QUINTILE_LABELS = [
    "Q1 (Bottom 20%)",
    "Q2",
    "Q3",
    "Q4",
    "Q5 (Top 20%)",
]


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--cd", choices=["1", "2"], default="1",
        help="Conference draft to model: 1=CD1 (default), 2=CD2",
    )
    return p.parse_args()


def _fmt_dollar(x: float) -> str:
    if abs(x) >= 1_000_000:
        return f"${x/1_000_000:,.2f}M"
    if abs(x) >= 1_000:
        return f"${x:,.0f}"
    return f"${x:.0f}"


def compute_quintile_breakdown(projected, baseline_cfg, scenario_cfg, calc, *, cd="1"):
    """Return a DataFrame with one row per income quintile for the given year."""
    import pandas as pd

    proj = projected.copy()

    # ---- Per-unit tax under each system (static scoring) --------------------
    # CG income for §235-16 cap: synthetic filers carry synthetic_cg_share;
    # base PUMS units don't (default 0 → no cap applied, consistent with
    # ACS not capturing realized capital gains for sub-$1M filers).
    import numpy as _np
    cg_shares = (
        proj["synthetic_cg_share"].fillna(0.0).values
        if "synthetic_cg_share" in proj.columns
        else _np.zeros(len(proj))
    )
    base_tax, scen_tax = [], []
    ndep_col = proj.get("num_dependents") if hasattr(proj, "get") else proj["num_dependents"]
    for inc, fs, ndep, cg_share in zip(
        proj["income"], proj["filing_status"], ndep_col, cg_shares
    ):
        cg_inc = float(inc) * float(cg_share)
        b = calc.calculate_tax(inc, baseline_cfg, fs,
                               num_exemptions=int(ndep) + 1, cg_income=cg_inc)
        s = calc.calculate_tax(inc, scenario_cfg, fs,
                               num_exemptions=int(ndep) + 1, cg_income=cg_inc)
        base_tax.append(b["tax_liability"])
        scen_tax.append(s["tax_liability"])

    proj["base_tax"] = base_tax
    proj["scen_tax"] = scen_tax
    proj["delta"]    = proj["scen_tax"] - proj["base_tax"]

    # ---- Quintile assignment (equal-population, cumulative weight) ----------
    proj_sorted = proj.sort_values("income").reset_index(drop=True)
    cumw        = proj_sorted["weight"].cumsum()
    total_w     = float(cumw.iloc[-1])
    proj_sorted["quintile"] = pd.cut(
        cumw / total_w,
        bins=[i / 5 for i in range(6)],
        labels=QUINTILE_LABELS,
        include_lowest=True,
    )

    # ---- Weighted aggregation per quintile ----------------------------------
    grp = proj_sorted.groupby("quintile", observed=True)

    def wsum(col):
        return grp.apply(lambda d: (d[col] * d["weight"]).sum())

    def wavg(col):
        return grp.apply(
            lambda d: (d[col] * d["weight"]).sum() / d["weight"].sum()
        )

    result = pd.DataFrame({
        "income_min_$":                       grp["income"].min(),
        "income_max_$":                       grp["income"].max(),
        "avg_income_$":                       wavg("income"),
        "n_filers":                           grp["weight"].sum(),
        "base_tax_total_$M":                  wsum("base_tax") / 1e6,
        f"sb3125_cd{cd}_tax_total_$M":        wsum("scen_tax") / 1e6,
        "delta_total_$M":                     wsum("delta") / 1e6,
        "avg_delta_per_filer_$":              wavg("delta"),
        "pct_filers_with_change":             grp.apply(
            lambda d: d.loc[d["delta"] != 0, "weight"].sum() / d["weight"].sum() * 100
        ),
    }).reset_index()

    return result


def print_quintile_table(year: int, qt, *, cd: str = "1"):
    """Pretty-print a quintile table for one tax year."""
    cd_label = f"CD{cd}"
    print(f"\n{'─'*95}", flush=True)
    print(
        f"TY {year} — SB 3125 {cd_label} vs Act 46  |  "
        f"Bracket change by income quintile (MID scenario)",
        flush=True,
    )
    print(
        "  (Bracket only; REEC/CGEC/TCRA credit overlay not included in quintile delta)",
        flush=True,
    )
    print(f"{'─'*95}", flush=True)
    hdr = (
        f"  {'Quintile':<20}  {'Income range':>26}  {'Avg income':>12}  "
        f"{'N filers':>10}  {'Delta $M':>10}  {'Avg $/filer':>13}  {'% affected':>10}"
    )
    print(hdr, flush=True)
    print(f"  {'─'*89}", flush=True)
    total_delta = 0.0
    for _, row in qt.iterrows():
        rng = f"{_fmt_dollar(row['income_min_$'])} – {_fmt_dollar(row['income_max_$'])}"
        delta_str = f"{row['delta_total_$M']:+.1f}"
        avg_str   = f"{row['avg_delta_per_filer_$']:+,.0f}"
        pct_str   = f"{row['pct_filers_with_change']:.1f}%"
        print(
            f"  {row['quintile']:<20}  {rng:>26}  "
            f"{_fmt_dollar(row['avg_income_$']):>12}  "
            f"{row['n_filers']:>10,.0f}  "
            f"{delta_str:>10}  "
            f"{avg_str:>13}  "
            f"{pct_str:>10}",
            flush=True,
        )
        total_delta += row["delta_total_$M"]
    print(f"  {'─'*89}", flush=True)
    print(f"  {'TOTAL (all quintiles)':<20}  {'':>26}  {'':>12}  "
          f"{'':>10}  {total_delta:>+10.1f}", flush=True)


def _make_pdf(df: "pd.DataFrame", *, cd: str = "2") -> None:
    """Generate distributional PDF report. Only called for --cd 2."""
    import matplotlib
    matplotlib.rcParams["text.parse_math"] = False
    matplotlib.rcParams["font.family"] = ["DejaVu Sans"]
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from matplotlib.backends.backend_pdf import PdfPages

    cd_label     = f"CD{cd}"
    PDF_OUT      = Path(f"/tmp/sb3125_cd{cd}_quintile_distributional_report.pdf")
    ENHANCED_CSV = Path(f"/tmp/sb3125_cd{cd}_enhanced_2027_2031.csv")

    HH_BREAKS = [28_336, 60_915, 100_510, 168_638]
    Q_LABELS  = ["Q1 (Bottom 20%)", "Q2", "Q3", "Q4", "Q5 (Top 20%)"]
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
    ORANGE   = "#c05e2b"
    PILL_BG  = "#e8eef7"
    PILL_FG  = "#1e3a5f"
    TXT_GREY = "#4a5568"
    RULE     = "#cbd5e0"
    BLUE     = "#2b6cb0"

    years = sorted(df["tax_year"].unique())

    def _fmt(val, fmt):
        if fmt == "dollar":
            return f"{'+' if val >= 0 else '-'}${abs(val):,.0f}"
        if fmt == "pct":
            return f"{val:.1f}%"
        if fmt == "millions":
            return f"{'+' if val >= 0 else '-'}${abs(val):,.1f}M"
        return str(val)

    # ---- Page 1: summary tables ----

    def table_page(pdf):
        fig = plt.figure(figsize=(11, 11))
        fig.suptitle(
            f"SB 3125 {cd_label} vs Act 46 — Distributional Impact (MID Scenario)",
            fontsize=15, fontweight="bold", y=0.97, color=NAVY,
        )
        fig.text(
            0.5, 0.935,
            f"Per-filer bracket-change impact by income quintile, TY 2027–2031  "
            f"·  §235-51 only  ·  REEC/CGEC/TCRA shown separately on pages 5–6",
            ha="center", fontsize=10, style="italic", color=TXT_GREY,
        )
        specs = [
            ("Avg Tax Change per Filer",          "avg_delta_per_filer_$",  "dollar"),
            ("Share of Filers with Any Change",   "pct_filers_with_change", "pct"),
            ("Total Tax Change for Quintile",     "delta_total_$M",         "millions"),
        ]
        n = len(specs)
        top, bot, pad = 0.90, 0.06, 0.025
        ph = (top - bot - (n - 1) * pad) / n
        for i, (title, col, fmt) in enumerate(specs):
            y0 = top - i * (ph + pad)
            ax = fig.add_axes([0.05, y0 - ph, 0.90, ph])
            ax.axis("off")
            ax.text(0, 1.0, title, transform=ax.transAxes,
                    fontsize=11.5, fontweight="bold", color=NAVY, va="top")
            rows = []
            for ql, qn, qr in zip(Q_LABELS, Q_NAMES, Q_RANGES):
                row = [qn, qr]
                for yr in years:
                    sub = df[(df["tax_year"] == yr) & (df["quintile"] == ql)]
                    row.append(_fmt(float(sub.iloc[0][col]), fmt) if not sub.empty else "—")
                rows.append(row)
            col_labels = ["Quintile", "Household income"] + [str(y) for y in years]
            col_widths  = [0.16, 0.22] + [0.124] * len(years)
            tbl = ax.table(cellText=rows, colLabels=col_labels,
                           colWidths=col_widths, loc="upper left",
                           bbox=[0, 0, 1, 0.85], cellLoc="center")
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(9)
            for j in range(len(col_labels)):
                c = tbl[(0, j)]
                c.set_facecolor(NAVY)
                c.set_text_props(color="white", fontweight="bold")
                c.set_edgecolor("white")
            for r in range(1, len(rows) + 1):
                for j in range(len(col_labels)):
                    c = tbl[(r, j)]
                    c.set_edgecolor(RULE)
                    if j == 0:
                        c.set_text_props(fontweight="bold", color=NAVY)
                        c.set_facecolor(PILL_BG)
                    elif j == 1:
                        c.set_text_props(color=TXT_GREY)
                        c.set_facecolor(PILL_BG)
                    if r == len(rows) and j >= 2:
                        c.set_facecolor("#fff5f5")
        fig.text(
            0.05, 0.025,
            f"Positive = filer pays more under SB 3125 {cd_label} vs Act 46 (bracket change only). "
            "Bottom quintiles see tax cuts from lower mid-bracket rates; top quintile sees "
            "increases from the new 13% bracket. Credit-cap savings (REEC) shown on pages 5–6.",
            ha="left", fontsize=7.5, style="italic", color=TXT_GREY,
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    # ---- Pages 2–4: bar chart pages ----

    def _panel(ax, yr, col, fmt, bar_color):
        vals = []
        for ql in Q_LABELS:
            sub = df[(df["tax_year"] == yr) & (df["quintile"] == ql)]
            vals.append(float(sub.iloc[0][col]) if not sub.empty else 0.0)
        yp   = np.arange(len(Q_LABELS))[::-1]
        ax.barh(yp, vals, height=0.55, color=bar_color, edgecolor="none")
        vmax = max(abs(min(vals)), abs(max(vals))) or 1.0
        pad  = vmax * 0.04
        for y, v in zip(yp, vals):
            lbl = _fmt(v, fmt)
            if v >= 0:
                ax.text(v + pad, y, lbl, va="center", ha="left",
                        fontsize=10, fontweight="bold", color="#2d3748")
            else:
                ax.text(v - pad, y, lbl, va="center", ha="right",
                        fontsize=10, fontweight="bold", color="#2d3748")
        ax.set_yticks(yp)
        ax.set_yticklabels([])
        for y, name, rng in zip(yp, Q_NAMES, Q_RANGES):
            ax.text(-0.01, y + 0.12, name, transform=ax.get_yaxis_transform(),
                    ha="right", va="center", fontsize=9.5, fontweight="bold", color=PILL_FG,
                    bbox=dict(boxstyle="round,pad=0.35", facecolor=PILL_BG, edgecolor="none"))
            ax.text(-0.01, y - 0.22, rng, transform=ax.get_yaxis_transform(),
                    ha="right", va="center", fontsize=8.5, color=TXT_GREY)
        ax.set_title(f"Tax Year {yr}", loc="left", fontsize=12, fontweight="bold", color=NAVY)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_color(RULE)
        ax.tick_params(axis="y", length=0)
        ax.tick_params(axis="x", colors=TXT_GREY, labelsize=8)
        ax.grid(axis="x", linestyle=":", alpha=0.35, color=RULE)
        ax.axvline(0, color=RULE, lw=0.7)
        if min(vals) < 0:
            ax.set_xlim(min(vals) - vmax * 0.30, max(vals) + vmax * 0.30)
        else:
            ax.set_xlim(0, max(vals) * 1.30)

    def chart_page(pdf, title, subtitle, col, fmt, bar_color):
        fig = plt.figure(figsize=(11, 10))
        fig.suptitle(title, fontsize=14, fontweight="bold", y=0.965, color=NAVY)
        fig.text(0.5, 0.93, subtitle, ha="center", fontsize=10, style="italic", color=TXT_GREY)
        for i, yr in enumerate([2027, 2031]):
            ax = fig.add_axes([0.22, 0.50 - i * 0.42, 0.72, 0.36])
            _panel(ax, yr, col, fmt, bar_color)
        fig.text(0.5, 0.02,
                 "Source: Census-Forecaster microsim. Quintiles defined on 2026 household income.",
                 ha="center", fontsize=8, style="italic", color=TXT_GREY)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    # ---- Page 5: REEC incidence by income group ----

    # DOTAX TY2023 actuals: (label, individual_claim_$M, agi_eligible_share)
    REEC_IND_BINS = [
        ("<$10K",       4.731, 1.000),
        ("$10K–$30K",   2.522, 1.000),
        ("$30K–$60K",   3.121, 1.000),
        ("$60K–$100K",  5.752, 1.000),
        ("$100K–$200K", 16.150, 0.972),
        ("$200K+",      26.018, 0.561),
    ]
    REEC_CORP_M = 38.565 + 3.217  # corp + other TY2023

    def _reec_rows(pro_rata: float) -> list:
        rows = []
        for label, claim, elig in REEC_IND_BINS:
            eligible  = claim * elig
            after_cap = eligible * pro_rata
            rows.append({
                "group":      label,
                "baseline":   claim,
                "eligible":   eligible,
                "lost_agi":   claim - eligible,
                "after_cap":  after_cap,
                "lost_cap":   eligible - after_cap,
                "total_lost": (claim - eligible) + (eligible - after_cap),
                "pct_lost":   ((claim - eligible) + (eligible - after_cap)) / claim * 100,
            })
        corp_after = REEC_CORP_M * pro_rata
        rows.append({
            "group":      "Corporate / Other",
            "baseline":   REEC_CORP_M,
            "eligible":   REEC_CORP_M,
            "lost_agi":   0.0,
            "after_cap":  corp_after,
            "lost_cap":   REEC_CORP_M - corp_after,
            "total_lost": REEC_CORP_M - corp_after,
            "pct_lost":   (REEC_CORP_M - corp_after) / REEC_CORP_M * 100,
        })
        return rows

    def reec_incidence_page(pdf, pro_rata: float = 0.7806):
        rows = _reec_rows(pro_rata)
        fig  = plt.figure(figsize=(11, 10))
        fig.suptitle(
            "REEC Credit Restriction — Impact by Income Group",
            fontsize=14, fontweight="bold", y=0.97, color=NAVY,
        )
        fig.text(
            0.5, 0.935,
            f"TY2023 DOTAX actuals  ·  TY2027 MID pro-rata factor {pro_rata:.0%}  "
            f"·  §235-12.5 AGI limits ($175K single / $350K joint) + $40M aggregate cap",
            ha="center", fontsize=9.5, style="italic", color=TXT_GREY,
        )
        retained = [r["after_cap"]  for r in rows]
        lost_cap = [r["lost_cap"]   for r in rows]
        lost_agi = [r["lost_agi"]   for r in rows]
        yp       = np.arange(len(rows))[::-1]
        ax       = fig.add_axes([0.26, 0.18, 0.68, 0.70])

        ax.barh(yp, retained, height=0.55, color=TEAL,   edgecolor="none", label="Retained after cap")
        ax.barh(yp, lost_cap, height=0.55, color=ORANGE, edgecolor="none",
                left=retained, label="Lost to cap (pro-rata)")
        ax.barh(yp, lost_agi, height=0.55, color=NAVY,   edgecolor="none",
                left=[r + c for r, c in zip(retained, lost_cap)], label="Lost to AGI filter")

        for ypos, row in zip(yp, rows):
            ax.text(
                row["baseline"] + 0.4, ypos,
                f"-${row['total_lost']:.1f}M  ({row['pct_lost']:.0f}%)",
                va="center", ha="left", fontsize=9, color=NAVY, fontweight="bold",
            )

        ax.set_yticks(yp)
        ax.set_yticklabels([])
        for ypos, row in zip(yp, rows):
            is_corp = row["group"] == "Corporate / Other"
            ax.text(
                -0.01, ypos, row["group"],
                transform=ax.get_yaxis_transform(), ha="right", va="center",
                fontsize=9.5, fontweight="bold" if is_corp else "normal",
                color=NAVY if is_corp else PILL_FG,
                bbox=dict(boxstyle="round,pad=0.35", facecolor=PILL_BG, edgecolor="none"),
            )

        ax.axhline(y=0.5, color=RULE, linewidth=1.0, linestyle="--")
        ax.set_xlabel("Credit ($M, TY2023 basis)", fontsize=9, color=TXT_GREY)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_color(RULE)
        ax.tick_params(axis="y", length=0)
        ax.tick_params(axis="x", colors=TXT_GREY, labelsize=8)
        ax.grid(axis="x", linestyle=":", alpha=0.35, color=RULE)
        ax.set_xlim(0, max(r["baseline"] for r in rows) * 1.45)
        ax.legend(loc="lower right", fontsize=9, framealpha=0.9, edgecolor=RULE)

        ind_lost  = sum(r["total_lost"] for r in rows if r["group"] != "Corporate / Other")
        corp_lost = rows[-1]["total_lost"]
        grand_b   = sum(r["baseline"]   for r in rows)
        grand_l   = sum(r["total_lost"] for r in rows)
        fig.text(
            0.05, 0.10,
            "Amounts from DOTAX TY2023 'Tax Credits Claimed' (most recent available). "
            "TY2027 individual demand is lower due to federal §25D termination (OBBBA, PL 119-21) "
            "— relative incidence across groups is similar. "
            "Corporate REEC not subject to AGI limit under MID scenario. "
            "Pro-rata factor reflects endogenous demand suppression (η=0.3, MID).",
            ha="left", fontsize=7.5, style="italic", color=TXT_GREY,
        )
        fig.text(
            0.05, 0.055,
            f"TY2023 totals: individual "
            f"${sum(r['baseline'] for r in rows if r['group'] != 'Corporate / Other'):.1f}M  "
            f"|  corporate ${REEC_CORP_M:.1f}M  |  combined ${grand_b:.1f}M.  "
            f"Aggregate lost (TY2023 basis): "
            f"individual −${ind_lost:.1f}M  |  corporate −${corp_lost:.1f}M  "
            f"|  total −${grand_l:.1f}M.",
            ha="left", fontsize=7.5, color=TXT_GREY,
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    # ---- Page 6: REEC savings trajectory ----

    def reec_time_series_page(pdf, df_enh: "pd.DataFrame"):
        scenarios = ["LOW", "MID", "HIGH"]
        colors    = {"LOW": "#8fa8c8", "MID": TEAL, "HIGH": ORANGE}
        yr_list   = [2027, 2028, 2029, 2030, 2031]
        x         = np.arange(len(yr_list))

        fig = plt.figure(figsize=(11, 10))
        fig.suptitle(
            "REEC Savings Over Time — Baseline vs. Bill State Cost",
            fontsize=14, fontweight="bold", y=0.97, color=NAVY,
        )
        fig.text(
            0.5, 0.935,
            f"§235-12.5 renewable energy credit  ·  TY2027–2031  ·  LOW / MID / HIGH scenarios",
            ha="center", fontsize=10, style="italic", color=TXT_GREY,
        )

        # Top: grouped bars of REEC savings by scenario
        ax_top = fig.add_axes([0.10, 0.52, 0.84, 0.36])
        n_s     = len(scenarios)
        width   = 0.22
        offsets = np.linspace(-(n_s - 1) / 2 * width, (n_s - 1) / 2 * width, n_s)
        for scen, offset in zip(scenarios, offsets):
            sub  = df_enh[df_enh["scenario"] == scen].set_index("tax_year")
            vals = [sub.loc[y, "reec_savings_$M"] for y in yr_list]
            bars = ax_top.bar(x + offset, vals, width=width * 0.92,
                              color=colors[scen], edgecolor="none", label=scen)
            for bar, val in zip(bars, vals):
                ax_top.text(
                    bar.get_x() + bar.get_width() / 2, val + 1.0,
                    f"${val:.0f}M", ha="center", va="bottom",
                    fontsize=7.5, color=colors[scen], fontweight="bold",
                )

        ax_top.set_xticks(x)
        ax_top.set_xticklabels([f"TY{y}" for y in yr_list], fontsize=10, color=TXT_GREY)
        ax_top.set_ylabel("REEC savings ($M)", fontsize=9, color=TXT_GREY)
        ax_top.set_title("Annual REEC Fiscal Savings (Baseline − Bill State Cost)",
                         loc="left", fontsize=11, fontweight="bold", color=NAVY)
        ax_top.spines["top"].set_visible(False)
        ax_top.spines["right"].set_visible(False)
        ax_top.spines["left"].set_color(RULE)
        ax_top.spines["bottom"].set_color(RULE)
        ax_top.tick_params(colors=TXT_GREY, labelsize=8)
        ax_top.grid(axis="y", linestyle=":", alpha=0.35, color=RULE)
        ax_top.set_ylim(0, 145)
        ax_top.legend(loc="upper left", fontsize=9, framealpha=0.9, edgecolor=RULE)
        ax_top.axvspan(2.5, 4.5, alpha=0.06, color=NAVY, zorder=0)
        ax_top.text(3.5, 135, "§235-12.5(p)\nsunset", ha="center", va="top",
                    fontsize=8.5, color=NAVY, style="italic")

        # Cumulative callout
        for scen, color in colors.items():
            sub = df_enh[df_enh["scenario"] == scen]
            cum = sub["reec_savings_$M"].sum()
            ax_top.annotate(
                f"{scen} 5yr: ${cum:.0f}M",
                xy=(0, 0), xycoords="axes fraction",
                xytext=(0.01 + list(scenarios).index(scen) * 0.18, 0.05),
                textcoords="axes fraction",
                fontsize=8, color=color, fontweight="bold",
            )

        # Bottom: MID cost decomposition
        ax_bot = fig.add_axes([0.10, 0.10, 0.84, 0.34])
        mid      = df_enh[df_enh["scenario"] == "MID"].set_index("tax_year")
        base_c   = [mid.loc[y, "reec_base_state_cost_$M"]  for y in yr_list]
        scen_ref = [mid.loc[y, "reec_scen_refundable_$M"]   for y in yr_list]
        scen_nr  = [mid.loc[y, "reec_scen_nonref_usage_$M"] for y in yr_list]

        ax_bot.plot(x, base_c, color=NAVY, linewidth=2.0, marker="o",
                    markersize=5, label="Baseline (no cap)", zorder=3)
        ax_bot.bar(x, scen_ref, width=0.45, color=TEAL,     edgecolor="none",
                   label="Bill: refundable (in-year)", zorder=2)
        ax_bot.bar(x, scen_nr,  width=0.45, color="#8fa8c8", edgecolor="none",
                   bottom=scen_ref, label="Bill: nonref carryforward drawdown", zorder=2)

        ax_bot.set_xticks(x)
        ax_bot.set_xticklabels([f"TY{y}" for y in yr_list], fontsize=10, color=TXT_GREY)
        ax_bot.set_ylabel("State cost ($M)", fontsize=9, color=TXT_GREY)
        ax_bot.set_title("MID Scenario — State Cost Components",
                         loc="left", fontsize=11, fontweight="bold", color=NAVY)
        ax_bot.spines["top"].set_visible(False)
        ax_bot.spines["right"].set_visible(False)
        ax_bot.spines["left"].set_color(RULE)
        ax_bot.spines["bottom"].set_color(RULE)
        ax_bot.tick_params(colors=TXT_GREY, labelsize=8)
        ax_bot.grid(axis="y", linestyle=":", alpha=0.35, color=RULE)
        ax_bot.set_ylim(0, 125)
        ax_bot.legend(loc="upper right", fontsize=9, framealpha=0.9, edgecolor=RULE)
        ax_bot.axvspan(2.5, 4.5, alpha=0.06, color=NAVY, zorder=0)

        fig.text(
            0.05, 0.03,
            "Baseline: Act 46 (no cap, no AGI limit, no sunset). "
            f"Bill: §235-12.5 — $40M cap TY2027–2029, $0 new certifications TY2030+ (§(p) sunset). "
            "Savings = baseline − bill state cost. "
            "LOW: interpretation A (TY2026 cap binds), η=0.5. "
            "MID/HIGH: interpretation B, η=0.3/0.15.",
            ha="left", fontsize=7.5, style="italic", color=TXT_GREY,
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    # ---- Assemble PDF ----

    # Pull TY2027 MID pro-rata for incidence page; fall back to hardcoded if CSV missing
    pro_rata_mid = 0.7806
    df_enh       = None
    if ENHANCED_CSV.exists():
        import pandas as _pd
        df_enh = _pd.read_csv(ENHANCED_CSV)
        mid_2027 = df_enh[(df_enh["scenario"] == "MID") & (df_enh["tax_year"] == 2027)]
        if not mid_2027.empty and "reec_pro_rata_factor" in mid_2027.columns:
            pro_rata_mid = float(mid_2027["reec_pro_rata_factor"].iloc[0])

    with PdfPages(PDF_OUT) as pdf:
        table_page(pdf)
        chart_page(pdf,
                   "Average Tax Change per Filer by Quintile",
                   f"SB 3125 {cd_label} vs Act 46 — MID Scenario  ·  §235-51 bracket changes only",
                   "avg_delta_per_filer_$", "dollar", BLUE)
        chart_page(pdf,
                   "Share of Filers with Any Tax Change",
                   f"SB 3125 {cd_label} vs Act 46 — MID Scenario  ·  §235-51 bracket changes only",
                   "pct_filers_with_change", "pct", NAVY)
        chart_page(pdf,
                   "Total Tax Change by Quintile",
                   f"SB 3125 {cd_label} vs Act 46 — MID Scenario  ·  §235-51 bracket changes only",
                   "delta_total_$M", "millions", BLUE)
        reec_incidence_page(pdf, pro_rata=pro_rata_mid)
        if df_enh is not None:
            reec_time_series_page(pdf, df_enh)
        else:
            print(f"  (skipping REEC time-series page — {ENHANCED_CSV} not found)", flush=True)

        m = pdf.infodict()
        m["Title"]   = f"SB 3125 {cd_label} Distributional Analysis"
        m["Author"]  = "Census-Forecaster"
        m["Subject"] = f"Per-quintile bracket impact + REEC credit incidence, TY 2027–2031, MID"

    print(f"Saved: {PDF_OUT}", flush=True)


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)

    args = _parse_args()
    CD       = args.cd
    OUT_CSV  = Path(f"/tmp/sb3125_cd{CD}_quintile_2027_2031.csv")
    cd_label = f"CD{CD}"

    try:
        import time
        import pandas as pd

        print(f"SB 3125 {cd_label} static quintile analysis", flush=True)
        print("Importing modules...", flush=True)
        from tax_modeler.pipeline import _enrich_for_credits, _compute_base_tax, _calibrate
        from tax_modeler.projection.tax_unit_projector import project_tax_units_forward
        from tax_modeler.config.tax_system_config import (
            TaxCalculator, TaxSystemRegistry,
        )
        from tax_modeler.scenarios.top_income_synthesis import (
            synthesize_top_filers, validate_top_synthesis,
            rescale_synthetic_tail_to_tax_target,
        )
        from tax_modeler.scenarios.behavioral_response import (
            apply_top_income_growth_premium,
            apply_itemized_deduction_adjustment,
        )

        get_scenario_system = (
            TaxSystemRegistry.get_sb3125_cd1_system if CD == "1"
            else TaxSystemRegistry.get_sb3125_cd2_system
        )

        wall_start = time.perf_counter()

        # ---- One-time setup -------------------------------------------------
        if not CACHE_FILE.exists():
            print(f"ERROR: cache not found at {CACHE_FILE}", flush=True)
            print(f"Run forecast_sb3125.py --cd {CD} first to build the cache.", flush=True)
            sys.exit(1)

        print(f"Loading cached units from {CACHE_FILE}...", flush=True)
        units = pd.read_parquet(CACHE_FILE)
        print(f"  {len(units):,} units loaded", flush=True)

        print("Enriching + base tax + calibrating...", flush=True)
        t0 = time.perf_counter()
        units = _enrich_for_credits(units)
        units = _compute_base_tax(units)
        units = _calibrate(units)
        print(f"  Done in {time.perf_counter()-t0:.1f}s", flush=True)

        print(f"Synthesizing top-income filers (Pareto α={PARETO_ALPHA})...", flush=True)
        t0 = time.perf_counter()
        units = synthesize_top_filers(units, pareto_alpha=PARETO_ALPHA)
        units = _compute_base_tax(units)
        units, tail_k = rescale_synthetic_tail_to_tax_target(units)
        units = _compute_base_tax(units)
        v = validate_top_synthesis(units)
        print(f"  {v['filers_1m_plus']:,.0f} filers @ $1M+ "
              f"({100*v['filer_target_ratio']:.1f}%), "
              f"${v['tax_1m_plus_$M']:,.1f}M tax "
              f"({100*v['tax_target_ratio']:.1f}% of $663M target), "
              f"tail_k={tail_k:.4f} "
              f"in {time.perf_counter()-t0:.1f}s", flush=True)

        # ---- Per-year quintile analysis -------------------------------------
        calc = TaxCalculator()
        all_rows = []

        for year in TARGET_YEARS:
            t0 = time.perf_counter()
            print(f"\nTY {year}: projecting...", flush=True)

            projected = project_tax_units_forward(
                units, target_year=year, method="ensemble"
            )
            # MID adjustments: no growth premium, itemized deduction adjustment
            projected = apply_top_income_growth_premium(
                projected, target_year=year, annual_premium=TOP_PREMIUM
            )
            if ITEMIZED_ADJ:
                projected = apply_itemized_deduction_adjustment(projected)

            baseline_cfg = TaxSystemRegistry.get_act46_system(year)
            scenario_cfg = get_scenario_system(year)

            print(f"  Computing per-unit tax ({len(projected):,} units × 2 systems)...",
                  flush=True)
            qt = compute_quintile_breakdown(projected, baseline_cfg, scenario_cfg, calc, cd=CD)
            qt.insert(0, "tax_year", year)

            print_quintile_table(year, qt, cd=CD)
            all_rows.append(qt)
            print(f"  TY {year} done in {time.perf_counter()-t0:.1f}s", flush=True)

        # ---- Save combined CSV ----------------------------------------------
        df_out = pd.concat(all_rows, ignore_index=True)
        df_out.to_csv(OUT_CSV, index=False)

        # ---- Summary pivot: Q5 delta across years ---------------------------
        print(f"\n{'='*95}", flush=True)
        print("Q5 (Top 20%) bracket delta by year — the filers driving most of the revenue gain",
              flush=True)
        print(f"{'='*95}", flush=True)
        q5 = df_out[df_out["quintile"] == "Q5 (Top 20%)"].set_index("tax_year")
        for yr in TARGET_YEARS:
            r = q5.loc[yr]
            print(f"  TY {yr}: income ${r['income_min_$']:,.0f}–${r['income_max_$']:,.0f}  "
                  f"avg ${r['avg_income_$']:,.0f}  "
                  f"delta {r['delta_total_$M']:+.1f}M  "
                  f"avg/filer ${r['avg_delta_per_filer_$']:+,.0f}",
                  flush=True)

        print(f"\nSaved: {OUT_CSV}", flush=True)

        # ---- PDF generation (CD2 only) -------------------------------------
        if CD == "2":
            print("\nRendering PDF...", flush=True)
            _make_pdf(df_out, cd=CD)

        print(f"Total elapsed: {time.perf_counter()-wall_start:.1f}s", flush=True)

    except Exception as e:
        print(f"\nERROR: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
