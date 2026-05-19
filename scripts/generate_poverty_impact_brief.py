"""Generate Hawaii Appleseed-styled policy brief PDF from poverty-impact CSVs."""

from __future__ import annotations

import argparse
import datetime as _dt
import math
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from fpdf import FPDF

REPO_ROOT = Path(__file__).resolve().parents[1]

TEAL = "#005F73"
GOLD = "#E9B949"
SLATE = "#4A4E69"
LIGHT_TEAL = "#E8F4F6"
CHARCOAL = "#2D2D2D"
LIGHT_GRAY = "#F5F5F5"
WHITE = "#FFFFFF"

TIER_PREFERENCE = [
    "poverty_impact_2024_tier4_spm",
    "poverty_impact_2024_tier3",
    "poverty_impact_2024_tier2",
    "poverty_impact_2024_review",
    "poverty_impact_2024_tier1",
    "poverty_impact_2024",
]

DATA_SOURCE_CITATION = (
    "Source: U.S. Census Bureau 5-Year ACS PUMS 2018-2022; Census-Forecaster "
    "tax simulation model, Hawaiʻi Appleseed 2025"
)


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _fmt_int(n: float | int | None) -> str:
    if n is None or (isinstance(n, float) and math.isnan(n)):
        return "n/a"
    return f"{int(round(float(n))):,}"


def _fmt_money_m(n: float | int | None) -> str:
    if n is None or (isinstance(n, float) and math.isnan(n)):
        return "n/a"
    return f"${float(n) / 1e6:,.0f}M"


def _fmt_pct(rate: float | None, digits: int = 1) -> str:
    if rate is None or (isinstance(rate, float) and math.isnan(rate)):
        return "n/a"
    return f"{float(rate) * 100:.{digits}f}%"


@dataclass
class BriefData:
    tax_year: int
    data_dir: Path
    state: pd.Series
    counties: pd.DataFrame
    house_districts: pd.DataFrame
    senate_districts: pd.DataFrame
    household_types: pd.DataFrame | None = None
    racial_stats: pd.DataFrame | None = None
    rxkids_state: pd.Series | None = None
    rxkids_dir: Path | None = None


def _resolve_data_dir(explicit: Path | None, tax_year: int) -> Path:
    if explicit is not None:
        if not (explicit / "by_state.csv").exists():
            raise FileNotFoundError(
                f"--data-dir does not contain by_state.csv: {explicit}"
            )
        return explicit
    candidates = [REPO_ROOT / "reports" / name for name in TIER_PREFERENCE]
    for cand in candidates:
        if (cand / "by_state.csv").exists():
            return cand
    raise FileNotFoundError(
        "No poverty_impact_* directory with by_state.csv found under reports/. "
        f"Tried: {[c.name for c in candidates]}"
    )


def _resolve_rxkids_dir(explicit: Path | None, tax_year: int) -> Path | None:
    if explicit is not None:
        return explicit if (explicit / "by_state.csv").exists() else None
    cand = REPO_ROOT / "reports" / f"rxkids_impact_{tax_year}"
    return cand if (cand / "by_state.csv").exists() else None


def _compute_racial_stats(pums_dir: Path) -> pd.DataFrame | None:
    """Compute poverty rate and median personal income by race from ACS 2024 1-year PUMS."""
    # Prefer 2024 1-year PUMS; fall back to 2018-2022 5-year if absent.
    acs2024_dir = pums_dir / "pums_2024_1yr"
    if (acs2024_dir / "psam_p15.parquet").exists():
        persons_path = acs2024_dir / "psam_p15.parquet"
        vintage = "ACS 2024 1-Year"
    elif (pums_dir / "psam_p15.parquet").exists():
        persons_path = pums_dir / "psam_p15.parquet"
        vintage = "ACS 2018-2022 5-Year"
    else:
        return None
    import numpy as np
    persons = pd.read_parquet(persons_path)
    race_groups = [
        ("White alone", persons["RAC1P"] == 1),
        ("Asian alone", persons["RAC1P"] == 6),
        ("Native Hawaiian\n(alone or in combo)", persons["RACNH"] == 1),
        ("Pacific Islander\n(NHPI alone)", persons["RAC1P"] == 7),
        ("Two or more races", persons["RAC1P"] == 9),
        ("Black alone", persons["RAC1P"] == 2),
    ]
    rows = []
    for label, mask in race_groups:
        sub = persons[mask]
        tot = sub["PWGTP"].sum()
        if tot < 10000:
            continue
        pov = sub[sub["POVPIP"] < 100]["PWGTP"].sum()
        earners = sub[(sub["PERNP"] > 0) & sub["PERNP"].notna()].copy()
        earners["adj"] = earners["PERNP"] * earners["ADJINC"] / 1e6
        earners = earners.sort_values("adj")
        cum = earners["PWGTP"].cumsum()
        half = earners["PWGTP"].sum() / 2
        med_row = earners[cum >= half]
        med_inc = float(med_row["adj"].iloc[0]) if len(med_row) > 0 else np.nan
        rows.append({"race": label, "poverty_rate": pov / tot, "median_income": med_inc, "n": int(tot), "vintage": vintage})
    return pd.DataFrame(rows)


def _load_data(
    data_dir: Path, tax_year: int, rxkids_dir: Path | None
) -> BriefData:
    state = pd.read_csv(data_dir / "by_state.csv").iloc[0]
    counties = pd.read_csv(data_dir / "by_county.csv")
    hd = pd.read_csv(data_dir / "by_house_district.csv")
    sd = pd.read_csv(data_dir / "by_senate_district.csv")
    hht_path = data_dir / "by_household_type.csv"
    household_types = pd.read_csv(hht_path) if hht_path.exists() else None
    rxkids_state = None
    if rxkids_dir is not None:
        rxkids_state = pd.read_csv(rxkids_dir / "by_state.csv").iloc[0]
    pums_dir = REPO_ROOT / "packages" / "data" / "raw"
    racial_stats = _compute_racial_stats(pums_dir)
    return BriefData(
        tax_year=tax_year,
        data_dir=data_dir,
        state=state,
        counties=counties,
        house_districts=hd,
        senate_districts=sd,
        household_types=household_types,
        racial_stats=racial_stats,
        rxkids_state=rxkids_state,
        rxkids_dir=rxkids_dir,
    )


def _set_chart_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Manrope",
                "Poppins",
                "Inter",
                "Helvetica",
                "Arial",
                "DejaVu Sans",
            ],
            "axes.edgecolor": CHARCOAL,
            "axes.labelcolor": CHARCOAL,
            "axes.titlecolor": CHARCOAL,
            "axes.titleweight": "bold",
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "xtick.color": CHARCOAL,
            "ytick.color": CHARCOAL,
            "axes.grid": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def _horizontal_bar(
    labels: list[str],
    values: list[float],
    out_path: Path,
    color: str,
    title: str,
    value_fmt: str = "{:.1f}%",
    xlabel: str = "",
    width: float = 7.5,
    height: float = 4.0,
) -> None:
    fig, ax = plt.subplots(figsize=(width, height))
    y_pos = list(range(len(labels)))
    bars = ax.barh(y_pos, values, color=color, edgecolor="white", height=0.65)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    if xlabel:
        ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left", pad=12)
    max_v = max(values) if values else 1.0
    for bar, v in zip(bars, values):
        ax.text(
            bar.get_width() + max_v * 0.01,
            bar.get_y() + bar.get_height() / 2,
            value_fmt.format(v),
            va="center",
            fontsize=8,
            color=CHARCOAL,
        )
    ax.set_xlim(0, max_v * 1.18)
    ax.tick_params(axis="x", length=0)
    plt.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _vertical_bar(
    labels: list[str],
    values: list[float],
    out_path: Path,
    color: str,
    title: str,
    value_fmt: str = "{:,.0f}",
    ylabel: str = "",
    width: float = 7.5,
    height: float = 4.0,
) -> None:
    fig, ax = plt.subplots(figsize=(width, height))
    x_pos = list(range(len(labels)))
    bars = ax.bar(x_pos, values, color=color, edgecolor="white", width=0.65)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left", pad=12)
    max_v = max(values) if values else 1.0
    for bar, v in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max_v * 0.02,
            value_fmt.format(v),
            ha="center",
            va="bottom",
            fontsize=8,
            color=CHARCOAL,
        )
    ax.set_ylim(0, max_v * 1.18)
    ax.tick_params(axis="y", length=0)
    plt.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _stacked_vertical_bar(
    group_labels: list[str],
    series: dict[str, list[float]],
    colors: dict[str, str],
    out_path: Path,
    title: str,
    value_fmt: str = "{:,.0f}",
    ylabel: str = "",
    width: float = 7.5,
    height: float = 4.2,
) -> None:
    fig, ax = plt.subplots(figsize=(width, height))
    x = list(range(len(group_labels)))
    bottoms = [0.0] * len(group_labels)
    series_items = list(series.items())
    totals = [sum(s[i] for _, s in series_items) for i in range(len(group_labels))]
    max_total = max(totals) if totals else 1.0
    for label, values in series_items:
        bars = ax.bar(
            x,
            values,
            bottom=bottoms,
            color=colors.get(label, TEAL),
            edgecolor="white",
            label=label,
            width=0.55,
        )
        for bar, v in zip(bars, values):
            if v < max_total * 0.04:
                continue
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_y() + bar.get_height() / 2,
                value_fmt.format(v),
                ha="center",
                va="center",
                fontsize=8,
                color="white",
                fontweight="bold",
            )
        bottoms = [b + v for b, v in zip(bottoms, values)]
    # Totals on top
    for xi, total in zip(x, totals):
        ax.text(
            xi,
            total + max_total * 0.02,
            value_fmt.format(total),
            ha="center",
            va="bottom",
            fontsize=9,
            color=CHARCOAL,
            fontweight="bold",
        )
    ax.set_xticks(x)
    ax.set_xticklabels(group_labels)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left", pad=12)
    ax.set_ylim(0, max_total * 1.20)
    ax.tick_params(axis="y", length=0)
    ax.legend(frameon=False, loc="upper right", fontsize=8)
    plt.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _grouped_vertical_bar(
    group_labels: list[str],
    series: dict[str, list[float]],
    colors: dict[str, str],
    out_path: Path,
    title: str,
    value_fmt: str = "{:,.0f}",
    ylabel: str = "",
    width: float = 7.5,
    height: float = 4.0,
) -> None:
    fig, ax = plt.subplots(figsize=(width, height))
    n_groups = len(group_labels)
    n_series = len(series)
    bar_width = 0.8 / max(n_series, 1)
    x = list(range(n_groups))
    max_v = max((max(v) for v in series.values()), default=1.0)
    for i, (label, values) in enumerate(series.items()):
        offsets = [xi - 0.4 + bar_width * (i + 0.5) for xi in x]
        bars = ax.bar(
            offsets,
            values,
            width=bar_width,
            color=colors.get(label, TEAL),
            label=label,
            edgecolor="white",
        )
        for bar, v in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max_v * 0.02,
                value_fmt.format(v),
                ha="center",
                va="bottom",
                fontsize=8,
                color=CHARCOAL,
            )
    ax.set_xticks(x)
    ax.set_xticklabels(group_labels)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left", pad=12)
    ax.set_ylim(0, max_v * 1.22)
    ax.tick_params(axis="y", length=0)
    ax.legend(frameon=False, loc="upper right", fontsize=8)
    plt.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _make_figures(data: BriefData, charts_dir: Path) -> dict[str, Path]:
    _set_chart_style()
    charts_dir.mkdir(parents=True, exist_ok=True)

    counties = data.counties.copy()
    counties = counties.sort_values("poverty_rate_baseline", ascending=False)

    fig1 = charts_dir / "fig1_poverty_rate_by_county.png"
    state_rate = float(data.state["poverty_rate_baseline"]) * 100
    labels = list(counties["county"]) + ["Hawaiʻi (statewide)"]
    values = list(counties["poverty_rate_baseline"] * 100) + [state_rate]
    _horizontal_bar(
        labels,
        values,
        fig1,
        TEAL,
        f"Figure 1. Supplemental Poverty Measure rates by county, Hawaiʻi (TY{data.tax_year})",
        value_fmt="{:.1f}%",
    )

    fig2 = charts_dir / "fig2_eitc_stacked_by_county.png"
    counties_sorted_eitc = counties.assign(
        _eitc_total=counties["persons_lifted_no_eitc"]
        + counties["persons_lifted_no_hi_eitc"]
    ).sort_values("_eitc_total", ascending=False)
    eitc_labels = list(counties_sorted_eitc["county"]) + ["Statewide"]
    _stacked_vertical_bar(
        eitc_labels,
        {
            "Federal EITC": list(counties_sorted_eitc["persons_lifted_no_eitc"])
            + [float(data.state["persons_lifted_no_eitc"])],
            "Hawaiʻi state EITC": list(
                counties_sorted_eitc["persons_lifted_no_hi_eitc"]
            )
            + [float(data.state["persons_lifted_no_hi_eitc"])],
        },
        {"Federal EITC": TEAL, "Hawaiʻi state EITC": GOLD},
        fig2,
        f"Figure 2. People lifted out of poverty by EITC (federal + state), by county (TY{data.tax_year})",
        value_fmt="{:,.0f}",
        ylabel="People lifted out of poverty",
    )

    fig3 = charts_dir / "fig3_ctc_by_county.png"
    counties_sorted_ctc = counties.sort_values(
        "persons_lifted_no_ctc", ascending=False
    )
    _vertical_bar(
        list(counties_sorted_ctc["county"]),
        list(counties_sorted_ctc["persons_lifted_no_ctc"]),
        fig3,
        SLATE,
        f"Figure 3. People lifted out of poverty by federal Child Tax Credit, by county (TY{data.tax_year})",
        value_fmt="{:,.0f}",
        ylabel="People lifted out of poverty",
    )

    fig4 = charts_dir / "fig4_rxkids_impact.png"
    if data.rxkids_state is not None:
        rx = data.rxkids_state
        rx_lifted = float(rx["persons_lifted_rxkids_hi"])
        hi_eitc_100 = float(data.state.get("persons_lifted_hi_eitc_100pct", 0))
        hi_ctc_650 = float(data.state.get("persons_lifted_hi_ctc_650", 0))
        _vertical_bar(
            ["RxKids Hawaiʻi\n($1,500 prenatal\n+ $500×6 postnatal)",
             "HI EITC raised\nto 100% of federal",
             "New $650/child\nHI state CTC"],
            [rx_lifted, hi_eitc_100, hi_ctc_650],
            fig4,
            GOLD,
            f"Figure 4. Additional people lifted out of poverty by proposed expansions (TY{data.tax_year})",
            value_fmt="{:,.0f}",
            ylabel="Additional people lifted",
            width=7.5,
            height=4.2,
        )
    else:
        fig4 = None

    sd_top = (
        data.senate_districts.sort_values("persons_lifted_no_credits", ascending=False)
        .head(10)
        .copy()
    )
    sd_labels = [f"SD {int(s)}" for s in sd_top["senate_district"]]
    fig5 = charts_dir / "fig5_combined_top_senate.png"
    _horizontal_bar(
        sd_labels,
        list(sd_top["persons_lifted_no_credits"]),
        fig5,
        TEAL,
        f"Figure 5. People kept out of poverty by all three credits, top 10 senate districts (TY{data.tax_year})",
        value_fmt="{:,.0f}",
        xlabel="People lifted out of poverty",
    )

    fig6 = charts_dir / "fig6_expansion_scenarios.png"
    scen_series_6: dict[str, list[float]] = {
        "HI EITC at 100% of federal": [
            float(data.state["persons_lifted_hi_eitc_100pct"])
        ],
        "New $650/child HI state CTC": [
            float(data.state["persons_lifted_hi_ctc_650"])
        ],
    }
    colors_6: dict[str, str] = {
        "HI EITC at 100% of federal": TEAL,
        "New $650/child HI state CTC": GOLD,
    }
    if data.rxkids_state is not None:
        scen_series_6["RxKids Hawaiʻi"] = [
            float(data.rxkids_state["persons_lifted_rxkids_hi"])
        ]
        colors_6["RxKids Hawaiʻi"] = SLATE
    _stacked_vertical_bar(
        [f"Hawaiʻi statewide (TY{data.tax_year})"],
        scen_series_6,
        colors_6,
        fig6,
        f"Figure 6. Additional people lifted by proposed expansions — additive (TY{data.tax_year})",
        value_fmt="{:,.0f}",
        ylabel="Additional people lifted out of poverty",
    )

    # Background section charts
    fig_bg1 = None
    if data.household_types is not None:
        hht = data.household_types.copy()
        label_map = {
            "head_of_household": "Single parent\n(head of household)",
            "single": "Single adult\n(no dependents)",
            "married_filing_jointly": "Married couple",
            "married_filing_separately": "Married filing\nseparately",
        }
        hht["label"] = hht["filing_status"].map(label_map)
        hht = hht[hht["label"].notna()].sort_values("poverty_rate_baseline", ascending=True)
        state_rate = float(data.state["poverty_rate_baseline"]) * 100
        labels_bg = list(hht["label"]) + ["Hawaiʻi\n(statewide)"]
        values_bg = list(hht["poverty_rate_baseline"] * 100) + [state_rate]
        colors_bg = [TEAL] * len(hht) + [GOLD]
        fig_bg1 = charts_dir / "fig_bg1_poverty_by_household_type.png"
        fig_b, ax_b = plt.subplots(figsize=(7.5, 3.8))
        bars = ax_b.barh(labels_bg, values_bg, color=colors_bg, edgecolor="white")
        for bar, v in zip(bars, values_bg):
            ax_b.text(v + 0.3, bar.get_y() + bar.get_height() / 2, f"{v:.1f}%",
                      va="center", fontsize=9, color=CHARCOAL)
        ax_b.set_xlabel("SPM Poverty Rate (%)")
        ax_b.set_xlim(0, max(values_bg) * 1.2)
        ax_b.tick_params(axis="x", length=0)
        ax_b.set_title(
            f"Figure B1. SPM poverty rate by household type, Hawaiʻi (TY{data.tax_year})",
            loc="left", pad=10)
        plt.tight_layout()
        fig_b.savefig(fig_bg1, dpi=200, bbox_inches="tight", facecolor="white")
        plt.close(fig_b)

    fig_bg2 = None
    if data.racial_stats is not None:
        rs = data.racial_stats.sort_values("poverty_rate", ascending=True).copy()
        fig_bg2 = charts_dir / "fig_bg2_poverty_by_race.png"
        fig_r, ax_r = plt.subplots(figsize=(7.5, 3.8))
        bar_colors = [GOLD if "Hawaiian" in r or "Pacific" in r or "NHPI" in r else TEAL for r in rs["race"]]
        bars_r = ax_r.barh(list(rs["race"]), list(rs["poverty_rate"] * 100),
                           color=bar_colors, edgecolor="white")
        for bar, v in zip(bars_r, rs["poverty_rate"] * 100):
            ax_r.text(v + 0.3, bar.get_y() + bar.get_height() / 2, f"{v:.1f}%",
                      va="center", fontsize=9, color=CHARCOAL)
        ax_r.set_xlabel("Official Poverty Rate (%)")
        ax_r.set_xlim(0, max(rs["poverty_rate"] * 100) * 1.25)
        ax_r.tick_params(axis="x", length=0)
        rs_vintage = rs["vintage"].iloc[0] if "vintage" in rs.columns else "ACS PUMS"
        ax_r.set_title(
            f"Figure B2. Official poverty rate by race/ethnicity, Hawaiʻi ({rs_vintage})",
            loc="left", pad=10)
        plt.tight_layout()
        fig_r.savefig(fig_bg2, dpi=200, bbox_inches="tight", facecolor="white")
        plt.close(fig_r)

    out = {
        "fig1": fig1,
        "fig2": fig2,
        "fig3": fig3,
        "fig5": fig5,
        "fig6": fig6,
    }
    if fig4 is not None:
        out["fig4"] = fig4
    if fig_bg1 is not None:
        out["fig_bg1"] = fig_bg1
    if fig_bg2 is not None:
        out["fig_bg2"] = fig_bg2
    return out


def _matplotlib_font(name: str) -> Path:
    import matplotlib

    return Path(matplotlib.get_data_path()) / "fonts" / "ttf" / name


class BriefPDF(FPDF):
    """PDF with the Appleseed-style page chrome."""

    BODY_FONT = "Sans"
    ITALIC_FONT = "SansItalic"

    def __init__(self, tax_year: int):
        super().__init__(format="Letter", unit="in")
        self.tax_year = tax_year
        self.set_auto_page_break(auto=False)
        self.set_margins(0.75, 0.75, 0.75)
        self._suppress_chrome = False
        self.alias_nb_pages()
        # Register a Unicode font family so we can render the ʻokina and other
        # non-Latin-1 characters used throughout the brief.
        self.add_font(self.BODY_FONT, "", str(_matplotlib_font("DejaVuSans.ttf")))
        self.add_font(self.BODY_FONT, "B", str(_matplotlib_font("DejaVuSans-Bold.ttf")))
        self.add_font(self.BODY_FONT, "I", str(_matplotlib_font("DejaVuSans-Oblique.ttf")))
        self.add_font(
            self.BODY_FONT, "BI", str(_matplotlib_font("DejaVuSans-BoldOblique.ttf"))
        )

    def header(self) -> None:  # noqa: D401
        # Per-page header handled manually per page; nothing here.
        return None

    def footer(self) -> None:  # noqa: D401
        if self._suppress_chrome:
            return
        if self.page_no() <= 1:
            return
        self.set_y(-0.55)
        self.set_font(BriefPDF.BODY_FONT, "", 8)
        self.set_text_color(*_hex_to_rgb(SLATE))
        left = "Hawaiʻi Appleseed Center for Law & Economic Justice  |  hiappleseed.org"
        right = f"Page {self.page_no()} of {{nb}}"
        self.cell(0, 0.3, left, align="L")
        self.set_xy(-3.0, -0.55)
        self.cell(2.25, 0.3, right, align="R")
        self.set_text_color(0, 0, 0)


def _add_section_title(pdf: BriefPDF, label_small: str, heading: str) -> None:
    pdf.set_font(BriefPDF.BODY_FONT, "B", 9)
    pdf.set_text_color(*_hex_to_rgb(GOLD))
    pdf.cell(0, 0.22, label_small.upper(), ln=1)
    pdf.set_text_color(*_hex_to_rgb(TEAL))
    page_w = pdf.w - pdf.l_margin - pdf.r_margin
    # Auto-shrink the heading to fit on a single line if needed.
    size = 22
    pdf.set_font(BriefPDF.BODY_FONT, "B", size)
    while size > 12 and pdf.get_string_width(heading) > page_w - 0.05:
        size -= 1
        pdf.set_font(BriefPDF.BODY_FONT, "B", size)
    line_h = (size / 72.0) * 1.2
    pdf.multi_cell(page_w, line_h, heading, align="L")
    # underline
    x1 = pdf.l_margin
    x2 = pdf.w - pdf.r_margin
    y = pdf.get_y() + 0.02
    pdf.set_draw_color(*_hex_to_rgb(GOLD))
    pdf.set_line_width(0.02)
    pdf.line(x1, y, x2, y)
    pdf.ln(0.18)
    pdf.set_text_color(*_hex_to_rgb(CHARCOAL))


def _body_paragraph(pdf: BriefPDF, text: str, width: float | None = None) -> None:
    pdf.set_font(BriefPDF.BODY_FONT, "", 10.5)
    pdf.set_text_color(*_hex_to_rgb(CHARCOAL))
    if width is None:
        width = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.multi_cell(width, 0.19, text, align="L")
    pdf.ln(0.08)


def _callout_box(
    pdf: BriefPDF, headline: str, body: str, *, x: float, y: float, w: float, h: float
) -> None:
    pdf.set_fill_color(*_hex_to_rgb(LIGHT_TEAL))
    pdf.set_draw_color(*_hex_to_rgb(LIGHT_TEAL))
    pdf.rect(x, y, w, h, "F")
    # Headline
    pdf.set_xy(x + 0.2, y + 0.2)
    pdf.set_text_color(*_hex_to_rgb(TEAL))
    # Headline font size shrinks to fit inside the box (single line preferred).
    size = 22
    pdf.set_font(BriefPDF.BODY_FONT, "B", size)
    while size > 11 and pdf.get_string_width(headline) > (w - 0.4):
        size -= 1
        pdf.set_font(BriefPDF.BODY_FONT, "B", size)
    pdf.multi_cell(w - 0.4, (size / 72.0) * 1.15, headline, align="L")
    # Body
    pdf.set_xy(x + 0.2, pdf.get_y() + 0.08)
    pdf.set_text_color(*_hex_to_rgb(CHARCOAL))
    pdf.set_font(BriefPDF.BODY_FONT, "", 9.5)
    pdf.multi_cell(w - 0.4, 0.16, body, align="L")


def _cover_page(pdf: BriefPDF, data: BriefData, date_str: str) -> None:
    pdf.add_page()
    pdf._suppress_chrome = True

    page_w = pdf.w
    page_h = pdf.h
    # Full-bleed teal block on top half (slightly more than half so the title
    # has room and the lower stat block sits comfortably in the white area).
    teal_h = page_h * 0.62
    pdf.set_fill_color(*_hex_to_rgb(TEAL))
    pdf.rect(0, 0, page_w, teal_h, "F")
    # Gold accent strip directly under the teal block.
    pdf.set_fill_color(*_hex_to_rgb(GOLD))
    pdf.rect(0, teal_h, page_w, 0.1, "F")

    # Logo placeholder — wider so "CENTER FOR LAW & ECONOMIC JUSTICE" fits.
    logo_x, logo_y, logo_w, logo_h = 0.6, 0.6, 3.1, 0.85
    pdf.set_fill_color(255, 255, 255)
    pdf.set_draw_color(255, 255, 255)
    pdf.rect(logo_x, logo_y, logo_w, logo_h, "F")
    pdf.set_xy(logo_x + 0.18, logo_y + 0.14)
    pdf.set_text_color(*_hex_to_rgb(TEAL))
    pdf.set_font(BriefPDF.BODY_FONT, "B", 14)
    pdf.cell(logo_w - 0.36, 0.28, "HAWAIʻI APPLESEED")
    pdf.set_xy(logo_x + 0.18, logo_y + 0.45)
    pdf.set_font(BriefPDF.BODY_FONT, "B", 8)
    pdf.cell(logo_w - 0.36, 0.22, "CENTER FOR LAW & ECONOMIC JUSTICE")

    # Date top right.
    pdf.set_xy(page_w - 2.6, 0.85)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(BriefPDF.BODY_FONT, "B", 12)
    pdf.cell(1.85, 0.25, date_str.upper(), align="R")

    # Title — render each line individually so wrap doesn't trigger fpdf2's
    # automatic word-spacing, and use a tight line-height tied to font size.
    title_lines = ["KEEPING HAWAIʻI'S", "FAMILIES OUT OF", "POVERTY"]
    title_size = 38
    pdf.set_font(BriefPDF.BODY_FONT, "B", title_size)
    # Shrink to fit the widest title line within the page width.
    while title_size > 22 and max(
        pdf.get_string_width(line) for line in title_lines
    ) > page_w - 1.5:
        title_size -= 1
        pdf.set_font(BriefPDF.BODY_FONT, "B", title_size)
    line_step = (title_size / 72.0) * 1.12  # inches per line, ~1.12× font size
    title_y = 2.4
    pdf.set_text_color(255, 255, 255)
    for i, line in enumerate(title_lines):
        pdf.set_xy(0.75, title_y + i * line_step)
        pdf.cell(0, line_step, line)

    # Subtitle (white) immediately below the title block.
    subtitle_y = title_y + len(title_lines) * line_step + 0.2
    pdf.set_xy(0.75, subtitle_y)
    pdf.set_font(BriefPDF.BODY_FONT, "", 13)
    pdf.multi_cell(
        page_w - 1.5,
        0.22,
        "How federal and state tax credits lift tens of thousands of local "
        "residents above the poverty line — and what expanding them would do.",
        align="L",
    )

    # Lower (white) section: brief metadata + headline stat.
    pdf.set_xy(0.75, teal_h + 0.4)
    pdf.set_font(BriefPDF.BODY_FONT, "B", 11)
    pdf.set_text_color(*_hex_to_rgb(TEAL))
    pdf.cell(0, 0.25, "A POLICY BRIEF", ln=1)

    pdf.set_x(0.75)
    pdf.set_font(BriefPDF.BODY_FONT, "", 11)
    pdf.set_text_color(*_hex_to_rgb(CHARCOAL))
    pdf.cell(0, 0.22, "Author: Devin Thomas", ln=1)
    pdf.set_x(0.75)
    pdf.cell(0, 0.22, "Hawaiʻi Appleseed Center for Law & Economic Justice", ln=1)
    pdf.set_x(0.75)
    pdf.cell(0, 0.22, date_str, ln=1)

    # Headline statistic anchored near bottom.
    state = data.state
    combined_lifted = int(round(float(state["persons_lifted_no_credits"])))
    pdf.set_xy(0.75, page_h - 2.4)
    pdf.set_font(BriefPDF.BODY_FONT, "B", 34)
    pdf.set_text_color(*_hex_to_rgb(TEAL))
    pdf.cell(0, 0.5, _fmt_int(combined_lifted), ln=1)
    pdf.set_x(0.75)
    pdf.set_font(BriefPDF.BODY_FONT, "", 12)
    pdf.set_text_color(*_hex_to_rgb(CHARCOAL))
    pdf.multi_cell(
        page_w - 1.5,
        0.2,
        "local residents kept out of poverty every year by the federal EITC, "
        f"federal CTC, and Hawaiʻi state EITC combined (TY{data.tax_year}).",
        align="L",
    )

    pdf.set_xy(0.75, page_h - 0.9)
    pdf.set_font(BriefPDF.BODY_FONT, "", 8.5)
    pdf.set_text_color(*_hex_to_rgb(SLATE))
    pdf.multi_cell(page_w - 1.5, 0.16, DATA_SOURCE_CITATION, align="L")

    pdf._suppress_chrome = False


def _executive_summary(pdf: BriefPDF, data: BriefData) -> None:
    pdf.add_page()
    _add_section_title(pdf, "Executive Summary", "AT A GLANCE")

    state = data.state
    combined_lifted = int(round(float(state["persons_lifted_no_credits"])))
    combined_gap = float(state["gap_closed_no_credits_$"])
    hi_ctc_lifted = int(round(float(state["persons_lifted_hi_ctc_650"])))

    # 3 callout boxes
    page_w = pdf.w - pdf.l_margin - pdf.r_margin
    box_w = (page_w - 0.4) / 3
    box_h = 1.9
    y = pdf.get_y()

    _callout_box(
        pdf,
        f"{_fmt_int(combined_lifted)} people",
        "kept out of poverty every year by federal EITC, federal CTC, and "
        "Hawaiʻi state EITC combined.",
        x=pdf.l_margin,
        y=y,
        w=box_w,
        h=box_h,
    )
    _callout_box(
        pdf,
        f"{_fmt_money_m(combined_gap)}",
        "in poverty gap closed annually by these three tax credits.",
        x=pdf.l_margin + box_w + 0.2,
        y=y,
        w=box_w,
        h=box_h,
    )
    _callout_box(
        pdf,
        f"+{_fmt_int(hi_ctc_lifted)}",
        "additional residents would be lifted out of poverty if Hawaiʻi "
        "enacted a $650-per-child state Child Tax Credit.",
        x=pdf.l_margin + (box_w + 0.2) * 2,
        y=y,
        w=box_w,
        h=box_h,
    )

    pdf.set_y(y + box_h + 0.35)
    _body_paragraph(
        pdf,
        "Hawaiʻi has the highest cost of living in the nation. Rent, food, and "
        "child care consume a disproportionate share of working families' "
        "budgets, pushing many local residents into poverty even when they hold "
        "full-time jobs. Refundable tax credits — dollars paid directly to "
        "low- and moderate-income filers — are among the most effective "
        "anti-poverty tools we have, and they pay for themselves several times "
        "over in stronger family budgets, healthier kids, and reduced reliance "
        "on safety-net programs.",
    )
    _body_paragraph(
        pdf,
        "This brief uses the Supplemental Poverty Measure (SPM), the Census "
        "Bureau's more comprehensive measure of poverty, applied to the "
        "American Community Survey 5-Year Public Use Microdata Sample for "
        "Hawaiʻi (2018–2022). It estimates how many local residents are "
        "kept above the poverty line each year by the federal Earned Income Tax "
        "Credit (EITC), the federal Child Tax Credit (CTC), and Hawaiʻi's "
        "state EITC — and what would happen if Hawaiʻi expanded its own "
        "credits.",
    )

    combined_pp = (float(state["poverty_rate_no_credits"]) - float(state["poverty_rate_baseline"])) * 100
    state_rate = _fmt_pct(state["poverty_rate_baseline"])
    persons_in_pov = _fmt_int(state["persons_in_poverty_baseline"])
    no_credits_pop = _fmt_int(int(round(float(state["persons_in_poverty_baseline"]))) + combined_lifted)
    _body_paragraph(
        pdf,
        f"In TY{data.tax_year}, an estimated {persons_in_pov} Hawaiʻi "
        f"residents ({state_rate}) lived below the SPM poverty line. Together, "
        f"the federal EITC, federal CTC, and Hawaiʻi state EITC reduce the SPM "
        f"poverty rate by {combined_pp:.1f} percentage points — keeping "
        f"{_fmt_int(combined_lifted)} residents above the line. Without these "
        f"credits, approximately {no_credits_pop} residents would be in poverty.",
    )

    pdf.set_y(pdf.h - 1.2)
    pdf.set_font(BriefPDF.BODY_FONT, "I", 8.5)
    pdf.set_text_color(*_hex_to_rgb(SLATE))
    pdf.multi_cell(0, 0.16, DATA_SOURCE_CITATION, align="L")


def _figure_page(
    pdf: BriefPDF,
    section_label: str,
    heading: str,
    figure_path: Path,
    narrative_paragraphs: list[str],
) -> None:
    pdf.add_page()
    _add_section_title(pdf, section_label, heading)
    page_w = pdf.w - pdf.l_margin - pdf.r_margin
    # Image
    pdf.image(str(figure_path), x=pdf.l_margin, w=page_w)
    pdf.ln(0.25)
    for para in narrative_paragraphs:
        _body_paragraph(pdf, para)


def _expansion_page(
    pdf: BriefPDF, data: BriefData, figure_path: Path
) -> None:
    pdf.add_page()
    _add_section_title(
        pdf,
        "Looking Ahead",
        "WHAT MORE COULD BE DONE?",
    )
    state = data.state
    page_w = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.image(str(figure_path), x=pdf.l_margin, w=page_w)
    pdf.ln(0.2)

    # Table
    pdf.set_font(BriefPDF.BODY_FONT, "B", 10)
    pdf.set_fill_color(*_hex_to_rgb(TEAL))
    pdf.set_text_color(255, 255, 255)
    col_w = [3.1, 1.5, 1.2, 1.2]
    pdf.cell(col_w[0], 0.3, "Policy scenario", border=0, fill=True)
    pdf.cell(col_w[1], 0.3, "Est. people lifted", border=0, fill=True, align="R")
    pdf.cell(col_w[2], 0.3, "Gap closed", border=0, fill=True, align="R")
    pdf.cell(col_w[3], 0.3, "Annual cost*", border=0, fill=True, align="R")
    pdf.ln()

    rows = [
        (
            "Raise HI state EITC to 100% of federal",
            _fmt_int(state["persons_lifted_hi_eitc_100pct"]),
            _fmt_money_m(state["gap_closed_hi_eitc_100pct_$"]),
            "~$30M",
        ),
        (
            "Enact new $650/child HI state CTC",
            _fmt_int(state["persons_lifted_hi_ctc_650"]),
            _fmt_money_m(state["gap_closed_hi_ctc_650_$"]),
            "~$83M",
        ),
    ]
    _rx = data.rxkids_state
    if _rx is not None:
        rows.append((
            "RxKids Hawaiʻi (proposed)",
            _fmt_int(_rx["persons_lifted_rxkids_hi"]),
            _fmt_money_m(_rx["gap_closed_rxkids_hi_$"]),
            "~$60M",
        ))
        _total_lifted = (
            float(state["persons_lifted_hi_eitc_100pct"])
            + float(state["persons_lifted_hi_ctc_650"])
            + float(_rx["persons_lifted_rxkids_hi"])
        )
        _total_gap = (
            float(state["gap_closed_hi_eitc_100pct_$"])
            + float(state["gap_closed_hi_ctc_650_$"])
            + float(_rx["gap_closed_rxkids_hi_$"])
        )
        rows.append((
            "All three combined",
            "~" + _fmt_int(_total_lifted),
            _fmt_money_m(_total_gap),
            "~$173M",
        ))
    else:
        rows.append((
            "Both combined (non-additive)",
            "~"
            + _fmt_int(
                float(state["persons_lifted_hi_eitc_100pct"])
                + float(state["persons_lifted_hi_ctc_650"])
            ),
            _fmt_money_m(
                float(state["gap_closed_hi_eitc_100pct_$"])
                + float(state["gap_closed_hi_ctc_650_$"])
            ),
            "~$113M",
        ))
    pdf.set_text_color(*_hex_to_rgb(CHARCOAL))
    pdf.set_font(BriefPDF.BODY_FONT, "", 10)
    for i, row in enumerate(rows):
        fill = i % 2 == 0
        if fill:
            pdf.set_fill_color(*_hex_to_rgb(LIGHT_GRAY))
        pdf.cell(col_w[0], 0.3, row[0], border=0, fill=fill)
        pdf.cell(col_w[1], 0.3, row[1], border=0, fill=fill, align="R")
        pdf.cell(col_w[2], 0.3, row[2], border=0, fill=fill, align="R")
        pdf.cell(col_w[3], 0.3, row[3], border=0, fill=fill, align="R")
        pdf.ln()

    pdf.ln(0.1)
    pdf.set_font(BriefPDF.BODY_FONT, "I", 8.5)
    pdf.set_text_color(*_hex_to_rgb(SLATE))
    pdf.multi_cell(
        0,
        0.16,
        "* Annual cost figures are legislative estimates from prior fiscal notes, "
        "not produced by this model. Persons-lifted and gap-closed figures are "
        "model output and may differ from other estimates because they reflect "
        "the SPM definition of poverty and IRS-calibrated take-up.",
        align="L",
    )
    pdf.ln(0.1)
    pdf.set_font(BriefPDF.BODY_FONT, "", 10.5)
    pdf.set_text_color(*_hex_to_rgb(CHARCOAL))
    if data.rxkids_state is not None:
        _body_paragraph(
            pdf,
            "Any of these three policies would meaningfully reduce poverty in "
            "Hawaiʻi. Enacted together, they represent a comprehensive strategy: "
            "expanding EITC reaches low-income workers; a new state CTC supports "
            "parents of young children; and RxKids delivers direct cash to "
            "expecting mothers and infants in the critical first months of life. "
            "Because all three channels target the families with the lowest "
            "incomes, every dollar is likely to flow back into the local economy "
            "through rent, food, and child care.",
        )
    else:
        _body_paragraph(
            pdf,
            "Either expansion would meaningfully reduce poverty in Hawaiʻi; "
            "together they would lift several thousand additional residents above "
            "the SPM threshold and close hundreds of millions of dollars in "
            "remaining poverty gap. Because both credits are refundable, they reach "
            "the families with the lowest incomes — those most likely to spend "
            "every dollar locally on rent, food, and child care.",
        )


def _methodology_page(pdf: BriefPDF, data: BriefData) -> None:
    pdf.add_page()
    _add_section_title(pdf, "Methodology", "HOW WE DID THIS")
    _body_paragraph(
        pdf,
        "These estimates are produced by the Census-Forecaster tax simulation "
        "model maintained by Hawaiʻi Appleseed. The model uses the U.S. "
        "Census Bureau's 5-Year American Community Survey Public Use "
        "Microdata Sample (ACS PUMS) for Hawaiʻi, 2018–2022, projected "
        "forward to the tax year of interest using a recency-weighted, "
        "cadence-aware damped-trend ensemble.",
    )
    _body_paragraph(
        pdf,
        "Poverty is measured using the Supplemental Poverty Measure (SPM), the "
        "Census Bureau's comprehensive poverty measure. Unlike the official "
        "poverty measure, the SPM accounts for federal and state tax payments, "
        "refundable tax credits, non-cash benefits such as SNAP and housing "
        "subsidies, medical out-of-pocket costs, and Hawaiʻi's "
        "above-average cost of living through a geographic adjustment to the "
        "poverty threshold.",
    )
    _body_paragraph(
        pdf,
        "Following Census P60-280, poverty is measured at the SPM-unit level "
        "(the resource-sharing group within a household: householder + "
        "relatives + unmarried partner + foster children + any unrelated "
        "children under 15), not at the tax-unit level. Tax credits and "
        "benefits are computed on tax returns and then summed to the SPM "
        "unit for the poverty comparison.",
    )
    _body_paragraph(
        pdf,
        "Counterfactual scenarios are static: each scenario re-runs the SPM "
        "calculation with the relevant credit removed (or expanded), holding "
        "labor supply and program take-up fixed. Take-up of each credit is "
        "calibrated to IRS SOI Hawaiʻi totals so that modeled receipt "
        "matches administrative records, not statutory eligibility.",
    )
    _body_paragraph(
        pdf,
        "District-level estimates (Senate and House) reflect within-PUMA "
        "imputation and carry larger uncertainty than statewide and county "
        "figures — typically ±20 percent at the district level. "
        "Statewide totals are within roughly 5 percent of administrative "
        "benchmarks where available.",
    )
    _body_paragraph(
        pdf,
        "The methodology, parameters, and full results tables are documented "
        "in this project's public methodology files (METHODOLOGY.md, "
        "REVIEW_FINDINGS.md). The model and its source code are maintained as a "
        "Python package; a v2 release was published in 2025.",
    )


def _about_page(pdf: BriefPDF, date_str: str) -> None:
    pdf.add_page()
    _add_section_title(pdf, "About", "ABOUT HAWAIʻI APPLESEED")
    _body_paragraph(
        pdf,
        "Hawaiʻi Appleseed Center for Law & Economic Justice is committed "
        "to a more socially and economically just Hawaiʻi, where everyone "
        "has genuine opportunities to achieve economic security and fulfill "
        "their potential. We change systems to address inequity and foster "
        "greater opportunity by conducting data analysis and research to "
        "address income inequality, educating policymakers and the public, "
        "engaging in collaborative problem solving and coalition building, and "
        "advocating for policy and systems change.",
    )
    _body_paragraph(
        pdf,
        "The work of Hawaiʻi Appleseed is about people. The issues we work "
        "on — housing, food, wages, mobility, the state budget and "
        "taxation, and racial and indigenous equity — are important because "
        "they ensure people have access to shelter, sustenance, and the means "
        "to survive and thrive individually and collectively.",
    )
    pdf.ln(0.25)
    _add_section_title(pdf, "Author", "ACKNOWLEDGMENTS")
    _body_paragraph(
        pdf,
        f"Author: Devin Thomas, Policy Analyst, Hawaiʻi Appleseed.",
    )
    _body_paragraph(
        pdf,
        "This brief uses the Census-Forecaster open-source tax simulation "
        "model. The author thanks the Hawaiʻi state Department of Taxation "
        "and the U.S. Census Bureau for the public data that make this analysis "
        "possible.",
    )
    pdf.ln(0.4)
    pdf.set_font(BriefPDF.BODY_FONT, "", 9.5)
    pdf.set_text_color(*_hex_to_rgb(SLATE))
    pdf.multi_cell(
        0,
        0.18,
        f"Published {date_str}. "
        f"Hawaiʻi Appleseed Center for Law & Economic Justice, "
        f"733 Bishop Street, Suite 1180, Honolulu, HI 96813. "
        f"hiappleseed.org",
        align="L",
    )
    pdf.ln(0.1)
    pdf.set_font(BriefPDF.BODY_FONT, "I", 8.5)
    pdf.multi_cell(0, 0.16, DATA_SOURCE_CITATION, align="L")


def _background_page(
    pdf: BriefPDF,
    data: BriefData,
    charts: dict[str, Path],
) -> None:
    pdf.add_page()
    _add_section_title(pdf, "Background", "WHO BEARS THE BURDEN OF POVERTY IN HAWAIʻI?")

    state = data.state
    hht = data.household_types
    rs = data.racial_stats

    hoh_rate = None
    mfj_rate = None
    if hht is not None:
        hoh_row = hht[hht["filing_status"] == "head_of_household"]
        mfj_row = hht[hht["filing_status"] == "married_filing_jointly"]
        if len(hoh_row) > 0:
            hoh_rate = float(hoh_row.iloc[0]["poverty_rate_baseline"])
        if len(mfj_row) > 0:
            mfj_rate = float(mfj_row.iloc[0]["poverty_rate_baseline"])

    if hoh_rate is not None and mfj_rate is not None:
        ratio = hoh_rate / mfj_rate
        _body_paragraph(
            pdf,
            f"Poverty in Hawaiʻi is not spread evenly. Single-parent households "
            f"face an SPM poverty rate of {hoh_rate*100:.1f}% — more than "
            f"{ratio:.0f} times the {mfj_rate*100:.1f}% rate among married-couple "
            f"households. These are the families most exposed when rent increases, "
            f"child-care costs rise, or a job is lost — and they are the primary "
            f"beneficiaries of the tax credits analyzed in this brief.",
        )

    if "fig_bg1" in charts:
        fig_img_w = pdf.w - pdf.l_margin - pdf.r_margin
        fig_img_h = fig_img_w * (3.8 / 7.5)
        y_fig = pdf.get_y() + 0.1
        pdf.image(str(charts["fig_bg1"]), x=pdf.l_margin, y=y_fig,
                  w=fig_img_w, h=fig_img_h)
        pdf.set_y(y_fig + fig_img_h + 0.15)

    if rs is not None:
        nhpi = rs[rs["race"].str.contains("Pacific Islander|NHPI", na=False)]
        nh_combo = rs[rs["race"].str.contains("Hawaiian.*alone or", na=False)]
        wht = rs[rs["race"].str.contains("White", na=False)]
        rs_vintage = rs["vintage"].iloc[0] if "vintage" in rs.columns else "ACS PUMS"
        if len(nhpi) > 0 and len(wht) > 0:
            nhpi_rate = float(nhpi.iloc[0]["poverty_rate"])
            wht_rate = float(wht.iloc[0]["poverty_rate"])
            nhpi_inc = float(nhpi.iloc[0]["median_income"])
            wht_inc = float(wht.iloc[0]["median_income"])
            nh_txt = ""
            if len(nh_combo) > 0:
                nh_rate = float(nh_combo.iloc[0]["poverty_rate"])
                nh_txt = (
                    f" Native Hawaiians (alone or in combination with another race) "
                    f"experience a {nh_rate*100:.1f}% official poverty rate, "
                    f"compared to {wht_rate*100:.1f}% for White alone residents."
                )
            _body_paragraph(
                pdf,
                f"Racial disparities compound this picture. Pacific Islander households "
                f"(NHPI alone) have an official poverty rate of {nhpi_rate*100:.1f}% — "
                f"nearly twice the {wht_rate*100:.1f}% rate for White alone residents. "
                f"The median personal income for NHPI-alone earners is "
                f"${nhpi_inc:,.0f}/year, compared to ${wht_inc:,.0f} for White alone "
                f"earners — a gap of ${wht_inc - nhpi_inc:,.0f}.{nh_txt} "
                f"(Source: {rs_vintage} PUMS, official poverty measure.)",
            )

    if "fig_bg2" in charts:
        fig_img_w = pdf.w - pdf.l_margin - pdf.r_margin
        fig_img_h = fig_img_w * (3.8 / 7.5)
        y_fig2 = pdf.get_y() + 0.1
        if y_fig2 + fig_img_h < pdf.h - 1.5:
            pdf.image(str(charts["fig_bg2"]), x=pdf.l_margin, y=y_fig2,
                      w=fig_img_w, h=fig_img_h)
            pdf.set_y(y_fig2 + fig_img_h + 0.1)

    pdf.set_y(pdf.h - 1.2)
    pdf.set_font(BriefPDF.BODY_FONT, "I", 8.5)
    pdf.set_text_color(*_hex_to_rgb(SLATE))
    pdf.multi_cell(0, 0.16, DATA_SOURCE_CITATION, align="L")


def _build_pdf(
    data: BriefData,
    charts: dict[str, Path],
    out_pdf: Path,
    date_str: str,
) -> None:
    pdf = BriefPDF(tax_year=data.tax_year)
    _cover_page(pdf, data, date_str)
    _executive_summary(pdf, data)
    _background_page(pdf, data, charts)

    state = data.state
    state_rate = _fmt_pct(state["poverty_rate_baseline"])
    state_pov = _fmt_int(state["persons_in_poverty_baseline"])

    _figure_page(
        pdf,
        "Baseline",
        "HOW MANY HAWAIʻI RESIDENTS ARE IN POVERTY?",
        charts["fig1"],
        [
            f"Under the Supplemental Poverty Measure, an estimated {state_pov} "
            f"Hawaiʻi residents — {state_rate} of the state population — "
            f"lived in poverty in TY{data.tax_year}. The SPM differs from the "
            "official poverty measure by accounting for taxes, refundable tax "
            "credits, non-cash benefits, medical out-of-pocket costs, and "
            "Hawaiʻi's above-average cost of living.",
            "Neighbor-island counties show higher SPM rates than Oʻahu, "
            "reflecting lower wages combined with rents and food prices that "
            "remain near urban-Honolulu levels. These geographic differences "
            "are why a flat federal threshold understates poverty in Hawaiʻi.",
        ],
    )
    fed_eitc = int(round(float(state["persons_lifted_no_eitc"])))
    hi_eitc = int(round(float(state["persons_lifted_no_hi_eitc"])))
    eitc_total = fed_eitc + hi_eitc
    fed_eitc_pp = (float(state["poverty_rate_no_eitc"]) - float(state["poverty_rate_baseline"])) * 100
    hi_eitc_pp = (float(state["poverty_rate_no_hi_eitc"]) - float(state["poverty_rate_baseline"])) * 100
    _figure_page(
        pdf,
        "EITC (Federal + State)",
        "HAWAIʻI'S LARGEST ANTI-POVERTY CREDIT",
        charts["fig2"],
        [
            f"The Earned Income Tax Credit is Hawaiʻi's single most "
            f"powerful anti-poverty tool. The federal EITC alone reduces "
            f"the SPM poverty rate by {fed_eitc_pp:.1f} percentage points, "
            f"lifting {_fmt_int(fed_eitc)} residents above the poverty line "
            f"each year. Hawaiʻi's state EITC — made fully refundable and "
            f"raised to 40% of the federal credit by Act 209 (2023) — reduces "
            f"the rate by an additional {hi_eitc_pp:.1f} percentage points, "
            f"lifting {_fmt_int(hi_eitc)} more residents. Combined, the two "
            f"EITCs keep roughly {_fmt_int(eitc_total)} local residents out "
            f"of poverty annually (sum is approximate; the credits interact).",
            "Both credits are fully refundable, targeted at low- and "
            "moderate-income workers, and scale with earnings up to a "
            "plateau — rewarding work while still reaching the lowest-income "
            "families. Because EITC dollars arrive as a tax refund, they "
            "typically flow back into the local economy through rent, "
            "groceries, and child care.",
            "Hawaiʻi's 40% state match is now among the most generous in "
            "the country. Raising it further — or simplifying eligibility "
            "for the lowest-income filers — would deliver meaningful "
            "additional poverty reduction at modest fiscal cost (see "
            "expansion scenarios below).",
        ],
    )
    ctc_pp = (float(state["poverty_rate_no_ctc"]) - float(state["poverty_rate_baseline"])) * 100
    ctc_lifted_str = _fmt_int(state["persons_lifted_no_ctc"])
    _figure_page(
        pdf,
        "Federal CTC",
        "THE FEDERAL CHILD TAX CREDIT",
        charts["fig3"],
        [
            f"The federal Child Tax Credit reduces the SPM poverty rate by "
            f"{ctc_pp:.1f} percentage points, lifting {ctc_lifted_str} "
            f"Hawaiʻi residents above the poverty line. After the "
            "American Rescue Plan's 2021 expansion expired, the credit reverted "
            "to a partially refundable structure that leaves many of the lowest-income "
            "families with less than the full benefit.",
            "Even in its current form, the CTC remains one of the most "
            "powerful tools available for reducing child poverty in Hawaiʻi — "
            "and is among the credits whose expansion would have the largest "
            "incremental impact on families with young children.",
        ],
    )
    if "fig4" in charts and data.rxkids_state is not None:
        rx = data.rxkids_state
        rx_lifted = int(round(float(rx["persons_lifted_rxkids_hi"])))
        rx_gap = float(rx["gap_closed_rxkids_hi_$"])
        rx_pp = (float(rx["poverty_rate_baseline"]) - float(rx["poverty_rate_rxkids_hi"])) * 100
        _figure_page(
            pdf,
            "RxKids Hawaiʻi (Proposed)",
            "A CASH PRESCRIPTION FOR HAWAIʻI'S YOUNGEST",
            charts["fig4"],
            [
                f"RxKids is a prenatal-and-infant cash-transfer program "
                f"first launched in Flint, Michigan and now operating in "
                f"35+ Michigan communities. A Hawaiʻi-equivalent program — "
                f"modeled here as an unconditional benefit available to "
                f"all expecting mothers regardless of income — would provide "
                f"a one-time $1,500 payment during pregnancy and six monthly "
                f"payments of $500 beginning at birth ($3,000 postnatal "
                f"total per child).",
                f"Under this design, an estimated {_fmt_int(rx_lifted)} "
                f"Hawaiʻi residents would be lifted above the SPM poverty "
                f"line, reducing the SPM poverty rate by {rx_pp:.1f} percentage "
                f"points and closing "
                f"{_fmt_money_m(rx_gap)} in poverty gap. "
                f"The program would cost roughly $60M per year statewide — "
                f"reaching all ~15,500 annual births with a combined "
                f"$4,500 per pregnancy benefit.",
                "The SPM poverty-line crossing count is a conservative "
                "floor on the program's value. Research on the Flint "
                "program documents significant downstream effects on "
                "birth weight, maternal mental health, and infant "
                "developmental outcomes that are not captured in the "
                "poverty-rate metric. For comparison, Figure 4 also "
                "shows the projected lift from the two other proposed "
                "Hawaiʻi credit expansions modeled in this brief.",
            ],
        )
    _figure_page(
        pdf,
        "Combined Impact",
        "BY STATE SENATE DISTRICT",
        charts["fig5"],
        [
            "Looking across the state's 25 Senate districts, the top ten "
            "districts — generally those covering working-class "
            "neighborhoods on Oʻahu and the neighbor islands — "
            "account for more than half of all residents lifted out of poverty "
            "by the three credits combined.",
            "These district-level estimates are useful for legislators "
            "evaluating who in their communities benefits today — and how "
            "many more would benefit if Hawaiʻi expanded its credits.",
        ],
    )
    _expansion_page(pdf, data, charts["fig6"])
    _methodology_page(pdf, data)
    _about_page(pdf, date_str)

    pdf.output(str(out_pdf))


def _rxkids_html_section(data: BriefData, images: dict[str, str]) -> str:
    if "fig4" not in images or data.rxkids_state is None:
        return ""
    rx = data.rxkids_state
    rx_pp = (float(rx["poverty_rate_baseline"]) - float(rx["poverty_rate_rxkids_hi"])) * 100
    return f"""
<section>
  <div class="smalllabel">RxKids Hawaiʻi (Proposed)</div>
  <h2>A Cash Prescription for Hawaiʻi's Youngest</h2>
  <div class="figure">
    <img src="data:image/png;base64,{images['fig4']}" />
  </div>
  <p>
    A Hawaiʻi-equivalent of the Flint RxKids program — $4,500 prenatal
    plus $1,500/year per child under 5, targeted at Medicaid-eligible
    families — would reach a cohort of roughly
    {_fmt_int(rx['weighted_persons'])} local residents, lift an
    additional {_fmt_int(rx['persons_lifted_rxkids_hi'])} infants and
    young children above the SPM poverty line, and reduce the SPM
    poverty rate by {rx_pp:.1f} percentage points.
  </p>
</section>
"""


def _build_html_fallback(
    data: BriefData,
    charts: dict[str, Path],
    out_html: Path,
    date_str: str,
) -> None:
    """Self-contained HTML version (base64 images, inline CSS) as a fallback."""
    import base64

    def _img_b64(path: Path) -> str:
        return base64.b64encode(path.read_bytes()).decode("ascii")

    state = data.state
    combined_lifted = _fmt_int(state["persons_lifted_no_credits"])
    combined_gap = _fmt_money_m(state["gap_closed_no_credits_$"])
    hi_ctc_lifted = _fmt_int(state["persons_lifted_hi_ctc_650"])
    _html_fed_eitc_pp = (float(state["poverty_rate_no_eitc"]) - float(state["poverty_rate_baseline"])) * 100
    _html_hi_eitc_pp = (float(state["poverty_rate_no_hi_eitc"]) - float(state["poverty_rate_baseline"])) * 100
    _html_ctc_pp = (float(state["poverty_rate_no_ctc"]) - float(state["poverty_rate_baseline"])) * 100
    _html_combined_pp = (float(state["poverty_rate_no_credits"]) - float(state["poverty_rate_baseline"])) * 100

    # Background section text (images added after images dict is built below)
    hht = data.household_types
    rs = data.racial_stats
    _bg_hh_text = ""
    if hht is not None:
        hoh_rows = hht[hht["filing_status"] == "head_of_household"]
        mfj_rows = hht[hht["filing_status"] == "married_filing_jointly"]
        if len(hoh_rows) > 0 and len(mfj_rows) > 0:
            hoh_r = float(hoh_rows.iloc[0]["poverty_rate_baseline"])
            mfj_r = float(mfj_rows.iloc[0]["poverty_rate_baseline"])
            _bg_hh_text = (
                f"<p>Single-parent households face an SPM poverty rate of "
                f"{hoh_r*100:.1f}% — more than {hoh_r/mfj_r:.0f} times the "
                f"{mfj_r*100:.1f}% rate among married-couple households.</p>"
            )
    _bg_race_text = ""
    if rs is not None:
        nhpi_rows = rs[rs["race"].str.contains("Pacific Islander|NHPI", na=False)]
        wht_rows = rs[rs["race"].str.contains("White", na=False)]
        nh_combo_rows = rs[rs["race"].str.contains("Hawaiian.*alone or", na=False)]
        rs_vintage_html = rs["vintage"].iloc[0] if "vintage" in rs.columns else "ACS PUMS"
        if len(nhpi_rows) > 0 and len(wht_rows) > 0:
            nhpi_r = float(nhpi_rows.iloc[0]["poverty_rate"])
            wht_r = float(wht_rows.iloc[0]["poverty_rate"])
            nhpi_i = float(nhpi_rows.iloc[0]["median_income"])
            wht_i = float(wht_rows.iloc[0]["median_income"])
            nh_sentence = ""
            if len(nh_combo_rows) > 0:
                nh_r = float(nh_combo_rows.iloc[0]["poverty_rate"])
                nh_sentence = (
                    f" Native Hawaiians (alone or in combination) face a "
                    f"{nh_r*100:.1f}% official poverty rate vs {wht_r*100:.1f}% "
                    f"for White alone residents."
                )
            _bg_race_text = (
                f"<p>Pacific Islander households (NHPI alone) have an official poverty "
                f"rate of {nhpi_r*100:.1f}% — nearly twice the {wht_r*100:.1f}% rate "
                f"for White alone residents. Median earnings for NHPI-alone workers "
                f"are ${nhpi_i:,.0f}/year vs ${wht_i:,.0f} for White alone — a gap of "
                f"${wht_i - nhpi_i:,.0f}.{nh_sentence} "
                f"({rs_vintage_html} PUMS, official poverty measure.)</p>"
            )

    _hrx = data.rxkids_state
    if _hrx is not None:
        _html_rx_row = (
            f"<tr><td>RxKids Hawaiʻi (proposed)</td>"
            f"<td style=\"text-align:right;\">{_fmt_int(_hrx['persons_lifted_rxkids_hi'])}</td>"
            f"<td style=\"text-align:right;\">{_fmt_money_m(_hrx['gap_closed_rxkids_hi_$'])}</td>"
            f"<td style=\"text-align:right;\">~$60M</td></tr>"
        )
        _html_c_lifted = (
            float(state["persons_lifted_hi_eitc_100pct"])
            + float(state["persons_lifted_hi_ctc_650"])
            + float(_hrx["persons_lifted_rxkids_hi"])
        )
        _html_c_gap = (
            float(state["gap_closed_hi_eitc_100pct_$"])
            + float(state["gap_closed_hi_ctc_650_$"])
            + float(_hrx["gap_closed_rxkids_hi_$"])
        )
        _html_combined_row = (
            f"<tr><td>All three combined</td>"
            f"<td style=\"text-align:right;\">~{_fmt_int(_html_c_lifted)}</td>"
            f"<td style=\"text-align:right;\">{_fmt_money_m(_html_c_gap)}</td>"
            f"<td style=\"text-align:right;\">~$173M</td></tr>"
        )
    else:
        _html_rx_row = ""
        _html_combined_row = (
            f"<tr><td>Both combined (non-additive)</td>"
            f"<td style=\"text-align:right;\">~{_fmt_int(float(state['persons_lifted_hi_eitc_100pct']) + float(state['persons_lifted_hi_ctc_650']))}</td>"
            f"<td style=\"text-align:right;\">{_fmt_money_m(float(state['gap_closed_hi_eitc_100pct_$']) + float(state['gap_closed_hi_ctc_650_$']))}</td>"
            f"<td style=\"text-align:right;\">~$113M</td></tr>"
        )

    css = f"""
    @page {{ size: Letter; margin: 0.75in; }}
    body {{ font-family: 'Manrope','Poppins','Inter','Helvetica',sans-serif;
            color: {CHARCOAL}; margin: 0; }}
    h1, h2 {{ color: {TEAL}; }}
    h1 {{ font-size: 28pt; margin: 0 0 0.4em 0; }}
    h2 {{ font-size: 16pt; border-bottom: 2px solid {GOLD}; padding-bottom: 4pt; }}
    .smalllabel {{ color: {GOLD}; text-transform: uppercase; font-weight: bold;
                  letter-spacing: 0.08em; font-size: 9pt; margin-top: 1em; }}
    .cover {{ background: {TEAL}; color: white; padding: 1in 0.75in; min-height: 6in; }}
    .cover h1 {{ color: white; font-size: 42pt; line-height: 1.0; }}
    .callout {{ background: {LIGHT_TEAL}; padding: 0.5em; margin: 0.4em 0;
                border-left: 6px solid {TEAL}; }}
    .callout .stat {{ font-size: 22pt; color: {TEAL}; font-weight: bold;
                      display: block; }}
    .scenario-table {{ width: 100%; border-collapse: collapse; margin-top: 0.4em; }}
    .scenario-table th {{ background: {TEAL}; color: white; padding: 0.3em;
                          text-align: left; }}
    .scenario-table td {{ padding: 0.3em; border-bottom: 1px solid #ddd; }}
    .scenario-table tr:nth-child(even) td {{ background: {LIGHT_GRAY}; }}
    .figure {{ margin: 1em 0; }}
    .figure img {{ max-width: 100%; }}
    .footer {{ color: {SLATE}; font-size: 9pt; margin-top: 2em;
               border-top: 1px solid #ccc; padding-top: 0.3em; }}
    """

    images = {k: _img_b64(v) for k, v in charts.items()}

    _bg_hh_img = (
        f'<div class="figure"><img src="data:image/png;base64,{images["fig_bg1"]}" /></div>'
        if "fig_bg1" in images else ""
    )
    _bg_race_img = (
        f'<div class="figure"><img src="data:image/png;base64,{images["fig_bg2"]}" /></div>'
        if "fig_bg2" in images else ""
    )
    _html_background_section = f"""
<section>
  <div class="smalllabel">Background</div>
  <h2>Who Bears the Burden of Poverty in Hawaiʻi?</h2>
  {_bg_hh_text}
  {_bg_hh_img}
  {_bg_race_text}
  {_bg_race_img}
</section>
"""

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Keeping Hawaiʻi's Families Out of Poverty</title>
<style>{css}</style>
</head>
<body>

<section class="cover">
  <div class="smalllabel" style="color:{GOLD};">{date_str}</div>
  <h1>Keeping Hawaiʻi's<br/>Families Out of Poverty</h1>
  <p style="font-size: 13pt; max-width: 6.5in;">
    How federal and state tax credits lift tens of thousands of local
    residents above the poverty line — and what expanding them would do.
  </p>
  <p style="margin-top: 2em;">
    <strong>{combined_lifted} residents</strong> kept out of poverty annually
    by the federal EITC, federal CTC, and Hawaiʻi state EITC combined
    (TY{data.tax_year}).
  </p>
  <p style="font-size: 10pt; margin-top: 2em;">
    Author: Devin Thomas &nbsp;·&nbsp; Hawaiʻi Appleseed Center for
    Law & Economic Justice
  </p>
</section>

<section>
  <div class="smalllabel">Executive Summary</div>
  <h2>At a Glance</h2>
  <div style="display:flex; gap:0.4em;">
    <div class="callout" style="flex:1;">
      <span class="stat">{combined_lifted} people</span>
      kept out of poverty every year by federal EITC, federal CTC, and
      Hawaiʻi state EITC combined.
    </div>
    <div class="callout" style="flex:1;">
      <span class="stat">{combined_gap}</span>
      in poverty gap closed annually by these three credits.
    </div>
    <div class="callout" style="flex:1;">
      <span class="stat">+{hi_ctc_lifted}</span>
      additional residents lifted out of poverty if Hawaiʻi enacted a
      $650-per-child state Child Tax Credit.
    </div>
  </div>
  <p>
    Hawaiʻi has the highest cost of living in the nation. Refundable tax
    credits remain among the most effective anti-poverty tools we have.
    This brief uses the Census Bureau's Supplemental Poverty Measure (SPM)
    applied to the 5-Year ACS PUMS to estimate how many local residents are
    kept above the poverty line each year by the federal EITC, the federal
    CTC, and Hawaiʻi's state EITC — and what would happen if Hawaiʻi
    expanded its own credits. Together, the three credits reduce the SPM
    poverty rate by {_html_combined_pp:.1f} percentage points.
  </p>
</section>

{_html_background_section}

<section>
  <div class="smalllabel">Baseline</div>
  <h2>How Many Hawaiʻi Residents Are in Poverty?</h2>
  <div class="figure">
    <img src="data:image/png;base64,{images['fig1']}" />
  </div>
  <p>
    Under the SPM, an estimated {_fmt_int(state['persons_in_poverty_baseline'])}
    Hawaiʻi residents ({_fmt_pct(state['poverty_rate_baseline'])}) lived
    in poverty in TY{data.tax_year}.
  </p>
</section>

<section>
  <div class="smalllabel">EITC (Federal + State)</div>
  <h2>Hawaiʻi's Largest Anti-Poverty Credit</h2>
  <div class="figure">
    <img src="data:image/png;base64,{images['fig2']}" />
  </div>
  <p>
    The federal EITC reduces the SPM poverty rate by {_html_fed_eitc_pp:.1f} percentage
    points, lifting {_fmt_int(state['persons_lifted_no_eitc'])} residents above
    the poverty line. Hawaiʻi's state EITC reduces the rate by an additional
    {_html_hi_eitc_pp:.1f} percentage points, lifting
    {_fmt_int(state['persons_lifted_no_hi_eitc'])} more. Combined, the two EITCs
    keep roughly
    {_fmt_int(float(state['persons_lifted_no_eitc']) + float(state['persons_lifted_no_hi_eitc']))}
    local residents out of poverty each year. Hawaiʻi's 40% state match
    (Act 209, 2023) is among the most generous in the country.
  </p>
</section>

<section>
  <div class="smalllabel">Federal CTC</div>
  <h2>The Federal Child Tax Credit</h2>
  <div class="figure">
    <img src="data:image/png;base64,{images['fig3']}" />
  </div>
  <p>
    The federal Child Tax Credit reduces the SPM poverty rate by {_html_ctc_pp:.1f} percentage
    points, lifting {_fmt_int(state['persons_lifted_no_ctc'])} Hawaiʻi residents
    above the poverty line.
  </p>
</section>
{_rxkids_html_section(data, images)}

<section>
  <div class="smalllabel">Combined Impact</div>
  <h2>By State Senate District</h2>
  <div class="figure">
    <img src="data:image/png;base64,{images['fig5']}" />
  </div>
</section>

<section>
  <div class="smalllabel">Looking Ahead</div>
  <h2>What More Could Be Done?</h2>
  <div class="figure">
    <img src="data:image/png;base64,{images['fig6']}" />
  </div>
  <table class="scenario-table">
    <thead>
      <tr>
        <th>Policy scenario</th>
        <th style="text-align:right;">Est. people lifted</th>
        <th style="text-align:right;">Gap closed</th>
        <th style="text-align:right;">Annual cost*</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>Raise HI state EITC to 100% of federal</td>
        <td style="text-align:right;">{_fmt_int(state['persons_lifted_hi_eitc_100pct'])}</td>
        <td style="text-align:right;">{_fmt_money_m(state['gap_closed_hi_eitc_100pct_$'])}</td>
        <td style="text-align:right;">~$30M</td></tr>
      <tr><td>Enact new $650/child HI state CTC</td>
        <td style="text-align:right;">{_fmt_int(state['persons_lifted_hi_ctc_650'])}</td>
        <td style="text-align:right;">{_fmt_money_m(state['gap_closed_hi_ctc_650_$'])}</td>
        <td style="text-align:right;">~$83M</td></tr>
      {_html_rx_row}
      {_html_combined_row}
    </tbody>
  </table>
  <p style="font-size:9pt; color:{SLATE}; font-style:italic;">
    * Annual cost figures are legislative estimates, not produced by this model.
  </p>
</section>

<section>
  <div class="smalllabel">Methodology</div>
  <h2>How We Did This</h2>
  <p>
    Estimates are produced by the Census-Forecaster tax simulation model
    using the U.S. Census Bureau's 5-Year ACS PUMS for Hawaiʻi (2018–2022),
    projected forward using a cadence-aware damped-trend ensemble. Poverty is
    measured using the Supplemental Poverty Measure with Hawaiʻi-specific
    geographic adjustment. The unit of analysis is the SPM unit per Census
    P60-280 (the resource-sharing group within a household: householder +
    relatives + unmarried partner + foster children + any unrelated
    children under 15); tax credits and benefits are computed on tax
    returns and summed to the SPM unit for the poverty comparison.
    Counterfactual scenarios re-run the SPM calculation with the relevant
    credit removed or expanded, holding labor supply fixed and calibrating
    take-up to IRS SOI Hawaiʻi administrative totals. District-level
    estimates carry larger uncertainty (typically ±20 percent).
  </p>
</section>

<section>
  <div class="smalllabel">About</div>
  <h2>About Hawaiʻi Appleseed</h2>
  <p>
    Hawaiʻi Appleseed Center for Law & Economic Justice is committed to a
    more socially and economically just Hawaiʻi, where everyone has
    genuine opportunities to achieve economic security and fulfill their
    potential.
  </p>
  <div class="footer">
    Author: Devin Thomas · Published {date_str} · Hawaiʻi Appleseed,
    733 Bishop Street, Suite 1180, Honolulu, HI 96813 · hiappleseed.org<br/>
    {DATA_SOURCE_CITATION}
  </div>
</section>

</body></html>
"""
    out_html.write_text(html, encoding="utf-8")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tax-year", type=int, default=2024)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "reports" / "poverty_impact_brief",
    )
    p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Path to a reports/poverty_impact_*/ directory. "
        "If omitted, auto-detects the latest tier available.",
    )
    p.add_argument(
        "--rxkids-dir",
        type=Path,
        default=None,
        help="Path to a reports/rxkids_impact_*/ directory. "
        "If omitted, auto-detects reports/rxkids_impact_<tax-year>/.",
    )
    p.add_argument(
        "--date",
        type=str,
        default=None,
        help="Date string to print on the cover (e.g. 'May 2026'). Defaults to today.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    data_dir = _resolve_data_dir(args.data_dir, args.tax_year)
    print(f"[brief] using data dir: {data_dir.relative_to(REPO_ROOT)}", flush=True)
    rxkids_dir = _resolve_rxkids_dir(args.rxkids_dir, args.tax_year)
    if rxkids_dir is not None:
        print(
            f"[brief] using rxkids dir: {rxkids_dir.relative_to(REPO_ROOT)}",
            flush=True,
        )
    else:
        print("[brief] no rxkids report found — skipping RxKids section", flush=True)

    data = _load_data(data_dir, args.tax_year, rxkids_dir)

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    charts_dir = out_dir / "_charts"
    charts = _make_figures(data, charts_dir)

    date_str = args.date or _dt.date.today().strftime("%B %Y")

    out_pdf = out_dir / f"HI_Appleseed_Poverty_Impact_Brief_TY{data.tax_year}.pdf"
    out_html = out_dir / f"HI_Appleseed_Poverty_Impact_Brief_TY{data.tax_year}.html"

    pdf_ok = True
    try:
        _build_pdf(data, charts, out_pdf, date_str)
        print(f"[brief] wrote {out_pdf.relative_to(REPO_ROOT)}", flush=True)
    except Exception as exc:  # pragma: no cover - defensive
        pdf_ok = False
        print(f"[brief] PDF generation failed: {exc}", file=sys.stderr)
        print(
            "[brief] continuing with HTML fallback; install weasyprint or "
            "reportlab to enable an alternate PDF path.",
            file=sys.stderr,
        )

    _build_html_fallback(data, charts, out_html, date_str)
    print(f"[brief] wrote {out_html.relative_to(REPO_ROOT)}", flush=True)

    return 0 if pdf_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
