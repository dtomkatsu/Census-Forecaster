# SB 3125 CD1 — Hawaii Income Tax Fiscal Impact Forecast
## Tax Years 2027–2031

**Last updated:** May 27, 2026
**Analyst:** Hawaii Appleseed Center for Law and Economic Justice
**Model version:** CD2 vintage carryforward model + Round-2 REEC refinements (May 14, 2026).

> **Maintenance note:** This document must be updated whenever forecast methodology changes — including parameter recalibration, new behavioral channels, tax treatment corrections, or data source changes. Update the relevant section(s) and the Results table before committing.

---

## SOI-anchored EITC dollar calibration — May 27, 2026

**Methodology addition:** Post-take-up proportional scaling to match IRS SOI HI TY2022 aggregate EITC dollars ($184.7M).

After count-based take-up imputation (which marks non-recipients to zero), the model may still understate the aggregate EITC dollar total due to ACS wage underreporting and filer mix-shift. A new `scale_benefit_to_dollar_target()` step now applies a proportional scalar (`target_dollars_M / model_dollars_M`) to `eitc_amount` for all imputed recipients. The HI EITC (`hi_eitc_amount`, 40% of federal) is scaled by the same factor to preserve the 40% rate.

**Guard rails:** The scalar is logged at WARNING level when it falls outside [0.5, 2.0] — values outside this range indicate a data mismatch rather than a calibration adjustment. A zero model total skips scaling entirely to prevent divide-by-zero.

**Files changed:**
- `packages/tax_modeler/src/tax_modeler/calibration/takeup_imputation.py` — added `scale_benefit_to_dollar_target()` function and integrated it into `calibrate_benefits()` for the 'eitc' and 'hi_eitc' programs.
- `packages/tax_modeler/src/tax_modeler/calibration/__init__.py` — exported `scale_benefit_to_dollar_target`.
- `packages/tax_modeler/src/tax_modeler/__init__.py` — exported `scale_benefit_to_dollar_target`.
- `tests/tax_modeler/smoke/test_takeup_smoke.py` — 5 new tests covering scalar application, HI-EITC proportionality, unusual-scalar warning, zero-model guard, and calibrate_benefits integration.
- `tests/tax_modeler/poverty/test_impact.py` — updated `test_credit_takeup_reduces_baseline_lift` to use count-only caseload (annual_dollars_millions=0) so the zeroing-behavior invariant is tested independently of dollar scaling.

**Forecast impact:** Closes the remaining dollar gap between the model and IRS SOI HI TY2022 actuals after the filer-age fix. The scalar applied to the full PUMS population should be ≈1.0–1.3 (small upward adjustment). SB 3125 CD1 bracket and REEC/CGEC/TCRA computations are not affected; this calibration applies to the baseline EITC receipt column only.

---

## EITC age-eligibility correction — May 27, 2026

**Tax treatment correction:** Enforced IRC §32(c)(1)(A)(ii) age 25–64 requirement
for childless filers in `calculate_eitc()`.

Prior behavior allowed childless filers of any age to receive the federal EITC,
which overstated EITC receipts by ~$10.6M vs IRS SOI Hawaii TY2022 actuals
($184.7M actual). Affected filers: 28,084 under-25 claimants (~$9.9M) and 3,147
over-64 claimants (~$0.7M).

**Files changed:**
- `packages/tax_modeler/src/tax_modeler/credits/eitc.py` — added age guard after
  qualifying-child count; defaults to age 40 (eligible) when `primary_agep` is
  absent to avoid penalizing incomplete records.
- `tests/tax_modeler/credits/test_eitc.py` — 6 new tests covering boundary ages
  (24/25/64/65), parent exemption, and missing-age default.

**Forecast impact:** Reduces modeled EITC base slightly. Does not affect the SB
3125 CD1 income-tax bracket or REEC/CGEC/TCRA credit computations directly, but
improves accuracy of the baseline tax-unit income distribution used in Step 5
calibration.

---

## CD2 REEC model — Round 2 refinements (May 14, 2026, late)

Following the May 14 vintage-carryforward correction, five additional
refinements were folded into the REEC fiscal model. Each is independently
toggle-able via parameters on `compute_credit_overlay`; default values
preserve backward compatibility.

### 1. DOTAX TY2018-2022 historical actuals

Replaced the 3%/yr synthetic backcast with measured DOTAX
"Tax Credits Claimed" actuals for TY2018-2022:

| Vintage | Individual ($M) | Corporate+Other ($M) | All ($M) |
|---------|----------------:|---------------------:|---------:|
| TY2018  | $34.21M | $36.29M | $70.50M |
| TY2019  | $44.02M | $16.29M | $60.31M |
| TY2020  | $46.59M | $66.03M | $112.61M |
| TY2021  | $51.45M | $15.86M | $67.32M |
| TY2022  | $55.02M | $50.74M | $105.76M |
| TY2023  | $58.29M | $41.78M | $100.07M |

Individual REEC grew ~10%/yr 2018→2023 — substantially faster than the
3%/yr synthetic backcast. Corporate is volatile (commercial PV
tax-equity transaction timing) and uses `all_total - individual_total`
to capture the disclosure-protected financial-corp pool. Loader is
`scripts/fetch_dotax_credits_historical.py` (one-shot fetch);
parsed CSV at
`packages/tax_modeler/src/tax_modeler/data/raw/dotax_reec_historical.csv`.

### 2. Dynamic AGI eligibility recomputation per year

§235-12.5(a) thresholds ($175K single/HoH/MFS, $350K MFJ) are
unindexed. New helper `compute_dynamic_agi_eligibility_share(projected_units)`
computes the aggregate eligibility share each forecast year from the
projected tax-unit AGI distribution, weighted by TY2023 DOTAX REEC
dollar shares per bin. Replaces the frozen TY2023 PUMS-derived 0.796.
The enhanced forecast calls it for each TY 2027-2031 and passes a
year-specific override.

### 3. Pro-rata demand suppression (endogenous)

§235-12.5(h)'s pro-rata cap allocation discounts the expected value of
each filer's credit when the cap binds. New `pro_rata_elasticity`
parameter applies suppression factor `s = pro_rata^η` to demand. Scenario
bands: LOW η=0.5, MID η=0.3, HIGH η=0.15. Disabled (η=0) for backward
compat.

### 4. Refundable share adjustment for AGI-screened pool

AGI filter removes high-income / high-tax-liability filers; the remaining
pool skews lower-income. Per §235-12.5(k) (30% reduced refundable) and
§235-12.5(l) (auto-refundable for low-AGI), lower-income filers elect
refundability more. New
`_refundable_share_individual_for_eligibility(eligibility_share)` returns
a piecewise estimate (0.23 at 1.0 eligibility → 0.45 at 0.5).

### 5. TY2026 retroactive cap interpretation (A vs B)

Section 9(1) makes Section 1 retroactive to TY2026. §235-12.5(c)(1) caps
CY2027 certifications at $40M. Under interpretation A (CY of certification =
TY of install + 1), CY2027 cap binds TY2026 installations. Under
interpretation B (CY = TY, default), TY2026 is uncapped. New
`interpretation: "A" | "B"` parameter. LOW uses A (conservative for the
State); MID/HIGH/RECESSION use B.

### Round-2 impact on MID 5-year cumulative

| Channel | After May 14 vintage | After Round 2 | Δ |
|---------|---------------------:|--------------:|--:|
| Total fiscal impact | $781.8M | $781.9M | +$0.1M |
| Credit total | $441.9M | $442.0M | +$0.1M |
| Bracket delta | $339.9M | $339.9M | unchanged |

MID barely moves: TY2027 income hasn't grown enough from TY2023 to
materially shift dynamic eligibility (0.796 → ~0.795); pro-rata suppression
reduces both new certs and future drawdown ~symmetrically; the refundable
share shift moves the timing of state cost but not the total. **LOW
shifts +$11M (to $703.7M) because interpretation A caps the TY2026 vintage,
reducing the pre-2027 stock entering the simulation window.**

The bigger value of Round 2 is **diagnostic transparency** rather than
headline fiscal impact: per-year eligibility share, pro-rata factor,
suppression factor, refundable share, and interpretation flag are now
reported per forecast year, enabling clean sensitivity sweeps.

### Files changed

- `packages/tax_modeler/src/tax_modeler/scenarios/sb3125_cd1_credits.py` —
  DOTAX loader, `compute_dynamic_agi_eligibility_share`,
  `_refundable_share_individual_for_eligibility`,
  `_certified_credits_for_vintage` extended, `simulate_reec_state_cost_path`
  extended, `compute_credit_overlay` gains four optional params
- `scripts/fetch_dotax_credits_historical.py` — DOTAX XLSX fetcher/parser
- `packages/tax_modeler/src/tax_modeler/data/raw/dotax_reec_historical.csv`
- `forecast_sb3125_cd2_enhanced.py` — scenario knobs + per-year AGI
  eligibility computation
- `tests/tax_modeler/scenarios/test_sb3125_cd1_credits_v2.py` — 16 new tests

---

## CD2 vintage carryforward correction — May 14, 2026

After reviewing the enrolled CD2 text, the REEC fiscal model was extended to
track nonrefundable credit stock by vintage year. Three findings from the
bill review drove the change:

1. **§235-12.5(j) preserves "until exhausted" carryforward** with no time
   limit and no AGI re-test. The bill amendments do not void or restrict
   credits certified before TY2027 — they remain usable indefinitely
   against future tax liability.
2. **§235-12.5(h) cap applies to DBEDT certifications**, not to utilization
   of previously-certified credits. The $40M aggregate cap therefore does
   not constrain drawdown of pre-2027 vintage stock.
3. **§235-12.5(p) sunset prevails over §235-12.5(c)(4)**: the section
   "shall not apply to taxable years beginning after December 31, 2029."
   TY2030 has no new certifications even though (c)(4) lists a $40M cap
   for CY2030. The legacy static-overlay model treated TY2030 as a cap
   year ($40M payout), materially understating savings.

**Modeling approach.** A vintage simulation tracks individual and corporate
nonrefundable stock from TY2010 forward using the dynamic
`stock_t = (1-u)·(stock_{t-1} + nonref_certs_t)` with `usage_t = u·(stock_{t-1} + nonref_certs_t)`,
where `u = reec_effective_claim_share`. Pre-2023 vintages are back-cast at 3%/yr nominal growth; TY2024–2026 use the model's
nominal income growth × OBBBA demand decay. The simulator is run twice per
target year — once with `cap_enabled=False` (baseline: no cap, no AGI filter,
no sunset) and once with `cap_enabled=True` (bill: AGI filter for TY2027+,
$40M cap for TY2027–2029, zero for TY2030+). State cost in target year =
refundable payments certified that year + nonref stock drawdown. Savings =
baseline state cost − scenario state cost. Pre-2027 stock drawdown is
identical under both paths and cancels in the differential; what remains is
(a) ineligible-by-AGI demand permanently lost in cap years and (b) reduced
future drawdown from capped 2027–2029 vintages.

**Impact on MID results (5-year cumulative, 2027–2031):**

| Channel | Legacy static | Vintage simulation | Δ |
|---------|--------------:|-------------------:|--:|
| REEC savings | $236.3M | $343.3M | +$107.0M |
| Total credit | $334.6M | $441.9M | +$107.3M |
| Total fiscal impact | $674.5M | $781.8M | +$107.3M |

The TY2030 row carries most of the correction (+$50M from properly applying
the (p) sunset instead of treating TY2030 as a $40M cap year).

**Files changed:**
- `packages/tax_modeler/src/tax_modeler/scenarios/sb3125_cd1_credits.py` — added `simulate_reec_state_cost_path`, `_historical_reec_individual/corporate`, `_certified_credits_for_vintage`; added `model_carryforward_pool` flag to `compute_credit_overlay` (default `False` for backward compatibility).
- `forecast_sb3125_cd2_enhanced.py` — now calls overlay with `model_carryforward_pool=True`.

**Interpretation note.** The model uses interpretation B (CY in §235-12.5(c)
maps directly to TY of installation). Interpretation A (CY = TY of
certification = TY of install + 1) produces the same qualitative results —
TY2026–2029 installations are capped at $40M each, TY2030+ blocked by (p).
The difference is bookkeeping only.

---

## CD2 update — May 11, 2026

SB 3125 CD2 has been received and a new `sb3125_cd2` scenario has been
added to the model.

**Key finding:** The brackets loaded in the CSV under the `sb3125_cd1` tag
already reflected the CD2-vintage bracket values (2.50%/5.00% mid rates,
13% at $1M+ MFJ/$750K+ HoH/$500K+ Single). The CD1-labeled brackets in
the codebase were CD2 brackets — so **running `forecast_sb3125_cd2.py`
produces identical fiscal-impact numbers to the existing CD1 forecast**.

The `sb3125_cd2` tag in the CSV and `get_sb3125_cd2_system()` in the
registry are now the authoritative labels going forward.

**What CD2 adds vs the "CD1" that was modeled:**

Credit provisions — all already reflected in `sb3125_cd1_credits.py`
(reused by `forecast_sb3125_cd2.py`):
- §235-12.5 REEC: AGI limits $175K single / $350K MFJ, $40M cap 2027–2030, sunset after Dec 31, 2029
- §235-110.7 CGEC: sunset after Dec 31, 2027
- Act 261 §5 TCRA: repeal accelerated to Jan 1, 2029

New repeals in CD2 **not yet modeled** (treated as $0):
- §235-110.51 Technology Infrastructure Renovation Tax Credit: repealed TY 2028+ — no TY2023 DOTAX line data available; estimated near-zero
- §235-110.9 High Technology Business Investment Tax Credit: repealed TY 2029+ — credit was carryforward-only by TY2023; estimated near-zero

**New files added:**
- `reforms/sb3125_cd2.yaml`
- `forecast_sb3125_cd2.py` (output: `/tmp/sb3125_cd2_fiscal_impact_2027_2031.csv`)

---

## Methodology revisions — May 2026

The following corrections were merged after the May 2026 review and supersede
the corresponding sections below; results in Section 10 will refresh on the
next forecast run.

1. **Per-filer ETI based on actual MTR change.** The old ETI step
   applied a flat ``((1 − 0.13)/(1 − 0.11)) ** eti`` factor to every
   filer above the new 13% threshold. SB 3125 CD1 raises rates across
   the entire $350K–$1M MFJ range (and equivalents for HoH/Single), not
   just at $1M+, so the old approach attributed *zero* behavioral
   response to those mid-tier rate increases — overstating the static
   bracket gain in the upper-middle band. The new
   :func:`apply_eti_response` looks up each filer's marginal rate under
   both Act 46 and SB 3125 CD1 (via vectorized bracket-boundary
   ``searchsorted``) and applies the ETI factor based on the actual
   per-filer net-of-tax change. Filers facing no rate change get
   factor 1.0; filers facing a rate cut also get 1.0 (asymmetric
   treatment, matching the literature).

2. **Effective deduction plumbed into the bracket comparison.**
   ``project_tax_units_forward`` already computes each filer's
   effective deduction (the larger of standard and Pease-limited
   itemized) and stores it as ``hi_standard_deduction``. Previously
   ``compare_systems`` ignored that column and applied the standard
   deduction on its own, which forced a separate
   ``apply_itemized_deduction_adjustment`` step that subtracted a
   flat $40K–$80K from each top filer's income as a stand-in.
   ``compare_systems`` now accepts a ``deduction_col`` parameter; the
   enhanced forecast passes ``"hi_standard_deduction"`` for both
   baseline and scenario, so the bracket comparison uses the same
   per-filer deduction as the projection step. The per-scenario
   ``itemized_adj`` flag has been retired.

3. **REEC: residential vs commercial demand decay.** OBBBA terminated
   §25D (residential) but extended §48E (commercial) through
   12/31/2027. The old code applied the §25D-based demand decay
   (`obbba_mid`, `obbba_severe`) to *both* individual and corporate
   REEC pools, understating corporate baseline demand by ~10–20%.
   The new ``_reec_demand_factor_corporate`` returns 1.0 for all
   forecast years; only individual / residential REEC sees the §25D
   decay.

4. **REEC: refundable / nonrefundable utilization split.** The old
   ``effective_claim_share`` parameter was applied uniformly to all
   REEC dollars. But refundable claims offset state revenue 1:1; only
   nonrefundable claims have utilization concerns (carry-forward,
   expiration). DOTAX 2023 actuals: individual REEC is ~23%
   refundable, corporate REEC is ~89% refundable. The parameter has
   been re-interpreted as a *nonrefundable utilization rate*; the
   aggregate effective share is computed per pool. At the MID setting
   of 0.80, individual aggregate share is ~85% and corporate is ~98%
   (vs the previous 80% for both).

5. **Top-income growth premium base-year alignment.** Previously
   ``TOP_INCOME_PREMIUM_BASE_YEAR = 2023`` while the PUMS panel and
   B19013 county projections anchor on 2024 (the most recent ACS
   1-year vintage in the bundled panel). Compounding from 2023 added
   one extra year of premium on top of the projection. Base year is
   now 2024; the MID multiplier for TY 2027 falls from
   ``1.013⁴ = 1.053`` (+5.3%) to ``1.013³ = 1.040`` (+4.0%).

---

## Table of Contents

1. [Overview](#1-overview)
2. [Bill Summary](#2-bill-summary)
3. [Act 46 vs SB 3125 CD1 — Bracket-by-Bracket Comparison](#3-act-46-vs-sb-3125-cd1--bracket-by-bracket-comparison)
4. [Data Sources](#4-data-sources)
5. [Methodology](#5-methodology)
6. [Behavioral Response](#6-behavioral-response)
7. [Credit Overlay](#7-credit-overlay)
8. [Scenario Design](#8-scenario-design)
9. [Distributional Analysis](#9-distributional-analysis)
10. [Results](#10-results)
11. [Caveats and Limitations](#11-caveats-and-limitations)
12. [Scripts and File Map](#12-scripts-and-file-map)
13. [Software and Packages](#13-software-and-packages)

---

## 1. Overview

This forecast estimates the year-by-year fiscal impact to the State of Hawaii from enacting **SB 3125 CD1** (2026 conference draft) relative to the current-law baseline of **Act 46 (2024)** for tax years 2027 through 2031.

The model uses a **bottom-up microsimulation** approach: it constructs roughly 43,000 representative Hawaii income tax units from the U.S. Census Bureau's Public Use Microdata Sample, calibrates them against DOTAX administrative data, projects them forward year by year using county-level income growth forecasts, and computes each unit's tax liability under both the baseline and the proposed law. The total fiscal impact is the population-weighted difference, adjusted for behavioral responses and a separate static-scoring credit overlay.

**MID scenario 5-year result: $673.0M** (May 7, 2026 re-run incorporating population growth, COR March 2026 projections, and updated calibration. PTE shift is currently zero in this run — see Section 8a. Credit overlay revised down to $334.6M from earlier $503.2M estimate due to updated REEC and CGEC baseline projections.)

---

## 2. Bill Summary

SB 3125 CD1 changes Hawaii's individual income tax in three ways:

### 2a. §235-51 Bracket Changes (Effective TY 2027 and TY 2029)

The bill strikes Act 46's scheduled bracket phase-ins and replaces them with two new schedules:

| Change | Act 46 Rate | SB 3125 CD1 Rate | Who It Affects |
|--------|-------------|------------------|----------------|
| Second bracket cut | 3.20% | 2.50% | Income above ~$28,800 (MFJ) / $14,400 (Single) |
| Third bracket cut | 5.50% | 5.00% | Income above ~$38,400 (MFJ) / $19,200 (Single) |
| New top bracket | 11% (max) | **13%** | Income above $1,000,000 (MFJ) / $750,000 (HoH) / $500,000 (Single) |

The 1.40% bottom bracket rate is **unchanged** in both systems — Act 46 and SB 3125 CD1 use an identical 1.40% rate and identical bracket width in all modeled years. Act 46's phase-in widens the 1.40% bracket threshold (from $19,200 to $38,400 MFJ by 2029); SB 3125 CD1 preserves these same expanded thresholds.

A second set of bracket schedules takes effect for TY 2029 (per bill text "after December 31, 2028"), further widening the lower brackets. Both schedules are modeled explicitly.

### 2b. §235-12.5 Renewable Energy Technologies Income Tax Credit (REEC)

- Caps aggregate annual claims at **$40M for TY 2027–2030**
- Eliminates the credit entirely **from TY 2031** (cap → $0)
- Adds AGI eligibility limits: $175K single / $350K joint

DOTAX TY2023 baseline: $99.6M in total REEC claims ($58.3M individual + $38.6M corporate + $3.2M other).

### 2c. §235-110.7 Capital Goods Excise Tax Credit (CGEC)

- Sunsets effective December 31, 2027 — applies from **TY 2028** onward
- DOTAX TY2023 baseline: $34.6M in total CGEC claims (rising trend from $29.3M in 2021)

### 2d. §235-110.91 Tax Credit for Research Activities (TCRA)

- Accelerated wind-down relative to Act 46 baseline
- One-time acceleration effect modeled for **TY 2029** only (~$8–9M)

---

## 3. Act 46 vs SB 3125 CD1 — Bracket-by-Bracket Comparison

The tables below show every bracket for each filing status and each effective period. Cells marked **bold** differ between the two systems. A "—" means no bracket exists at that threshold under that system.

> **How to read these tables:** Each row is a bracket that begins at the listed income threshold and runs to the next row's threshold. The rate shown applies to income within that range only (Hawaii uses a progressive structure). The 1.40% bottom bracket is identical in both systems across all years — Act 46's phase-ins widen it without changing the rate.

---

### Married Filing Jointly / Qualifying Surviving Spouse

#### TY 2027–2028

| Income Threshold | Act 46 Rate | SB 3125 CD1 Rate | Change |
|-----------------|------------|-----------------|--------|
| $0 | 1.40% | 1.40% | — |
| $28,800 | 3.20% | **2.50%** | **−0.70 pp** |
| $38,400 | 5.50% | **5.00%** | **−0.50 pp** |
| $48,000 | 6.40% | 6.40% | — |
| $72,000 | 6.80% | 6.80% | — |
| $96,000 | 7.20% | 7.20% | — |
| $250,000 | 7.60% | 7.60% | — |
| $350,000 | 7.90% | **8.25%** | **+0.35 pp** |
| $450,000 | 8.25% | **9.00%** | **+0.75 pp** |
| $550,000 | 9.00% | **10.00%** | **+1.00 pp** |
| $650,000 | 10.00% | **11.00%** | **+1.00 pp** |
| $800,000 | 11.00% | 11.00%¹ | — |
| $1,000,000 | — | **13.00%** | **New bracket** |

¹ Under SB 3125 CD1, the 11% bracket runs from $650K to $1M (a narrower range than Act 46's $800K–∞). The 13% bracket then applies above $1M.

#### TY 2029–2031

| Income Threshold | Act 46 Rate | SB 3125 CD1 Rate | Change |
|-----------------|------------|-----------------|--------|
| $0 | 1.40% | 1.40% | — |
| $38,400 | 3.20% | **2.50%** | **−0.70 pp** |
| $48,000 | 5.50% | **5.00%** | **−0.50 pp** |
| $72,000 | 6.40% | 6.40% | — |
| $96,000 | 6.80% | 6.80% | — |
| $250,000 | 7.20% | 7.20% | — |
| $350,000 | 7.60% | **8.25%** | **+0.65 pp** |
| $450,000 | 7.90% | **9.00%** | **+1.10 pp** |
| $550,000 | 8.25% | **10.00%** | **+1.75 pp** |
| $650,000 | 9.00% | **11.00%** | **+2.00 pp** |
| $800,000 | 10.00% | — | *(absorbed into 11% bracket)* |
| $950,000 | 11.00% | 11.00%¹ | — |
| $1,000,000 | — | **13.00%** | **New bracket** |

---

### Head of Household

#### TY 2027–2028

| Income Threshold | Act 46 Rate | SB 3125 CD1 Rate | Change |
|-----------------|------------|-----------------|--------|
| $0 | 1.40% | 1.40% | — |
| $21,600 | 3.20% | **2.50%** | **−0.70 pp** |
| $28,800 | 5.50% | **5.00%** | **−0.50 pp** |
| $36,000 | 6.40% | 6.40% | — |
| $54,000 | 6.80% | 6.80% | — |
| $72,000 | 7.20% | 7.20% | — |
| $187,500 | 7.60% | 7.60% | — |
| $262,500 | 7.90% | **8.25%** | **+0.35 pp** |
| $337,500 | 8.25% | **9.00%** | **+0.75 pp** |
| $412,500 | 9.00% | **10.00%** | **+1.00 pp** |
| $487,500 | 10.00% | **11.00%** | **+1.00 pp** |
| $600,000 | 11.00% | 11.00%¹ | — |
| $750,000 | — | **13.00%** | **New bracket** |

¹ SB 3125 CD1 narrows the 11% bracket to $487,500–$750,000; above $750,000 the 13% rate applies.

#### TY 2029–2031

| Income Threshold | Act 46 Rate | SB 3125 CD1 Rate | Change |
|-----------------|------------|-----------------|--------|
| $0 | 1.40% | 1.40% | — |
| $28,800 | 3.20% | **2.50%** | **−0.70 pp** |
| $36,000 | 5.50% | **5.00%** | **−0.50 pp** |
| $54,000 | 6.40% | 6.40% | — |
| $72,000 | 6.80% | 6.80% | — |
| $187,500 | 7.20% | 7.20% | — |
| $262,500 | 7.60% | **8.25%** | **+0.65 pp** |
| $337,500 | 7.90% | **9.00%** | **+1.10 pp** |
| $412,500 | 8.25% | **10.00%** | **+1.75 pp** |
| $487,500 | 9.00% | **11.00%** | **+2.00 pp** |
| $600,000 | 10.00% | — | *(absorbed into 11% bracket)* |
| $712,500 | 11.00% | 11.00%¹ | — |
| $750,000 | — | **13.00%** | **New bracket** |

---

### Single / Married Filing Separately

#### TY 2027–2028

| Income Threshold | Act 46 Rate | SB 3125 CD1 Rate | Change |
|-----------------|------------|-----------------|--------|
| $0 | 1.40% | 1.40% | — |
| $14,400 | 3.20% | **2.50%** | **−0.70 pp** |
| $19,200 | 5.50% | **5.00%** | **−0.50 pp** |
| $24,000 | 6.40% | 6.40% | — |
| $36,000 | 6.80% | 6.80% | — |
| $48,000 | 7.20% | 7.20% | — |
| $125,000 | 7.60% | 7.60% | — |
| $175,000 | 7.90% | **8.25%** | **+0.35 pp** |
| $225,000 | 8.25% | **9.00%** | **+0.75 pp** |
| $275,000 | 9.00% | **10.00%** | **+1.00 pp** |
| $325,000 | 10.00% | **11.00%** | **+1.00 pp** |
| $400,000 | 11.00% | 11.00%¹ | — |
| $500,000 | — | **13.00%** | **New bracket** |

¹ SB 3125 CD1 narrows the 11% bracket to $325,000–$500,000; above $500,000 the 13% rate applies.

#### TY 2029–2031

| Income Threshold | Act 46 Rate | SB 3125 CD1 Rate | Change |
|-----------------|------------|-----------------|--------|
| $0 | 1.40% | 1.40% | — |
| $19,200 | 3.20% | **2.50%** | **−0.70 pp** |
| $24,000 | 5.50% | **5.00%** | **−0.50 pp** |
| $36,000 | 6.40% | 6.40% | — |
| $48,000 | 6.80% | 6.80% | — |
| $125,000 | 7.20% | 7.20% | — |
| $175,000 | 7.60% | **8.25%** | **+0.65 pp** |
| $225,000 | 7.90% | **9.00%** | **+1.10 pp** |
| $275,000 | 8.25% | **10.00%** | **+1.75 pp** |
| $325,000 | 9.00% | **11.00%** | **+2.00 pp** |
| $400,000 | 10.00% | — | *(absorbed into 11% bracket)* |
| $475,000 | 11.00% | 11.00%¹ | — |
| $500,000 | — | **13.00%** | **New bracket** |

---

### Summary: What Changes and for Whom

| Income Band (MFJ example) | Net Rate Change TY2027 | Net Rate Change TY2029 | Effect |
|--------------------------|------------------------|------------------------|--------|
| $0 – $28,800 | None | None | Unchanged |
| $28,800 – $38,400 | **−0.70 pp** (3.20→2.50) | **−0.70 pp** (3.20→2.50) | Tax cut |
| $38,400 – $48,000 | **−0.50 pp** (5.50→5.00) | **−0.50 pp** (5.50→5.00) | Tax cut |
| $48,000 – $250,000 | None | None | Unchanged |
| $250,000 – $350,000 | None | None | Unchanged |
| $350,000 – $450,000 | **+0.35 pp** (7.90→8.25) | **+0.65 pp** (7.60→8.25) | Tax increase |
| $450,000 – $550,000 | **+0.75 pp** (8.25→9.00) | **+1.10 pp** (7.90→9.00) | Tax increase |
| $550,000 – $650,000 | **+1.00 pp** (9.00→10.00) | **+1.75 pp** (8.25→10.00) | Tax increase |
| $650,000 – $1,000,000 | **+1.00 pp** (10.00→11.00) | **+2.00 pp** (9.00→11.00) | Tax increase |
| Above $1,000,000 | **+2.00 pp** (11.00→13.00) | **+2.00 pp** (11.00→13.00) | Tax increase |

> **Key observation:** The bill is not simply "low rates cut, high rates raised." Rates in the $350K–$1M range are also raised — by up to 2 pp under the TY2029 schedule. This means a meaningful portion of the revenue gain comes from earners well below the $1M threshold. The upper-middle bracket increases grow larger over time because Act 46 progressively lowers those rates in 2027 and 2029, widening the gap that SB 3125 CD1 then closes upward.

---

## 4. Data Sources

### Microdata
| Source | Description | Use |
|--------|-------------|-----|
| **ACS 5-Year PUMS 2020–2024** | U.S. Census Bureau, Hawaii (State FIPS 15) — `psam_p15.csv` / `psam_h15.csv` | Base population of tax units |
| **IRS Statistics of Income (SOI) 2022, Table A8 — Hawaii** | High-income filer count and tax by AGI bracket | Targets for top-income synthesis: 1,824 filers at $1M+, $663M in tax |
| **DOTAX "Tax Credits Claimed by Hawai`i Taxpayers — Tax Year 2023"** | Table A-1 (REEC aggregate), Table A-5 (REEC by AGI bin), line 1490 (CGEC) | Credit overlay baseline values |

### Administrative Benchmarks
| Source | Description | Use |
|--------|-------------|-----|
| **DOTAX TY2023 aggregate statistics** | Revenue by filing status and AGI bracket | IPF calibration targets |
| **Hawaii Council on Revenues (COR), September 2025 Forecast** | FY2027 individual income tax projection: $3.05B | Baseline validation (microsim gap documented) |

### Legal / Statutory
| Source | Description |
|--------|-------------|
| **Act 46, SLH 2024** | Current-law baseline bracket schedules and phase-in dates |
| **SB 3125 CD1 (2026 conference draft)** | Bill text — bracket schedules, credit cap amounts, effective dates |
| **Act 50, SLH 2024** | Hawaii Pass-Through Entity (PTE) tax — rate fixed at **9%** for TY2024+, does not auto-track individual rate |

### Economic Projections
| Source | Description | Use |
|--------|-------------|-----|
| **ACS B19013 (Median Household Income by County)** | Census Bureau, bundled ACS panel | County-level income growth rates for TY projection |
| **SEIA U.S. Solar Market Insight (2025)** | National residential solar demand forecasts | REEC demand decay scenarios post-OBBBA |

### Academic Literature (Behavioral Response)
| Citation | Use |
|----------|-----|
| Saez, Slemrod & Giertz (2012), "The Elasticity of Taxable Income with Respect to Marginal Tax Rates," *Journal of Economic Literature* | ETI range: 0.15–0.60 |
| Young, Varner, Lurie & Prisinzano (2016), "Millionaire Migration and Taxation of the Elite," *American Sociological Review* | Top-1% migration elasticity: 0.05–0.15 per pp rate change |
| Rauh & Shyu (2024), California 13.3% top-rate study | State-level ETI calibration anchor for MID scenario |
| IRS SOI migration data — Hawaii high-income outmigration trends | Migration response calibration |

---

## 5. Methodology

### Step 1 — Load PUMS

**Script:** `forecast_sb3125_cd1.py` → `PUMSDataLoader`  
**File:** `packages/tax_modeler/src/tax_modeler/loaders/pums_loader.py`

Loads Hawaii person and household records from the ACS 5-year PUMS CSV files (`psam_p15.csv`, `psam_h15.csv`). The loader handles cross-vintage column renaming (e.g., `STATE`→`ST`) and batches reads to manage memory. Income variables are adjusted using ADJINC (1.222017 for the 2020–2024 vintage, representing the 5-year inflation adjustment to 2024 dollars).

### Step 2 — Construct Tax Units

**Class:** `TaxUnitConstructor`  
**File:** `packages/tax_modeler/src/tax_modeler/units/constructor.py`

Assembles person and household PUMS records into income tax filing units using rule-based logic:

- **Head of household:** Single filer with qualifying dependent(s)
- **Married filing jointly:** Married couple in same household
- **Single / married filing separately:** All other configurations

Each unit inherits the household weight (`WGTP`) as its initial statistical weight representing the number of real Hawaii filers it stands in for. Income components (wages `WAGP`, self-employment `SEMP`, interest `INTP`, retirement `RETP`, Social Security `SSP`, etc.) are summed across the primary filer and spouse. Results are cached at `/tmp/tax_units_cache.parquet` to avoid the ~3-minute rebuild on repeated runs (~43,300 units before top-income synthesis).

### Step 3 — Enrich for Credits

**Function:** `_enrich_for_credits()`  
**File:** `packages/tax_modeler/src/tax_modeler/pipeline.py`

Adds credit-eligibility fields needed for the REEC AGI eligibility test (Hawaii §235-12.5 AGI limits: $175K single / $350K joint). Derives `agi_approx` from the income components and flags units as eligible or ineligible for the credit overlay.

### Step 4 — Compute Base Tax

**Function:** `_compute_base_tax()`  
**File:** `packages/tax_modeler/src/tax_modeler/pipeline.py`

Runs `TaxCalculator.calculate_tax()` on each unit using the current-law bracket schedule (Act 46, TY2025 parameters). Produces `base_tax_liability`, `marginal_rate`, and `effective_rate` columns used downstream for calibration and ETI calculations.

### Step 5 — IPF Rake Calibration

**Function:** `apply_ipf_calibration_via_rake()`  
**File:** `packages/tax_modeler/src/tax_modeler/calibration.py`

Iterative Proportional Fitting (IPF) adjusts unit weights so the PUMS-derived totals match DOTAX administrative benchmarks across multiple dimensions simultaneously (filing status × AGI bracket). Weight cap: 1.5× original weight per unit to prevent extreme upweighting of a single record. This step corrects the known PUMS undercount of higher-income filers within the range reachable by reweighting alone.

### Step 6 — Top-Income Synthesis (Pareto)

**Function:** `synthesize_top_filers()`  
**File:** `packages/tax_modeler/src/tax_modeler/scenarios/top_income_synthesis.py`

**Why this step exists:** The IPF rake can close small gaps but cannot close the 5× gap at $1M+. The ACS PUMS contains only ~342 weighted filers above $1M (after calibration) vs. the DOTAX/IRS SOI target of 1,824. This 5× undercount would make the 13% top bracket appear almost invisible in the model.

**How it works:** Generates synthetic tax units with incomes drawn from a Pareto distribution with shape parameter α (default α = 1.5, calibrated to match the IRS SOI 2022 Hawaii tail shape). These units are given realistic filing-status mixes (drawn from the DOTAX TY2023 $1M+ filer population: ~65% MFJ, ~25% Single, ~8% HoH, ~2% MFS) and are added to the calibrated dataset. Base tax is recomputed for all units after synthesis.

**Validation target:** 1,824 weighted $1M+ filers with $663M in aggregate tax (from IRS SOI 2022 Hawaii Table A8 and DOTAX TY2023). The synthesis hits 100% of the filer count target by construction.

### Step 6a — Synthetic Tail Tax-Target Calibration

**Function:** `rescale_synthetic_tail_to_tax_target()`  
**File:** `packages/tax_modeler/src/tax_modeler/scenarios/top_income_synthesis.py`

**Why this step exists:** The Pareto conditional-mean income formula slightly underestimates income concentration above ~$10M — the very top of the tail — causing the raw synthesis to recover only ~88% of the $663M tax benchmark. A 12% shortfall in the baseline tax at $1M+ directly translates to a ~12% undercount of marginal revenue from the 13% bracket, approximately $14–17M per year.

**How it works:** After `synthesize_top_filers()` and an initial `_compute_base_tax()` call, a uniform scale factor `k` is computed:

```
k = target_tax_m / actual_tax_on_synthetic_1m_plus_filers
```

All income-related columns (`income`, `agi`, `synthetic_total_income`, `earned_income`, `investment_income`, etc.) on synthetic rows are multiplied by `k`. Tax columns are cleared and `_compute_base_tax()` is re-run, after which `validate_top_synthesis()` confirms the tax target ratio rises to ≥99.5%.

**Why single-pass k is sufficient:** Hawaii's top income tax bracket is linear above the $200K threshold (11% marginal rate for Act 46). At $1M+ incomes, the effective marginal rate is approximately flat, so `tax ≈ k × income × rate`. A single application of k achieves the target within 0.5% without iteration.

**Per-scenario k values** (from most recent forecast run):

| Scenario | Pareto α | tail_k | Post-scale tax ratio |
|----------|----------|--------|----------------------|
| LOW      | 1.7      | 1.5745 | 100.0%               |
| MID      | 1.5      | 1.2793 | 100.0%               |
| HIGH     | 1.4      | 1.1001 | 100.0%               |

k is larger for the LOW scenario (α=1.7, thinner tail → lower initial tax capture) and smaller for HIGH (α=1.4, fatter tail → higher initial tax capture). k values are also elevated by the §235-16 capital gains cap (Step 10a): correctly applying the 7.25% CG cap to synthetic filers reduces simulated tax below the $663M target, requiring a larger scaling factor to close the gap. Each scenario is independently calibrated to the same $663M DOTAX benchmark.

### Step 7 — Project to Target Year

**Function:** `project_tax_units_forward()`  
**File:** `packages/tax_modeler/src/tax_modeler/projection/tax_unit_projector.py`

Scales each unit's income from the PUMS base year to each target year (2027–2031) using **county-specific income growth factors** derived from the ACS B19013 (Median Household Income) panel:

```
growth_factor(county, year) = projected_B19013(county, year) / anchor_B19013(county, base_year)
```

Hawaii's four counties (Honolulu, Maui, Hawaii, Kauai) each get their own growth trajectory. Kalawao County (~90 residents) is redirected to the Maui forecast. The `method="ensemble"` option uses the census_forecaster's ensemble projector for point estimates with 90% confidence intervals. All units in a given county receive the same multiplicative income scaling (proportional growth).

### Step 8 — Top-Income Growth Premium (MID/HIGH scenarios)

**Function:** `apply_top_income_growth_premium()`
**File:** `packages/tax_modeler/src/tax_modeler/scenarios/behavioral_response.py`

Applies an additional annual growth premium to units with income above $500K, on top of the county-level B19013 scaling. This corrects for the known divergence between top-1% income growth and median-anchored projections.

**Empirical calibration (IRS SOI 2012–2019):** The $500K+ AGI bracket nationally averaged ~3.0%/yr real growth vs. ~1.2%/yr for the median — a structural differential of ~1.8pp/yr. A 0.5pp Hawaii outmigration haircut (Young & Varner 2016 top-1% migration elasticity applied to Hawaii's geography) yields the MID anchor of **+1.3%/yr**. LOW and HIGH are symmetric ±1.0pp bounds:

| Scenario | Premium | Rationale |
|----------|---------|-----------|
| LOW | +0.3%/yr | Strong outmigration suppresses Hawaii top-income growth to near-median |
| **MID** | **+1.3%/yr** | IRS SOI 1.8pp national differential minus 0.5pp Hawaii haircut |
| HIGH | +2.3%/yr | Hawaii top-income growth converges toward national rates |

Formula: `multiplier = (1 + annual_premium)^(target_year − 2024)`. The base
year is **2024** to match the PUMS panel anchor (the bundled ACS 5-year
2020–2024 vintage is inflation-adjusted to 2024 dollars, and the
county B19013 projector anchors on the most recent 1-year ACS observation
— also 2024). For MID at TY 2027: 1.013³ = 1.040 (+4.0% vs. the
county-median-anchored projection). The previous version used base
year 2023, which compounded one extra year of premium on top of the
projection.

### Step 9 — Effective Deduction (per-filer, plumbed through comparison)

**File:** `packages/tax_modeler/src/tax_modeler/projection/tax_unit_projector.py`,
`packages/tax_modeler/src/tax_modeler/liability/hawaii.py`,
`packages/tax_modeler/src/tax_modeler/config/tax_system_config.py`

`project_tax_units_forward` computes each filer's effective deduction —
the larger of the year-appropriate standard deduction and the
expected-value itemized deduction (mortgage interest with homeownership
probability + tier-banded charitable + medical expenses + real-estate
taxes, with Hawaii's Pease limitation applied) — and stores it as
`hi_standard_deduction`. The enhanced forecast passes that column to
`compare_systems` via the new `deduction_col` parameter, so the
bracket comparison applies each filer's actual effective deduction
under both Act 46 and SB 3125 CD1.

This replaces the prior `apply_itemized_deduction_adjustment` step,
which subtracted a flat dollar amount ($40–$80K depending on filing
status) from each top filer's income to approximate the same effect.
The flat-amount approach was crude (real itemized deductions scale
with AGI — federal income tax paid alone is ~$300K+ at $1M AGI) and
required a per-scenario `itemized_adj` flag (with HIGH turning it off
entirely, which inflated HIGH's bracket gain by overstating the
taxable base). Both have been retired.

### Step 10 — Per-Unit Tax Calculation

**Class:** `TaxCalculator`  
**File:** `packages/tax_modeler/src/tax_modeler/config/tax_system_config.py`

For each projected unit, `TaxCalculator.calculate_tax()` computes tax liability under a given `TaxSystemConfig`. It applies the bracket schedule (looked up from the master CSV by year and scenario tag), computes taxable income after standard deduction and personal exemptions, applies brackets progressively, and returns tax liability along with marginal rate and effective rate.

Two configs are constructed for each year:

- `TaxSystemRegistry.get_act46_system(year)` — baseline Act 46 brackets
- `TaxSystemRegistry.get_sb3125_cd1_system(year)` — SB 3125 CD1 brackets (scenario tag `sb3125_cd1`, bracket_year 2027 for TY 2027–2028, bracket_year 2029 for TY 2029+)

The delta (SB 3125 CD1 minus Act 46) is the static bracket change before behavioral corrections.

### Step 10a — Capital Gains Cap (Hawaii §235-16)

**Implementation:** `TaxCalculator.calculate_tax()` (both `tax_system_config.py` and `liability/hawaii.py`)

Hawaii HRS §235-16 caps the tax rate on net long-term capital gains at **7.25%** of the gain. This is applied in the model using the "stack" method:

```
ordinary_tax      = brackets applied to (total_income − cg_income)
cg_tax_uncapped   = total_bracket_tax − ordinary_tax
cg_tax_capped     = min(cg_tax_uncapped, cg_income × 7.25%)
final_tax         = ordinary_tax + cg_tax_capped
```

**SB 3125 CD1 does not change the §235-16 cap.** It remains 7.25% under both Act 46 and SB 3125 CD1. This means the 13% new bracket applies only to the *ordinary income* portion of $1M+ filer AGI — the CG portion is already taxed at a flat 7.25% and sees zero bracket delta from the bill.

**Data source for CG share:** Synthetic $1M+ filers carry a `synthetic_cg_share` column (derived from IRS SOI Hawaii high-income composition data). Base PUMS units default to `cg_share=0` — ACS does not capture realized capital gains for sub-$1M filers, consistent with their negligible incidence there.

**Model impact:** Correctly applying the CG cap reduces the simulated baseline tax on synthetic filers, which in turn requires a larger tail_k in Step 6a to reach the $663M target. The cap also reduces the static bracket delta — income that was previously over-taxed at bracket rates is correctly taxed at 7.25%, leaving less incremental revenue when the 13% bracket applies only to the ordinary component.

### Step 11 — Bracket Schedules (Master CSV)

**File:** `packages/tax_modeler/src/tax_modeler/data/raw/hawaii_tax_brackets_master_all.csv`

Contains all bracket schedules as rows with columns: `income_min`, `income_max`, `rate`, `base_tax`, `base_income`, `year`, `filing_status`, `scenario`.

| Year | Scenario tag | Description |
|------|-------------|-------------|
| 2018 | *(blank)* | Pre-Act 46 baseline |
| 2025 | *(blank)* | Act 46 first phase-in |
| 2027 | *(blank)* | Act 46 second phase-in (baseline for TY2027–2028) |
| 2029 | *(blank)* | Act 46 third phase-in (baseline for TY2029+) |
| 2027 | `sb3125_cd1` | SB 3125 CD1 TY2027–2028 schedules |
| 2029 | `sb3125_cd1` | SB 3125 CD1 TY2029+ schedules |

The `_bracket_year()` lookup selects the largest available vintage year ≤ the target year, so adding 2027 and 2029 entries automatically covers all five forecast years.

---

## 6. Behavioral Response

**File:** `packages/tax_modeler/src/tax_modeler/scenarios/behavioral_response.py`

Three behavioral channels are modeled, applied to the projected population before revenue comparison. All are applied only to filers above the new 13% threshold (~$500K+).

### 5a. Taxable Income Elasticity (ETI) — per-filer MTR change

High-income filers reduce their *reported* taxable income in response to a higher marginal rate — through increased charitable giving, deferred compensation, additional retirement contributions, and accelerated deductions. The standard form is:

```
%ΔTaxable Income = ETI × %Δ(1 − MTR)
```

The model computes each filer's marginal rate under both Act 46
and SB 3125 CD1 (vectorized bracket-boundary lookup on
``income − effective_deduction − exemption``) and applies the ETI
factor based on the actual per-filer rate change:

```
factor = ((1 − scen_mtr) / (1 − base_mtr)) ** ETI
```

This correctly captures the rate increases that SB 3125 CD1 applies
across $350K–$1M MFJ (and equivalents) as well as the new 13% bracket
above $1M. The previous implementation hard-coded ``base_mtr = 11%``
and ``scen_mtr = 13%`` for filers above the new top threshold and
applied no ETI at all to mid-tier filers, even though those filers
also face rate increases under the bill. Filers facing no rate change
(or a rate cut) get factor 1.0 — the literature is asymmetric and
rate cuts have weaker, less-established income-shrinkage feedback.

**Source:** Saez, Slemrod & Giertz (2012); state-level calibration from Rauh & Shyu (2024) California 13.3% study.

| Scenario | ETI | 5-year revenue impact (pending refresh) |
|----------|-----|----------------------|
| LOW (high behavioral) | 0.60 | −$81M (pre-fix) |
| **MID** | **0.40** | **−$71M (pre-fix)** |
| HIGH (low behavioral) | 0.15 | −$27M (pre-fix) |

Per-filer ETI will *increase* the absolute behavioral offset relative
to the prior version because filers in $350K–$1M who previously got
no ETI now contribute. Magnitude depends on bracket-by-bracket rate
change × that bracket's income mass. Awaiting forecast re-run.

### 5b. Migration Response

Some high-earners leave Hawaii when rates rise. Young & Varner (2016) estimate a top-1% migration elasticity of ~0.10–0.15 per percentage-point rate change. Applied as a weight reduction on $1M+ filers, phased in linearly over 5 years from TY2027 (migration is slow — people don't leave overnight). A 50% discount is applied relative to the published national elasticities to account for Hawaii's unique geography (harder to leave than New Jersey, the focus of most migration studies).

| Scenario | Migration elasticity | Effect |
|----------|---------------------|--------|
| LOW | 0.15 | Largest filer-count reduction |
| **MID** | **0.10** | Included in −$71M ETI figure above |
| HIGH | 0.05 | Minimal |

### 5c. Pass-Through Entity (PTE) Election — Dominant Behavioral Offset

**This is the largest single behavioral offset in the model.**

Hawaii's Act 50 (SLH 2024) created a PTE tax at a fixed rate of **9%** for TY2024 and beyond. Critically, this rate does **not** automatically track the individual income tax rate. When SB 3125 CD1 raises the individual top rate to 13%, pass-through business owners (S-corps, partnerships, LLCs) face a **4-percentage-point arbitrage**: paying at the entity level (9%) vs. the individual level (13%).

A modeled share of eligible $1M+ pass-through filers elect PTE treatment, shifting their income out of the individual return and into the entity-level PTE return. This reduces individual income tax revenue by:

```
PTE revenue loss = eligible_ordinary_income × rate_differential × pte_capture
                 = (ordinary pass-through income above threshold) × 4% × capture_rate
```

**Capital gains are excluded from the PTE election pool** for two independent reasons:
1. CG income is not pass-through business income and is ineligible for HRS §235-110.93 election by statute.
2. Even if theoretically eligible, electing PTE on CG income would be irrational: the PTE rate (9%) exceeds the §235-16 CG cap (7.25%), so any rational filer would pay the cap rate rather than elect PTE.

In practice, the model uses `synthetic_cg_share` to compute `ordinary_income = total_income × (1 − cg_share)`, and the PTE excess is computed on ordinary income only. This reduces the PTE offset by approximately 50% relative to using total income, consistent with the high CG share (~50%) of $1M+ filer income.

| Scenario | PTE capture rate | 5-year revenue loss |
|----------|-----------------|---------------------|
| LOW | 90% | ~−$194M |
| **MID** | **70%** | **~−$185M** |
| HIGH | 40% | ~−$147M |

**Source:** Hawaii HRS §235-110.93 (Act 50, 2024); PTE rate confirmed at 9% via legislative history. CG ineligibility confirmed by statute (§235-110.93 applies to "qualified net income" of the entity, not to individual capital gains).

---

## 7. Credit Overlay

**File:** `packages/tax_modeler/src/tax_modeler/scenarios/sb3125_cd1_credits.py`  
**Function:** `compute_credit_overlay(target_year, reec_demand_scenario, ...)`

The REEC, CGEC, and TCRA credit changes are **aggregate static-scoring overlays** — they cannot be attributed to individual PUMS filers because credit claim data only exists at aggregate level from DOTAX reports. They are computed separately and added to the bracket microsimulation result.

### 6a. REEC — Renewable Energy Technologies Income Tax Credit

**DOTAX TY2023 baseline:** $99.6M total claims
- Individual refundable: $13.4M (~23% of $58.3M individual)
- Individual nonrefundable: $44.9M (~77%)
- Corporate refundable: $37.3M (~89% of $41.8M corporate + other)
- Corporate nonrefundable: ~$4.5M (~11%)

**Effective claim share — refundable / nonrefundable split.** Refundable
claims offset state revenue 1:1; nonrefundable claims that exceed
current-year tax liability carry forward and don't immediately reduce
revenue. The ``reec_effective_claim_share`` parameter is the
**nonrefundable utilization rate** (literature midpoint ~0.80); the
aggregate effective share is computed per pool from the refundable mix:

| Pool | Refundable share | Effective at 0.80 nonrefundable | Effective at 1.00 |
|------|------------------|--------------------------------|--------------------|
| Individual | ~23% | ~85% | 100% |
| Corporate + Other | ~89% | ~98% | 100% |

A previous version applied a single ``effective_claim_share`` (e.g.
0.80) to both pools, which understated the dollar value of corporate
REEC by ~15%.

**OBBBA demand impact — residential vs commercial.** OBBBA (PL 119-21,
Jul 2025) terminated **§25D (residential)** but extended **§48E
(commercial)** through 12/31/2027. Hawaii residential and commercial
REEC see different decays:

- *Individual / residential REEC* uses the §25D decay scenario:
  - `pre_obbba` — no demand decay (upper bound)
  - `obbba_mid` — −10% in 2026 (Hawaii-tempered; SEIA national −19% discounted for Hawaii's lease-heavy market), gradual recovery
  - `obbba_severe` — −19% in 2026 (SEIA national figures applied directly), slow recovery
  - `safe_harbor_mid` — OBBBA Mid base + §25D safe-harbor overhang. IRS
    Notice 2013-29 allows filers to lock in §25D at commencement of
    construction (5% safe-harbor payment) with up to 4 years to complete.
    HECO recorded a +37% surge in H2 2025 interconnection applications;
    that backlog completes installation in 2026-2027. Factors: 2026 = 1.05
    (above pre-OBBBA baseline), 2027 = 0.97, reverting to OBBBA Mid from
    2028. Under confirmed Interpretation A retroactivity (SB 3125 §9(1),
    TY beginning after 12/31/2025), this elevated 2026-2027 demand binds
    the $40M cap more tightly → lower pro-rata factor → higher state
    savings. Used in the REEC report's sensitivity band upper bound.
- *Corporate / commercial REEC* uses ``_reec_demand_factor_corporate``
  which returns **1.0** for all forecast years (no §48E impact through
  2027; tapering schedule is downstream of the forecast horizon).

The previous version applied the residential decay factor to both
pools, biasing total revenue gain down.

**Interpretation A (retroactivity, May 2026):** SB 3125 §9(1) confirmed to
apply retroactively to taxable years beginning after 12/31/2025 (TY2026),
with only the §235-12.5(a) AGI-limit amendments deferred to TY2027+. The
model now uses `interpretation="A"` for all scenarios: TY2026 certifications
(filed in CY2027) fall under the $40M cap. AGI limit still does not apply to
TY2026. Net effect: less nonrefundable stock enters the carryforward pool from
TY2026 → lower state RETITC cost in TY2027-2031 → ~+$9M cumulative savings
vs prior Interpretation B baseline.

**Cap impact logic:**
- TY2027–2030: `cap_savings = max(0, projected_baseline − $40M cap)`
- TY2031+: `cap_savings = full projected_baseline` (cap → $0)

**MID scenario REEC savings (pre-fix):** $42M (2027) → $104M (2031),
total ~$307M over 5 years. Post-fix savings will be higher because
corporate baseline no longer decays and corporate aggregate effective
share rises from ~80% to ~98%. Awaiting re-run.

### 6b. CGEC — Capital Goods Excise Tax Credit

**DOTAX TY2023 baseline:** $34.6M (rising trend from $29.3M in 2021)  
**Growth rate (MID: 3%/yr):** Calibrated to Hawaii business investment growth, not statewide nominal GDP.  
**Pull-forward haircut (10%):** Capital goods purchases are partially accelerated into TY2027 before the sunset, reducing the post-2027 base modestly.

**Sunset impact logic:**
- TY2027: $0 (credit still active)
- TY2028+: full projected baseline (all claims go away)

**MID scenario CGEC savings:** ~$29M/yr starting TY2028, total ~$121M over 5 years.

### 6c. TCRA — Tax Credit for Research Activities

One-time acceleration effect modeled for **TY2029 only**:
- MID: ~$8.4M  
- HIGH: ~$8.8M  

---

## 8. Scenario Design

Four integrated scenarios: three behavioral sensitivity scenarios (no recession macro) plus one recession scenario using MID behavioral parameters.

### 8a. Behavioral Scenarios (No Recession Macro)

| Parameter | LOW | **MID (Recommended)** | HIGH |
|-----------|-----|----------------------|------|
| Pareto α (top-income concentration) | 1.7 (lighter tail) | **1.5** | 1.4 (heavier tail) |
| REEC residential demand scenario | obbba_severe | **obbba_mid** | pre_obbba |
| REEC commercial demand factor | 1.0 (no §48E impact) | **1.0** | 1.0 |
| ETI | 0.60 | **0.40** | 0.15 |
| Migration elasticity | 0.15 | **0.10** | 0.05 |
| PTE capture rate | 90% | **70%** | 40% |
| Top-income growth premium | +0.3%/yr | **+1.3%/yr** | +2.3%/yr |
| REEC nonrefundable utilization | 65% | **80%** | 100% |
| CGEC annual growth | 2%/yr | **3%/yr** | 4%/yr |
| Corporate AGI limit on REEC | Yes | **No** | No |
| Per-filer effective deduction in compare_systems | Yes | **Yes** | Yes |
| Macro shock | None | **None** | None |

**Calibration anchor:** The model anchors to DOTAX's $663M baseline tax figure for $1M+ filers. The MID result ($629.6M) is ~7.5% below the official ~$680M estimate due to two corrections applied after the official score was produced: (1) §235-16 CG cap (7.25%) properly applied to synthetic $1M+ filers — reduces the bracket-delta contribution of capital gains income; (2) PTE election pool excludes CG income per statute and economic rationality (9% PTE > 7.25% CG cap) — reduces the PTE offset, which in turn reduces the net bracket gain. LOW reflects maximum plausible behavioral response (strong ETI, 90% PTE shift, severe OBBBA solar decay). HIGH reflects minimal behavioral response and optimistic demand assumptions.

### 8b. Recession Scenario

**Script:** `forecast_sb3125_cd1_enhanced.py` (RECESSION entry in SCENARIOS list)  
**New file:** `packages/tax_modeler/src/tax_modeler/scenarios/macro_scenarios.py`

Models a **mild-to-moderate recession with trough in 2027 and gradual recovery through 2031** — consistent with elevated current recession odds (25–50% 12-month, >50% five-year historically) and empirical recession patterns from 2001 and 2008. Uses MID behavioral parameters; behavioral-macro interaction effects (e.g., higher PTE takeup in recession, slower migration) are not modeled (conservative simplification).

**Methodology — cumulative deviation from baseline.** The shock values are CUMULATIVE deviations from the baseline trajectory at each year, not year-on-year deltas. This correctly models persistent recession damage: by year 2 the income gap is smaller than year 1 (recovery underway), but income is still below trend. The previous year-on-year interpretation incorrectly produced a "rebound year" with income *above* baseline, which is not how recessions recover.

**Macro shock parameters (applied after `project_tax_units_forward()` and top-income premium, before behavioral response):**

| Year | All-filer cumulative gap to baseline | Top-income additional gap (≥$200K) | Total top-income gap |
|------|-------------------------------------:|----------------------------------:|---------------------:|
| 2027 | −2.0% | −1.5% | **−3.5%** |
| 2028 | −1.5% | −1.0% | **−2.5%** |
| 2029 | −1.0% | −0.3% | **−1.3%** |
| 2030 | −0.5% | 0.0% | **−0.5%** |
| 2031 |  0.0% | 0.0% | **0.0%** (full recovery) |

The top-income extra gap captures capital gains realization collapse and pass-through business income cyclicality (historical precedent: 2008–09 saw 40–60% CG declines and 6–12% peak-to-trough top-1% income drops, with full recovery within 4 years).

**Results (May 7, 2026 re-run):** RECESSION and MID are within $1.5M over 5 years; RECESSION is slightly above MID in 2030–2031. ⚠️ *This is unexpected — recession should depress revenue, not raise it. Likely an artifact of COR scaling or income-projection interaction; needs investigation before citing.*

| Year | MID | RECESSION | Δ vs MID |
|------|----:|----------:|---------:|
| 2027 | $101.2M | $97.5M | −$3.7M |
| 2028 | $122.0M | $120.6M | −$1.4M |
| 2029 | $139.7M | $138.8M | −$0.9M |
| 2030 | $137.2M | $141.0M | +$3.8M |
| 2031 | $173.0M | $176.5M | +$3.5M |
| **5yr** | **$673.0M** | **$674.5M** | **+$1.5M** |

**Why the effect is moderate in absolute terms:** This forecast measures the *delta* between Act 46 and SB 3125 CD1, not absolute state revenue. Both tax systems face the same income shock, so the delta is partially protected — only the marginal rate × marginal income above thresholds differs between them.

1. **Bracket delta** (~$338M of $673M MID): small changes expected in recession as income shocks affect both systems equally
2. **Credit overlay** (~$335M of $673M MID): unchanged — REEC/CGEC claim levels don't depend on individual filer income

**Note on absolute revenue impact:** Absolute state individual income tax revenue would drop substantially more in a recession (likely 5–10% peak-to-trough on a ~$3B base). That is a property of any income tax under any rate schedule, not specific to SB 3125 CD1.

---

## 9. Distributional Analysis

**Script:** `forecast_sb3125_cd1_quintile.py`  
**Output:** `/tmp/sb3125_cd1_quintile_2027_2031.csv`

Methodology follows CBO/Tax Policy Center standard distributional analysis:

- **Population sorted by income** and divided into **5 equal-population quintiles** using cumulative weight percentiles (not equal income spans)
- **Static incidence scoring**: per-unit tax is computed at each filer's projected income before ETI/migration adjustments — reflects who bears the statutory burden before behavioral avoidance
- **Bracket change only**: REEC/CGEC/TCRA credit overlay savings are not attributable to individual filers and are excluded from the quintile breakdown
- **MID scenario only**

Key finding: **Q5 (top 20%, income $102K+) bears more than 100% of the aggregate bracket revenue gain**, with Q1–Q4 receiving modest net benefits from the lower middle rates. The 13% bracket is the dominant force; the middle rate cuts (3.20%→2.50%, 5.50%→5.00%) offset approximately 15% of the Q5 gain.

Note: Q1 filers (avg income ~$3K) are **completely unaffected** because their gross income is below Hawaii's standard deduction + personal exemption threshold — they have zero taxable income and no rate applies.

---

## 10. Results

### Annual Fiscal Impact by Scenario ($M, vs. Act 46 baseline)

**Updated May 7, 2026** from fresh forecast run incorporating population growth (0.5%/yr DBEDT 2050) and COR March 2026 projections. PTE shift is $0 in this run. Results are post-behavioral (ETI/migration only).

| Tax Year | LOW | **MID** | HIGH | RECESSION |
|----------|----:|--------:|-----:|----------:|
| 2027 | $92.6M | **$101.2M** | $124.2M | $97.5M |
| 2028 | $102.6M | **$122.0M** | $154.6M | $120.6M |
| 2029 | $116.5M | **$139.7M** | $180.2M | $138.8M |
| 2030 | $111.4M | **$137.2M** | $183.9M | $141.0M |
| 2031 | $146.8M | **$173.0M** | $226.9M | $176.5M |
| **5-year total** | **$569.9M** | **$673.0M** | **$869.9M** | **$674.5M** |

*Positive = net revenue gain for the State. Includes bracket microsim + credit overlay + behavioral response.*

**RECESSION scenario note:** See Section 8b. ⚠️ RECESSION is slightly above MID in 2030–2031 in this run — unexpected behavior that needs investigation before citing.

### MID Scenario Decomposition

| Channel | 5-year Total |
|---------|-------------:|
| Static bracket gain (13% top bracket + middle cuts) | +$411.6M |
| ETI / migration behavioral offset | −$73.2M |
| PTE election shift | $0 ⚠️ |
| **Post-behavioral bracket delta** | **+$338.4M** |
| REEC savings (cap + elimination) | +$236.3M |
| CGEC savings (sunset) | +$90.5M |
| TCRA savings (acceleration) | +$7.8M |
| **Credit overlay total** | **+$334.6M** |
| **Total MID** | **+$673.0M** |

*⚠️ PTE shift is $0 in this run — previously modeled at −$120.4M. Needs investigation to confirm whether this is intentional (e.g., PTE disabled in latest pipeline) or a bug. Credit overlay revised down from $503.2M to $334.6M reflecting updated REEC and CGEC baselines.*

### Distributional Impact — TY 2027 Bracket Change (MID)

| Quintile | Income Range | Avg Income | Delta $M | Avg $/Filer |
|----------|-------------|-----------|---------|------------|
| Q1 (Bottom 20%) | Below $11K | $2,919 | $0 | $0 |
| Q2 | $11K – $29K | $18,858 | −$0.3M | −$3 |
| Q3 | $29K – $54K | $41,070 | −$4.9M | −$42 |
| Q4 | $54K – $102K | $74,612 | −$9.8M | −$82 |
| Q5 (Top 20%) | $102K – $165M | $244,822 | +$97.6M | +$824 |

*Negative = filer pays less (savings from rate cut). Positive = filer pays more. Bracket change only; credit overlay excluded.*

---

### SB 3125 CD2 Results — May 14, 2026 (vintage carryforward correction)

**Key finding (revised May 14):** The previous static credit overlay
understated REEC savings by ~$107M over 5 years because it (a) treated
TY2030 as a $40M cap year rather than applying the §235-12.5(p) sunset,
and (b) did not track pre-existing carryforward stock drawdown. The
vintage simulation corrects both. Numbers in the tables below reflect the
new vintage-pool model.

**CD2 vs Act 46 baseline, post-behavioral, post-Round-2 ($M):**

| Tax Year | LOW | **MID** | HIGH | RECESSION |
|----------|----:|--------:|-----:|----------:|
| 2027 | $108.8M | **$108.3M** | $129.1M | $102.7M |
| 2028 | $122.3M | **$135.2M** | $164.7M | $133.3M |
| 2029 | $137.0M | **$155.8M** | $191.8M | $153.2M |
| 2030 | $164.2M | **$187.9M** | $231.2M | $192.1M |
| 2031 | $171.5M | **$194.7M** | $244.7M | $198.2M |
| **5-year total** | **$703.7M** | **$781.9M** | **$961.4M** | **$779.5M** |

*LOW uses interpretation A (TY2026 cap binds) + pro-rata η=0.5; other scenarios
use interpretation B + scenario-band η. All scenarios use DOTAX
TY2018-2022 actuals, dynamic AGI eligibility, and dynamic refundable share.*

**Pre-Round-2 results (May 14 vintage carryforward only, for comparison):**

| Tax Year | LOW | **MID** | HIGH | RECESSION |
|----------|----:|--------:|-----:|----------:|
| 2027 | $103.8M | **$108.8M** | $129.4M | $103.2M |
| 2028 | $119.8M | **$135.4M** | $164.7M | $133.5M |
| 2029 | $135.8M | **$155.9M** | $191.8M | $153.3M |
| 2030 | $162.3M | **$187.3M** | $230.8M | $191.4M |
| 2031 | $170.6M | **$194.4M** | $244.6M | $198.0M |
| **5-year total** | **$692.4M** | **$781.8M** | **$961.3M** | **$779.4M** |

**Credit savings breakdown, MID scenario ($M) — illustrating vintage carryforward correction:**

*"Vintage model" column is pre-Round-2; Round-2 final MID numbers are in the table above ($47.3M, $72.0M, $85.5M, $116.5M, $120.6M).*

| Year | Legacy static | Vintage model (pre-R2) | TY2030 driver |
|------|--------------:|-----------------------:|---------------|
| 2027 | $41.8M | $47.9M | Pre-2027 stock + ineligibles |
| 2028 | $59.2M | $72.2M | Higher baseline (steady-state cost) |
| 2029 | $69.8M | $85.6M | Higher baseline |
| 2030 | $65.5M | **$115.8M** | **§235-12.5(p) sunset (was treated as $40M cap)** |
| 2031 | $98.3M | $120.4M | Includes 2027–2029 vintage drawdown |

---

### SB 3125 CD2 Results — May 11, 2026 (legacy static overlay, pre-correction)

**Note:** Superseded by May 14 vintage-corrected results above. Retained for
historical reference.

**Key finding:** The bracket values loaded under the `sb3125_cd1` label in the CSV already reflected CD2-vintage numbers (2.50%/5.00% mid rates, 13% at $1M+ MFJ). Therefore, the CD2 forecast produces **identical fiscal-impact numbers to the CD1 forecast above**. The difference is in labeling and authoritative tag going forward.

**CD2 vs Act 46 baseline, all scenarios, final post-behavioral numbers ($M):**

| Tax Year | LOW | **MID** | HIGH | RECESSION |
|----------|----:|--------:|-----:|----------:|
| 2027 | $93.4M | **$102.8M** | $125.7M | $97.2M |
| 2028 | $103.0M | **$122.4M** | $155.0M | $120.4M |
| 2029 | $115.6M | **$140.1M** | $180.8M | $137.5M |
| 2030 | $111.3M | **$136.9M** | $183.2M | $141.1M |
| 2031 | $147.4M | **$172.4M** | $224.4M | $175.9M |
| **5-year total** | **$570.7M** | **$674.5M** | **$869.2M** | **$672.1M** |

**CD2 sensitivity (static scoring, no behavioral response, $M):**

| Tax Year | LOW | **MID** | HIGH |
|----------|----:|--------:|-----:|
| 2027 | $79.3M | **$88.0M** | $107.9M |
| 2028 | $114.1M | **$123.8M** | $143.1M |
| 2029 | $139.0M | **$147.0M** | $165.8M |
| 2030 | $141.8M | **$148.5M** | $165.8M |
| 2031 | $193.0M | **$192.3M** | $214.0M** |
| **5-year total** | **$667.2M** | **$699.6M** | **$796.7M** |

**CD2 vs FY2026-frozen baseline (ITEP-comparable, $M):**

*Answers: "What does CD2 cost vs if nothing had been enacted after 2026?" Negative = revenue lost.*

| Tax Year | Bracket effect | SD expansion | **Total** | ITEP estimate | Gap |
|----------|---------------:|-------------:|----------:|---------------:|-----:|
| 2027 | −$171.4M | −$32.4M | **−$203.7M** | −$227.0M | +$23.3M |
| 2028 | −$161.6M | −$67.2M | **−$228.9M** | −$258.0M | +$29.1M |
| 2029 | −$387.6M | −$85.3M | **−$472.9M** | −$534.0M | +$61.1M |
| 2030 | −$375.5M | −$123.1M | **−$498.6M** | −$563.0M | +$64.4M |
| 2031 | −$353.6M | −$182.9M | **−$536.5M** | −$622.0M | +$85.5M |
| **5-year Σ** | **−$1,449.7M** | **−$491.0M** | **−$1,940.6M** | **−$2,204.0M** | **+$263.4M** |

Our microsim runs ~12% below ITEP on the vs-frozen baseline. Likely sources: ITEP includes non-residents and PTE pass-through attribution not in the microsim; their dynamic inflation assumptions may also differ over the 5-year window.

**MID scenario quintile breakdown (bracket only, TY 2027, CD2 vs Act 46):**

| Quintile | Income Range | Avg Income | N filers | Bracket Delta | Avg $/filer |
|----------|---------------|-----------|----------|--------------|-------------|
| Q1 (Bottom 20%) | −$18.6K – $11.2K | $2,961 | 124,948 | $0.0M | $0 |
| Q2 | $11.2K – $31.3K | $19,834 | 124,505 | −$0.8M | −$6 |
| Q3 | $31.3K – $56.0K | $42,628 | 125,514 | −$5.5M | −$44 |
| Q4 | $56.0K – $103.5K | $76,346 | 125,006 | −$10.5M | −$84 |
| Q5 (Top 20%) | $103.5K – $211.6M | $253,959 | 124,994 | **+$82.7M** | **+$662** |

### Baseline Validation

The microsim TY2027 Act 46 baseline is approximately $2.26B — roughly $790M below the COR's $3.05B FY2027 projection. This gap is **expected and not a calibration error**:

- Pass-through entity (PTE) tax revenue (~$124M+): taxed at entity level, not on individual returns
- Non-resident withholding: captured in DOTAX but not in PUMS-based microsim
- Audit, penalty, and late-filing assessments
- Rounding and timing differences between tax year (TY) and fiscal year (FY)

The **bracket delta** (SB 3125 CD1 minus Act 46) is robust to this level-shift — both systems are subject to the same coverage gaps, so the difference cancels them out.

---

## 11. Caveats and Limitations

1. **PUMS income underreporting at the top.** The ACS PUMS understates income for very high earners even after Pareto synthesis. The Pareto approximation underweights income concentration above ~$10M. The raw synthesis recovers only ~65–80% of the IRS SOI $663M tax target when the §235-16 CG cap is correctly applied (lower than the pre-cap estimate because CG income is taxed at 7.25% rather than bracket rates, reducing simulated baseline tax). The gap is closed by the post-synthesis uniform tail scaling step (Step 6a), which brings the tax target ratio to 100.0% before projection (tail_k: LOW=1.575, MID=1.279, HIGH=1.100).

2. **Static credit overlay.** REEC and CGEC are scored as aggregate static overlays. The model does not simulate individual solar adoption behavior or capital investment timing at the filer level.

3. **No general equilibrium effects.** The model does not simulate wage effects, employment changes, or business investment responses beyond the three modeled behavioral channels.

4. **PTE capture rate uncertainty.** The 4pp arbitrage (13% individual vs. 9% PTE) creates a strong incentive for restructuring. The MID scenario's 70% capture rate is a judgment call — actual takeup depends on legal/accounting costs and awareness. The pass-through share (0.20) is now calibrated to Hawaii IRS SOI 2022 data ($200K+ filers: 12.6% of total income as partnership/S-corp income, ~15% of ordinary income), replacing the prior national top-1% figure of 0.40. Remaining uncertainty: the IRS SOI does not break out $1M+ filers separately; the $1M+ sub-population may have a modestly higher pass-through share than the full $200K+ bracket.

5. **OBBBA demand uncertainty.** Federal repeal of Section 25D in 2025 creates genuine uncertainty for Hawaii solar demand 2026–2031. The three REEC scenarios bracket the plausible range from SEIA forecasts.

6. **No tax avoidance timing effects.** High-income filers may accelerate income recognition into 2026 (before the bill takes effect) or defer it to 2028 if they anticipate the 2029 bracket change. These timing effects are not modeled.

7. **Behavioral response is phased in linearly.** Migration and PTE election are assumed to phase in gradually. In practice, some response may occur immediately (legal restructuring) while other responses may be permanent (migration).

---

## 10a. Margin of error on the poverty-impact pipeline (added May 2026)

The poverty-impact tables emitted by `scripts/poverty_impact_report.py`
(separate from the SB 3125 fiscal-impact tables in Section 10) now
carry two new families of uncertainty columns when invoked with the
appropriate flags:

* `<col>_se` — PUMS sampling SE via 80-replicate Successive Difference
  Replication. Activated by `--replicate-weights`.
* `<col>_param_min` / `<col>_param_max` / `<col>_param_median` —
  one-at-a-time parameter sweep across the four behavioral-uncertainty
  parameters (take-up rates + forward-projection α elasticity).
  Activated by merging `scripts/poverty_impact_sweep.py` output via
  `--merge-sweep`.

The two bands are reported **separately, not combined in quadrature**,
so reviewers can see whether uncertainty is dominated by sampling or by
policy assumptions. See `METHODOLOGY.md` § *Margin of error on the
poverty-impact pipeline* for the SDR formula, the empirical anchors
behind each sweep band, and the rationale for not collapsing the two
sources into one headline interval.

### Narrowed parameter band on HI CTC (2026-Q2)

A first-cut sweep produced a ±37 % parameter range on
`persons_lifted_hi_ctc_650`, too wide to be useful for stakeholders.
Decomposing the range showed two distinct drivers:

* `hi_ctc_per_child` band ($300 → $1000) → ±38 % contribution.
  This is a **policy-design counterfactual** ("what if the bill had
  said $300?"), not behavioral uncertainty given the bill as drafted.
* `hi_ctc_takeup` band (0.60 → 0.95, literature pool) → ±22 %.
  Wide because it conflated first-year and steady-state estimates.

The per-child axis was moved out of the sweep entirely and into the
named scenario set: the default scenario menu now ships
`hi_ctc_300`, `hi_ctc_650`, and `hi_ctc_1000` side-by-side, each with
its own SE and parameter range. The take-up band was replaced with a
Hawaii-empirical anchor: observed federal-EITC take-up in HI 2022 =
84,010 admin claims ÷ ~120,535 PUMS-eligible filers ≈ **0.70** with
±5 pp judgment band. The estimator lives at
`tax_modeler.calibration.hi_eitc_takeup_estimate`.

**Result on the headline cell:** parameter range on
`persons_lifted_hi_ctc_650` tightens from ±37 % → **~±10 %**. Quotable:
> EITC lifts ~19,000 persons in Hawaiʻi (SDR 90 % CI ±3,200; parameter
> range ±10 %). A $650/child state CTC would lift an additional ~5,260
> (SDR ±1,640; parameter range ~4,700–5,800). A $1,000/child variant
> would lift ~8,000.

The headline SB 3125 fiscal-impact numbers in Section 10 are unaffected
by this change — only the auxiliary poverty-impact tables ship the new
columns.

---

## 12. Scripts and File Map

### Forecast Scripts (repo root)

#### SB 3125 CD1

| Script | Purpose | Output |
|--------|---------|--------|
| `forecast_sb3125_cd1.py` | Original forecast with decile snapshot | `/tmp/sb3125_cd1_fiscal_impact_2027_2031.csv` |
| `forecast_sb3125_cd1_sensitivity.py` | Sensitivity across Pareto α × REEC scenarios (pre-behavioral) | `/tmp/sb3125_cd1_sensitivity_2027_2031.csv` |
| `forecast_sb3125_cd1_enhanced.py` | **Primary forecast** — 3 behavioral scenarios + RECESSION macro scenario | `/tmp/sb3125_cd1_enhanced_2027_2031.csv` |
| `forecast_sb3125_cd1_quintile.py` | Distributional analysis by income quintile (MID) | `/tmp/sb3125_cd1_quintile_2027_2031.csv` |

#### SB 3125 CD2 (May 2026)

| Script | Purpose | Output |
|--------|---------|--------|
| `forecast_sb3125_cd2.py` | Static forecast vs Act 46 baseline | `/tmp/sb3125_cd2_fiscal_impact_2027_2031.csv` |
| `forecast_sb3125_cd2_sensitivity.py` | Sensitivity across Pareto α × REEC scenarios (static, no behavioral) | `/tmp/sb3125_cd2_sensitivity_2027_2031.csv` |
| `forecast_sb3125_cd2_enhanced.py` | **Primary CD2 forecast** — 4 scenarios (LOW/MID/HIGH/RECESSION) with behavioral response | `/tmp/sb3125_cd2_enhanced_2027_2031.csv` |
| `forecast_sb3125_cd2_quintile.py` | Distributional quintile analysis (bracket only, all 5 years) | `/tmp/sb3125_cd2_quintile_2027_2031.csv` |
| `forecast_sb3125_cd2_vs_fy26base.py` | ITEP-comparable: CD2 vs FY2026-frozen baseline | `/tmp/cd2_vs_fy26base_*.csv` |

### Key Package Files

| File | Purpose |
|------|---------|
| `packages/tax_modeler/src/tax_modeler/loaders/pums_loader.py` | PUMS CSV loader |
| `packages/tax_modeler/src/tax_modeler/units/constructor.py` | Tax unit construction from person/household records |
| `packages/tax_modeler/src/tax_modeler/pipeline.py` | Pipeline orchestration (`_enrich_for_credits`, `_compute_base_tax`, `_calibrate`) |
| `packages/tax_modeler/src/tax_modeler/calibration.py` | IPF rake calibration |
| `packages/tax_modeler/src/tax_modeler/config/tax_system_config.py` | `TaxCalculator`, `TaxSystemConfig`, `TaxSystemRegistry`, `compare_systems()` |
| `packages/tax_modeler/src/tax_modeler/data/raw/hawaii_tax_brackets_master_all.csv` | All bracket schedules (Act 46 and SB 3125 CD1) |
| `packages/tax_modeler/src/tax_modeler/projection/tax_unit_projector.py` | County-level income projection |
| `packages/tax_modeler/src/tax_modeler/scenarios/top_income_synthesis.py` | Pareto $1M+ filer synthesis |
| `packages/tax_modeler/src/tax_modeler/scenarios/behavioral_response.py` | ETI, migration, PTE election, itemized adjustment |
| `packages/tax_modeler/src/tax_modeler/scenarios/macro_scenarios.py` | Macro recession shock (`apply_macro_recession_shock`) |
| `packages/tax_modeler/src/tax_modeler/scenarios/sb3125_cd1_credits.py` | REEC/CGEC/TCRA credit overlay |

### Output Files

#### CD1 Outputs

| File | Description |
|------|-------------|
| `/tmp/sb3125_cd1_fiscal_impact_2027_2031.csv` | Static base forecast vs Act 46 |
| `/tmp/sb3125_cd1_enhanced_2027_2031.csv` | Final calibrated forecast (all 4 scenarios, post-behavioral) |
| `/tmp/sb3125_cd1_quintile_2027_2031.csv` | Quintile distributional results (MID, all 5 years) |
| `/tmp/sb3125_cd1_sensitivity_2027_2031.csv` | Sensitivity range (LOW/MID/HIGH, static scoring) |

#### CD2 Outputs (May 11, 2026)

| File | Description |
|------|-------------|
| `/tmp/sb3125_cd2_fiscal_impact_2027_2031.csv` | Static base forecast vs Act 46 |
| `/tmp/sb3125_cd2_enhanced_2027_2031.csv` | Enhanced forecast (all 4 scenarios, post-behavioral) |
| `/tmp/sb3125_cd2_quintile_2027_2031.csv` | Per-unit quintile analysis (bracket only, TY2027–2031) |
| `/tmp/sb3125_cd2_sensitivity_2027_2031.csv` | Sensitivity range (LOW/MID/HIGH, static scoring) |
| `/tmp/cd2_vs_fy26base_bracket_mid_2027_2031.csv` | ITEP-comparable bracket-only vs frozen baseline |
| `/tmp/cd2_vs_fy26base_quintile_mid_2027_2031.csv` | ITEP-comparable quintile breakdown |
| `/tmp/sb3125_cd2_decile_TY2027.csv` | Decile snapshot from base static forecast |

#### Cache

| File | Description |
|------|-------------|
| `/tmp/tax_units_cache.parquet` | Calibrated base-year tax units (pre-synthesis); rebuilds in ~3 min if deleted |
| `/tmp/sb3125_calibrated_base.pkl` | Calibrated units saved after top-income synthesis (used by enhanced scripts for state-level analysis) |

---

## 13. Software and Packages

### Language and Runtime
- **Python 3.12** via `uv` (Astral) package manager
- All scripts run as: `cd /Users/dtomkatsu/Census-Forecaster && uv run python <script>.py`

### External Python Libraries

| Library | Version | Use |
|---------|---------|-----|
| `pandas` | ≥2.0 | Data manipulation, groupby aggregation, CSV I/O |
| `numpy` | ≥1.24 | Numerical computations, Pareto distribution draws |
| `pyarrow` | ≥14.0 | Parquet cache I/O |
| `scipy` | ≥1.11 | Statistical distributions (Pareto synthesis) |

### Internal Packages (this repo)

| Package | Path | Role |
|---------|------|------|
| `tax_modeler` | `packages/tax_modeler/src/` | Core tax calculation, bracket schedules, pipeline, projection, scenarios |
| `census_forecaster` | `packages/census_forecaster/src/` | ACS B19013 ensemble projector for county income growth |
| `pums_estimator` | `packages/pums_estimator/src/` | PUMS control totals and crosswalk utilities |
| `common` | `packages/common/src/` | Shared utilities (logging, config, type helpers) |

### Data Storage
- **PUMS source data:** `/Users/dtomkatsu/ctc-and-eitc/data/raw/pums/` (shared with ctc-and-eitc repo)
- **Tax unit cache:** `/tmp/tax_units_cache.parquet`
- **Forecast outputs:** `/tmp/sb3125_cd1_*.csv`
