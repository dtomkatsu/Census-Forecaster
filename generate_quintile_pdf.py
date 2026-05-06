"""Render the SB 3125 CD1 quintile distributional analysis to PDF.

Reads /tmp/sb3125_quintile_mid_2027_2031.csv (produced by
forecast_sb3125_cd1_enhanced.py) and produces:
  /tmp/sb3125_quintile_distributional_report.pdf

Layout:
  Page 1 — Three clean stacked tables: avg per-filer tax change, %
           filers paying more, total impact ($M). Each is 5 quintiles ×
           5 years with the income range alongside each quintile label.
  Page 2 — Avg per-filer tax change: horizontal bar chart, panels for
           TY 2027 and TY 2031 (visual style matches HiTaxFairness one-pager).
  Page 3 — % filers paying more: same panel layout.
  Page 4 — Total quintile-level impact ($M): same panel layout.
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

CSV_IN = Path("/tmp/sb3125_quintile_mid_2027_2031.csv")
PDF_OUT = Path("/tmp/sb3125_quintile_distributional_report.pdf")

HH_BREAKS = [28_336, 60_915, 100_510, 168_638]
Q_LABELS = ["Q1 (bottom 20%)", "Q2", "Q3", "Q4", "Q5 (top 20%)"]
Q_NAMES = ["Bottom 20%", "2nd 20%", "3rd 20%", "4th 20%", "Top 20%"]
Q_RANGES = [
    f"under ${HH_BREAKS[0]/1000:.0f}K",
    f"${HH_BREAKS[0]/1000:.0f}K – ${HH_BREAKS[1]/1000:.0f}K",
    f"${HH_BREAKS[1]/1000:.0f}K – ${HH_BREAKS[2]/1000:.0f}K",
    f"${HH_BREAKS[2]/1000:.0f}K – ${HH_BREAKS[3]/1000:.0f}K",
    f"${HH_BREAKS[3]/1000:.0f}K+",
]

# Visual palette
NAVY = "#1e3a5f"
TEAL = "#2c8c87"
PILL_BG = "#e8eef7"
PILL_FG = "#1e3a5f"
TEXT_GREY = "#4a5568"
RULE_GREY = "#cbd5e0"


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
        "SB 3125 CD1 vs Act 46 — Distributional Impact (MID Scenario)",
        fontsize=15, fontweight="bold", y=0.97, color=NAVY,
    )
    fig.text(
        0.5, 0.935,
        "Per-household impact by ITEP-anchored 2026 household-income quintile, TY 2027 – 2031",
        ha="center", fontsize=10, style="italic", color=TEXT_GREY,
    )

    # Three vertically stacked sub-tables
    has_hh  = "avg_per_hh_total_change" in df.columns
    avg_col = "avg_per_hh_total_change" if has_hh else "avg_total_change"
    avg_lbl = ("Avg Tax Change per Household" if has_hh else "Avg Per-Filer Tax Change")
    table_specs = [
        (avg_lbl,                              avg_col,           "dollar"),
        ("Share of Households with Tax Increase", "pct_pay_more",  "pct"),
        ("Total Tax Change for Quintile",      "total_change_$M", "millions"),
    ]

    n = len(table_specs)
    top, bottom = 0.90, 0.03
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
                sub = df[(df["tax_year"] == yr) & (df["quintile"] == q_label)].iloc[0]
                row.append(_format_value(sub[col], fmt))
            rows.append(row)

        col_labels = ["Quintile", "Household income"] + [str(y) for y in years]
        col_widths = [0.16, 0.22] + [0.124] * len(years)

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
                if r == len(rows):  # Top quintile highlight
                    if j >= 2:
                        c.set_facecolor("#fff5f5")

    # Methodology / coverage note at the bottom — explains the difference
    # between modeled-population totals and statewide COR-anchored totals.
    has_cor = "total_change_cor_$M" in df.columns
    if has_cor:
        diag_lines = []
        for yr in years:
            sub = df[df["tax_year"] == yr]
            raw = sub["total_change_$M"].sum()
            scl = sub["total_change_cor_$M"].sum()
            diag_lines.append(f"TY {yr}: raw ${raw:+,.0f}M  /  COR-anchored ${scl:+,.0f}M")
        fig.text(
            0.05, 0.018,
            "Aggregate impact (raw microsim total / COR-anchored statewide estimate):  "
            + "  |  ".join(diag_lines),
            ha="left", fontsize=7.5, color=TEXT_GREY,
        )
        fig.text(
            0.05, 0.005,
            "Per-quintile averages above are RAW (modeled population). COR-anchored totals scale "
            "to the official Council on Revenues IIT baseline to account for population-coverage "
            "gaps in the microsim (PTE filers, non-resident withholding, withholding-only filers).",
            ha="left", fontsize=7, style="italic", color=TEXT_GREY,
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
        v = float(df_year[df_year["quintile"] == q].iloc[0][col])
        values.append(v)

    y_pos = np.arange(len(Q_LABELS))[::-1]  # top-to-bottom
    bars = ax.barh(y_pos, values, height=0.55, color=bar_color, edgecolor="none")

    # Determine x-range and label offset
    vmax = max(abs(min(values)), abs(max(values))) or 1.0
    pad = vmax * 0.04

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

    # Y-axis: pill-styled labels (name + range)
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

    # Cosmetic axis cleanup
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(RULE_GREY)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", colors=TEXT_GREY, labelsize=8)
    ax.grid(axis="x", linestyle=":", alpha=0.35, color=RULE_GREY)
    ax.axvline(0, color=RULE_GREY, linewidth=0.7)

    # Pad x-range so labels fit
    if min(values) < 0:
        ax.set_xlim(min(values) - vmax * 0.30, max(values) + vmax * 0.30)
    else:
        ax.set_xlim(0, max(values) * 1.30)


def render_chart_page(
    df: pd.DataFrame, pdf: PdfPages,
    title: str, subtitle: str, col: str, fmt: str,
    bar_color: str = TEAL,
) -> None:
    years_to_plot = [2027, 2031]

    fig = plt.figure(figsize=(11, 10))
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.965, color=NAVY)
    fig.text(0.5, 0.93, subtitle, ha="center", fontsize=10, style="italic", color=TEXT_GREY)

    for i, yr in enumerate(years_to_plot):
        ax = fig.add_axes([0.22, 0.50 - i * 0.42, 0.72, 0.36])
        sub = df[df["tax_year"] == yr]
        _draw_quintile_panel(ax, sub, yr, col, fmt, bar_color)

    fig.text(
        0.5, 0.02,
        "Source: Census-Forecaster microsim. Quintiles defined on 2026 household income.",
        ha="center", fontsize=8, style="italic", color=TEXT_GREY,
    )

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    if not CSV_IN.exists():
        raise SystemExit(f"Input not found: {CSV_IN}. Run forecast_sb3125_cd1_enhanced.py first.")
    df = pd.read_csv(CSV_IN)

    has_hh  = "avg_per_hh_total_change" in df.columns
    avg_col = "avg_per_hh_total_change" if has_hh else "avg_total_change"
    avg_title = "Average Tax Change per Household by Quintile" if has_hh \
                else "Average Per-Filer Tax Change by Quintile"

    with PdfPages(PDF_OUT) as pdf:
        render_table_page(df, pdf)
        render_chart_page(
            df, pdf,
            title=avg_title,
            subtitle="SB 3125 CD1 vs Act 46 — MID Scenario",
            col=avg_col, fmt="dollar", bar_color=TEAL,
        )
        render_chart_page(
            df, pdf,
            title="Share of Households with a Tax Increase",
            subtitle="SB 3125 CD1 vs Act 46 — MID Scenario",
            col="pct_pay_more", fmt="pct", bar_color=NAVY,
        )
        render_chart_page(
            df, pdf,
            title="Total Tax Change by Quintile",
            subtitle="SB 3125 CD1 vs Act 46 — MID Scenario",
            col="total_change_$M", fmt="millions", bar_color=TEAL,
        )

        meta = pdf.infodict()
        meta["Title"] = "SB 3125 CD1 Distributional Analysis"
        meta["Author"] = "Census-Forecaster"
        meta["Subject"] = "Per-quintile per-household tax impact, TY 2027–2031, MID scenario"

    print(f"Saved: {PDF_OUT}")


if __name__ == "__main__":
    main()
