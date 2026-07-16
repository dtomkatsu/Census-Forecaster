# National-unemployment feature ablation (registry form) — 2026-07-16

Panel: 1440 series; anchors [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]; horizons [1, 2, 3, 4, 5]. Gates: no RMSE regression > 2% absolute; CI90 coverage in [85%, 95%]. Both arms carry mkt_* + the rest of the national-macro registry; the only difference is the 'unemp' registry entry (natl_unemp_lvl/chg1/chg2 — the migrated form of the former bespoke channel).

## ensemble_with_ml — sans-unemp (A) vs +unemp (B)

| indicator | RMSE A | RMSE B | ΔRMSE | coverage A → B | flag |
|---|---|---|---|---|---|
| B01002_001E | 0.0187 | 0.0187 | -0.0000 | 88.68% → 88.68% |  |
| B19013_001E | 0.0682 | 0.0682 | -0.0000 | 87.27% → 87.27% |  |
| B20002_001E | 0.0695 | 0.0693 | -0.0002 | 88.38% → 87.54% |  |
| B25058_001E | 0.0745 | 0.0745 | +0.0000 | 86.66% → 86.73% |  |
| B25064_001E | 0.0727 | 0.0728 | +0.0001 | 87.60% → 87.73% |  |
| B25071_001E | 0.0957 | 0.0956 | -0.0000 | 88.38% → 88.24% |  |
| B25077_001E | 0.0881 | 0.0881 | +0.0000 | 86.09% → 86.03% |  |
| S1501_C02_014E | 0.0192 | 0.0192 | -0.0000 | 89.89% → 89.96% |  |
| S1501_C02_015E | 0.0845 | 0.0844 | -0.0000 | 88.21% → 88.38% |  |
| S1701_C03_001E | 0.1974 | 0.1974 | +0.0000 | 85.36% → 85.52% |  |
| S2301_C04_001E | 0.3698 | 0.3687 | -0.0011 | 90.46% → 90.53% |  |
| homeownership_rate | 0.0429 | 0.0429 | +0.0000 | 87.30% → 87.24% |  |
| in_migration_rate | 0.2280 | 0.2278 | -0.0002 | 90.95% → 89.60% |  |
| pct_professional | 0.0746 | 0.0744 | -0.0002 | 88.75% → 88.89% |  |
| pct_service_occupations | 0.1350 | 0.1351 | +0.0001 | 89.80% → 89.60% |  |
| vacancy_rate | 0.2703 | 0.2692 | -0.0011 | 90.36% → 90.80% |  |

## natl_unemp_* permutation importance

- B19013_001E / natl_unemp_lvl: +0.00000 ± 0.00000
- B19013_001E / natl_unemp_chg1: +0.00009 ± 0.00003
- B19013_001E / natl_unemp_chg2: +0.00016 ± 0.00005
- S1701_C03_001E / natl_unemp_lvl: +0.00105 ± 0.00011
- S1701_C03_001E / natl_unemp_chg1: +0.00146 ± 0.00032
- S1701_C03_001E / natl_unemp_chg2: +0.01027 ± 0.00106
- S2301_C04_001E / natl_unemp_lvl: +0.00101 ± 0.00007
- S2301_C04_001E / natl_unemp_chg1: +0.00207 ± 0.00012
- S2301_C04_001E / natl_unemp_chg2: +0.00004 ± 0.00002

## Verdict: **GATE PASSED** — no RMSE regression, coverage in band. (`use_ml` remains opt-in.)

---

## Disposition (post-run) — registry migration verified

**Migration confirmed; feature remains SHIPPED (opt-in).** This re-run
proves the `unemp` registry entry (level_diff2) behaves correctly in the
migrated form: gate passed, and adding unemp on top of the rest of the
registry still *improves* S2301 unemployment (−0.0011) and vacancy_rate
(−0.0011) with coverage in band.

**On the importance drop vs the 2026-07-15 run (+0.243 → +0.001 for
S2301/lvl):** the feature values are bit-identical (pinned by equivalence
tests); what changed is the comparison context. The original run measured
unemployment as the ONLY national labour variable in the panel. Both arms
now carry the full registry — including employment-population ratio and
LFPR, near-mechanical correlates of the unemployment rate — and permutation
importance famously splits across correlated substitutes: permuting
natl_unemp_lvl barely hurts when the tree can reach for natl_emp_pop_lvl.
The +0.243 was the labour-market signal's TOTAL worth measured through one
column; that worth is now spread across the correlated labour columns.

**Follow-up worth considering** (noted in REGISTRY_MIGRATION_SCOPE.md
spirit): unemp / emp_pop / lfpr are three views of one labour market. A
future pruning pass could test whether one or two of them carry the family's
full signal — grouped permutation importance (permute the family together)
is the right instrument, not single-column importance.
