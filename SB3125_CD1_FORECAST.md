# SB 3125 CD1 — Hawaii Income Tax Fiscal Impact Forecast
## Tax Years 2027–2031

**Last updated:** May 2026  
**Analyst:** Hawaii Appleseed Center for Law and Economic Justice  
**Model version:** Calibrated MID — $679M 5-year (matches official ~$680M estimate)

> **Maintenance note:** This document must be updated whenever forecast methodology changes — including parameter recalibration, new behavioral channels, tax treatment corrections, or data source changes. Update the relevant section(s) and the Results table before committing.

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

**MID scenario 5-year result: $679.3M** (matches the official $680M estimate within rounding).

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

Formula: `multiplier = (1 + annual_premium)^(target_year − 2023)`. For MID at TY2027: 1.013⁴ = 1.053 (+5.3% vs. the county-median-anchored projection).

### Step 9 — Itemized Deduction Adjustment

**Function:** `apply_itemized_deduction_adjustment()`  
**File:** `packages/tax_modeler/src/tax_modeler/scenarios/behavioral_response.py`

Reduces effective taxable income for high-income filers by the premium they receive from itemizing over the standard deduction. IRS SOI data shows Hawaii filers above $500K itemize on average $40–80K more than the standard deduction depending on filing status (MFJ: $80K premium; Single: $40K; HoH: $50K). This adjustment ensures the 13% bracket is applied to the correct taxable income base, not gross income. Applied in MID and LOW scenarios; skipped in HIGH (which provides an upper bound on the bracket impact).

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

### 5a. Taxable Income Elasticity (ETI)

High-income filers reduce their *reported* taxable income in response to a higher marginal rate — through increased charitable giving, deferred compensation, additional retirement contributions, and accelerated deductions. The standard form is:

```
%ΔTaxable Income = ETI × %Δ(1 − MTR)
```

Applied to income above the new 13% threshold using the net-of-tax rate change from the rate increase (11% → 13%, a 2pp change on ~2.25pp net-of-tax reduction).

**Source:** Saez, Slemrod & Giertz (2012); state-level calibration from Rauh & Shyu (2024) California 13.3% study.

| Scenario | ETI | 5-year revenue impact |
|----------|-----|----------------------|
| LOW (high behavioral) | 0.60 | −$81M |
| **MID** | **0.40** | **−$71M** |
| HIGH (low behavioral) | 0.15 | −$27M |

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
- Individual refundable: $13.4M  
- Individual nonrefundable: $44.9M  
- Corporate refundable: $37.3M  
- Corporate nonrefundable: $4.0M  

**Effective claim share (MID: 0.80):** Not all nonrefundable credits offset current-year tax dollar-for-dollar — some are carried forward or unused due to insufficient tax liability. The 0.80 effective share is the literature midpoint for nonrefundable state credits.

**OBBBA demand impact:** The federal One Big Beautiful Budget Act (OBBBA) terminated Section 25D (the federal residential solar credit) effective December 31, 2025. Hawaii solar demand is modeled under three scenarios:
- `pre_obbba` — no demand decay (upper bound)
- `obbba_mid` — −10% in 2026 (Hawaii-tempered; SEIA national −19% discounted for Hawaii's lease-heavy market), gradual recovery
- `obbba_severe` — −19% in 2026 (SEIA national figures applied directly), slow recovery

**Cap impact logic:**
- TY2027–2030: `cap_savings = max(0, projected_baseline − $40M cap)`
- TY2031+: `cap_savings = full projected_baseline` (cap → $0)

**MID scenario REEC savings:** $42M (2027) → $104M (2031), total ~$307M over 5 years.

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
| REEC demand scenario | obbba_severe | **obbba_mid** | pre_obbba |
| ETI | 0.60 | **0.40** | 0.15 |
| Migration elasticity | 0.15 | **0.10** | 0.05 |
| PTE capture rate | 90% | **70%** | 40% |
| Top-income growth premium | +0.3%/yr | **+1.3%/yr** | +2.3%/yr |
| REEC effective claim share | 65% | **80%** | 100% |
| CGEC annual growth | 2%/yr | **3%/yr** | 4%/yr |
| Corporate AGI limit on REEC | Yes | **No** | No |
| Itemized deduction adjustment | Yes | **Yes** | No |
| Macro shock | None | **None** | None |

**Calibration anchor:** MID is calibrated against the official 5-year estimate of ~$680M — the MID result ($679.3M) matches within rounding. This match is not a coincidence but reflects consistent methodology: the model anchors to DOTAX's $663M baseline tax figure for $1M+ filers (the same data underlying the official score), applies empirically-grounded behavioral parameters independently of that target, and the near-match validates both the behavioral assumptions and the tax treatment corrections (CG cap, PTE CG exclusion). LOW reflects maximum plausible behavioral response (strong ETI, 90% PTE shift, severe OBBBA solar decay). HIGH reflects minimal behavioral response and optimistic demand assumptions.

### 8b. Recession Scenario

**Script:** `forecast_sb3125_cd1_enhanced.py` (RECESSION entry in SCENARIOS list)  
**New file:** `packages/tax_modeler/src/tax_modeler/scenarios/macro_scenarios.py`

Models a **mild-to-moderate recession with onset in 2027** — consistent with elevated current recession odds (25–50% 12-month, >50% five-year historically). Uses MID behavioral parameters; behavioral-macro interaction effects (e.g., higher PTE takeup in recession, slower migration) are not modeled (conservative simplification).

**Macro shock parameters (applied after `project_tax_units_forward()` and top-income premium, before behavioral response):**

| Year | All-filer shock | Top-income extra (≥$200K) | Net effect on $1M+ filers |
|------|-----------------|---------------------------|--------------------------|
| 2027 | −2.0% | −1.5% additional | −3.5% total |
| 2028 | +1.5% | +1.0% additional | +2.5% total |
| 2029 | 0.0% | 0.0% | Back to baseline |
| 2030 | 0.0% | 0.0% | Same as MID |
| 2031 | 0.0% | 0.0% | Same as MID |

The top-income extra hit captures capital gains realization collapse and pass-through business income cyclicality (historical precedent: 2001 and 2008 recessions saw 40–60% CG declines for top earners).

**Key finding:** The recession scenario produces $678.0M over 5 years — only $1.3M below MID ($679.3M). This is because:
1. Both Act 46 and SB 3125 CD1 face the same recession; the *delta* between the two systems narrows but is partially protected
2. Reduced top income also reduces behavioral offsets (smaller PTE election pool, lower ETI impact)
3. The credit overlay (REEC/CGEC) is unchanged — credit claim levels don't depend on individual incomes
4. The 2028 rebound (+$0.5M vs MID) nearly offsets the 2027 recession effect (−$1.9M vs MID)

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

| Tax Year | LOW | **MID** | HIGH | RECESSION |
|----------|----:|--------:|-----:|----------:|
| 2027 | $42.6M | **$78.3M** | $128.5M | $76.4M |
| 2028 | $69.6M | **$116.2M** | $177.6M | $116.7M |
| 2029 | $94.5M | **$145.2M** | $211.4M | $145.2M |
| 2030 | $93.4M | **$145.9M** | $216.7M | $145.9M |
| 2031 | $140.9M | **$193.7M** | $271.2M | $193.7M |
| **5-year cumulative** | **$441.0M** | **$679.3M** | **$1,005.4M** | **$678.0M** |

*Positive = net revenue gain for the State. Includes bracket microsim + credit overlay.*

**RECESSION scenario note:** The $1.3M difference from MID ($678.0M vs $679.3M) reflects that both tax systems face the same macro shock — the *delta* between them is largely preserved. See Section 8b for methodology and interpretation.

### MID Scenario Decomposition

| Channel | 5-year Total |
|---------|-------------:|
| Static bracket gain (13% top bracket + middle cuts) | +$498M |
| ETI / migration behavioral offset | −$71M |
| PTE election shift (ordinary income only; CG excluded) | −$185M |
| **Post-behavioral bracket delta** | **+$242M** |
| Credit overlay (REEC cap + CGEC sunset + TCRA) | +$437M |
| **Total MID** | **+$679M** |

*The bracket delta is lower than a naive static calculation because (a) the §235-16 CG cap limits the bracket-delta contribution of CG income to zero under both systems, and (b) behavioral responses reduce ordinary income subject to the 13% rate. The credit overlay is the second-largest component, dominated by REEC cap savings as the $40M cap phases to $0 by TY2031.*

### Distributional Impact — TY 2027 Bracket Change (MID)

| Quintile | Income Range | Avg Income | Delta $M | Avg $/Filer |
|----------|-------------|-----------|---------|------------|
| Q1 (Bottom 20%) | Below $11K | $2,919 | $0 | $0 |
| Q2 | $11K – $29K | $18,858 | −$0.3M | −$3 |
| Q3 | $29K – $54K | $41,070 | −$4.9M | −$42 |
| Q4 | $54K – $102K | $74,612 | −$9.8M | −$82 |
| Q5 (Top 20%) | $102K – $165M | $244,822 | +$97.6M | +$824 |

*Negative = filer pays less (savings from rate cut). Positive = filer pays more. Bracket change only; credit overlay excluded.*

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

4. **PTE capture rate uncertainty.** The 4pp arbitrage (13% individual vs. 9% PTE) creates a strong incentive for restructuring. The MID scenario's 70% capture rate is a judgment call — actual takeup depends on legal/accounting costs and awareness. This is the largest single source of model uncertainty.

5. **OBBBA demand uncertainty.** Federal repeal of Section 25D in 2025 creates genuine uncertainty for Hawaii solar demand 2026–2031. The three REEC scenarios bracket the plausible range from SEIA forecasts.

6. **No tax avoidance timing effects.** High-income filers may accelerate income recognition into 2026 (before the bill takes effect) or defer it to 2028 if they anticipate the 2029 bracket change. These timing effects are not modeled.

7. **Behavioral response is phased in linearly.** Migration and PTE election are assumed to phase in gradually. In practice, some response may occur immediately (legal restructuring) while other responses may be permanent (migration).

---

## 12. Scripts and File Map

### Forecast Scripts (repo root)

| Script | Purpose | Output |
|--------|---------|--------|
| `forecast_sb3125_cd1.py` | Original forecast with decile snapshot | `/tmp/sb3125_cd1_fiscal_impact_2027_2031.csv` |
| `forecast_sb3125_cd1_sensitivity.py` | Sensitivity across Pareto α × REEC scenarios (pre-behavioral) | `/tmp/sb3125_cd1_sensitivity_2027_2031.csv` |
| `forecast_sb3125_cd1_enhanced.py` | **Primary forecast** — 3 behavioral scenarios + RECESSION macro scenario | `/tmp/sb3125_cd1_enhanced_2027_2031.csv` |
| `forecast_sb3125_cd1_quintile.py` | Distributional analysis by income quintile (MID) | `/tmp/sb3125_cd1_quintile_2027_2031.csv` |

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

### Cache Files

| File | Description |
|------|-------------|
| `/tmp/tax_units_cache.parquet` | Calibrated base-year tax units (pre-synthesis); rebuilds in ~3 min if deleted |
| `/tmp/sb3125_cd1_enhanced_2027_2031.csv` | Final calibrated forecast results (all 3 scenarios) |
| `/tmp/sb3125_cd1_quintile_2027_2031.csv` | Quintile distributional results (MID, all 5 years) |

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
