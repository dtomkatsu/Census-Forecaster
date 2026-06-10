# RxKids Hawaiʻi — Methodology

> Companion documentation for `tax_modeler.programs.rxkids_hi`. Documents
> sourcing, parameter calibration, eligibility approximations, and
> known limitations. Required for advocacy use.

## 1. Program origin

**RxKids** is a universal prenatal + infant cash prescription program
launched in Flint, Michigan, in **January 2024** and administered by
**Michigan State University** with cash disbursement through
**GiveDirectly**. By mid-2026 it has expanded to **35+ Michigan
communities** including Kalamazoo, Detroit, multiple Wayne County
cities, and 15+ Upper Peninsula counties.

The program is the first community-wide implementation of a
prescription-style universal cash transfer in the perinatal window —
the period of life when child-poverty risk is highest and when
unconditional cash has the strongest measured effect on health,
material hardship, and economic stability outcomes (Hanna et al. 2025,
JAMA Network Open).

### Flint program parameters (as of May 2026)

| Parameter | Value |
|---|---|
| Operator | Michigan State University + GiveDirectly |
| Eligibility | Resident of designated community; minimum 16 weeks pregnant OR legal guardian of child <6 months |
| Income test | **None** (universal) |
| Medicaid test | **None** |
| Prenatal payment | **$1,500 one-time** (after 16 weeks pregnancy) |
| Postnatal payment | **$500/month for 6–12 months** (varies by community) |
| Tax treatment | Non-taxable charitable disbursement (GiveDirectly) |
| Observed take-up | **98%** of eligible newborns (Jan 2024–Sept 2025) |
| Cumulative reach (May 2026) | 10,774 families, $37.76M disbursed |

### Published outcomes evidence base

| Study | Year | Journal | Finding |
|---|---|---|---|
| Hanna et al. | 2025 | JAMA Network Open | ↑ prenatal care engagement |
| Hanna et al. | 2025 | American J. Public Health | ↑ maternal mental health; ↑ economic stability |
| Dickson et al. | 2024 | Family Justice Journal | ↓ child maltreatment via poverty reduction |
| Shaefer et al. | 2024 | The Lancet | Framework for universal child cash benefits |
| RxKids team | 2026 | RxKids Birth Impact brief | Births rose ~10% post-launch in Flint |

No published SPM-based poverty-reduction RCT is available yet — the
program is too new. Best evidence on mechanism: RxKids spending
analysis (2026) finds payments routed entirely to "essential needs —
starting with diapers", with measurable material hardship reductions.

## 2. Hawaii adaptation

This module models a **Hawaii-targeted variant** whose default
eligibility follows the **statutory** two-clause test (see §3): a unit
qualifies if it **either** (1) qualifies for benefits under the State's
Medicaid (Med-QUEST) program, **or** (2) has family income ≤ **300% FPL**
for a family of applicable size *including the expected unborn child(ren)*.
This is substantially broader than a Medicaid-only (138% FPL) gate and
sits between the Medicaid-targeted (~$8–15M) and fully-universal (~$110M)
cost poles.

A Medicaid-adult-only income variant remains achievable by overriding
`income_fpl_cap=1.38`; an effectively-universal variant by setting a high
cap (e.g. `10.0`). See the module docstring for override recipes.

### Hawaii context

- **Annual live births (2022)**: **15,535** — CDC NVSR 73-02, Table on
  births by state by race/ethnicity. Composition: 3,854 Asian /
  1,486 NHPI / 2,896 White / 326 Black / 2,701 Hispanic.
- **Births financed by Medicaid**: Hawaii estimate **~40%** (~6,200/yr)
  — Hawaii has higher employer-sponsored insurance coverage than the
  US average (national ~42%). KFF state health facts.
- **QUEST Integration income limits**: pregnant women 196% FPL,
  children 0-1 308% FPL, children 1-5 308% FPL, adults 138% FPL.
- **Hawaii has no RxKids-equivalent pending legislation** (2025
  session). Closest analogs: WIC HI (~31k participants), Healthy Start
  Hawaii (home visiting), Keiki O Ka Aina (early childhood) — none
  provide unrestricted cash.

### Parameter defaults (`RxKidsHIParams`)

| Parameter | Default | Rationale |
|---|---|---|
| `prenatal_monthly` | $1,500 | Flint's one-time prenatal payment (`prenatal_months=1`). |
| `postnatal_monthly_per_child` | $500 | Flint's postnatal monthly payment. |
| `prenatal_months` | 1 | One-time prenatal payment. |
| `postnatal_months` | 6 | Flint's 6-month postnatal window (lower bound of the 6–12 mo range). |
| `postnatal_age_cutoff` | 1 | Infants in their first year (Flint design). PUMS carries no sub-year age, so age 0 is the closest proxy. |
| `income_fpl_cap` | **3.00** | Statutory clause 2: 300% FPL income test (at family size). |
| `pregnant_fpl_cap` | **1.96** | Clause 1 prenatal Medicaid pregnancy pathway (196% FPL). Subsumed by the 300% income test at default; binds only if the income cap is set below 196%. |
| `takeup_rate` | 0.90 | Anchored by *delivery channel* (clinic-enrolled, sub-Flint) — see "Take-up rate — how it is anchored" below. |
| `is_taxable` | `False` | Match Flint design — charitable disbursement, not IRS-reported. Routes through SPM resources only. |
| `child_under_age_share` | 0.066 | **Proxy-only fallback** (used when no observed birth count is supplied; the forecast default is observed age-0 dependents — see §3). Annual qualifying-birth rate per dependent: Hawaii births 15,535 ÷ ACS dependents 0-17 ≈ 233,000. NOTE the proxy applies this to *all* `num_dependents` (~410k weighted, incl. adult dependents), overstating births ~1.7×; prefer the observed basis. Sensitivity: linear. |

Plus the Medicaid clause, evaluated in `compute_rxkids_for_units` from the
`medicaid_receives` column produced by `compute_medicaid_for_units` (the
caller pre-attaches it).

### Take-up rate — how it is anchored

`takeup_rate` (default **0.90**) is the single most important and least
data-anchored input — it scales the whole estimate linearly. It is set by
analogy, not by an administrative caseload (no Hawaiʻi RxKids exists). The
key principle: **take-up is driven primarily by the *delivery channel*, not
the benefit type.**

- **Tax-delivered** benefits (EITC, CTC) have take-up limited by tax-filing
  friction — non-filers, complexity, awareness. EITC ≈ 78% overall / ~85%
  for families with children; CTC ≈ 90% among filers.
- **Clinically enrolled / "prescribed"** benefits — RxKids' actual design in
  Flint (enroll at a prenatal-care visit, disbursed via GiveDirectly) — clear
  that friction because nearly every pregnant person has prenatal contact.
  Flint observed **98%** of eligible newborns. The same perinatal channel
  drives high take-up in WIC-infants (~90%+) and Medicaid-for-pregnant-women
  (~90%+).
- **Application-based** standalone programs sit lower (WIC pregnant/children
  ~55–65%; SNAP ~82%).

So **EITC/CTC are the right anchor only if Hawaiʻi delivers RxKids as a tax
credit.** For a Flint-style clinic-enrolled cash program, the perinatal
analogs (WIC-infants, Medicaid-pregnant, Flint itself) put steady-state
take-up at **~0.85–0.98**, which is why the 0.90 default is justified — and
why EITC/CTC should be treated as a *floor*, not the central estimate.

Reference scenarios by delivery channel (override with `--takeup-rate`):

| Delivery design | Take-up anchor | Rate |
|---|---|---|
| Refundable tax credit | EITC/CTC families | ~0.85 |
| **Clinic-enrolled, maturing (default)** | Perinatal analogs, sub-Flint | **0.90** |
| Flint-mature (hospital partnership) | Flint observed | 0.98 |
| Standalone application | WIC pregnant/children | ~0.60 |

**Arm-specific take-up.** Mothers enroll prenatally at a lower rate than
newborns are enrolled (Flint: ~90% prenatal vs ~98% of newborns). The model
sets postnatal (newborn) take-up = `takeup_rate` and prenatal take-up =
`takeup_rate × 0.92` (`PRENATAL_TAKEUP_RATIO`). So the **0.90 default →
postnatal 0.90 / prenatal 0.83**, and the Flint scenario (`--takeup-rate
0.98`) → 0.98 / 0.90, recovering Flint's observed arm rates. (The library
default leaves the two arms uniform; the forecast applies the split.)

Three structural notes: (1) take-up here is the **steady-state** rate — the
launch-year ramp (§10) separately models lower year-1 enrollment; (2) the
assumption band sweeps the postnatal rate (and scales prenatal with it), so
this uncertainty is in the reported range; (3) take-up figures are standard
IRS/USDA/CMS/RxKids estimates (see §8 for sourcing).

### Estimated annual cost (statutory eligibility)

The 300%-FPL-OR-Medicaid gate is far more inclusive than the legacy 138%
"Medicaid variant," so the modeled cost lands materially above the old
~$8–15M back-of-envelope and below the ~$110M fully-universal figure. The
authoritative figure is produced by `forecast_rxkids_2028.py` (see §10),
which weights the per-unit expected benefit by the PUMS household weight on
the real PUMS frame; the ranges below are only order-of-magnitude poles.

For reference, a **universal Flint-equivalent variant**:

- 15,535 births × $1,500 prenatal × 0.95 take-up = $22.1M
- 15,535 births × $500/mo × 12 × 0.95 = $88.5M
- **Total: ~$111M/yr**

## 3. Statutory eligibility (Medicaid OR 300% FPL incl. unborn)

A unit is eligible if it satisfies **either** clause:

- **Clause 1 — Medicaid.** Any member qualifies for benefits under the
  State's Medicaid (Med-QUEST) program. Implemented by reusing the
  `medicaid_receives` boolean from
  `tax_modeler.benefits.compute_medicaid_for_units` (all categorical
  pathways: 138% adult, 196% pregnant, 313% children, 100% aged). The
  caller pre-attaches this column; if it is absent the module applies
  clause 2 only and logs a warning.
- **Clause 2 — 300% FPL.** `income / FPL(family_size) <= income_fpl_cap`
  (default 3.00), tested at family size. A birth's family includes the
  child either way (the unborn child pre-birth equals the newborn
  dependent in the cross-section), so a single family-size test serves
  both arms — no separate "+unborn" increment is needed. For the prenatal
  arm, clause 1 additionally honors the Medicaid **pregnancy pathway**
  (`pregnant_fpl_cap`, 196% FPL); at the 300% default this is subsumed.

The income test uses the FPL table for the run's `tax_year`
(`benefits/_fpl.py`), so forward-projected incomes are tested against
same-year thresholds (see §7 caveat 4).

### Both arms are birth-driven

Both arms are driven by the same **birth events**. Two bases are supported:

- **Observed (default in `forecast_rxkids_2028.py`).** PUMS *does* carry
  individual ages: the tax-unit constructor records each claimed dependent's
  real age, so an **age-0 dependent is an infant born in the last ~12 months**
  — the annual birth flow, the correct basis for the full per-birth
  entitlement (not a <6-month stock, which understates ~2×). The per-unit
  observed birth count = the number of age-0 dependents (twins → 2). The
  forecast attaches this as `observed_births` and passes it to
  `compute_rxkids_for_units(..., birth_count_col="observed_births")`. The
  weighted observed count (~15,419 on the 2018–2022 5-yr frame) matches CDC
  NVSR resident births (15,535, 2022) within ~1%.

- **Proxy (library fallback; `--use-proxy-births`).**
  `birth_events = num_dependents × child_under_age_share`. The legacy basis,
  retained for backward comparison. It multiplies an *all-dependents* count
  (older children, students, adult dependents — ~410k weighted) by a rate
  calibrated against a *children-only* denominator (~233k), so it overstates
  total births ~1.7× and, because dependent counts skew toward lower-income
  families, inflates the eligible-birth share. **Prefer the observed basis.**

Either way a first birth shows up as the newborn dependent in the PUMS
cross-section, so the model captures **first AND repeat births across ALL
filing statuses** (married couples included), not just a single/HoH-no-
dependent proxy. The observed basis additionally fixes the proxy's level and
income-distribution biases.

#### Birth-cohort projection (observed basis)

The observed infant count is a *base-year* stock. Because the forecast ages
**incomes** to the target year, the **birth cohort** is aged coherently too:
the weighted observed count is calibrated to a single target via one scalar
factor folding in (1) the PUMS→vital-statistics base correction and (2) the
base-year→target-year trend. The trend comes from running the CDC NVSR
resident-birth series (`HI_BIRTHS_BY_YEAR`, by state of residence) through the
package's own damped-trend + AR(1) ensemble (`project_acs_ensemble`, φ=0.85/yr
annual cadence — the same machinery the income forecast uses). For TY2028 the
ensemble projects **~13,632 births** (90% PI ~[10,500, 16,800]) from a 2022
base of 15,535 — a ×0.884 factor, driven mainly by the 2023 drop to 14,643 in
an otherwise flat 2018–2022 series. Pass `--no-birth-projection` to hold the
cohort at the base-year level instead.

Each eligible birth draws one prenatal and one postnatal payment:

- **Prenatal** (`rxkids_prenatal_amount`): `birth_events × prenatal_monthly
  × prenatal_months × takeup_rate`, gated on `num_dependents > 0` AND
  (clause 1 incl. pregnancy pathway OR clause 2).
- **Postnatal** (`rxkids_postnatal_amount`): `birth_events ×
  postnatal_monthly_per_child × postnatal_months × takeup_rate`, gated on
  `num_dependents > 0` AND (clause 1 OR clause 2).

Both are **probabilistic** per unit, not deterministic; the weighted state
total recovers the right population-level expectation. At a uniform take-up
the prenatal arm is exactly **half** the postnatal arm (the $1,500 vs $3,000
per-birth payment ratio); with the default arm-specific take-up (§2) it is a
bit less than half (lower prenatal enrollment).

The combined `rxkids_amount = rxkids_prenatal_amount +
rxkids_postnatal_amount` is what feeds SPM resources; the two subtotals
let the cost report split program outlay by arm.

## 4. SPM resource accounting

RxKids cash is modeled as **non-taxable** (`is_taxable=False`), matching
the Flint program structure. This means:

1. `rxkids_amount` is **NOT added to** `total_cash_income` →
   no interaction with AGI / EITC / CTC phase-outs.
2. `rxkids_amount` **IS added to** `spm_resources` via the
   `rxkids_col` argument of `compute_spm_resources`.

The baseline `compute_poverty_impact` run passes `rxkids_col=None` so
baseline poverty reflects current Hawaii policy (no RxKids). The
`rxkids_hi` scenario adds `rxkids_amount` to baseline resources as
an expansion counterfactual.

If a Hawaii legislative proposal structured the payment differently
(e.g. as a refundable tax credit flowing through Form N-11), the
modeling would need to route `rxkids_amount` through AGI and recompute
EITC / CTC interactions — currently not supported.

## 5. Single-mother poverty disaggregation

`compute_poverty_impact` now returns a `by_household_type` frame
disaggregating poverty metrics by `filing_status`:

- `single` (no dependents)
- `head_of_household` (closest tax-unit proxy for single mother — an
  unmarried adult filing with at least one qualifying dependent)
- `married_filing_jointly`
- `married_filing_separately`

The `head_of_household` row is the **single-mother proxy** used for
RxKids analysis. The `by_state` frame is augmented with:

- `poverty_rate_hoh_baseline` — baseline HoH SPM rate
- `persons_in_poverty_hoh_baseline`
- `weighted_persons_hoh`
- `persons_lifted_{scenario}_hoh` — HoH-specific lift for each scenario
- `poverty_rate_{scenario}_hoh` — HoH-specific scenario rate

These let advocates cite the **single-mother-specific** poverty
reduction directly, which is the natural framing for a perinatal
cash-transfer program.

### Limitations of the HoH proxy

- HoH is a tax-filing status, not a household composition. Some HoH
  filers are not mothers (e.g. unmarried fathers, adult children
  caring for parents).
- Married mothers in low-income MFJ households also benefit but are
  not captured in the HoH row.
- Cohabiting unmarried mothers may file as `single` rather than HoH
  depending on dependent-claiming arrangements.
- As of Tier 4 (F-14), the poverty pipeline defaults to SPM-unit
  granularity per Census P60-280, so cohabiting partners and shared
  households are already pooled correctly. Single-mother attribution
  is the `single`/`head_of_household` subset of the SPM filing-status
  proxy (single adult with children).

## 6. Comparison to Flint outcomes

Projected Hawaii impact under default Medicaid-targeted parameters:

| Metric | Flint (observed) | HI projected (this model) |
|---|---|---|
| Take-up | 98% | 0.90 postnatal / 0.83 prenatal (default) |
| Avg disbursement / recipient | ~$3,505 (rolling) | ~$2,280 (prenatal+postnatal mix) |
| Reach | 10,774 families (cumulative) | ~12,700 recipients/yr (~6,100 pregnancies + ~6,600 infants) |
| Annual cost | ~$25-30M (single-city) | ~$29M benefit / ~$31M w/ admin (statutory 300%-FPL-OR-Medicaid); ~$111M (universal) |
| Persons lifted out of poverty | Not yet published | Reported per `--apply-rxkids` run |

The Hawaii model matches Flint's per-payment amounts ($1,500 one-time
prenatal, $500/mo postnatal); the difference from Flint is the eligibility
gate (statutory Medicaid-OR-300%-FPL vs Flint's universal no-test design) and
the conservative 0.90 take-up. Advocates can override parameters to model the
Flint-equivalent universal program — see the override recipe in the module
docstring.

## 7. Limitations & caveats

1. **Pregnancy not directly observable on PUMS** — the model uses **observed
   births** (age-0 dependents) as the common driver of both arms, calibrated
   to vital statistics and projected forward (§3). Each observed infant stands
   for one birth that had a prenatal period, so both arms are right in level
   and distribution. Unit-level amounts are still expectations (the prenatal
   arm is the observed infant standing in for its own pregnancy), not literal
   payments. The legacy `num_dependents × child_under_age_share` proxy remains
   available via `--use-proxy-births` but overstates births (§3).
2. **Birth basis** — postnatal (and prenatal) counts use age-0 dependents, an
   infant stock that ≈ the annual birth flow (an infant <1yr was born in the
   last ~12 months). This is the correct entitlement basis; a narrower
   <6-month stock would understate the postnatal arm ~2×. Twins are counted
   correctly (two age-0 dependents → two payments).
   Sensitivity: linear.
3. **No labor supply / fertility response modeled** — static
   counterfactual. The literature suggests unconditional cash
   transfers slightly reduce maternal labor supply (small effect,
   ~1-3 pp) but plausibly increase fertility on the margin. Neither
   is modeled.
4. **FPL is year-aware (`benefits/_fpl.py`)** — published 2024 and 2025
   HHS Hawaii tables, with CPI-projected forward years 2026–2028 (~2.3%/yr
   off the 2025 base, per CBO Jan 2025). `compute_rxkids_for_units` and
   `compute_medicaid_for_units` take a `tax_year` and test eligibility
   against that year's table, so a 2028 projection ages incomes AND
   thresholds coherently. The 2026–2028 inflator is an estimate; replace
   with a real HHS table when published.
5. **No admin-caseload anchor** — because RxKids is hypothetical for
   Hawaii, there's no IRS or DHS caseload to take-up-calibrate
   against (unlike SNAP, WIC, EITC). Take-up is set via the
   `takeup_rate` parameter; sensitivity sweep is the natural
   robustness check.
6. **HoH proxy ≠ single mother** — see Section 5 limitations.
7. **Modeled as charitable cash (non-taxable)** — if implemented as
   a refundable tax credit instead, the EITC/CTC phase-out
   interaction is not modeled.

## 8. Research findings (data collected 2026-05-16)

Compiled from `https://rxkids.org` (main page, /about, /impact/dashboard,
/impact/research/rx-kids-publications/), CDC NVSR 73-02 (2022 final
natality), Census P60-280 (SPM Technical Documentation), KFF state
health facts, and Hawaii DOH vital statistics index.

Key facts feeding this methodology:

- RxKids is **universal, residency-based, no income test, no Medicaid
  test** in its actual Flint implementation. Hawaii model defaults
  to a means-tested variant for cost reasons but supports universal
  modeling via parameter override.
- **98% take-up** of eligible newborns Jan 2024–Sept 2025 — universal
  design + hospital partnership are the take-up drivers.
- Hawaii **15,535 annual births (2022)** with ~40% Medicaid-financed
  → ~6,200 Medicaid births/yr. CDC NVSR resident-births series (by state of
  residence), used for the birth-cohort projection (`HI_BIRTHS_BY_YEAR`):
  2018 15,404 · 2019 15,403 · 2020 15,730 · 2021 15,620 · 2022 15,535 ·
  2023 14,643 (flat through 2022, then a notable 2023 drop).
- Hawaii Medicaid adult expansion threshold **138% FPL** — one of the
  Med-QUEST pathways feeding the clause-1 `medicaid_receives` test. The
  default `income_fpl_cap` is **3.00** (statutory clause 2), not 1.38.
- Modeling cash as **non-taxable resource** (added to SPM resources,
  not money income) matches Flint program structure and is the
  Census-recommended treatment for charitable cash disbursements
  (Census P60-280 §III).

### Updated literature review (data collected 2026-06)

A second, more thorough pass through the RxKids evidence base
(`rxkids.org/about`, `/impact`, `/dashboard`, `/research/publications`):

**Program design (validates the model's parameters):**
- Payments: **$1,500 prenatal + $500/mo for 6 *or* 12 months** — the
  duration is set per community by funds raised. (Confirms our payment
  amounts and the modeled 6-vs-12-month option.)
- **Universal, residency-based, no income test** in Michigan. (Confirms
  Michigan offers no income-eligibility-grain precedent — the Hawaiʻi
  income test is the bill's own design.)

**Take-up (empirical anchor for `takeup_rate`):**
- **98% of eligible newborns** enrolled (Jan 2024–Sept 2025); **>90% of
  mothers enroll prenatally** — "far exceeds WIC and SNAP." This is the
  direct evidence for the delivery-channel anchoring (§2) and shows the
  0.90 default is *conservative* vs Flint. It also distinguishes the arms:
  **postnatal ~0.98, prenatal ~0.90** (a possible model refinement).
- Dashboard (May 2026): **$41.77M disbursed, 11,751 families, 8,936 births**
  (~$3,553/family *to date* — a mid-stream snapshot, not the lifetime
  per-birth entitlement, so consistent with our ~$4,500 6-month per-birth).

**Fertility response (sources the +10% scenario):**
- **"Births rise nearly 10% following launch"** — *Rx Kids Flint Birth
  Report (2026)*. This is the basis for `--fertility-response 0.10`.
  **Caveat:** Flint's rise may blend a conception response with in-migration
  of pregnant residents into eligible areas; Hawaiʻi (island geography)
  would see far less migration, so the transferable fertility effect is
  uncertain — keep it an explicit, off-by-default scenario.

**Health/economic outcomes (enable a gross-vs-net framing):**
- *Lancet Public Health (2026)*, Richterman & Thirumurthy: **18% fewer
  preterm births, 27% fewer low-birthweight births.**
- *JAMA Network Open (2025)*, Hanna et al.: improved adequate prenatal care.
- *JAMA Pediatrics (2026)*, Agarwal et al.: ~**32% fewer infant-maltreatment
  investigations.**
- *Upjohn Institute (2025)*, Bartik et al.: **$0.60–$3.00 returned per $1**
  to the state economy.
- These are **offsets/benefits, not cost inputs** — the gross program cost
  (~$29M benefit / ~$31M appropriation, statutory eligibility) is partly offset
  by downstream health savings and economic return. A Hawaiʻi-scaled net-cost
  estimate is a natural extension (not yet built).

Cached research notes: `/tmp/rxkids-research.md` (session-scoped).

## 9. Verification

Tests at `tests/tax_modeler/programs/test_rxkids.py` cover:

- Clause 2: income ≤ 300% FPL eligible; > 300% (no Medicaid) excluded
- Clause 1: Medicaid receipt qualifies a unit above 300% FPL (proves OR)
- Birth-driven arms: a married (MFJ) family with a child draws a prenatal
  payment (previously excluded); a childless filer draws nothing
- Prenatal arm = exactly half the postnatal arm (per-birth payment ratio)
- Medicaid pregnancy pathway (196% FPL) binds the prenatal arm when the
  income cap is set below 196%
- Family-grain income test (household income/size, not per tax unit)
- Missing `medicaid_receives` column ⇒ clause-2-only fallback + warning
- High-income units excluded
- Postnatal amount scales linearly with `num_dependents`
- Non-taxable treatment: SPM resources increase by exactly
  `rxkids_amount`, while `total_cash_income` is unchanged
- Monotone take-up: higher `takeup_rate` ⇒ proportionally larger amount
- HoH baseline poverty rate strictly decreases under `rxkids_hi`
  scenario on calibrated synthetic cohort
- At least some persons lifted under realistic synthetic frames
- Backwards compatibility: runs without `rxkids_amount` column produce
  identical baselines and credit-removal results
- Override validation: unknown parameter keys raise `ConfigError`
- Range validation: out-of-range `takeup_rate` raises `ConfigError`
- Factory parity: `hawaii_rxkids_parameters()` matches documented defaults

Full suite: `.venv/bin/python -m pytest tests/tax_modeler/programs/ -v`

Integration run:
```bash
.venv/bin/python scripts/poverty_impact_report.py \
    --tax-year 2024 --apply-snap --apply-credit-takeup --apply-moop \
    --apply-housing-subsidy --apply-childcare-subsidy \
    --apply-spm-expenses --apply-rxkids \
    --scenarios rxkids_hi,no_eitc,no_ctc,hi_ctc_650 \
    --pums-data-dir packages/data/raw/pums \
    --out reports/rxkids_impact_2024/
```

Output CSVs (5):
`by_state.csv`, `by_county.csv`, `by_house_district.csv`,
`by_senate_district.csv`, `by_household_type.csv`.

Key columns on `by_state.csv` for RxKids analysis:
- `persons_lifted_rxkids_hi` — state total lift
- `persons_lifted_rxkids_hi_hoh` — HoH (single-mother proxy) lift
- `poverty_rate_hoh_baseline`, `poverty_rate_rxkids_hi_hoh`

## 10. Cost of implementation (2028)

`forecast_rxkids_2028.py` (repo root) estimates the **annual fiscal
outlay** of the program — distinct from the poverty *lift* scored by
`poverty_impact_report.py`.

### Cost identity

Program cost = the weighted sum of the expected RxKids benefit:

```
cost = Σ_SPM  rxkids_amount × weight
```

at **SPM-unit grain**, using the **WGTP-derived household weight** — the
correct fiscal weight. (The tax-unit `weight` is edited by the EITC
by-children reweight lever in the revenue path; the SPM-grain weight from
`aggregate_to_spm_units` is independent of that and is the right basis for
a fiscal total.) The prenatal/postnatal subtotals
(`rxkids_prenatal_amount`, `rxkids_postnatal_amount`) are summed the same
way and reported separately.

### Forward projection

1. Load PUMS with replicate weights; attach SPM unit IDs.
2. `project_tax_units_forward(target_year=2028)` ages incomes (WGTP weights
   carried forward unchanged).
3. FPL thresholds are taken at `tax_year=2028` (§7 caveat 4), so income and
   thresholds are on one coherent basis.
4. Compute `medicaid_receives` (clause 1) then the RxKids benefit, and
   aggregate to SPM units.

### Headline (real PUMS, TY2028)

| | Value |
|---|---|
| **Steady-state annual cost (benefit)** | **~$29M** (prenatal ~$9M + postnatal ~$20M) |
| Administrative load (8%) | +~$2.3M |
| **Appropriation total (benefit + admin)** | **~$31M** |
| Sampling 90% CI | ~$26M–$32M |
| **Assumption band (joint corners)** | **~$17M–$37M** |
| Expected recipients / year | ~12,700 (≈6,100 pregnancies + 6,600 infants) |
| Avg benefit per recipient | ~$2,280 |
| First fiscal year (launch, 12-mo ramp) | ~$12M (41% of steady) |
| Optional +6-month postnatal | +~$20M (12-month-design total ~$49M) |

> **Methodology revision (2026-06).** The birth driver changed from the
> ``num_dependents × child_under_age_share`` **proxy** to **observed** age-0
> dependents (PUMS), calibrated to CDC NVSR resident births and projected to
> 2028 with the repo's damped-trend ensemble. This roughly halves the headline
> ($53M → $29M). Decomposition: the proxy multiplied an *all-dependents* count
> (~410k weighted, incl. older children, students, adult dependents) by a rate
> calibrated against a *children-only* denominator (~233k), overstating total
> births ~1.7× and — because dependents skew toward lower-income families —
> inflating the eligible-birth share. Switching to observed births at the
> base-year level gives **~$33M** (−39%); the 2028 birth-cohort projection
> (×0.884, see below) takes it to **~$29M**. The admin line is new (the prior
> headline was pure benefit dollars).

Take-up is **arm-specific** (see §2): postnatal/newborn **0.90**, prenatal
**0.83** (0.92 × postnatal, from Flint's ~90% prenatal vs ~98% newborn). So
postnatal is a bit *more* than 2× prenatal — the 2× per-birth payment ratio
($3,000 vs $1,500) plus the lower prenatal take-up. (Single-rate runs, e.g.
the library default, keep both arms equal → prenatal exactly half.)

Eligibility is tested on the **MAGI household ≈ the tax unit** (filer +
spouse + tax dependents, the family concept Medicaid uses — 42 CFR 435.603),
on a **MAGI income proxy** (100% of Social Security, per Medicaid/ACA rules).
Because the statute anchors eligibility to Medicaid (clause 1), the 300% FPL
test (clause 2) uses the same MAGI-household grain — NOT the broader SPM
resource-sharing family (which would pool cohabiting partners / separately-
filing relatives whose income MAGI excludes) and NOT the physical household
(which would count unrelated roommates). See §10.

#### Scenarios (take-up + behavioral fertility)

The headline above is the **conservative** default (90% take-up, no
behavioral response). Two Flint-observed assumptions raise it:

| Scenario | Take-up (post/pre) | Fertility | Steady-state cost | Band |
|---|---|---|---|---|
| Conservative (default) | 0.90 / 0.83 | — | **~$29M** | ~$17–37M |
| **Flint-equivalent** | 0.98 / 0.90 | +10% | **~$35M** | ~$20–44M |

`--takeup-rate 0.98 --fertility-response 0.10` produces the Flint scenario —
which sets postnatal take-up to 0.98 and prenatal to 0.98 × 0.92 ≈ 0.90,
recovering Flint's *observed* arm rates exactly. The **fertility response**
(`_apply_fertility`) models the ~10% post-launch birth rise documented in the
*Rx Kids Flint Birth Report (2026)* as a uniform +10% on eligible births
(×1.10 on both arms): ~$29M × (0.98/0.90 take-up lift) × 1.10 ≈ $35M.
It is a real upside risk a static model would miss, but **off by default**:
Flint's rise may blend a conception response with in-migration of pregnant
residents into eligible areas, and Hawaiʻi's island geography would see far
less migration — so the transferable effect is uncertain.

### Eligible base vs recipients

"Eligible families" (~8k weighted on the observed basis — families with an
**observed birth** clearing the income/Medicaid test) is NOT the recipient
count. Actual **expected recipients** (pregnancies + infants) are ~12,700/yr,
recovered by dividing each arm's expected-dollar column by its full
per-recipient payment ($1,500 prenatal, $3,000 postnatal). Report recipients,
not the eligible base. (Under the legacy proxy the eligible base was ~96k —
every family with *any* dependent contributed fractional births; the observed
basis correctly restricts it to families with an actual infant.)

### Coherent arms (no birth-anchor needed)

Both arms are driven by the same birth events (§3), so prenatal expected
pregnancies = postnatal eligible births by construction — each eligible
birth draws one $1,500 prenatal + one $3,000 postnatal payment. (An earlier
model used a flat pregnancy probability over a single/HoH-no-dependent
universe, which overcounted pregnancies ~2× and required a runtime
"birth-anchor" rescale; the unified birth-driven arms remove that machinery.)

### Eligible-birth cross-check

On the **observed** basis the model implies **~7,300 eligible births** (=
~6,592 infant recipients ÷ 0.90 take-up) out of the ~13,632 projected 2028
births = **~54% of births eligible**, on the MAGI-household grain.

- **External anchor:** Hawaii Medicaid-financed births ≈ 40% (~6,200) — a
  *floor* (the pregnancy-Medicaid pathway sits at 196% FPL). The model's 54%
  sits above it, as it should: the gate (≤300% FPL OR Medicaid/CHIP) is
  broader than the pregnancy threshold.
- **Why ~54% (vs the proxy's inflated 86%)?** The proxy distributed
  *fractional* births across **all** families with dependents, in proportion
  to dependent count — and larger-dependent families skew lower-income, so the
  proxy over-weighted low-income families and pushed the eligible share to 86%
  (well above the ~60–65% Census-family benchmark). The **observed** births
  are the actual joint distribution of new infants × MAGI income; ~54% of them
  clear the gate. For a high-cost, high-median-income state where 300% FPL for
  a family of 3 is ~$85k, roughly half of birth families qualifying is
  plausible. The shift from 86% to 54% is the largest *qualitative* correction
  from the observed-births change.
- **Nuance:** clause 1 (Medicaid) is *broader* than clause 2 here because
  `medicaid_receives` includes the children's CHIP-equivalent pathway at
  **313% FPL** — slightly above the 300% income clause. That residual is the
  Medicaid clause's only marginal contribution and rests on treating
  CHIP-313% as "Medicaid" (a policy reading; see §4).

### Launch (first fiscal year)

`_first_year_disbursement` models year-1 cash, which is far below steady
state because (a) enrollment ramps from zero to full over `--ramp-months`
(default 12) and (b) the 6-month postnatal caseload takes 6 months to fill.
A monthly simulation sums prenatal payments scaled by enrollment and
postnatal payments scaled by the trailing-window caseload; postnatal
dollars that pay out past the fiscal year are reported as **deferred to the
next FY** (not lost). `--launch-operating-months` < 12 models a mid-year
launch. Ramp speed is the dominant year-1 driver (6/12/18-month sensitivity
is reported).

### Uncertainty

- **Sampling 90% CI** — SDR (Fay method, factor 4.0) over the 80 PUMS
  household replicate weights `weight_r01..weight_r80`, reusing
  `poverty.impact._sdr_se_from_replicates`. Captures ACS sampling error
  only (~±5%) and badly understates total uncertainty.
- **Assumption band (joint corners)** — the all-low and all-high corners of
  `takeup_rate` (swept around the assumed central value) and the **birth
  count** (±25%). In observed mode the ±25% multiplier is applied to the
  `observed_births` column directly (the `child_under_age_share` parameter is
  inert); the ±25% band also comfortably covers the ensemble birth-projection's
  ~±23% 90% PI. Cost is monotone in each, so the joint corners give the true
  outer envelope.
- **Overall MOE — treat as ±25–35%.** The estimate is dominated by
  **specification** uncertainty, not sampling. The birth driver is now
  observed-and-calibrated (a real improvement over the proxy), but take-up
  still has no admin caseload to calibrate against and the birth-cohort
  projection carries a wide PI, so present the headline as a point estimate
  **with the band always beside it**, never as a ±5% figure.

### Caveats specific to the 2028 run

- Federal EITC/CTC parameter tables fall back to TY2025 for years > 2025.
  **Immaterial here** — RxKids is non-taxable and never touches AGI /
  EITC / CTC.
- **Eligibility unit = MAGI household ≈ tax unit.** Medicaid/ACA define the
  household by tax-filing relationships (42 CFR 435.603) — filer + spouse +
  tax dependents — and the statute anchors clause 1 to Medicaid, so the 300%
  FPL test (clause 2) uses the same grain. Each tax unit is tested on its own
  MAGI at its own size. We do **not** pool to the SPM resource-sharing family
  (which would count cohabiting-partner / extended-family income that MAGI
  excludes — over-pooling that understates eligibility ~15%) nor to the
  physical household (which would count unrelated roommates). The income is a
  **MAGI proxy** (`_magi_proxy`): gross income with 100% of Social Security
  counted (the model's `income` counts only the 85% taxable portion), per
  Medicaid/ACA rules. Above-the-line deductions and tax-exempt interest are
  not observable in PUMS, so MAGI ≈ gross + SS add-back (a standard survey-
  based proxy). Residual: PUMS tax units approximate but do not perfectly
  match the MAGI-household composition rules; if the bill defines "family"
  more broadly than MAGI, the SPM-family grain (~$45M) is the alternative —
  a ~$9M / ~18% lever.
- The birth cohort is **projected to 2028** with the package's damped-trend
  ensemble off the CDC NVSR resident-birth series (`HI_BIRTHS_BY_YEAR`), so the
  demographic driver is aged coherently with income (×0.884 for 2028). Update
  `HI_BIRTHS_BY_YEAR` as new NVSR final-data releases land; pass
  `--no-birth-projection` to hold the cohort at the base-year level.
- Program cost is **benefit dollars**; an 8% administrative load (override
  `--admin-load`) is reported as a separate appropriation line. Cash-transfer
  admin loads typically run 5–10%.
- The 2026–2028 FPL inflator is a CPI projection, not a published table.

### Outputs (`reports/rxkids_2028/`)

- `cost_by_state.csv` — benefit cost, CI, admin load + appropriation total,
  birth driver + calibrated/target births, potential +6mo, launch year,
  recipients.
- `cost_by_county.csv` — per-county cost + expected recipients.
- `benefits_by_income_quintile.csv` — benefit received by income quintile.
- `rxkids_2028_cost_and_impact.xlsx` — workbook (Summary / quintile / county
  / assumptions / notes).
- `rxkids_2028_cost_and_impact.pdf` — one-page shareable summary.
- `spm_units.parquet` — SPM-grain frame.

Run:
```bash
.venv/bin/python forecast_rxkids_2028.py \
    --tax-year 2028 \
    --pums-data-dir packages/data/raw/pums \
    --out reports/rxkids_2028/
```
