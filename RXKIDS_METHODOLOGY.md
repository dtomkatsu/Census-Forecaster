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

This module models a **Hawaii-targeted variant** that defaults to a
**Medicaid-eligibility-gated** design (138% FPL adult cap), in
contrast to Flint's universal design. The narrow targeting brings the
program cost into a politically tractable ~$8–15M range vs ~$110M for
a universal Hawaii version scaled to all 15,535 annual births.

The universal variant remains achievable by overriding
`income_fpl_cap` to a high value — see the module docstring for the
override recipe.

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
| `prenatal_monthly` | $500 | Task-spec anchor; equivalent to a Hawaii-COL-scaled fraction of Flint's $1,500 one-time payment spread over 9 months. |
| `postnatal_monthly_per_child` | $125 | Task-spec anchor (Flint $60/mo with Hawaii COL adjustment ~2×). Lower than Flint actual ($500/mo) to keep targeted variant cost low. |
| `prenatal_months` | 9 | Full pregnancy. |
| `postnatal_age_cutoff` | 5 | Spans the ARPA CTC eligibility age range (vs Flint's age-1 cutoff). Lets the program complement HI CTC scenarios. |
| `income_fpl_cap` | 1.38 | Hawaii Medicaid adult expansion threshold (QUEST adults). |
| `takeup_rate` | 0.80 | Conservative vs Flint's observed 0.98; reflects year-1 ramp without hospital-partnership infrastructure. |
| `is_taxable` | `False` | Match Flint design — charitable disbursement, not IRS-reported. Routes through SPM resources only. |
| `prenatal_pregnancy_probability` | 0.12 | Hawaii Medicaid-financed births (~6,200/yr) ÷ Hawaii Medicaid-eligible adult women filing units (~50,000). Sensitivity: linear. |
| `child_under_age_share` | 0.20 | ACS PUMS 2018-2022 Hawaii: ~20% of dependents 0-17 in Medicaid-eligible households are 0-5. |

### Estimated annual cost (default Medicaid-targeted)

Working from the Hawaii synthetic-fixture eligibility share scaled to
real PUMS weights:

- **Prenatal**: ~5,000 eligible HoH/single women × 0.12 pregnancy ×
  $4,500 × 0.80 take-up ≈ **$2.2M**
- **Postnatal**: ~10,000 eligible HHs with kids × 0.5 effective kids 0-5
  × $1,500/yr × 0.80 take-up ≈ **$6M**
- **Total**: ~$8–15M/yr (highly sensitive to take-up and eligibility-cap
  assumptions)

For a **universal Flint-equivalent variant**:

- 15,535 births × $1,500 prenatal × 0.95 take-up = $22.1M
- 15,535 births × $500/mo × 12 × 0.95 = $88.5M
- **Total: ~$111M/yr**

## 3. Eligibility approximation

PUMS does not observe pregnancy and the tax-unit frame does not carry
individual child ages. The module uses two probabilistic adjustments
to bridge this gap.

### Prenatal universe

- Proxy: filers with `filing_status in {single, head_of_household}`
  AND `num_dependents == 0` AND `income <= income_fpl_cap × FPL`.
- Pregnancy probability: `prenatal_pregnancy_probability` per
  eligible filer per year (default 0.12).
- Per-unit expected amount:
  `pregnancy_prob × prenatal_monthly × prenatal_months × takeup_rate`.

This is a **probabilistic** payment per unit, not deterministic. The
weighted state total recovers the right population-level expectation;
individual-unit amounts are average expectations rather than literal
payments.

### Postnatal universe

- Proxy: filers with `num_dependents > 0` AND income test passed.
- Effective children under cutoff:
  `num_dependents × child_under_age_share`.
- Per-unit amount:
  `n_kids_under_cutoff × postnatal_monthly_per_child × 12 × takeup_rate`.

The `child_under_age_share` is the key approximation. A unit with
1 dependent doesn't deterministically have a child under 6 — but
across all eligible units the weighted total approximates the
correct postnatal population.

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
- For the most accurate single-mother attribution, the analysis should
  be paired with `--pool-spm-units` (Tier 2 PR #5) to merge
  cohabiting partners into shared SPM units.

## 6. Comparison to Flint outcomes

Projected Hawaii impact under default Medicaid-targeted parameters:

| Metric | Flint (observed) | HI projected (this model) |
|---|---|---|
| Take-up | 98% | 80% (default) |
| Avg disbursement / family | ~$3,505 (rolling) | $1,500–4,500 (postnatal/prenatal mix) |
| Reach (households) | 10,774 (cumulative) | ~6,000 single mothers + ~600 pregnant women / yr |
| Annual cost | ~$25-30M (single-city) | ~$8-15M (targeted) / ~$111M (universal) |
| Persons lifted out of poverty | Not yet published | Reported per `--apply-rxkids` run |

Hawaii's projected per-family payments are lower than Flint actuals
because (a) Flint's universal design uses a larger one-time prenatal
payment and (b) Flint's postnatal payment ($500/mo) exceeds the
Hawaii default ($125/mo). The Hawaii model is structured so that
advocates can override parameters to model the Flint-equivalent
universal program — see the universal-variant override recipe in the
module docstring.

## 7. Limitations & caveats

1. **Pregnancy not observable on PUMS** — prenatal eligibility is
   probabilistic. Population-level totals are reliable; unit-level
   amounts are expectations rather than literal payments.
2. **Per-child ages not on tax-unit frame** — postnatal payment
   counts depend on `child_under_age_share`. Sensitivity: linear.
   For a major shift in this share (e.g. 0.20 → 0.10), expect a 50%
   reduction in modeled postnatal cost.
3. **No labor supply / fertility response modeled** — static
   counterfactual. The literature suggests unconditional cash
   transfers slightly reduce maternal labor supply (small effect,
   ~1-3 pp) but plausibly increase fertility on the margin. Neither
   is modeled.
4. **Default uses 2024 FPL for all years 2022-2025** — Hawaii FPL
   grew ~10% over the span; treating eligibility as 2024-anchored
   biases eligibility ~5% high for 2022 and ~5% low for 2025.
   Material bias is small relative to the take-up uncertainty.
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
- Hawaii Medicaid adult expansion threshold **138% FPL** — used as
  default `income_fpl_cap`.
- Modeling cash as **non-taxable resource** (added to SPM resources,
  not money income) matches Flint program structure and is the
  Census-recommended treatment for charitable cash disbursements
  (Census P60-280 §III).

Cached research notes: `/tmp/rxkids-research.md` (session-scoped).

## 9. Verification

Tests at `tests/tax_modeler/programs/test_rxkids.py` cover:

- High-income units excluded (`income > 138% FPL × FPL` → zero)
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
