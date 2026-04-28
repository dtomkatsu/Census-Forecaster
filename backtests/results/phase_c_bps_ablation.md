# ML ablation: ensemble_with_ml (+ BPS) vs ensemble_v3

| Indicator | RMSE no-ml | RMSE ml+BPS | Δ (rel) | RMSE ml-noBPS | BPS Δ (rel) | Cov90 no-ml | Cov90 ml+BPS | n folds |
|---|---:|---:|---:||---:|---:|---:|---:|---:|

## ml_trend stand-alone metrics

| Indicator | RMSE-pct | Cov90 | n folds |
|---|---:|---:|---:|
| B01002_001E | 1.79% | 88.8% | 2713 |
| B19013_001E | 7.12% | 91.9% | 2713 |
| B20002_001E | 6.84% | 91.1% | 2713 |
| B25058_001E | 7.59% | 92.8% | 2713 |
| B25064_001E | 7.51% | 90.4% | 2713 |
| B25071_001E | 9.36% | 88.4% | 2713 |
| B25077_001E | 9.83% | 91.6% | 2713 |
| S1501_C02_014E | 1.81% | 91.6% | 2713 |
| S1501_C02_015E | 8.02% | 90.9% | 2713 |
| S1701_C03_001E | 20.82% | 91.4% | 2713 |
| S2301_C04_001E | 33.45% | 90.5% | 2636 |
| homeownership_rate | 3.99% | 92.4% | 2713 |
| in_migration_rate | 21.72% | 92.0% | 2709 |
| pct_professional | 6.93% | 90.1% | 2681 |
| pct_service_occupations | 12.85% | 93.5% | 2681 |
| vacancy_rate | 26.72% | 93.3% | 2713 |

## Ship gate verdict

* Rule 1 (≥75% indicators improve RMSE by ≥5%): **FAIL** (0/0 = 0.0%)
* Rule 2 (CI90 coverage ∈ [85%, 95%] for all indicators): **PASS**
* Rule 3 (no indicator regresses by > 2% RMSE): **PASS** (0 indicator(s) regressed)

## **Verdict: HOLD** — keep `use_ml=False` default; ship as opt-in only.