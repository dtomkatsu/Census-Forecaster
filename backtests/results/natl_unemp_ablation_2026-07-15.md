# National-unemployment feature ablation — 2026-07-15

Panel: 1440 series; anchors [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]; horizons [1, 2, 3, 4, 5]. Gates: no RMSE regression > 2% absolute; CI90 coverage in [85%, 95%]. Both arms carry the shipped mkt_* market features; the only difference is the natl_unemp_* columns.

## ensemble_with_ml — baseline (A) vs +national-unemployment (B)

| indicator | RMSE A | RMSE B | ΔRMSE | coverage A → B | flag |
|---|---|---|---|---|---|
| B01002_001E | 0.0187 | 0.0187 | -0.0000 | 88.55% → 88.85% |  |
| B19013_001E | 0.0682 | 0.0682 | -0.0000 | 87.84% → 87.77% |  |
| B20002_001E | 0.0695 | 0.0693 | -0.0002 | 88.24% → 87.30% |  |
| B25058_001E | 0.0745 | 0.0746 | +0.0001 | 86.66% → 86.70% |  |
| B25064_001E | 0.0727 | 0.0726 | -0.0001 | 87.53% → 87.77% |  |
| B25071_001E | 0.0958 | 0.0971 | +0.0012 | 88.44% → 89.25% |  |
| B25077_001E | 0.0883 | 0.0882 | -0.0002 | 85.96% → 86.23% |  |
| S1501_C02_014E | 0.0192 | 0.0192 | -0.0000 | 90.19% → 90.49% |  |
| S1501_C02_015E | 0.0843 | 0.0846 | +0.0003 | 87.07% → 88.18% |  |
| S1701_C03_001E | 0.1971 | 0.1970 | -0.0001 | 85.86% → 85.62% |  |
| S2301_C04_001E | 0.3714 | 0.3710 | -0.0005 | 90.22% → 90.12% |  |
| homeownership_rate | 0.0430 | 0.0430 | -0.0000 | 86.97% → 87.17% |  |
| in_migration_rate | 0.2274 | 0.2273 | -0.0001 | 90.98% → 89.47% |  |
| pct_professional | 0.0743 | 0.0744 | +0.0001 | 88.75% → 88.34% |  |
| pct_service_occupations | 0.1351 | 0.1355 | +0.0004 | 89.36% → 89.26% |  |
| vacancy_rate | 0.2695 | 0.2694 | -0.0000 | 90.66% → 90.49% |  |

## natl_unemp_* permutation importance

- B19013_001E / natl_unemp_lag0: +0.00503 ± 0.00035
- B19013_001E / natl_unemp_chg1: +0.00129 ± 0.00013
- B19013_001E / natl_unemp_chg2: +0.00044 ± 0.00017
- S1701_C03_001E / natl_unemp_lag0: +0.00398 ± 0.00051
- S1701_C03_001E / natl_unemp_chg1: +0.00559 ± 0.00097
- S1701_C03_001E / natl_unemp_chg2: +0.03276 ± 0.00306
- S2301_C04_001E / natl_unemp_lag0: +0.24263 ± 0.00353
- S2301_C04_001E / natl_unemp_chg1: +0.00391 ± 0.00024
- S2301_C04_001E / natl_unemp_chg2: +0.00033 ± 0.00007

## Verdict: **GATE PASSED** — no RMSE regression, coverage in band. (`use_ml` remains opt-in.)

---

## Disposition (post-run)

**SHIPPED as an ML feature** (opt-in — `use_ml=False` default unchanged).

The ensemble-level RMSE is a wash (all |ΔRMSE| ≤ 0.0012, coverage in
band) because the ML member is blended down and geoid-constant national
signals act as year-effects at the ensemble level — same pattern as the
mkt_* features. But the permutation importances (trustworthy now that
`column_names` matches the real row order — see the ⚠️ note in
market_ml_ablation_2026-07-14.md) show the signal is real and lands
exactly where labour economics predicts:

- **S2301 (unemployment) / natl_unemp_lag0: +0.243** — by far the
  single strongest feature in any of these ablations. National
  unemployment level strongly predicts local unemployment growth.
- **S1701 (poverty) / natl_unemp_chg2: +0.033** — the 2-year change in
  national unemployment predicts poverty, which follows the labour
  market with a lag.
- B19013 (income) / natl_unemp_lag0: +0.005 — modest.

This is the vindication of moving the signal from the anchor path (which
FAILED — overconfident intervals, coverage collapse) to the feature
path: the same strong predictive content is now available for the tree
to use *when it helps*, without the anchor's coverage cost. The anchor's
0.47-vs-0.30 rate-band blowup is simply not a concern for a feature the
model weighs adaptively.
