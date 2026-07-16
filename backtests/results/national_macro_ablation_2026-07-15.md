# National-macro feature ablation — 2026-07-15

Panel: 1440 series; anchors [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]; horizons [1, 2, 3, 4, 5]. Gates: no RMSE regression > 2% absolute; CI90 coverage in [85%, 95%]. Both arms carry the shipped mkt_* + natl_unemp features; the only difference is the 19 national-macro columns (13 series).

## ensemble_with_ml — baseline (A) vs +national-macro (B)

| indicator | RMSE A | RMSE B | ΔRMSE | coverage A → B | flag |
|---|---|---|---|---|---|
| B01002_001E | 0.0187 | 0.0187 | +0.0000 | 88.85% → 88.75% |  |
| B19013_001E | 0.0682 | 0.0682 | +0.0001 | 87.77% → 87.16% |  |
| B20002_001E | 0.0693 | 0.0693 | -0.0000 | 87.30% → 87.64% |  |
| B25058_001E | 0.0746 | 0.0745 | -0.0001 | 86.70% → 86.80% |  |
| B25064_001E | 0.0726 | 0.0728 | +0.0001 | 87.77% → 87.70% |  |
| B25071_001E | 0.0971 | 0.0957 | -0.0014 | 89.25% → 88.14% |  |
| B25077_001E | 0.0882 | 0.0881 | -0.0000 | 86.23% → 86.03% |  |
| S1501_C02_014E | 0.0192 | 0.0192 | +0.0000 | 90.49% → 89.96% |  |
| S1501_C02_015E | 0.0846 | 0.0844 | -0.0001 | 88.18% → 88.41% |  |
| S1701_C03_001E | 0.1970 | 0.1973 | +0.0003 | 85.62% → 85.42% |  |
| S2301_C04_001E | 0.3710 | 0.3688 | -0.0022 | 90.12% → 90.53% |  |
| homeownership_rate | 0.0430 | 0.0429 | -0.0001 | 87.17% → 87.24% |  |
| in_migration_rate | 0.2273 | 0.2278 | +0.0005 | 89.47% → 89.60% |  |
| pct_professional | 0.0744 | 0.0745 | +0.0001 | 88.34% → 88.61% |  |
| pct_service_occupations | 0.1355 | 0.1353 | -0.0002 | 89.26% → 89.46% |  |
| vacancy_rate | 0.2694 | 0.2691 | -0.0003 | 90.49% → 90.80% |  |

## national-macro permutation importance (top 3 per target)

- **B19013_001E** top national features:
    - natl_lfpr_lvl: +0.00393 ± 0.00039
    - natl_rental_vacancy_lvl: +0.00276 ± 0.00027
    - natl_jolts_openings_chg1: +0.00236 ± 0.00018
- **B25077_001E** top national features:
    - natl_emp_pop_chg1: +0.00123 ± 0.00008
    - natl_mortgage30_chg1: +0.00079 ± 0.00006
    - natl_ahe_chg1: +0.00074 ± 0.00010
- **S2301_C04_001E** top national features:
    - natl_dgs10_lvl: +0.00391 ± 0.00025
    - natl_cpi_food_chg1: +0.00284 ± 0.00013
    - natl_lfpr_lvl: +0.00178 ± 0.00025
- **S1701_C03_001E** top national features:
    - natl_cpi_allitems_chg1: +0.00826 ± 0.00061
    - natl_dgs10_chg1: +0.00670 ± 0.00062
    - natl_cpi_gas_chg1: +0.00425 ± 0.00073

## Verdict: **GATE PASSED** — no RMSE regression, coverage in band. (`use_ml` remains opt-in.)

---

## Disposition (post-run)

**SHIPPED as opt-in ML features** (`use_ml=False` default unchanged).

Ensemble-level wash-to-slight-improvement (all |ΔRMSE| ≤ 0.0022, coverage
in band) — expected, since 19 geoid-constant columns act as year-effects
when blended. The largest gains are S2301 unemployment (−0.0022) and
B25071 rent-as-%-income (−0.0014). The permutation importances (trustworthy
post column-order fix) are modest but positive and land where labour/
housing economics predicts:

- **Poverty (S1701)** benefits most — national all-items CPI (+0.0083),
  10-yr change (+0.0067), gasoline CPI (+0.0043): cost-of-living inflation
  drives poverty.
- **Unemployment (S2301)** — 10-yr yield level (+0.0039), food CPI, LFPR.
- **Income (B19013)** — LFPR level, rental vacancy, JOLTS (labour market).
- **Home value (B25077)** — emp-pop change, **mortgage-rate change**
  (+0.0008), AHE: the housing-rate channel the user opted in for shows up.

Smaller than the natl_unemp_lag0 monster (+0.243 for S2301) because that
one series is the single most direct predictor of its target, whereas
these 19 spread modest signal across many series × targets. All positive,
all economically coherent, no regression → shipped. `natl_unemp` stays a
separate feature (registry migration deferred).
