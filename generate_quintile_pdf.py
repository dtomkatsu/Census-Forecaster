"""Render the SB 3125 CD2 quintile distributional analysis to PDF.

Reads /tmp/sb3125_cd2_quintile_2027_2031.csv (produced by
forecast_sb3125_cd2_quintile.py) and /tmp/sb3125_cd2_enhanced_2027_2031.csv
(produced by forecast_sb3125_cd2_enhanced.py) and produces:
  /tmp/sb3125_cd2_distributional_report.pdf

Layout:
  Page 1 — Three clean stacked tables: avg per-filer tax change, %
           filers with a change, total impact ($M). Each is 5 quintiles ×
           5 years with the income range alongside each quintile label.
  Page 2 — Avg per-filer tax change: horizontal bar chart, panels for
           TY 2027 and TY 2031 (visual style matches HiTaxFairness one-pager).
  Page 3 — % filers with a change: same panel layout.
  Page 4 — Total quintile-level impact ($M): same panel layout.
  Page 5 — REEC credit restriction: incidence by income group (TY2023
           actuals, showing AGI-filter and cap impact per group).
  Page 6 — REEC savings trajectory: baseline vs bill state cost TY2027–2031,
           LOW / MID / HIGH scenario bands.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.rcParams["text.parse_math"] = False
matplotlib.rcParams["font.family"] = ["DejaVu Sans"]

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch

CSV_IN       = Path("/tmp/sb3125_cd2_quintile_2027_2031.csv")
ENHANCED_CSV = Path("/tmp/sb3125_cd2_enhanced_2027_2031.csv")
PDF_OUT      = Path("/tmp/sb3125_cd2_distributional_report.pdf")

HH_BREAKS = [28_336, 60_915, 100_510, 168_638]
# Must match the quintile labels emitted by forecast_sb3125_cd2_quintile.py
Q_LABELS = ["Q1 (Bottom 20%)", "Q2", "Q3", "Q4", "Q5 (Top 20%)"]
Q_NAMES  = ["Bottom 20%", "2nd 20%", "3rd 20%", "4th 20%", "Top 20%"]
Q_RANGES = [
    f"under ${HH_BREAKS[0]/1000:.0f}K",
    f"${HH_BREAKS[0]/1000:.0f}K – ${HH_BREAKS[1]/1000:.0f}K",
    f"${HH_BREAKS[1]/1000:.0f}K – ${HH_BREAKS[2]/1000:.0f}K",
    f"${HH_BREAKS[2]/1000:.0f}K – ${HH_BREAKS[3]/1000:.0f}K",
    f"${HH_BREAKS[3]/1000:.0f}K+",
]

# Visual palette
NAVY      = "#1e3a5f"
TEAL      = "#2c8c87"
ORANGE    = "#c05e2b"
PILL_BG   = "#e8eef7"
PILL_FG   = "#1e3a5f"
TEXT_GREY = "#4a5568"
RULE_GREY = "#cbd5e0"

# REEC income-group data (DOTAX TY2023 "Tax Credits Claimed", Table A-1 / A-5)
# (label, individual_claim_$M, agi_eligible_share)
REEC_IND_BINS = [
    ("<$10K",       4.731, 1.000),
    ("$10K–$30K",   2.522, 1.000),
    ("$30K–$60K",   3.121, 1.000),
    ("$60K–$100K",  5.752, 1.000),
    ("$100K–$200K", 16.150, 0.972),
    ("$200K+",      26.018, 0.561),
]
REEC_CORP_M = 38.565 + 3.217   # corporations + other TY2023 ($M)
REEC_CAP_M  = 40.0


def _format_value(val: float, fmt: str) -> str:
    if fmt == "dollar":
        sign = "+" if val >= 0 else "-"
        return f"{sign}${abs(val):,.0f}"
    if fmt == "pct":
        return f"{val:.1f}%"
    if fmt == "millions":
        sign = "+" if val >= 0 else "-"
        return f"{sign}${abs(val):,.1f}M"
    return f"{val}"


# ---------------------------------------------------------------------------
# Page 1 — three stacked tables
# ---------------------------------------------------------------------------
def render_table_page(df: pd.DataFrame, pdf: PdfPages) -> None:
    years = sorted(df["tax_year"].unique())

    fig = plt.figure(figsize=(11, 11))
    fig.suptitle(
        "SB 3125 CD2 vs Act 46 — Distributional Impact (MID Scenario)",
        fontsize=15, fontweight="bold", y=0.97, color=NAVY,
    )
    fig.text(
        0.5, 0.935,
        "Per-filer impact by income quintile, TY 2027 – 2031  ·  bracket changes only (§235-51)",
        ha="center", fontsize=10, style="italic", color=TEXT_GREY,
    )

    table_specs = [
        ("Avg Tax Change per Filer",          "avg_delta_per_filer_$",   "dollar"),
        ("Share of Filers with Any Change",   "pct_filers_with_change",  "pct"),
        ("Total Tax Change for Quintile",     "delta_total_$M",          "millions"),
    ]

    n = len(table_specs)
    top, bottom = 0.90, 0.06
    pad = 0.025
    panel_h = (top - bottom - (n - 1) * pad) / n

    for i, (title, col, fmt) in enumerate(table_specs):
        y_top = top - i * (panel_h + pad)
        ax = fig.add_axes([0.05, y_top - panel_h, 0.90, panel_h])
        ax.axis("off")

        ax.text(
            0.0, 1.0, title,
            transform=ax.transAxes, fontsize=11.5, fontweight="bold",
            color=NAVY, va="top",
        )

        rows = []
        for q_label, q_name, q_range in zip(Q_LABELS, Q_NAMES, Q_RANGES):
            row = [q_name, q_range]
            for yr in years:
                sub = df[(df["tax_year"] == yr) & (df["quintile"] == q_label)]
                if sub.empty:
                    row.append("—")
                else:
                    row.append(_format_value(float(sub.iloc[0][col]), fmt))
            rows.append(row)

        col_labels = ["Quintile", "Household income"] + [str(y) for y in years]
        col_widths  = [0.16, 0.22] + [0.124] * len(years)

        tbl = ax.table(
            cellText=rows, colLabels=col_labels,
            colWidths=col_widths, loc="upper left",
            bbox=[0.0, 0.0, 1.0, 0.85], cellLoc="center",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)

        for j in range(len(col_labels)):
            cell = tbl[(0, j)]
            cell.set_facecolor(NAVY)
            cell.set_text_props(color="white", fontweight="bold")
            cell.set_edgecolor("white")

        for r in range(1, len(rows) + 1):
            for j in range(len(col_labels)):
                c = tbl[(r, j)]
                c.set_edgecolor(RULE_GREY)
                if j == 0:
                    c.set_text_props(fontweight="bold", color=NAVY)
                    c.set_facecolor(PILL_BG)
                elif j == 1:
                    c.set_text_props(color=TEXT_GREY)
                    c.set_facecolor(PILL_BG)
                if r == len(rows):
                    if j >= 2:
                        c.set_facecolor("#fff5f5")

    fig.text(
        0.05, 0.03,
        "Note: bracket-change impact only. REEC/CGEC/TCRA credit-cap savings are not attributable "
        "to individual filers and are reported separately (see pages 5–6). "
        "Positive values = filer pays more under SB 3125 CD2 vs Act 46.",
        ha="left", fontsize=7.5, style="italic", color=TEXT_GREY,
    )

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Bar-chart pages — horizontal bars, two-panel (TY 2027 + TY 2031)
# ---------------------------------------------------------------------------
def _draw_quintile_panel(
    ax, df_year: pd.DataFrame, year: int, col: str, fmt: str,
    bar_color: str, value_color: str = "#2d3748",
) -> None:
    values = []
    for q in Q_LABELS:
        sub = df_year[df_year["quintile"] == q]
        values.append(float(sub.iloc[0][col]) if not sub.empty else 0.0)

    y_pos = np.arange(len(Q_LABELS))[::-1]
    bars = ax.barh(y_pos, values, height=0.55, color=bar_color, edgecolor="none")

    vmax = max(abs(min(values)), abs(max(values))) or 1.0
    pad  = vmax * 0.04

    for bar, val in zip(bars, values):
        label = _format_value(val, fmt)
        if val >= 0:
            ax.text(
                val + pad, bar.get_y() + bar.get_height() / 2, label,
                va="center", ha="left", fontsize=10, fontweight="bold",
                color=value_color,
            )
        else:
            ax.text(
                val - pad, bar.get_y() + bar.get_height() / 2, label,
                va="center", ha="right", fontsize=10, fontweight="bold",
                color=value_color,
            )

    ax.set_yticks(y_pos)
    ax.set_yticklabels([])
    for yp, name, rng in zip(y_pos, Q_NAMES, Q_RANGES):
        ax.text(
            -0.01, yp + 0.12, name,
            transform=ax.get_yaxis_transform(), ha="right", va="center",
            fontsize=9.5, fontweight="bold", color=PILL_FG,
            bbox=dict(boxstyle="round,pad=0.35", facecolor=PILL_BG, edgecolor="none"),
        )
        ax.text(
            -0.01, yp - 0.22, rng,
            transform=ax.get_yaxis_transform(), ha="right", va="center",
            fontsize=8.5, color=TEXT_GREY,
        )

    ax.set_title(f"Tax Year {year}", loc="left", fontsize=12, fontweight="bold", color=NAVY)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(RULE_GREY)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", colors=TEXT_GREY, labelsize=8)
    ax.grid(axis="x", linestyle=":", alpha=0.35, color=RULE_GREY)
    ax.axvline(0, color=RULE_GREY, linewidth=0.7)

    if min(values) < 0:
        ax.set_xlim(min(values) - vmax * 0.30, max(values) + vmax * 0.30)
    else:
        ax.set_xlim(0, max(values) * 1.30)


def render_chart_page(
    df: pd.DataFrame, pdf: PdfPages,
    title: str, subtitle: str, col: str, fmt: str,
    bar_color: str = TEAL,
) -> None:
    fig = plt.figure(figsize=(11, 10))
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.965, color=NAVY)
    fig.text(0.5, 0.93, subtitle, ha="center", fontsize=10, style="italic", color=TEXT_GREY)

    for i, yr in enumerate([2027, 2031]):
        ax  = fig.add_axes([0.22, 0.50 - i * 0.42, 0.72, 0.36])
        sub = df[df["tax_year"] == yr]
        _draw_quintile_panel(ax, sub, yr, col, fmt, bar_color)

    fig.text(
        0.5, 0.02,
        "Source: Census-Forecaster microsim. Quintiles defined on 2026 household income.",
        ha="center", fontsize=8, style="italic", color=TEXT_GREY,
    )

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Page 5 — REEC incidence by income group
# ---------------------------------------------------------------------------
def _reec_incidence_rows(pro_rata_factor: float) -> list[dict]:
    """Compute per-row incidence using TY2023 DOTAX actuals + TY2027 MID pro-rata."""
    rows = []
    for label, claim, elig in REEC_IND_BINS:
        eligible  = claim * elig
        lost_agi  = claim - eligible
        after_cap = eligible * pro_rata_factor
        lost_cap  = eligible - after_cap
        rows.append({
            "group":      label,
            "baseline":   claim,
            "elig_pct":   elig * 100,
            "eligible":   eligible,
            "lost_agi":   lost_agi,
            "after_cap":  after_cap,
            "lost_cap":   lost_cap,
            "total_lost": lost_agi + lost_cap,
            "pct_lost":   (lost_agi + lost_cap) / claim * 100,
        })
    # Corporate row — no AGI limit under default MID scenario
    corp_after = REEC_CORP_M * pro_rata_factor
    rows.append({
        "group":      "Corporate / Other",
        "baseline":   REEC_CORP_M,
        "elig_pct":   100.0,
        "eligible":   REEC_CORP_M,
        "lost_agi":   0.0,
        "after_cap":  corp_after,
        "lost_cap":   REEC_CORP_M - corp_after,
        "total_lost": REEC_CORP_M - corp_after,
        "pct_lost":   (REEC_CORP_M - corp_after) / REEC_CORP_M * 100,
    })
    return rows


def render_reec_incidence_page(pdf: PdfPages, pro_rata_factor: float = 0.7806) -> None:
    rows = _reec_incidence_rows(pro_rata_factor)

    fig = plt.figure(figsize=(11, 10))
    fig.suptitle(
        "REEC Credit Restriction — Impact by Income Group",
        fontsize=14, fontweight="bold", y=0.97, color=NAVY,
    )
    fig.text(
        0.5, 0.935,
        f"TY2023 DOTAX actuals  ·  TY2027 MID pro-rata factor {pro_rata_factor:.0%}  "
        f"·  §235-12.5 AGI limits ($175K single / $350K joint) + $40M aggregate cap",
        ha="center", fontsize=9.5, style="italic", color=TEXT_GREY,
    )

    # Stacked horizontal bars: retained (teal) | lost to cap (orange) | lost to AGI (navy)
    group_labels = [r["group"] for r in rows]
    retained     = [r["after_cap"]  for r in rows]
    lost_cap     = [r["lost_cap"]   for r in rows]
    lost_agi     = [r["lost_agi"]   for r in rows]

    y_pos = np.arange(len(rows))[::-1]
    ax = fig.add_axes([0.26, 0.18, 0.68, 0.70])

    b1 = ax.barh(y_pos, retained, height=0.55, color=TEAL,   edgecolor="none", label="Retained after cap")
    b2 = ax.barh(y_pos, lost_cap, height=0.55, color=ORANGE, edgecolor="none",
                 left=retained, label="Lost to cap (pro-rata)")
    b3 = ax.barh(y_pos, lost_agi, height=0.55, color=NAVY,   edgecolor="none",
                 left=[r + c for r, c in zip(retained, lost_cap)], label="Lost to AGI filter")

    # Value labels: total credit lost (%) at right edge
    for yp, row in zip(y_pos, rows):
        pct  = row["pct_lost"]
        tot  = row["total_lost"]
        base = row["baseline"]
        ax.text(
            base + 0.4, yp,
            f"−${tot:.1f}M  ({pct:.0f}%)",
            va="center", ha="left", fontsize=9, color=NAVY, fontweight="bold",
        )

    # Left-side labels
    ax.set_yticks(y_pos)
    ax.set_yticklabels([])
    for yp, row in zip(y_pos, rows):
        is_corp = row["group"] == "Corporate / Other"
        ax.text(
            -0.01, yp, row["group"],
            transform=ax.get_yaxis_transform(), ha="right", va="center",
            fontsize=9.5, fontweight="bold" if is_corp else "normal",
            color=NAVY if is_corp else PILL_FG,
            bbox=dict(boxstyle="round,pad=0.35", facecolor=PILL_BG, edgecolor="none"),
        )

    ax.set_xlabel("Credit ($M, TY2023 basis)", fontsize=9, color=TEXT_GREY)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(RULE_GREY)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", colors=TEXT_GREY, labelsize=8)
    ax.grid(axis="x", linestyle=":", alpha=0.35, color=RULE_GREY)
    ax.set_xlim(0, max(r["baseline"] for r in rows) * 1.45)

    ax.legend(
        loc="lower right", fontsize=9, framealpha=0.9,
        edgecolor=RULE_GREY,
    )

    # Separator line between individual and corporate
    ax.axhline(y=0.5, color=RULE_GREY, linewidth=1.0, linestyle="--")

    fig.text(
        0.05, 0.10,
        "Totals based on DOTAX TY2023 actuals (most recent available). "
        "TY2027 individual demand is lower due to federal §25D termination (OBBBA, PL 119-21) "
        "— relative incidence across groups is similar. "
        "Corporate REEC is not subject to the AGI income limit under the MID scenario "
        "(§235-12.5(a) references 'adjusted gross income', ambiguous for corporations). "
        "Pro-rata factor reflects demand suppression under η=0.3 elasticity (MID).",
        ha="left", fontsize=7.5, style="italic", color=TEXT_GREY, wrap=True,
    )

    ind_total_lost = sum(r["total_lost"] for r in rows if r["group"] != "Corporate / Other")
    corp_lost      = rows[-1]["total_lost"]
    grand_baseline = sum(r["baseline"] for r in rows)
    grand_lost     = sum(r["total_lost"] for r in rows)

    fig.text(
        0.05, 0.06,
        f"TY2023 totals: individual ${sum(r['baseline'] for r in rows if r['group'] != 'Corporate / Other'):.1f}M"
        f"  |  corporate ${REEC_CORP_M:.1f}M  |  combined ${grand_baseline:.1f}M. "
        f"Aggregate credit lost under bill (TY2023 basis): "
        f"individual −${ind_total_lost:.1f}M  |  corporate −${corp_lost:.1f}M  |  total −${grand_lost:.1f}M.",
        ha="left", fontsize=7.5, color=TEXT_GREY,
    )

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Page 6 — REEC savings trajectory TY2027–2031
# ---------------------------------------------------------------------------
def render_reec_time_series_page(df_enhanced: pd.DataFrame, pdf: PdfPages) -> None:
    scenarios = ["LOW", "MID", "HIGH"]
    colors    = {
        "LOW":  "#8fa8c8",
        "MID":  TEAL,
        "HIGH": "#c05e2b",
    }
    years = [2027, 2028, 2029, 2030, 2031]

    fig = plt.figure(figsize=(11, 10))
    fig.suptitle(
        "REEC Savings Over Time — Baseline vs. Bill State Cost",
        fontsize=14, fontweight="bold", y=0.97, color=NAVY,
    )
    fig.text(
        0.5, 0.935,
        "§235-12.5 renewable energy credit  ·  TY2027–2031  ·  LOW / MID / HIGH scenarios",
        ha="center", fontsize=10, style="italic", color=TEXT_GREY,
    )

    # Top panel: grouped bar chart of REEC savings by scenario
    ax_top = fig.add_axes([0.10, 0.52, 0.84, 0.36])

    n_scen  = len(scenarios)
    width   = 0.22
    offsets = np.linspace(-(n_scen - 1) / 2 * width, (n_scen - 1) / 2 * width, n_scen)
    x = np.arange(len(years))

    for scen, offset in zip(scenarios, offsets):
        sub    = df_enhanced[df_enhanced["scenario"] == scen].set_index("tax_year")
        values = [sub.loc[y, "reec_savings_$M"] for y in years]
        bars   = ax_top.bar(x + offset, values, width=width * 0.92,
                            color=colors[scen], edgecolor="none", label=scen)
        for bar, val in zip(bars, values):
            ax_top.text(
                bar.get_x() + bar.get_width() / 2, val + 1.0,
                f"${val:.0f}M", ha="center", va="bottom", fontsize=7.5,
                color=colors[scen], fontweight="bold",
            )

    ax_top.set_xticks(x)
    ax_top.set_xticklabels([f"TY{y}" for y in years], fontsize=10, color=TEXT_GREY)
    ax_top.set_ylabel("REEC savings ($M)", fontsize=9, color=TEXT_GREY)
    ax_top.set_title("Annual REEC Fiscal Savings (Baseline − Bill State Cost)", loc="left",
                     fontsize=11, fontweight="bold", color=NAVY)
    ax_top.spines["top"].set_visible(False)
    ax_top.spines["right"].set_visible(False)
    ax_top.spines["left"].set_color(RULE_GREY)
    ax_top.spines["bottom"].set_color(RULE_GREY)
    ax_top.tick_params(axis="y", colors=TEXT_GREY, labelsize=8)
    ax_top.grid(axis="y", linestyle=":", alpha=0.35, color=RULE_GREY)
    ax_top.set_ylim(0, 145)
    ax_top.legend(loc="upper left", fontsize=9, framealpha=0.9, edgecolor=RULE_GREY)

    # Sunset annotation
    ax_top.axvspan(2.5, 4.5, alpha=0.06, color=NAVY, zorder=0)
    ax_top.text(3.5, 135, "§235-12.5(p)\nsunset", ha="center", va="top",
                fontsize=8.5, color=NAVY, style="italic")

    # Bottom panel: bill state cost decomposition (MID only)
    ax_bot = fig.add_axes([0.10, 0.10, 0.84, 0.34])

    mid = df_enhanced[df_enhanced["scenario"] == "MID"].set_index("tax_year")
    base_cost  = [mid.loc[y, "reec_base_state_cost_$M"] for y in years]
    scen_ref   = [mid.loc[y, "reec_scen_refundable_$M"]   for y in years]
    scen_nonref = [mid.loc[y, "reec_scen_nonref_usage_$M"] for y in years]

    ax_bot.plot(x, base_cost, color=NAVY, linewidth=2.0, marker="o",
                markersize=5, label="Baseline (no cap)", zorder=3)
    ax_bot.bar(x, scen_ref,    width=0.45, color=TEAL,   edgecolor="none",
               label="Bill: refundable (in-year)", zorder=2)
    ax_bot.bar(x, scen_nonref, width=0.45, color="#8fa8c8", edgecolor="none",
               bottom=scen_ref, label="Bill: nonref carryforward drawdown", zorder=2)

    ax_bot.set_xticks(x)
    ax_bot.set_xticklabels([f"TY{y}" for y in years], fontsize=10, color=TEXT_GREY)
    ax_bot.set_ylabel("State cost ($M)", fontsize=9, color=TEXT_GREY)
    ax_bot.set_title("MID Scenario — State Cost Components", loc="left",
                     fontsize=11, fontweight="bold", color=NAVY)
    ax_bot.spines["top"].set_visible(False)
    ax_bot.spines["right"].set_visible(False)
    ax_bot.spines["left"].set_color(RULE_GREY)
    ax_bot.spines["bottom"].set_color(RULE_GREY)
    ax_bot.tick_params(colors=TEXT_GREY, labelsize=8)
    ax_bot.grid(axis="y", linestyle=":", alpha=0.35, color=RULE_GREY)
    ax_bot.set_ylim(0, 125)
    ax_bot.legend(loc="upper right", fontsize=9, framealpha=0.9, edgecolor=RULE_GREY)

    ax_bot.axvspan(2.5, 4.5, alpha=0.06, color=NAVY, zorder=0)

    fig.text(
        0.05, 0.03,
        "Baseline: Act 46 (no cap, no AGI limit, no sunset). "
        "Bill: §235-12.5 as amended — $40M annual cap TY2027–2029, $0 new certifications TY2030+. "
        "State cost = refundable credits paid + nonrefundable carryforward stock drawdown. "
        "Savings = baseline − bill. LOW uses interpretation A (TY2026 cap binds); "
        "MID/HIGH use interpretation B. MID/HIGH pro-rata η=0.3/0.15; LOW η=0.5.",
        ha="left", fontsize=7.5, style="italic", color=TEXT_GREY,
    )

    # 5-year cumulative callout box
    for scen, color in colors.items():
        sub = df_enhanced[df_enhanced["scenario"] == scen]
        cum = sub["reec_savings_$M"].sum()
        ax_top.text(
            4.48 - list(scenarios).index(scen) * 0.30, 10,
            f"{scen}: ${cum:.0f}M",
            ha="right", va="bottom", fontsize=8, color=color, fontweight="bold",
            transform=ax_top.transData,
        )

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    if not CSV_IN.exists():
        raise SystemExit(f"Quintile CSV not found: {CSV_IN}\nRun forecast_sb3125_cd2_quintile.py first.")
    if not ENHANCED_CSV.exists():
        raise SystemExit(f"Enhanced CSV not found: {ENHANCED_CSV}\nRun forecast_sb3125_cd2_enhanced.py first.")

    df          = pd.read_csv(CSV_IN)
    df_enhanced = pd.read_csv(ENHANCED_CSV)

    # Pull TY2027 MID pro-rata factor for REEC incidence page
    mid_2027      = df_enhanced[(df_enhanced["scenario"] == "MID") & (df_enhanced["tax_year"] == 2027)]
    pro_rata_mid  = float(mid_2027["reec_pro_rata_factor"].iloc[0]) if not mid_2027.empty else 0.7806

    with PdfPages(PDF_OUT) as pdf:
        render_table_page(df, pdf)
        render_chart_page(
            df, pdf,
            title="Average Tax Change per Filer by Quintile",
            subtitle="SB 3125 CD2 vs Act 46 — MID Scenario  ·  §235-51 bracket changes only",
            col="avg_delta_per_filer_$", fmt="dollar", bar_color=TEAL,
        )
        render_chart_page(
            df, pdf,
            title="Share of Filers with Any Tax Change",
            subtitle="SB 3125 CD2 vs Act 46 — MID Scenario  ·  §235-51 bracket changes only",
            col="pct_filers_with_change", fmt="pct", bar_color=NAVY,
        )
        render_chart_page(
            df, pdf,
            title="Total Tax Change by Quintile",
            subtitle="SB 3125 CD2 vs Act 46 — MID Scenario  ·  §235-51 bracket changes only",
            col="delta_total_$M", fmt="millions", bar_color=TEAL,
        )
        render_reec_incidence_page(pdf, pro_rata_factor=pro_rata_mid)
        render_reec_time_series_page(df_enhanced, pdf)

        meta = pdf.infodict()
        meta["Title"]   = "SB 3125 CD2 Distributional Analysis"
        meta["Author"]  = "Census-Forecaster"
        meta["Subject"] = "Quintile tax impact + REEC credit incidence, TY 2027–2031, MID scenario"

    print(f"Saved: {PDF_OUT}")


if __name__ == "__main__":
    main()
