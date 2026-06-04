"""RxKids Hawaiʻi — 2028 cost and benefits-by-income-quintile analysis.

Produces a single shareable workbook combining both halves of the RxKids
analysis for a hypothetical Hawaiʻi RxKids prenatal + infant cash program
under its **statutory eligibility** (qualify for the State's Medicaid
program OR family income ≤ 300% FPL for a family of applicable size
*including the expected unborn child*), projected to **2028**:

  * **Cost** — the annual fiscal outlay = the weighted sum of the expected
    RxKids benefit (total + prenatal/postnatal arms), by state and county,
    with a SDR sampling 90% CI and a parameter assumption band.
  * **Household impact** — the RxKids benefit *received* by income quintile:
    families reached, total dollars, and average benefit per family in each
    fifth of the income distribution. This is a pure distribution-of-benefits
    view; it does NOT touch the tax engine or SPM poverty thresholds, so the
    whole run is genuine TY2028 in a single pass.

The deliverable is an Excel workbook (`rxkids_2028_cost_and_impact.xlsx`)
with Summary / By-county / By-income-quintile / Assumptions / Notes tabs —
the analyst-facing format. Component CSVs and the SPM-unit parquet are
written alongside.

Method
------
1. Load PUMS (with replicate weights) and attach SPM unit IDs.
2. Project incomes forward to the target year (FPL thresholds taken at the
   same year, so income and eligibility are coherent).
3. Compute the Medicaid flag (clause 1) and the RxKids benefit (clauses
   1 + 2), aggregate to SPM units.
4. Cost = Σ rxkids_amount × weight (WGTP household weight) at SPM grain.
   Quintiles: SPM units ranked on summed income, weighted by WGTP.

Caveats
-------
* FPL for 2026-2028 is CPI-projected off the 2025 HHS table.
* Pregnancy incidence and child-age share are held at base-year values; the
  assumption band brackets this.

Usage
-----
    uv run python forecast_rxkids_2028.py \\
        --tax-year 2028 \\
        --pums-data-dir packages/data/raw/pums_2024_1yr \\
        --out reports/rxkids_2028/

    # Smoke test on the synthetic fixture (no replicate SE):
    uv run python forecast_rxkids_2028.py --use-fixture
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

LOG = logging.getLogger("forecast_rxkids_2028")
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

PUMS_CONSTRUCTION_YEAR = 2022
WORKBOOK_NAME = "rxkids_2028_cost_and_impact.xlsx"
PDF_NAME = "rxkids_2028_cost_and_impact.pdf"
# Full Flint-design postnatal window. The base run uses the 6-month lower
# bound; this prices the optional extension to the full 12 months.
EXTENDED_POSTNATAL_MONTHS = 12
# Expected eligible pregnancies per eligible birth, used to birth-anchor the
# prenatal arm (1.0 = one prenatal claim per eligible birth). Slightly above
# 1 would account for miscarriage; 1.0 is the conservative coherence anchor.
PREG_PER_BIRTH = 1.0

_TEAL = (31, 111, 139)
_DARK = (31, 59, 77)
_GREY = (90, 90, 90)
_LIGHT = (235, 242, 245)


def _ascii(s) -> str:
    """fpdf2 core fonts are latin-1; map the few non-latin-1 glyphs we use."""
    return (
        str(s)
        .replace("ʻ", "'").replace("–", "-").replace("—", "-")
        .replace("≤", "<=").replace("→", "->").replace("×", "x")
        .encode("latin-1", "replace").decode("latin-1")
    )

# One-at-a-time assumption sweep. Cost is linear in each, so low/high values
# bracket the band.
_SWEEP = {
    "takeup_rate": [0.60, 0.95],
    "prenatal_pregnancy_probability_mult": [0.75, 1.25],
    "child_under_age_share_mult": [0.75, 1.25],
}


def _parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tax-year", type=int, default=2028,
                   help="Target year for the analysis. Default 2028.")
    p.add_argument("--pums-data-dir", type=Path,
                   default=REPO_ROOT / "packages" / "data" / "raw" / "pums_2024_1yr",
                   help="Directory containing psam_p15 and psam_h15 PUMS files.")
    p.add_argument("--use-fixture", action="store_true", default=False,
                   help="Use the synthetic test fixture (smoke test only; "
                        "disables replicate-weight sampling CIs).")
    p.add_argument("--out", type=Path, default=REPO_ROOT / "reports" / "rxkids_2028",
                   help="Output directory.")
    p.add_argument("--no-replicate-se", action="store_true", default=False,
                   help="Skip SDR sampling standard errors even on real PUMS.")
    p.add_argument("--no-assumption-band", action="store_true", default=False,
                   help="Skip the parameter assumption-band sweep.")
    p.add_argument("--no-pdf", action="store_true", default=False,
                   help="Skip the one-page PDF summary (write only the workbook + CSVs).")
    p.add_argument("--launch-operating-months", type=int, default=12,
                   help="Months the program operates in its first fiscal year "
                        "(12 = launch at FY start; e.g. 6 for a mid-year launch).")
    p.add_argument("--ramp-months", type=int, default=12,
                   help="Months for enrollment to ramp from zero to full take-up "
                        "in the launch year. Default 12 (gradual). Lower = faster.")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Cost + benefit helpers
# ---------------------------------------------------------------------------


def _weighted_cost(frame: pd.DataFrame, amount_col: str, weight_col: str = "weight") -> float:
    """Σ amount × weight over a frame (the fiscal-cost identity)."""
    if amount_col not in frame.columns:
        return 0.0
    a = frame[amount_col].fillna(0).to_numpy(dtype=float)
    w = frame[weight_col].fillna(0).to_numpy(dtype=float)
    return float((a * w).sum())


def _reached(frame: pd.DataFrame, amount_col: str, weight_col: str = "weight") -> float:
    """Weighted count of units with a positive expected benefit = the ELIGIBLE
    base (any family that clears the income/Medicaid test and has the relevant
    composition). NOT the recipient count — see _expected_recipients."""
    if amount_col not in frame.columns:
        return 0.0
    a = frame[amount_col].fillna(0).to_numpy(dtype=float)
    w = frame[weight_col].fillna(0).to_numpy(dtype=float)
    return float(w[a > 0].sum())


def _expected_recipients(
    frame: pd.DataFrame, *, pre_payment: float, post_payment: float,
    weight_col: str = "weight",
) -> tuple[float, float, float]:
    """Weighted EXPECTED recipients/year (pregnancies, infants, total).

    The arm dollar amount = (probability × per-recipient payment × take-up),
    so dividing by the full per-recipient payment recovers the expected number
    of actual claimers (probability × take-up). This is the true recipient
    count, far below the eligible base (_reached), because most eligible
    families do not have a pregnancy/infant in a given year.
    """
    w = frame[weight_col].fillna(0).to_numpy(dtype=float)
    pre = post = 0.0
    if pre_payment > 0 and "rxkids_prenatal_amount" in frame.columns:
        a = frame["rxkids_prenatal_amount"].fillna(0).to_numpy(dtype=float)
        pre = float((a / pre_payment * w).sum())
    if post_payment > 0 and "rxkids_postnatal_amount" in frame.columns:
        a = frame["rxkids_postnatal_amount"].fillna(0).to_numpy(dtype=float)
        post = float((a / post_payment * w).sum())
    return pre, post, pre + post


def _cost_with_sdr(frame: pd.DataFrame, amount_col: str) -> tuple[float, float]:
    """Return (cost, sdr_se) for an amount column on an SPM-grain frame.

    cost = Σ amount × weight (main WGTP weight); the SDR SE is computed over
    the weight_r01..weight_r80 replicate columns if present (else 0.0).
    """
    from tax_modeler.poverty.impact import (
        _detect_replicate_weight_cols,
        _sdr_se_from_replicates,
    )

    cost_0 = _weighted_cost(frame, amount_col, "weight")
    rep_cols = _detect_replicate_weight_cols(frame)
    if not rep_cols:
        return cost_0, 0.0
    a = frame[amount_col].fillna(0).to_numpy(dtype=float)
    cost_r = np.array([
        float((a * frame[rc].fillna(0).to_numpy(dtype=float)).sum())
        for rc in rep_cols
    ])
    se = float(_sdr_se_from_replicates(cost_0, cost_r))
    return cost_0, se


def _benefits_by_quintile(
    frame: pd.DataFrame, *, pre_payment: float, post_payment: float,
) -> list[dict]:
    """RxKids benefit received per weighted income quintile (SPM-unit grain).

    SPM units are ranked on summed ``income`` and split into population-equal
    fifths weighted by the WGTP household ``weight``. For each quintile:
    average income, families (weighted), expected recipients/year, total
    benefit dollars, average benefit per recipient, and share of total benefit.
    """
    from tax_modeler.metrics.distribution import weighted_ntile_labels

    if "income" not in frame.columns or frame.empty:
        return []
    labels = weighted_ntile_labels(
        frame["income"].fillna(0), frame["weight"].fillna(0), n=5, label_prefix="Q",
    ).to_numpy()
    rows = []
    for q in [f"Q{i}" for i in range(1, 6)]:
        mask = labels == q
        if not mask.any():
            continue
        sub = frame.loc[mask]
        w = sub["weight"].fillna(0).to_numpy(dtype=float)
        amt = sub["rxkids_amount"].fillna(0).to_numpy(dtype=float)
        inc = sub["income"].fillna(0).to_numpy(dtype=float)
        wsum = w.sum()
        total_benefit = float((amt * w).sum())
        _, _, recipients = _expected_recipients(
            sub, pre_payment=pre_payment, post_payment=post_payment,
        )
        rows.append({
            "quintile": q,
            "avg_income": round(float((inc * w).sum() / wsum), 0) if wsum > 0 else 0,
            "families": round(float(wsum), 0),
            "expected_recipients": round(recipients, 0),
            "total_benefit_$": round(total_benefit, 0),
            "avg_benefit_per_recipient_$": round(total_benefit / recipients, 0) if recipients > 0 else 0,
        })
    grand = sum(r["total_benefit_$"] for r in rows)
    for r in rows:
        r["share_of_benefit_pct"] = round(100.0 * r["total_benefit_$"] / grand, 1) if grand > 0 else 0.0
    return rows


def _first_year_disbursement(
    prenatal_annual: float,
    postnatal_annual: float,
    *,
    operating_months: int = 12,
    ramp_months: int = 12,
    postnatal_window: int = 6,
    start_frac: float = 0.0,
) -> dict:
    """First-fiscal-year *disbursement* (cash out the door), not benefits earned.

    A launch year differs from steady state in two ways, modeled monthly:

    * **Enrollment ramp** — take-up climbs from ``start_frac`` to full over
      ``ramp_months`` (linear). New prenatal payments scale directly with the
      enrollment level in the month they occur.
    * **Postnatal caseload fill** — each birth pays out over ``postnatal_window``
      months, so even at full enrollment the monthly postnatal caseload takes
      ``postnatal_window`` months to fill. The caseload in month t is the share
      of the trailing window already born-and-enrolled.

    Payments for late-year births that would spill past month
    ``operating_months`` fall into the next fiscal year and are excluded.
    """
    pre_m = prenatal_annual / 12.0      # steady-state monthly prenatal disbursement
    post_m = postnatal_annual / 12.0    # steady-state monthly postnatal disbursement

    def enroll(t: int) -> float:
        if ramp_months <= 0 or t >= ramp_months:
            return 1.0
        return start_frac + (1.0 - start_frac) * (t / ramp_months)

    pre_total = 0.0
    post_total = 0.0          # postnatal dollars actually paid within the FY
    post_entitlement = 0.0    # full postnatal entitlement of in-FY birth cohorts
    for t in range(1, operating_months + 1):
        pre_total += pre_m * enroll(t)
        # caseload fraction = trailing-window births that are enrolled, / window
        s = sum(enroll(t - k) for k in range(postnatal_window) if (t - k) >= 1)
        post_total += post_m * (s / postnatal_window)
        # full entitlement created by this month's birth cohort (pays out over
        # the next `postnatal_window` months; the part beyond operating_months
        # is deferred into the next fiscal year, not saved).
        post_entitlement += post_m * enroll(t)

    deferred_postnatal = max(0.0, post_entitlement - post_total)
    total = pre_total + post_total
    steady = prenatal_annual + postnatal_annual
    return {
        "prenatal": pre_total,
        "postnatal": post_total,
        "total": total,
        "deferred_postnatal": deferred_postnatal,
        "pct_of_steady": (total / steady) if steady > 0 else 0.0,
        "operating_months": operating_months,
        "ramp_months": ramp_months,
    }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def _load(pir, args):
    """Load PUMS once (with replicate weights if requested) + attach SPM ids."""
    want_se = not args.use_fixture and not args.no_replicate_se
    base_units, persons = pir._load_units(
        args.pums_data_dir, args.use_fixture, with_replicate_weights=want_se,
    )
    from tax_modeler.pipeline import enrich_with_spm_unit_id
    base_units, persons = enrich_with_spm_unit_id(base_units, persons)
    return base_units, persons


def _project(pir, base_units, year: int) -> pd.DataFrame:
    """Project base-year tax units forward to ``year`` (income aged)."""
    return pir._build_units_for_tax_year(
        base_units, year, project=(year != PUMS_CONSTRUCTION_YEAR),
    )


def _apply_rxkids(units: pd.DataFrame, *, tax_year: int, overrides: Optional[dict] = None) -> pd.DataFrame:
    """Medicaid flag (clause 1) then RxKids expected benefit on a tax-unit frame."""
    from tax_modeler.benefits.medicaid_hi_quest import compute_medicaid_for_units
    from tax_modeler.programs import compute_rxkids_for_units

    out = compute_medicaid_for_units(units, tax_year=tax_year)
    out = compute_rxkids_for_units(out, tax_year=tax_year, overrides=overrides)
    return out


def _assumption_band(
    units, persons, *, tax_year: int, base_cost: float, base_preg_prob: float,
) -> dict:
    """Joint (factorial-corner) assumption band over the three soft parameters.

    take-up scales both arms, pregnancy-probability scales only prenatal, and
    infant-share scales only postnatal — and cost is monotone increasing in
    each. So the true min/max sit at the all-low and all-high corners, NOT at
    any one-at-a-time perturbation (which would understate the range). We price
    those two corners directly. ``base_preg_prob`` is the birth-anchored
    pregnancy probability, so the prenatal sweep brackets the anchored value.
    """
    from tax_modeler.poverty.spm_aggregation import aggregate_to_spm_units
    from tax_modeler.programs import hawaii_rxkids_parameters

    base = hawaii_rxkids_parameters()
    tk = _SWEEP["takeup_rate"]
    pm = _SWEEP["prenatal_pregnancy_probability_mult"]
    cm = _SWEEP["child_under_age_share_mult"]

    def _cost_for(overrides: dict) -> float:
        u = _apply_rxkids(units, tax_year=tax_year, overrides=overrides)
        return _weighted_cost(aggregate_to_spm_units(u, persons), "rxkids_amount", "weight")

    def _corner(takeup, preg_mult, child_mult):
        return _cost_for({
            "takeup_rate": takeup,
            "prenatal_pregnancy_probability": float(np.clip(base_preg_prob * preg_mult, 0.0, 1.0)),
            "child_under_age_share": float(np.clip(base.child_under_age_share * child_mult, 0.0, 1.0)),
        })

    low = _corner(min(tk), min(pm), min(cm))
    high = _corner(max(tk), max(pm), max(cm))
    return {"min": low, "max": high, "base": base_cost,
            "takeup_range": tk, "mult_range": [min(pm), max(pm)]}


# ---------------------------------------------------------------------------
# Workbook
# ---------------------------------------------------------------------------


def _write_workbook(path: Path, *, ctx: dict) -> None:
    """Assemble the analyst-facing Excel workbook from the computed context."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    title_font = Font(bold=True, size=14, color="1F3B4D")
    hdr_font = Font(bold=True, color="FFFFFF")
    hdr_fill = PatternFill("solid", fgColor="1F6F8B")
    label_font = Font(bold=True)
    money_fmt = "#,##0"
    pct_fmt = "0.0"
    thin = Side(style="thin", color="D0D0D0")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def _style_header_row(ws, headers):
        for j, h in enumerate(headers, start=1):
            c = ws.cell(row=1, column=j, value=h)
            c.font = hdr_font
            c.fill = hdr_fill
            c.alignment = Alignment(horizontal="center")
        ws.freeze_panes = "A2"

    wb = Workbook()

    # ---- Summary ----
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = f"RxKids Hawaiʻi — Cost & Benefits by Income Quintile, TY {ctx['tax_year']}"
    ws["A1"].font = title_font
    ws["A2"] = ("Statutory eligibility: Medicaid (clause 1) OR income ≤ 300% FPL "
                "incl. expected unborn child (clause 2)")
    ws["A2"].font = Font(italic=True, color="555555")
    ws["A3"] = ("⚠ Point estimate — true uncertainty is ±30-40%. RxKids has no admin "
                "caseload to calibrate against; cost hinges on soft pregnancy/infant "
                "incidence assumptions. Read with the assumption band below.")
    ws["A3"].font = Font(italic=True, bold=True, color="B00000")

    rows = [
        ("FISCAL COST (annual)", None, None),
        ("Total program cost", ctx["cost_total"], money_fmt),
        ("  Prenatal arm", ctx["cost_prenatal"], money_fmt),
        ("  Postnatal arm", ctx["cost_postnatal"], money_fmt),
    ]
    if ctx["cost_se"] > 0:
        rows += [
            ("Sampling 90% CI — low", ctx["cost_total"] - ctx["moe"], money_fmt),
            ("Sampling 90% CI — high", ctx["cost_total"] + ctx["moe"], money_fmt),
            ("  SDR standard error", ctx["cost_se"], money_fmt),
        ]
    if ctx.get("band"):
        rows += [
            ("Assumption band — low", ctx["band"]["min"], money_fmt),
            ("Assumption band — high", ctx["band"]["max"], money_fmt),
        ]
    rows += [
        ("", None, None),
        (f"POTENTIAL — extend postnatal {ctx['base_postnatal_months']}→"
         f"{ctx['ext_postnatal_months']} months (optional)", None, None),
        ("  Additional cost (+6 months)", ctx["additional_cost"], money_fmt),
        ("  Total cost (12-month design)", ctx["ext_total"], money_fmt),
        ("", None, None),
        (f"FIRST FISCAL YEAR (launch) — {ctx['first_year']['operating_months']}mo "
         f"operating, {ctx['first_year']['ramp_months']}mo ramp", None, None),
        ("  Year-1 disbursement (total)", ctx["first_year"]["total"], money_fmt),
        ("    Prenatal", ctx["first_year"]["prenatal"], money_fmt),
        ("    Postnatal", ctx["first_year"]["postnatal"], money_fmt),
        ("    (postnatal deferred to next FY)", ctx["first_year"]["deferred_postnatal"], money_fmt),
        ("  Year-1 as % of steady state", round(100 * ctx["first_year"]["pct_of_steady"], 1), "0.0"),
        ("  Year-1 if ramp = 6mo (fast)", ctx["ramp_sensitivity"][6], money_fmt),
        ("  Year-1 if ramp = 18mo (slow)", ctx["ramp_sensitivity"][18], money_fmt),
        ("", None, None),
        ("HOUSEHOLD REACH", None, None),
        ("Eligible families (weighted)", ctx["eligible_families"], money_fmt),
        ("Expected recipients / year", ctx["rec_total"], money_fmt),
        ("  Expected pregnancies (prenatal)", ctx["rec_pregnancies"], money_fmt),
        ("  Expected infants (postnatal)", ctx["rec_infants"], money_fmt),
        ("Avg benefit per recipient", ctx["avg_benefit"], money_fmt),
        ("", None, None),
        ("Benefits by income quintile → see the 'By income quintile' tab.", None, None),
    ]

    r = 4
    for label, value, fmt in rows:
        cell = ws.cell(row=r, column=1, value=label)
        if value is None and fmt is None:
            cell.font = Font(bold=True, color="1F6F8B")  # section header
        else:
            cell.font = label_font if not label.startswith("  ") else Font()
            vcell = ws.cell(row=r, column=2, value=value)
            if fmt:
                vcell.number_format = fmt
        r += 1
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 20

    # ---- By income quintile ----
    wsq = wb.create_sheet("By income quintile")
    qheaders = [
        "Quintile", "Avg income ($)", "Families", "Expected recipients",
        "Total benefit ($)", "Avg benefit / recipient ($)",
        "Share of benefit (%)",
    ]
    _style_header_row(wsq, qheaders)
    for i, row in enumerate(ctx["quintiles"], start=2):
        vals = [
            row["quintile"], row["avg_income"], row["families"],
            row["expected_recipients"], row["total_benefit_$"],
            row["avg_benefit_per_recipient_$"], row["share_of_benefit_pct"],
        ]
        for j, v in enumerate(vals, start=1):
            c = wsq.cell(row=i, column=j, value=v)
            c.border = border
            if j in (2, 3, 4, 5, 6):
                c.number_format = money_fmt
            elif j == 7:
                c.number_format = pct_fmt
    for j in range(1, len(qheaders) + 1):
        wsq.column_dimensions[get_column_letter(j)].width = 22

    # ---- By county ----
    ws2 = wb.create_sheet("By county")
    headers = [
        "County", "Cost total ($)", "Cost prenatal ($)", "Cost postnatal ($)",
        "Cost SE ($)", "Expected recipients",
    ]
    _style_header_row(ws2, headers)
    for i, row in enumerate(ctx["county_rows"], start=2):
        vals = [
            row["county"], row["cost_total"], row["cost_prenatal"],
            row["cost_postnatal"], row["cost_se"], row["recipients"],
        ]
        for j, v in enumerate(vals, start=1):
            c = ws2.cell(row=i, column=j, value=v)
            c.border = border
            if j >= 2 and v is not None:
                c.number_format = money_fmt
    for j in range(1, len(headers) + 1):
        ws2.column_dimensions[get_column_letter(j)].width = 18

    # ---- Assumptions ----
    ws3 = wb.create_sheet("Assumptions")
    _style_header_row(ws3, ["Parameter", "Value", "Notes"])
    for i, (param, val, note) in enumerate(ctx["assumptions"], start=2):
        ws3.cell(row=i, column=1, value=param)
        ws3.cell(row=i, column=2, value=val)
        ws3.cell(row=i, column=3, value=note)
    ws3.column_dimensions["A"].width = 32
    ws3.column_dimensions["B"].width = 16
    ws3.column_dimensions["C"].width = 60

    # ---- Notes ----
    ws4 = wb.create_sheet("Notes")
    for i, line in enumerate(ctx["notes"], start=1):
        cell = ws4.cell(row=i, column=1, value=line)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        if i == 1:
            cell.font = title_font
    ws4.column_dimensions["A"].width = 100

    wb.save(path)


# ---------------------------------------------------------------------------
# PDF (one-page shareable)
# ---------------------------------------------------------------------------


def _quintile_chart_png(quintiles: list[dict]):
    """Render a benefit-share-by-quintile bar chart to an in-memory PNG."""
    if not quintiles:
        return None
    import io

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    qs = [r["quintile"] for r in quintiles]
    shares = [r["share_of_benefit_pct"] for r in quintiles]
    fig, ax = plt.subplots(figsize=(6.4, 2.5))
    ax.bar(qs, shares, color="#1F6F8B")
    ax.set_ylabel("Share of benefit (%)")
    ax.set_xlabel("Income quintile (Q1 = lowest income)")
    for i, v in enumerate(shares):
        ax.text(i, v + 0.6, f"{v:.0f}%", ha="center", fontsize=8)
    ax.set_ylim(0, max(shares + [1]) * 1.18)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf


def _pdf_table(pdf, *, headers, widths_frac, rows) -> None:
    """Draw a simple bordered table; first column left-aligned, rest right."""
    widths = [pdf.epw * f for f in widths_frac]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(*_TEAL)
    pdf.set_text_color(255, 255, 255)
    for h, w in zip(headers, widths):
        pdf.cell(w, 6, _ascii(h), fill=True, align="C")
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)
    fill = False
    for row in rows:
        pdf.set_fill_color(*_LIGHT)
        for j, (val, w) in enumerate(zip(row, widths)):
            pdf.cell(w, 6, _ascii(val), border="B", fill=fill,
                     align="L" if j == 0 else "R")
        pdf.ln()
        fill = not fill


def _write_pdf(path: Path, *, ctx: dict) -> None:
    """One-page analyst-facing PDF mirroring the workbook headline."""
    from fpdf import FPDF

    def money(x):
        return f"${x:,.0f}"

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    pdf.set_text_color(*_DARK)
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 9, _ascii(
        f"RxKids Hawaiʻi - Cost & Benefits by Income Quintile, TY {ctx['tax_year']}"),
        new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(*_GREY)
    pdf.multi_cell(0, 5, _ascii(
        "Statutory eligibility: Medicaid (clause 1) OR income <= 300% FPL "
        "incl. expected unborn child (clause 2)"))
    pdf.set_x(pdf.l_margin)
    pdf.set_text_color(176, 0, 0)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.multi_cell(0, 4, _ascii(
        "Point estimate - true uncertainty is +/-30-40%. No admin caseload exists "
        "to calibrate against; cost hinges on soft pregnancy/infant incidence "
        "assumptions. Read with the assumption band."))
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)

    def section(title):
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*_TEAL)
        pdf.cell(0, 7, _ascii(title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    def kv(label, value, indent=0):
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(95, 6, _ascii("   " * indent + label))
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, _ascii(value), new_x="LMARGIN", new_y="NEXT")

    section("Fiscal cost (annual)")
    kv("Total program cost", money(ctx["cost_total"]))
    kv("Prenatal arm", money(ctx["cost_prenatal"]), 1)
    kv("Postnatal arm", money(ctx["cost_postnatal"]), 1)
    if ctx["cost_se"] > 0:
        kv("Sampling 90% CI",
           f"{money(ctx['cost_total'] - ctx['moe'])} - {money(ctx['cost_total'] + ctx['moe'])}")
    if ctx.get("band"):
        kv("Assumption band",
           f"{money(ctx['band']['min'])} - {money(ctx['band']['max'])}")
    pdf.ln(1)

    section(f"Potential option - extend postnatal {ctx['base_postnatal_months']}"
            f"-{ctx['ext_postnatal_months']} months")
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(*_GREY)
    pdf.multi_cell(0, 4, _ascii(
        "The program may opt to extend postnatal payments to the full 12 "
        "months (Flint's upper bound). Priced here as an optional add-on:"))
    pdf.set_text_color(0, 0, 0)
    kv("Additional cost (+6 months)", money(ctx["additional_cost"]))
    kv("Total cost (12-month design)", money(ctx["ext_total"]))
    pdf.ln(1)

    fy = ctx["first_year"]
    section(f"First fiscal year (launch) - {fy['operating_months']}mo operating, "
            f"{fy['ramp_months']}mo enrollment ramp")
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(*_GREY)
    pdf.multi_cell(0, 4, _ascii(
        "Year-1 cash disbursement, below steady state: enrollment ramps up and "
        "the 6-month postnatal caseload takes time to fill."))
    pdf.set_text_color(0, 0, 0)
    kv("Year-1 disbursement (total)", money(fy["total"]))
    kv("Prenatal / Postnatal",
       f"{money(fy['prenatal'])} / {money(fy['postnatal'])}", 1)
    kv("Postnatal deferred to next FY", money(fy["deferred_postnatal"]), 1)
    kv("Year-1 as % of steady state", f"{100 * fy['pct_of_steady']:.0f}%", 1)
    kv("Ramp sensitivity (6 / 12 / 18 mo)",
       f"{money(ctx['ramp_sensitivity'][6])} / {money(ctx['ramp_sensitivity'][12])} / "
       f"{money(ctx['ramp_sensitivity'][18])}")
    pdf.ln(1)

    section("Household reach")
    kv("Eligible families (weighted)", f"{ctx['eligible_families']:,.0f}")
    kv("Expected recipients / year", f"{ctx['rec_total']:,.0f}")
    kv("Expected pregnancies / infants",
       f"{ctx['rec_pregnancies']:,.0f} / {ctx['rec_infants']:,.0f}", 1)
    kv("Avg benefit per recipient", money(ctx["avg_benefit"]))
    pdf.ln(2)

    chart = _quintile_chart_png(ctx["quintiles"])
    if chart is not None:
        section("Benefit received by income quintile")
        pdf.image(chart, w=pdf.epw * 0.72)
        pdf.ln(2)
        _pdf_table(
            pdf,
            headers=["Quintile", "Avg income", "Families", "Recipients",
                     "Total benefit", "Share"],
            widths_frac=[0.14, 0.20, 0.17, 0.16, 0.20, 0.13],
            rows=[[
                r["quintile"], money(r["avg_income"]), f"{r['families']:,.0f}",
                f"{r['expected_recipients']:,.0f}", money(r["total_benefit_$"]),
                f"{r['share_of_benefit_pct']:.1f}%",
            ] for r in ctx["quintiles"]],
        )
        pdf.ln(3)

    if ctx["county_rows"]:
        section("Cost by county")
        _pdf_table(
            pdf,
            headers=["County", "Cost total", "Prenatal", "Postnatal", "Recipients"],
            widths_frac=[0.30, 0.18, 0.17, 0.17, 0.18],
            rows=[[
                r["county"], money(r["cost_total"]), money(r["cost_prenatal"]),
                money(r["cost_postnatal"]), f"{r['recipients']:,.0f}",
            ] for r in ctx["county_rows"]],
        )
        pdf.ln(3)

    pdf.set_font("Helvetica", "I", 7.5)
    pdf.set_text_color(*_GREY)
    pdf.multi_cell(0, 4, _ascii(
        "Cost = weighted sum of the expected RxKids benefit (take-up- and "
        "pregnancy-probability-adjusted) at SPM-unit grain on the household "
        "(WGTP) weight. Benefits-by-quintile ranks SPM units on summed income "
        "into population-equal fifths. Sampling CI is ACS sampling error (SDR, "
        "80 replicate weights); the assumption band sweeps take-up, pregnancy "
        "incidence, and infant share. 2026-2028 FPL is CPI-projected off the "
        "2025 HHS table. Full methodology: RXKIDS_METHODOLOGY.md."))

    pdf.output(str(path))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[list] = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    import poverty_impact_report as pir
    from tax_modeler.poverty.spm_aggregation import aggregate_to_spm_units
    from tax_modeler.programs import hawaii_rxkids_parameters

    args.out.mkdir(parents=True, exist_ok=True)
    p = hawaii_rxkids_parameters()
    ty = args.tax_year
    pre_payment = p.prenatal_monthly * p.prenatal_months
    post_payment = p.postnatal_monthly_per_child * p.postnatal_months

    LOG.info("Loading PUMS (real PUMS=%s)", not args.use_fixture)
    base_units, persons = _load(pir, args)

    LOG.info("Projecting income to TY %d", ty)
    projected = _project(pir, base_units, ty)

    # ---- Prenatal birth-anchor calibration ----
    # The raw prenatal arm applies a flat pregnancy probability to the whole
    # single/HoH-no-dependent universe, which produces more expected pregnancies
    # than Hawaii has eligible births. Anchor it so expected pregnancies =
    # PREG_PER_BIRTH × the eligible-birth count implied by the postnatal arm
    # (one prenatal claim per eligible birth). pregnancy_probability is linear,
    # so a single scale on the raw rate is exact.
    raw_frame = aggregate_to_spm_units(_apply_rxkids(projected, tax_year=ty), persons)
    raw_preg, raw_inf, _ = _expected_recipients(
        raw_frame, pre_payment=pre_payment, post_payment=post_payment,
    )
    calib_preg_prob = p.prenatal_pregnancy_probability
    if raw_preg > 0:
        calib_preg_prob = p.prenatal_pregnancy_probability * (raw_inf * PREG_PER_BIRTH / raw_preg)
    calib = {"prenatal_pregnancy_probability": calib_preg_prob}
    LOG.info(
        "Prenatal birth-anchor: pregnancy prob %.4f -> %.4f "
        "(raw pregnancies %.0f vs eligible infants %.0f)",
        p.prenatal_pregnancy_probability, calib_preg_prob, raw_preg, raw_inf,
    )

    units = _apply_rxkids(projected, tax_year=ty, overrides=calib)
    frame = aggregate_to_spm_units(units, persons)
    LOG.info("Aggregated %d tax units -> %d SPM units", len(units), len(frame))

    # ---- Cost (state) ----
    total_cost, total_se = _cost_with_sdr(frame, "rxkids_amount")
    prenatal_cost, _ = _cost_with_sdr(frame, "rxkids_prenatal_amount")
    postnatal_cost, _ = _cost_with_sdr(frame, "rxkids_postnatal_amount")
    moe = 1.645 * total_se

    # ---- Potential option: extend postnatal payments to the full 12 months.
    #      The program may or may not opt in; we price the additional 6 months
    #      as an optional add-on (postnatal is linear in months). ----
    ext_units = _apply_rxkids(
        projected, tax_year=ty,
        overrides={**calib, "postnatal_months": EXTENDED_POSTNATAL_MONTHS},
    )
    ext_frame = aggregate_to_spm_units(ext_units, persons)
    ext_total = _weighted_cost(ext_frame, "rxkids_amount")
    ext_postnatal = _weighted_cost(ext_frame, "rxkids_postnatal_amount")
    additional_cost = ext_total - total_cost

    # ---- First fiscal year (launch): partial operating window + enrollment
    #      ramp + postnatal caseload fill. This is the appropriation-relevant
    #      year-1 cash flow, well below the steady-state annual cost. ----
    postnatal_window = int(p.postnatal_months)
    first_year = _first_year_disbursement(
        prenatal_cost, postnatal_cost,
        operating_months=args.launch_operating_months,
        ramp_months=args.ramp_months,
        postnatal_window=postnatal_window,
    )
    # Ramp sensitivity (the dominant year-1 driver): fast / base / slow.
    ramp_sensitivity = {
        rm: _first_year_disbursement(
            prenatal_cost, postnatal_cost,
            operating_months=args.launch_operating_months,
            ramp_months=rm, postnatal_window=postnatal_window,
        )["total"]
        for rm in (6, 12, 18)
    }

    # Eligible base (families clearing the test) vs the EXPECTED recipient
    # count (those actually getting a payment in the year). The avg benefit is
    # per recipient — i.e. the real per-family payment design, not cost spread
    # over the much larger eligible base.
    eligible_families = _reached(frame, "rxkids_amount")
    rec_pregnancies, rec_infants, rec_total = _expected_recipients(
        frame, pre_payment=pre_payment, post_payment=post_payment,
    )
    avg_benefit = (total_cost / rec_total) if rec_total > 0 else 0.0

    # ---- Household impact: benefits received by income quintile ----
    quintiles = _benefits_by_quintile(
        frame, pre_payment=pre_payment, post_payment=post_payment,
    )

    # ---- By county (cost) ----
    county_rows = []
    if "county" in frame.columns:
        for county, grp in frame.groupby("county", dropna=False):
            c_total, c_se = _cost_with_sdr(grp, "rxkids_amount")
            _, _, grp_rec = _expected_recipients(
                grp, pre_payment=pre_payment, post_payment=post_payment,
            )
            county_rows.append({
                "county": county,
                "cost_total": round(c_total, 0),
                "cost_prenatal": round(_weighted_cost(grp, "rxkids_prenatal_amount"), 0),
                "cost_postnatal": round(_weighted_cost(grp, "rxkids_postnatal_amount"), 0),
                "cost_se": round(c_se, 0),
                "recipients": round(grp_rec, 0),
            })

    # ---- Assumption band ----
    band = None
    if not args.no_assumption_band:
        LOG.info("Running assumption-band sweep")
        band = _assumption_band(units, persons, tax_year=ty, base_cost=total_cost,
                                base_preg_prob=calib_preg_prob)

    # ---- Assemble context ----
    assumptions = [
        ("Eligibility cap (income_fpl_cap)", f"{p.income_fpl_cap:.2f}× FPL", "Clause 2: 300% FPL income test"),
        ("Prenatal unborn count", p.prenatal_unborn_count, "Family-size increment for the prenatal FPL test"),
        ("Medicaid OR-clause", "on", "Clause 1: medicaid_receives from compute_medicaid_for_units"),
        ("Prenatal payment", f"${p.prenatal_monthly:,.0f} × {p.prenatal_months}", "One-time per pregnancy"),
        ("Postnatal payment", f"${p.postnatal_monthly_per_child:,.0f}/mo × {p.postnatal_months}", "Per infant under cutoff"),
        ("Take-up rate", p.takeup_rate, f"Swept {_SWEEP['takeup_rate']} for the band"),
        ("Pregnancy probability (anchored)", round(calib_preg_prob, 4),
         f"Birth-anchored from raw {p.prenatal_pregnancy_probability} so expected "
         f"pregnancies = eligible births; swept ±25%"),
        ("Child-under-age share", p.child_under_age_share,
         "Annual births ÷ dependents (FLOW); postnatal infant proxy; swept ±25%"),
        ("FPL table year", ty, "benefits/_fpl.py (2025 published; 2026-28 CPI-projected)"),
        ("Tax treatment", "non-taxable", "Added to SPM resources only; no AGI/EITC/CTC interaction"),
        ("Fiscal weight", "WGTP (household)", "SPM-grain household weight; not the EITC-reweighted tax-unit weight"),
        ("Income quintiles", "WGTP-weighted", "SPM units ranked on summed income; population-equal fifths"),
    ]
    notes = [
        f"RxKids Hawaiʻi — methodology notes (TY {ty})",
        "",
        "Cost = Σ (expected RxKids benefit × household weight) at SPM-unit grain. The "
        "benefit is already take-up- and pregnancy-probability-adjusted, so it is an "
        "expected annual dollar amount per unit, not a literal payment.",
        "",
        "Household impact here is the distribution of RxKids benefits RECEIVED across "
        "weighted income quintiles (SPM units ranked on summed income). This view does not "
        "use the tax engine or SPM poverty thresholds, so the whole run is genuine TY"
        f"{ty}. A poverty-lift view (persons lifted) would require those engines, which "
        "stop at TY2025 — out of scope for this run.",
        "",
        "Sampling 90% CI is ACS sampling error only (SDR over 80 PUMS replicate weights). "
        "The assumption band is a one-at-a-time sweep over the three soft, unanchored "
        "parameters (take-up, pregnancy incidence, infant share) — cost is linear in each.",
        "",
        "The base run prices the 6-month postnatal window (Flint's lower bound). The "
        "'potential' line prices the optional extension to the full 12 months — the "
        "program may or may not opt in. Postnatal cost is linear in months, so the "
        "additional 6 months roughly equals the base postnatal arm again.",
        "",
        "Caveats: 2026-2028 FPL is CPI-projected off the 2025 HHS table; pregnancy "
        "incidence and infant share are held at base-year values.",
        "",
        "Full methodology: RXKIDS_METHODOLOGY.md (program origin, parameter sourcing, "
        "eligibility approximations, limitations).",
    ]
    ctx = {
        "tax_year": ty,
        "cost_total": total_cost, "cost_prenatal": prenatal_cost,
        "cost_postnatal": postnatal_cost, "cost_se": total_se, "moe": moe,
        "base_postnatal_months": int(p.postnatal_months),
        "ext_postnatal_months": EXTENDED_POSTNATAL_MONTHS,
        "ext_total": ext_total, "ext_postnatal": ext_postnatal,
        "additional_cost": additional_cost,
        "first_year": first_year, "ramp_sensitivity": ramp_sensitivity,
        "eligible_families": eligible_families,
        "rec_total": rec_total, "rec_pregnancies": rec_pregnancies,
        "rec_infants": rec_infants, "avg_benefit": avg_benefit,
        "quintiles": quintiles, "band": band, "county_rows": county_rows,
        "assumptions": assumptions, "notes": notes,
    }

    # ---- Write outputs ----
    workbook_path = args.out / WORKBOOK_NAME
    _write_workbook(workbook_path, ctx=ctx)
    pdf_path = None
    if not args.no_pdf:
        pdf_path = args.out / PDF_NAME
        _write_pdf(pdf_path, ctx=ctx)
    pd.DataFrame(ctx["quintiles"]).to_csv(args.out / "benefits_by_income_quintile.csv", index=False)
    pd.DataFrame(county_rows).to_csv(args.out / "cost_by_county.csv", index=False)
    pd.DataFrame([{
        "geography": "Hawaii", "tax_year": ty,
        "cost_total_$": round(total_cost, 0),
        "cost_prenatal_$": round(prenatal_cost, 0),
        "cost_postnatal_$": round(postnatal_cost, 0),
        "cost_total_se_$": round(total_se, 0),
        "cost_total_ci90_low_$": round(total_cost - moe, 0),
        "cost_total_ci90_high_$": round(total_cost + moe, 0),
        "potential_additional_6mo_cost_$": round(additional_cost, 0),
        "potential_total_12mo_cost_$": round(ext_total, 0),
        "first_year_total_$": round(first_year["total"], 0),
        "first_year_prenatal_$": round(first_year["prenatal"], 0),
        "first_year_postnatal_$": round(first_year["postnatal"], 0),
        "first_year_pct_of_steady": round(100 * first_year["pct_of_steady"], 1),
        "eligible_families": round(eligible_families, 0),
        "expected_recipients": round(rec_total, 0),
        "expected_pregnancies": round(rec_pregnancies, 0),
        "expected_infants": round(rec_infants, 0),
        "avg_benefit_per_recipient_$": round(avg_benefit, 0),
    }]).to_csv(args.out / "cost_by_state.csv", index=False)
    frame.to_parquet(args.out / "spm_units.parquet")

    # ---- Console summary ----
    print(f"\nRxKids Hawaiʻi — TY {ty}")
    print("=" * 56)
    print(f"  Total annual cost          : ${total_cost:>16,.0f}")
    print(f"    Prenatal / Postnatal     : ${prenatal_cost:>14,.0f} / ${postnatal_cost:,.0f}")
    if total_se > 0:
        print(f"  Sampling 90% CI            : ${total_cost - moe:,.0f} – ${total_cost + moe:,.0f}")
    if band is not None:
        print(f"  Assumption band            : ${band['min']:,.0f} – ${band['max']:,.0f}")
    print(f"  POTENTIAL +6 months        : +${additional_cost:>15,.0f}"
          f"  (12-mo total ${ext_total:,.0f})")
    print(f"  FIRST FY (launch)          : ${first_year['total']:>16,.0f}"
          f"  ({100 * first_year['pct_of_steady']:.0f}% of steady; "
          f"{first_year['operating_months']}mo op, {first_year['ramp_months']}mo ramp)")
    print(f"    ramp 6/12/18mo           : ${ramp_sensitivity[6]:,.0f} / "
          f"${ramp_sensitivity[12]:,.0f} / ${ramp_sensitivity[18]:,.0f}")
    print(f"  Eligible families          : {eligible_families:>16,.0f}")
    print(f"  Expected recipients/year   : {rec_total:>16,.0f}"
          f"  ({rec_pregnancies:,.0f} preg + {rec_infants:,.0f} infants)")
    print(f"  Avg benefit per recipient  : ${avg_benefit:>15,.0f}")
    print("\n  Benefit received by income quintile:")
    for row in quintiles:
        print(f"    {row['quintile']}  avg inc ${row['avg_income']:>10,.0f}  "
              f"benefit ${row['total_benefit_$']:>14,.0f}  "
              f"({row['share_of_benefit_pct']:>5.1f}% of total)")
    print(f"\n  Workbook: {workbook_path}")
    if pdf_path is not None:
        print(f"  PDF     : {pdf_path}")
    LOG.info("Wrote workbook + %sCSVs + parquet to %s",
             "PDF + " if pdf_path else "", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
