# Market-signals ablation — 2026-08-05

Panel: 1440 series; anchors [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]; horizons [1, 2, 3, 4, 5]. Gates: no RMSE regression > 2% absolute; CI90 coverage in [85%, 95%].

## ML arms — ensemble_with_ml, no-mkt (A) vs with-mkt (B)

| indicator | RMSE A | RMSE B | ΔRMSE | coverage A → B | flag |
|---|---|---|---|---|---|
| B01002_001E | 0.0187 | 0.0187 | +0.0000 | 88.71% → 88.68% |  |
| B19013_001E | 0.0679 | 0.0681 | +0.0001 | 86.49% → 86.46% |  |
| B20002_001E | 0.0694 | 0.0693 | -0.0002 | 88.51% → 87.54% |  |
| B25058_001E | 0.0740 | 0.0741 | +0.0001 | 86.83% → 86.66% |  |
| B25064_001E | 0.0722 | 0.0723 | +0.0002 | 87.87% → 87.94% |  |
| B25071_001E | 0.0954 | 0.0956 | +0.0002 | 88.44% → 88.24% |  |
| B25077_001E | 0.0883 | 0.0881 | -0.0002 | 85.96% → 86.03% |  |
| S1501_C02_014E | 0.0192 | 0.0192 | -0.0000 | 90.09% → 89.96% |  |
| S1501_C02_015E | 0.0845 | 0.0844 | -0.0001 | 88.14% → 88.38% |  |
| S1701_C03_001E | 0.1972 | 0.1974 | +0.0002 | 85.46% → 85.52% |  |
| S2301_C04_001E | 0.3690 | 0.3687 | -0.0003 | 90.15% → 90.53% |  |
| homeownership_rate | 0.0430 | 0.0429 | -0.0000 | 86.97% → 87.24% |  |
| in_migration_rate | 0.2276 | 0.2278 | +0.0002 | 90.81% → 89.60% |  |
| pct_professional | 0.0745 | 0.0744 | -0.0002 | 88.75% → 88.89% |  |
| pct_service_occupations | 0.1351 | 0.1351 | -0.0000 | 89.60% → 89.60% |  |
| vacancy_rate | 0.2690 | 0.2692 | +0.0002 | 90.53% → 90.80% |  |

### mkt_* permutation importance (year-effect collinearity check)

- B19013_001E / mkt_energy_mom_lag0: +0.00143 ± 0.00014
- B19013_001E / mkt_shipping_mom_lag0: +0.00129 ± 0.00015
- B19013_001E / mkt_reit_mom_lag0: +0.00181 ± 0.00027
- B19013_001E / mkt_reit_mom_lag1: +0.00295 ± 0.00027
- B25077_001E / mkt_energy_mom_lag0: +0.00083 ± 0.00017
- B25077_001E / mkt_shipping_mom_lag0: +0.00075 ± 0.00007
- B25077_001E / mkt_reit_mom_lag0: +0.00196 ± 0.00016
- B25077_001E / mkt_reit_mom_lag1: +0.01177 ± 0.00093
- S2301_C04_001E / mkt_energy_mom_lag0: +0.00941 ± 0.00049
- S2301_C04_001E / mkt_shipping_mom_lag0: +0.03519 ± 0.00236
- S2301_C04_001E / mkt_reit_mom_lag0: +0.01195 ± 0.00060
- S2301_C04_001E / mkt_reit_mom_lag1: +0.00819 ± 0.00062

## Verdict: **GATE PASSED** — no RMSE regression, coverage in band. (`use_ml` remains opt-in regardless.)
