# Market-signals ablation — 2026-07-14

Panel: 1440 series; anchors [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]; horizons [1, 2, 3, 4, 5]. Gates: no RMSE regression > 2% absolute; CI90 coverage in [85%, 95%].

## ML arms — ensemble_with_ml, no-mkt (A) vs with-mkt (B)

| indicator | RMSE A | RMSE B | ΔRMSE | coverage A → B | flag |
|---|---|---|---|---|---|
| B01002_001E | 0.0187 | 0.0187 | -0.0000 | 88.38% → 88.55% |  |
| B19013_001E | 0.0681 | 0.0682 | +0.0001 | 87.80% → 87.84% |  |
| B20002_001E | 0.0694 | 0.0695 | +0.0001 | 87.44% → 88.24% |  |
| B25058_001E | 0.0744 | 0.0745 | +0.0001 | 86.70% → 86.66% |  |
| B25064_001E | 0.0726 | 0.0727 | +0.0001 | 87.67% → 87.53% |  |
| B25071_001E | 0.0956 | 0.0958 | +0.0003 | 88.41% → 88.44% |  |
| B25077_001E | 0.0884 | 0.0883 | -0.0000 | 86.26% → 85.96% |  |
| S1501_C02_014E | 0.0192 | 0.0192 | +0.0000 | 90.26% → 90.19% |  |
| S1501_C02_015E | 0.0843 | 0.0843 | -0.0001 | 88.28% → 87.07% |  |
| S1701_C03_001E | 0.1976 | 0.1971 | -0.0004 | 85.46% → 85.86% |  |
| S2301_C04_001E | 0.3636 | 0.3637 | +0.0001 | 87.20% → 87.13% |  |
| homeownership_rate | 0.0431 | 0.0430 | -0.0000 | 86.97% → 86.97% |  |
| in_migration_rate | 0.2270 | 0.2274 | +0.0004 | 90.65% → 90.98% |  |
| pct_professional | 0.0745 | 0.0743 | -0.0002 | 88.48% → 88.75% |  |
| pct_service_occupations | 0.1364 | 0.1351 | -0.0013 | 88.99% → 89.36% |  |
| vacancy_rate | 0.2691 | 0.2695 | +0.0004 | 90.36% → 90.66% |  |

### mkt_* permutation importance (year-effect collinearity check)

> **⚠️ These importance numbers are MISLABELED — do not cite them.**
> They were produced before the `FeatureSpec.column_names` ordering fix
> (2026-07-15): `column_names` disagreed with the real `_build_row`
> column order by the cross-indicator-column count, so `cols.index(name)`
> read the wrong column. The RMSE/coverage table above is unaffected
> (the model is name-blind; both arms use the same builder). Corrected
> importances live in `natl_unemp_ablation_2026-07-15.md` and are
> regression-guarded by `test_column_names_match_actual_row_order`.

- B19013_001E / mkt_energy_mom_lag0: +0.01789 ± 0.00075
- B19013_001E / mkt_shipping_mom_lag0: +0.00882 ± 0.00063
- B19013_001E / mkt_reit_mom_lag0: +0.00423 ± 0.00036
- B19013_001E / mkt_reit_mom_lag1: +0.00949 ± 0.00047
- B25077_001E / mkt_energy_mom_lag0: +0.00739 ± 0.00062
- B25077_001E / mkt_shipping_mom_lag0: +0.00406 ± 0.00021
- B25077_001E / mkt_reit_mom_lag0: +0.01159 ± 0.00076
- B25077_001E / mkt_reit_mom_lag1: +0.07253 ± 0.00114
- S2301_C04_001E / mkt_energy_mom_lag0: +0.00436 ± 0.00024
- S2301_C04_001E / mkt_shipping_mom_lag0: +0.02837 ± 0.00353
- S2301_C04_001E / mkt_reit_mom_lag0: +0.00475 ± 0.00048
- S2301_C04_001E / mkt_reit_mom_lag1: +0.00373 ± 0.00026

## Anchor arms — blended trend⊕anchor ensemble on S2301_C04_001E, row removed (C) vs active (D)

| indicator | RMSE C | RMSE D | ΔRMSE | coverage C → D | flag |
|---|---|---|---|---|---|
| S2301_C04_001E | 0.3821 | 0.3698 | -0.0123 | 91.74% → 88.19% |  |

## Anchor arms — level_anchor on S2301_C04_001E, row removed (C) vs active (D)

| indicator | RMSE C | RMSE D | ΔRMSE | coverage C → D | flag |
|---|---|---|---|---|---|
| S2301_C04_001E | 0.5037 | 0.5037 | +0.0000 | 89.98% → 89.98% |  |

## Anchor arms — multi_anchor on S2301_C04_001E, row removed (C) vs active (D)

| indicator | RMSE C | RMSE D | ΔRMSE | coverage C → D | flag |
|---|---|---|---|---|---|
| S2301_C04_001E | (absent) | 0.4505 | new member | — → 91.21% | new in with-row |

## Anchor arms — trend_ensemble on S2301_C04_001E, row removed (C) vs active (D)

| indicator | RMSE C | RMSE D | ΔRMSE | coverage C → D | flag |
|---|---|---|---|---|---|
| S2301_C04_001E | 0.3821 | 0.3821 | +0.0000 | 91.74% → 91.74% |  |

## Verdict: **GATE PASSED** — no RMSE regression, coverage in band. (`use_ml` remains opt-in regardless.)

---

## Disposition (post-run)

- **mkt_\* ML features: SHIPPED** (opt-in — `use_ml=False` default
  unchanged). Ensemble-level wash, in-band coverage; permutation
  importance shows real signal inside the ML member
  (`mkt_reit_mom_lag1` on B25077: +0.073 — the VNQ 12-month Granger
  lead reproduced as a tree feature).
- **National-unemployment rate anchor: REJECTED** despite the
  full-window RMSE gain — coverage cost (91.7% → 88.2%), recent-window
  regression (+2.7% on 2021/2022 anchors), and the rate-band invariant
  violation (0.47 vs 0.30). Registry row removed; removal pinned by
  tests. Arm-D rows above were produced with the row temporarily
  active for measurement.
