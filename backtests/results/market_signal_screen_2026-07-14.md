# Market-signal screen — 2026-07-14

Pre-registered ticker→target hypotheses (16 pairs), Granger F-tests on monthly log-returns at lags 3/6/12, BH-FDR q=0.1. 16 tests run.

**Granger ≠ causation.** A pass means the ticker's past adds predictive content beyond the target's own past. Confounders survive this screen; the Phase-3 forecaster ablation is the final arbiter. mom12 rows are descriptive cross-correlations only (overlapping windows invalidate the F-test).

## Full sample

| ticker | transform | target | lags | F | p | n | best xcorr | BH pass | note |
|---|---|---|---|---|---|---|---|---|---|
| SPY | - | HI_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| QQQ | - | HI_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| VTI | - | HI_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| XLF | - | HI_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| JETS | - | HI_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| JETS | - | US_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| XLRE | log_return | HONOLULU_ZHVI | 3 | 3.73 | 0.0133 | 124 | +0.196@5m | **YES** |  |
| XLRE | log_return | HONOLULU_ZHVI | 6 | 3.46 | 0.0036 | 121 | +0.196@5m | **YES** |  |
| XLRE | log_return | HONOLULU_ZHVI | 12 | — | — | — | +0.196@5m | no | insufficient aligned months |
| XLRE | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.440@2m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLRE | log_return | HONOLULU_ZORI | 3 | 4.27 | 0.0067 | 124 | +0.266@2m | **YES** |  |
| XLRE | log_return | HONOLULU_ZORI | 6 | 1.45 | 0.2013 | 121 | +0.266@2m | no |  |
| XLRE | log_return | HONOLULU_ZORI | 12 | — | — | — | +0.266@2m | no | insufficient aligned months |
| XLRE | mom12 | HONOLULU_ZORI | — | — | — | — | +0.302@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| VNQ | log_return | HONOLULU_ZHVI | 3 | 2.33 | 0.0746 | 253 | +0.231@9m | no |  |
| VNQ | log_return | HONOLULU_ZHVI | 6 | 1.41 | 0.2100 | 250 | +0.231@9m | no |  |
| VNQ | log_return | HONOLULU_ZHVI | 12 | 2.33 | 0.0080 | 244 | +0.231@9m | **YES** |  |
| VNQ | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.492@1m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| VNQ | log_return | HONOLULU_ZORI | 3 | 4.70 | 0.0038 | 133 | +0.282@2m | **YES** |  |
| VNQ | log_return | HONOLULU_ZORI | 6 | 1.87 | 0.0920 | 130 | +0.282@2m | no |  |
| VNQ | log_return | HONOLULU_ZORI | 12 | — | — | — | +0.282@2m | no | insufficient aligned months |
| VNQ | mom12 | HONOLULU_ZORI | — | — | — | — | +0.316@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLE | log_return | HONOLULU_CPI | 3 | 8.47 | 0.0000 | 189 | +0.209@1m | **YES** |  |
| XLE | log_return | HONOLULU_CPI | 6 | 3.93 | 0.0010 | 183 | +0.209@1m | **YES** |  |
| XLE | log_return | HONOLULU_CPI | 12 | — | — | — | +0.209@1m | no | insufficient aligned months |
| XLE | mom12 | HONOLULU_CPI | — | — | — | — | +0.215@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| BOH | - | HI_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| FHB | - | HI_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| HE | - | HI_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| MATX | log_return | HONOLULU_CPI | 3 | 4.72 | 0.0034 | 189 | +0.265@3m | **YES** |  |
| MATX | log_return | HONOLULU_CPI | 6 | 2.45 | 0.0266 | 183 | +0.265@3m | **YES** |  |
| MATX | log_return | HONOLULU_CPI | 12 | — | — | — | +0.265@3m | no | insufficient aligned months |
| MATX | mom12 | HONOLULU_CPI | — | — | — | — | +0.120@2m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| MATX | log_return | HONOLULU_ZHVI | 3 | 0.44 | 0.7239 | 253 | +0.171@9m | no |  |
| MATX | log_return | HONOLULU_ZHVI | 6 | 0.76 | 0.6052 | 250 | +0.171@9m | no |  |
| MATX | log_return | HONOLULU_ZHVI | 12 | 1.35 | 0.1923 | 244 | +0.171@9m | no |  |
| MATX | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.466@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |

## 2020 excluded (COVID sensitivity) — 14 tests

A signal that only exists because of the 2020 crash is a one-event artifact, not a relationship.

| ticker | transform | target | lags | F | p | n | best xcorr | BH pass | note |
|---|---|---|---|---|---|---|---|---|---|
| SPY | - | HI_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| QQQ | - | HI_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| VTI | - | HI_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| XLF | - | HI_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| JETS | - | HI_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| JETS | - | US_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| XLRE | log_return | HONOLULU_ZHVI | 3 | 3.01 | 0.0336 | 108 | +0.193@5m | **YES** |  |
| XLRE | log_return | HONOLULU_ZHVI | 6 | — | — | — | +0.193@5m | no | insufficient aligned months |
| XLRE | log_return | HONOLULU_ZHVI | 12 | — | — | — | +0.193@5m | no | insufficient aligned months |
| XLRE | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.380@16m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLRE | log_return | HONOLULU_ZORI | 3 | 3.16 | 0.0278 | 108 | +0.244@2m | **YES** |  |
| XLRE | log_return | HONOLULU_ZORI | 6 | — | — | — | +0.244@2m | no | insufficient aligned months |
| XLRE | log_return | HONOLULU_ZORI | 12 | — | — | — | +0.244@2m | no | insufficient aligned months |
| XLRE | mom12 | HONOLULU_ZORI | — | — | — | — | +0.200@18m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| VNQ | log_return | HONOLULU_ZHVI | 3 | 1.93 | 0.1261 | 237 | +0.274@9m | no |  |
| VNQ | log_return | HONOLULU_ZHVI | 6 | 1.25 | 0.2832 | 231 | +0.274@9m | no |  |
| VNQ | log_return | HONOLULU_ZHVI | 12 | 2.61 | 0.0030 | 219 | +0.274@9m | **YES** |  |
| VNQ | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.523@3m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| VNQ | log_return | HONOLULU_ZORI | 3 | 3.36 | 0.0214 | 117 | +0.252@2m | **YES** |  |
| VNQ | log_return | HONOLULU_ZORI | 6 | 1.47 | 0.1958 | 111 | +0.252@2m | no |  |
| VNQ | log_return | HONOLULU_ZORI | 12 | — | — | — | +0.252@2m | no | insufficient aligned months |
| VNQ | mom12 | HONOLULU_ZORI | — | — | — | — | +0.144@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLE | log_return | HONOLULU_CPI | 3 | 7.28 | 0.0001 | 173 | +0.209@3m | **YES** |  |
| XLE | log_return | HONOLULU_CPI | 6 | 3.10 | 0.0068 | 164 | +0.209@3m | **YES** |  |
| XLE | log_return | HONOLULU_CPI | 12 | — | — | — | +0.209@3m | no | insufficient aligned months |
| XLE | mom12 | HONOLULU_CPI | — | — | — | — | +0.136@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| BOH | - | HI_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| FHB | - | HI_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| HE | - | HI_UNEMPLOYMENT | — | — | — | — | — | no | target series unavailable |
| MATX | log_return | HONOLULU_CPI | 3 | 5.28 | 0.0017 | 173 | +0.292@3m | **YES** |  |
| MATX | log_return | HONOLULU_CPI | 6 | 2.66 | 0.0176 | 164 | +0.292@3m | **YES** |  |
| MATX | log_return | HONOLULU_CPI | 12 | — | — | — | +0.292@3m | no | insufficient aligned months |
| MATX | mom12 | HONOLULU_CPI | — | — | — | — | -0.095@5m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| MATX | log_return | HONOLULU_ZHVI | 3 | 0.11 | 0.9563 | 237 | +0.152@9m | no |  |
| MATX | log_return | HONOLULU_ZHVI | 6 | 0.39 | 0.8820 | 231 | +0.152@9m | no |  |
| MATX | log_return | HONOLULU_ZHVI | 12 | 1.20 | 0.2826 | 219 | +0.152@9m | no |  |
| MATX | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.382@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |

## Annual descriptive leads (NO hypothesis tests — n≈10–15)

| ticker | target | lead (yrs) | r | n |
|---|---|---|---|---|
| SPY | LAUS_HI_UNEMPLOYMENT | 0 | +0.060 | 15 |
| SPY | LAUS_HI_UNEMPLOYMENT | 1 | +0.185 | 16 |
| SPY | LAUS_HI_UNEMPLOYMENT | 2 | -0.442 | 16 |
| SPY | LAUS_HI_UNEMPLOYMENT | 3 | +0.107 | 16 |
| JETS | LAUS_HI_UNEMPLOYMENT | 0 | -0.393 | 10 |
| JETS | LAUS_HI_UNEMPLOYMENT | 1 | +0.497 | 10 |
| JETS | LAUS_HI_UNEMPLOYMENT | 2 | -0.180 | 9 |
| JETS | LAUS_HI_UNEMPLOYMENT | 3 | +0.422 | 8 |
| BOH | SAIPE_HI_POVERTY | 0 | -0.047 | 14 |
| BOH | SAIPE_HI_POVERTY | 1 | -0.261 | 14 |
| BOH | SAIPE_HI_POVERTY | 2 | +0.302 | 14 |
| BOH | SAIPE_HI_POVERTY | 3 | -0.549 | 14 |
| XLRE | ZHVI_HONOLULU_ANNUAL | 0 | +0.044 | 10 |
| XLRE | ZHVI_HONOLULU_ANNUAL | 1 | +0.396 | 10 |
| XLRE | ZHVI_HONOLULU_ANNUAL | 2 | +0.060 | 9 |
| XLRE | ZHVI_HONOLULU_ANNUAL | 3 | +0.184 | 8 |
| VNQ | ZHVI_HONOLULU_ANNUAL | 0 | +0.204 | 20 |
| VNQ | ZHVI_HONOLULU_ANNUAL | 1 | +0.570 | 20 |
| VNQ | ZHVI_HONOLULU_ANNUAL | 2 | +0.001 | 19 |
| VNQ | ZHVI_HONOLULU_ANNUAL | 3 | +0.039 | 18 |
| MATX | ZHVI_HONOLULU_ANNUAL | 0 | +0.019 | 20 |
| MATX | ZHVI_HONOLULU_ANNUAL | 1 | +0.589 | 20 |
| MATX | ZHVI_HONOLULU_ANNUAL | 2 | -0.015 | 19 |
| MATX | ZHVI_HONOLULU_ANNUAL | 3 | +0.323 | 18 |

## Limitations

- Granger causality is predictive precedence, not causation.
- Monthly n≈130–250 depending on ticker inception; ZORI starts 2015, JETS 2015, XLRE 2015, FHB 2016.
- Annual-cadence rows are descriptive only and must never be cited as significant.
- Signals passing here still require the Phase-3 walk-forward ablation (RMSE improvement + CI90 coverage in [85%, 95%]) before touching any forecast.
