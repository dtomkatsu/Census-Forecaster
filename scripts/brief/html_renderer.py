"""HTML fallback renderer for the poverty-impact brief (self-contained, base64 images)."""

from __future__ import annotations

import base64
from pathlib import Path

from .data import (
    CHARCOAL,
    DATA_SOURCE_CITATION,
    GOLD,
    LIGHT_GRAY,
    LIGHT_TEAL,
    SLATE,
    TEAL,
    BriefData,
    _fmt_int,
    _fmt_money_m,
    _fmt_pct,
)


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


# Public alias
build_html = _build_html_fallback
