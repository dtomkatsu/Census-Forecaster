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
| `child_under_age_share` | 0.066 | **Annual qualifying-birth rate per dependent (a FLOW)** — the common driver of BOTH arms: Hawaii births 15,535 ÷ ACS dependents 0-17 ≈ 233,000. Must be the full annual birth cohort, NOT a <6-month stock (a stock basis understates ~2×). Sensitivity: linear (scales total cost). |

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

Two structural notes: (1) 0.90 is the **steady-state** rate — the launch-year
ramp (§10) separately models lower year-1 enrollment; (2) the assumption band
already sweeps take-up, so this uncertainty is reflected in the reported
range. *(Take-up figures above are standard IRS/USDA/CMS estimates; see §8
for sourcing.)*

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

PUMS does not observe pregnancy or individual child ages, so both arms are
driven by the same **birth events**:

> `birth_events = num_dependents × child_under_age_share`

— the family's expected qualifying births this year. A first birth shows up
as the newborn dependent in the PUMS cross-section, so this captures **first
AND repeat births across ALL filing statuses** (married couples included),
not just a single/HoH-no-dependent proxy. (The earlier model restricted the
prenatal arm to childless single/HoH filers, which excluded married
first-time parents and repeat pregnancies — a distributional error this
unification fixes; it left the *total* unchanged.)

Each eligible birth draws one prenatal and one postnatal payment:

- **Prenatal** (`rxkids_prenatal_amount`): `birth_events × prenatal_monthly
  × prenatal_months × takeup_rate`, gated on `num_dependents > 0` AND
  (clause 1 incl. pregnancy pathway OR clause 2).
- **Postnatal** (`rxkids_postnatal_amount`): `birth_events ×
  postnatal_monthly_per_child × postnatal_months × takeup_rate`, gated on
  `num_dependents > 0` AND (clause 1 OR clause 2).

Both are **probabilistic** per unit, not deterministic; the weighted state
total recovers the right population-level expectation. Because both use the
same births and eligibility, the prenatal arm is exactly **half** the
postnatal arm (the $1,500 vs $3,000 per-birth payment ratio).

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
| Take-up | 98% | 80% (default) |
| Avg disbursement / family | ~$3,505 (rolling) | $1,500–4,500 (postnatal/prenatal mix) |
| Reach (households) | 10,774 (cumulative) | ~6,000 single mothers + ~600 pregnant women / yr |
| Annual cost | ~$25-30M (single-city) | ~$8-15M (targeted) / ~$111M (universal) |
| Persons lifted out of poverty | Not yet published | Reported per `--apply-rxkids` run |

The Hawaii model now matches Flint's per-payment amounts ($1,500
one-time prenatal, $500/mo postnatal); the difference from Flint is the
eligibility gate (statutory Medicaid-OR-300%-FPL vs Flint's universal
no-test design) and the conservative 0.90 take-up. Advocates can override
parameters to model the Flint-equivalent universal program — see the
override recipe in the module docstring.

## 7. Limitations & caveats

1. **Pregnancy not observable on PUMS** — both arms are probabilistic,
   driven by birth events (`num_dependents × child_under_age_share`). This
   captures first and repeat births across all filing statuses (married
   included), so the prenatal arm is now distributionally correct, not just
   right in total. Unit-level amounts are expectations, not literal payments.
2. **Per-child ages not on tax-unit frame** — postnatal counts depend on
   `child_under_age_share`, which must be the annual birth FLOW per
   dependent (~0.066), matched to the full per-birth entitlement. Using a
   point-in-time <6-month stock (~0.033) understates the postnatal arm ~2×.
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
  → ~6,200 Medicaid births/yr.
- Hawaii Medicaid adult expansion threshold **138% FPL** — one of the
  Med-QUEST pathways feeding the clause-1 `medicaid_receives` test. The
  default `income_fpl_cap` is **3.00** (statutory clause 2), not 1.38.
- Modeling cash as **non-taxable resource** (added to SPM resources,
  not money income) matches Flint program structure and is the
  Census-recommended treatment for charitable cash disbursements
  (Census P60-280 §III).

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
| **Steady-state annual cost** | **~$54M** (prenatal ~$18M + postnatal ~$36M) |
| Sampling 90% CI | ~$50M–$59M |
| **Assumption band (joint corners)** | **~$33M–$69M** |
| Expected recipients / year | ~24,200 (≈12,100 pregnancies + 12,100 infants) |
| Avg benefit per recipient | ~$2,250 |
| First fiscal year (launch, 12-mo ramp) | ~$23M (42% of steady) |
| Optional +6-month postnatal | +~$36M (12-month-design total ~$91M) |

Default take-up is **0.90** (see §2). Postnatal is ~2× prenatal purely by
payment design: each eligible birth draws a one-time $1,500 prenatal payment
but $500/mo × 6 = $3,000 postnatal — same recipients, double the per-birth
amount.

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

| Scenario | Take-up | Fertility | Steady-state cost | Band |
|---|---|---|---|---|
| Conservative (default) | 0.90 | — | **~$54M** | ~$33–69M |
| **Flint-equivalent** | 0.98 | +10% | **~$65M** | ~$39–83M |

`--takeup-rate 0.98 --fertility-response 0.10` produces the Flint scenario.
Take-up scales both arms linearly; the **fertility response**
(`_apply_fertility`) models Flint's documented ~10% post-launch birth rise
as a uniform +10% on eligible births (×1.10 on both arms). From the 0.90
default: $54M × (0.98/0.90) × 1.10 ≈ $65M. The fertility response is a real
upside risk a static model would miss; it is off by default and surfaced as
an explicit scenario.

### Eligible base vs recipients

"Eligible families" (~96k weighted, families with a child clearing the
income/Medicaid test) is NOT the recipient count. Actual **expected
recipients** (pregnancies + infants) are ~24,200/yr, recovered by dividing
each arm's expected-dollar column by its full per-recipient payment
($1,500 prenatal, $3,000 postnatal). Report recipients, not the eligible
base.

### Coherent arms (no birth-anchor needed)

Both arms are driven by the same birth events (§3), so prenatal expected
pregnancies = postnatal eligible births by construction — each eligible
birth draws one $1,500 prenatal + one $3,000 postnatal payment. (An earlier
model used a flat pregnancy probability over a single/HoH-no-dependent
universe, which overcounted pregnancies ~2× and required a runtime
"birth-anchor" rescale; the unified birth-driven arms remove that machinery.)

### Eligible-birth cross-check

The model implies **~13,400 eligible births** (= 12,089 infant recipients ÷
0.90 take-up) = **~86% of Hawaii's 15,535 annual births**, on the MAGI-
household grain.

- **External anchor:** Hawaii Medicaid-financed births ≈ 40% (~6,200) — a
  *floor* (the pregnancy-Medicaid pathway sits at 196% FPL). The model's 86%
  is well above it, as it should be: the gate (≤300% FPL OR Medicaid/CHIP) is
  far broader than the pregnancy threshold.
- **Why ~86% (vs ~73% under the SPM-family grain)?** The MAGI household is a
  **narrower income unit** — it excludes cohabiting-partner and extended-
  family income that the SPM resource-sharing family pools in. On the narrow
  (MAGI-correct) unit, more births fall under 300% FPL. This is higher than a
  *Census-family-income* benchmark (~60–65% nationally) would suggest, but
  that benchmark uses a broader income unit; the two are not directly
  comparable. The 86% is internally consistent with MAGI rules, which is the
  basis the Medicaid-anchored statute implies.
- **Nuance:** clause 1 (Medicaid) is *broader* than clause 2 here because
  `medicaid_receives` includes the children's CHIP-equivalent pathway at
  **313% FPL** — slightly above the 300% income clause. That ~5pp is the
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
- **Assumption band (joint corners)** — the all-low and all-high corners
  of `takeup_rate` (swept around the assumed central value) and
  `child_under_age_share` (±25%, the birth rate driving both arms). Cost is
  monotone in each, so the joint corners give the true outer envelope.
- **Overall MOE — treat as ±30–40%.** The estimate is dominated by
  **specification** uncertainty, not sampling. RxKids has no admin caseload
  to calibrate against, so the soft pregnancy-incidence and infant-share
  assumptions drive the answer. Present the headline as a point estimate
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
- Pregnancy incidence and child-age share are held at base-year values
  (no 2028 birth-trend adjustment); the assumption band brackets this.
- The 2026–2028 FPL inflator is a CPI projection, not a published table.

### Outputs (`reports/rxkids_2028/`)

- `cost_by_state.csv` — cost, CI, potential +6mo, launch year, recipients.
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
