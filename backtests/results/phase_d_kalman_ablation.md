# Kalman ablation: kalman_state_space vs best-existing-baseline

| Indicator | Baseline | RMSE base | RMSE kalman | Δ (rel) | Cov90 kalman |
|---|---|---:|---:|---:|---:|
| B01002_001E | trend | 2.25% | 2.69% | +19.64% | 99.5% |
| B19013_001E | anchor | 6.89% | 7.25% | +5.19% | 94.9% |
| B20002_001E | trend | 7.81% | 8.15% | +4.26% | 92.3% |
| B25058_001E | anchor | 7.83% | 7.98% | +1.97% | 92.1% |
| B25064_001E | anchor | 7.60% | 7.96% | +4.84% | 92.7% |
| B25071_001E | trend | 12.08% | 10.80% | -10.60% | 93.8% |
| B25077_001E | anchor | 8.93% | 10.83% | +21.23% | 79.0% |
| S1501_C02_014E | trend | 2.57% | 3.12% | +21.33% | 99.5% |
| S1501_C02_015E | trend | 10.32% | 9.16% | -11.21% | 96.3% |
| S1701_C03_001E | anchor | 21.45% | 18.94% | -11.69% | 84.7% |
| S2301_C04_001E | trend | 38.21% | 36.46% | -4.58% | 66.4% |
| homeownership_rate | trend | 5.29% | 4.60% | -13.15% | 99.8% |
| in_migration_rate | trend | 28.47% | 25.24% | -11.34% | 77.8% |
| pct_professional | trend | 8.81% | 7.64% | -13.25% | 97.5% |
| pct_service_occupations | trend | 15.35% | 13.06% | -14.96% | 90.8% |
| vacancy_rate | trend | 30.04% | 26.71% | -11.10% | 70.0% |

## Ship gate verdict

* Rule 1 (≥75% indicators improve RMSE by ≥5% vs best baseline): **FAIL** (8/16 = 50.0%)
* Rule 2 (CI90 coverage ∈ [85%, 95%] for all indicators): **FAIL** (failing: 10: B01002_001E, B25077_001E, S1501_C02_014E, S1501_C02_015E, S1701_C03_001E...)
* Rule 3 (no indicator regresses by > 2% RMSE): **FAIL** (6 regressed)

## **Verdict: HOLD** — kalman opt-in only (`use_kalman=False` default retained).

## Notes

- Infrastructure complete: kalman/ module, 24 unit tests, fold residuals in calibration.
- Coverage failures driven by diffuse init (too-wide CIs on smooth indicators:
  B01002, S1501_C02_014E, homeownership_rate) and COVID-era shocks
  (too-narrow CIs on S2301, vacancy_rate, in_migration_rate).
- Per-indicator allowlist candidates (≥5% RMSE vs baseline AND coverage in band):
  pct_service_occupations (−15.0%, 90.8%), B25071 (−10.6%, 93.8%).
