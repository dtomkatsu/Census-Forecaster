# Market-signal screen — 2026-08-05

Pre-registered ticker→target hypotheses (27 pairs), Granger F-tests on monthly log-returns at lags 3/6/12, BH-FDR q=0.1. 68 tests run.

**Granger ≠ causation.** A pass means the ticker's past adds predictive content beyond the target's own past. Confounders survive this screen; the Phase-3 forecaster ablation is the final arbiter. mom12 rows are descriptive cross-correlations only (overlapping windows invalidate the F-test).

## Full sample

| ticker | transform | target | lags | F | p | n | best xcorr | BH pass | note |
|---|---|---|---|---|---|---|---|---|---|
| SPY | log_return | HI_UNEMPLOYMENT | 3 | 7.92 | 0.0000 | 249 | -0.243@1m | **YES** |  |
| SPY | log_return | HI_UNEMPLOYMENT | 6 | 4.05 | 0.0007 | 243 | -0.243@1m | **YES** |  |
| SPY | log_return | HI_UNEMPLOYMENT | 12 | 2.75 | 0.0017 | 236 | -0.243@1m | **YES** |  |
| SPY | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.119@1m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| QQQ | log_return | HI_UNEMPLOYMENT | 3 | 3.02 | 0.0305 | 249 | -0.157@16m | **YES** |  |
| QQQ | log_return | HI_UNEMPLOYMENT | 6 | 1.42 | 0.2094 | 243 | -0.157@16m | no |  |
| QQQ | log_return | HI_UNEMPLOYMENT | 12 | 1.41 | 0.1648 | 236 | -0.157@16m | no |  |
| QQQ | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.103@1m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| VTI | log_return | HI_UNEMPLOYMENT | 3 | 8.51 | 0.0000 | 249 | -0.260@1m | **YES** |  |
| VTI | log_return | HI_UNEMPLOYMENT | 6 | 4.32 | 0.0004 | 243 | -0.260@1m | **YES** |  |
| VTI | log_return | HI_UNEMPLOYMENT | 12 | 2.89 | 0.0010 | 236 | -0.260@1m | **YES** |  |
| VTI | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.126@1m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLF | log_return | HI_UNEMPLOYMENT | 3 | 8.07 | 0.0000 | 249 | -0.267@1m | **YES** |  |
| XLF | log_return | HI_UNEMPLOYMENT | 6 | 4.36 | 0.0003 | 243 | -0.267@1m | **YES** |  |
| XLF | log_return | HI_UNEMPLOYMENT | 12 | 2.85 | 0.0012 | 236 | -0.267@1m | **YES** |  |
| XLF | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.096@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| JETS | log_return | HI_UNEMPLOYMENT | 3 | 15.68 | 0.0000 | 126 | -0.455@1m | **YES** |  |
| JETS | log_return | HI_UNEMPLOYMENT | 6 | 8.57 | 0.0000 | 120 | -0.455@1m | **YES** |  |
| JETS | log_return | HI_UNEMPLOYMENT | 12 | — | — | — | -0.455@1m | no | insufficient aligned months |
| JETS | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.167@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| JETS | log_return | US_UNEMPLOYMENT | 3 | 13.52 | 0.0000 | 127 | -0.447@1m | **YES** |  |
| JETS | log_return | US_UNEMPLOYMENT | 6 | 7.79 | 0.0000 | 121 | -0.447@1m | **YES** |  |
| JETS | log_return | US_UNEMPLOYMENT | 12 | — | — | — | -0.447@1m | no | insufficient aligned months |
| JETS | mom12 | US_UNEMPLOYMENT | — | — | — | — | +0.132@4m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
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
| XLE | log_return | HONOLULU_CPI | 3 | — | — | — | +0.363@2m | no | insufficient aligned months |
| XLE | log_return | HONOLULU_CPI | 6 | — | — | — | +0.363@2m | no | insufficient aligned months |
| XLE | log_return | HONOLULU_CPI | 12 | — | — | — | +0.363@2m | no | insufficient aligned months |
| XLE | mom12 | HONOLULU_CPI | — | — | — | — | +0.430@2m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLE | log_return | HI_ELECTRICITY | 3 | 24.54 | 0.0000 | 253 | +0.402@3m | **YES** |  |
| XLE | log_return | HI_ELECTRICITY | 6 | 15.00 | 0.0000 | 250 | +0.402@3m | **YES** |  |
| XLE | log_return | HI_ELECTRICITY | 12 | 7.39 | 0.0000 | 244 | +0.402@3m | **YES** |  |
| XLE | mom12 | HI_ELECTRICITY | — | — | — | — | +0.317@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| BOH | log_return | HI_UNEMPLOYMENT | 3 | 8.01 | 0.0000 | 249 | -0.248@1m | **YES** |  |
| BOH | log_return | HI_UNEMPLOYMENT | 6 | 5.20 | 0.0000 | 243 | -0.248@1m | **YES** |  |
| BOH | log_return | HI_UNEMPLOYMENT | 12 | 2.98 | 0.0007 | 236 | -0.248@1m | **YES** |  |
| BOH | mom12 | HI_UNEMPLOYMENT | — | — | — | — | +0.127@4m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| FHB | log_return | HI_UNEMPLOYMENT | 3 | 8.63 | 0.0000 | 110 | -0.396@1m | **YES** |  |
| FHB | log_return | HI_UNEMPLOYMENT | 6 | 5.48 | 0.0001 | 104 | -0.396@1m | **YES** |  |
| FHB | log_return | HI_UNEMPLOYMENT | 12 | — | — | — | -0.396@1m | no | insufficient aligned months |
| FHB | mom12 | HI_UNEMPLOYMENT | — | — | — | — | +0.145@4m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HE | log_return | HI_UNEMPLOYMENT | 3 | 0.44 | 0.7269 | 249 | -0.066@2m | no |  |
| HE | log_return | HI_UNEMPLOYMENT | 6 | 0.39 | 0.8851 | 243 | -0.066@2m | no |  |
| HE | log_return | HI_UNEMPLOYMENT | 12 | 0.23 | 0.9969 | 236 | -0.066@2m | no |  |
| HE | mom12 | HI_UNEMPLOYMENT | — | — | — | — | +0.062@3m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| MATX | log_return | HONOLULU_CPI | 3 | — | — | — | +0.339@7m | no | insufficient aligned months |
| MATX | log_return | HONOLULU_CPI | 6 | — | — | — | +0.339@7m | no | insufficient aligned months |
| MATX | log_return | HONOLULU_CPI | 12 | — | — | — | +0.339@7m | no | insufficient aligned months |
| MATX | mom12 | HONOLULU_CPI | — | — | — | — | +0.470@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| MATX | log_return | HI_ELECTRICITY | 3 | 5.59 | 0.0010 | 253 | +0.190@4m | **YES** |  |
| MATX | log_return | HI_ELECTRICITY | 6 | 3.07 | 0.0065 | 250 | +0.190@4m | **YES** |  |
| MATX | log_return | HI_ELECTRICITY | 12 | 1.90 | 0.0360 | 244 | +0.190@4m | **YES** |  |
| MATX | mom12 | HI_ELECTRICITY | — | — | — | — | +0.221@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| MATX | log_return | HONOLULU_ZHVI | 3 | 0.44 | 0.7239 | 253 | +0.171@9m | no |  |
| MATX | log_return | HONOLULU_ZHVI | 6 | 0.76 | 0.6052 | 250 | +0.171@9m | no |  |
| MATX | log_return | HONOLULU_ZHVI | 12 | 1.35 | 0.1923 | 244 | +0.171@9m | no |  |
| MATX | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.466@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HE | log_return | HI_ELECTRICITY | 3 | 0.67 | 0.5688 | 253 | -0.100@8m | no |  |
| HE | log_return | HI_ELECTRICITY | 6 | 1.05 | 0.3917 | 250 | -0.100@8m | no |  |
| HE | log_return | HI_ELECTRICITY | 12 | 0.88 | 0.5701 | 244 | -0.100@8m | no |  |
| HE | mom12 | HI_ELECTRICITY | — | — | — | — | +0.089@13m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_MORTGAGE30 | log_return | HONOLULU_ZHVI | 3 | 0.76 | 0.5186 | 313 | +0.180@0m | no |  |
| US_MORTGAGE30 | log_return | HONOLULU_ZHVI | 6 | 3.69 | 0.0015 | 310 | +0.180@0m | **YES** |  |
| US_MORTGAGE30 | log_return | HONOLULU_ZHVI | 12 | 3.31 | 0.0002 | 304 | +0.180@0m | **YES** |  |
| US_MORTGAGE30 | mom12 | HONOLULU_ZHVI | — | — | — | — | -0.312@15m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_MORTGAGE30 | log_return | HONOLULU_ZORI | 3 | 1.46 | 0.2285 | 133 | -0.188@9m | no |  |
| US_MORTGAGE30 | log_return | HONOLULU_ZORI | 6 | 0.29 | 0.9412 | 130 | -0.188@9m | no |  |
| US_MORTGAGE30 | log_return | HONOLULU_ZORI | 12 | — | — | — | -0.188@9m | no | insufficient aligned months |
| US_MORTGAGE30 | mom12 | HONOLULU_ZORI | — | — | — | — | -0.130@18m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_DGS10 | log_return | HONOLULU_ZHVI | 3 | 0.58 | 0.6255 | 313 | +0.149@0m | no |  |
| US_DGS10 | log_return | HONOLULU_ZHVI | 6 | 1.78 | 0.1024 | 310 | +0.149@0m | no |  |
| US_DGS10 | log_return | HONOLULU_ZHVI | 12 | 2.13 | 0.0154 | 304 | +0.149@0m | **YES** |  |
| US_DGS10 | mom12 | HONOLULU_ZHVI | — | — | — | — | -0.380@18m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_JOLTS | log_return | US_UNEMPLOYMENT | 3 | 6.07 | 0.0005 | 250 | -0.218@1m | **YES** |  |
| US_JOLTS | log_return | US_UNEMPLOYMENT | 6 | 4.15 | 0.0006 | 244 | -0.218@1m | **YES** |  |
| US_JOLTS | log_return | US_UNEMPLOYMENT | 12 | 2.28 | 0.0097 | 236 | -0.218@1m | **YES** |  |
| US_JOLTS | mom12 | US_UNEMPLOYMENT | — | — | — | — | -0.200@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_JOLTS | log_return | HI_UNEMPLOYMENT | 3 | 6.46 | 0.0003 | 249 | -0.228@1m | **YES** |  |
| US_JOLTS | log_return | HI_UNEMPLOYMENT | 6 | 3.74 | 0.0014 | 243 | -0.228@1m | **YES** |  |
| US_JOLTS | log_return | HI_UNEMPLOYMENT | 12 | 1.96 | 0.0295 | 236 | -0.228@1m | **YES** |  |
| US_JOLTS | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.163@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_AHE | log_return | HI_UNEMPLOYMENT | 3 | 1.95 | 0.1226 | 235 | +0.818@0m | no |  |
| US_AHE | log_return | HI_UNEMPLOYMENT | 6 | 1.66 | 0.1317 | 229 | +0.818@0m | no |  |
| US_AHE | log_return | HI_UNEMPLOYMENT | 12 | 1.52 | 0.1187 | 222 | +0.818@0m | no |  |
| US_AHE | mom12 | HI_UNEMPLOYMENT | — | — | — | — | +0.195@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_LFPR | log_return | HI_UNEMPLOYMENT | 3 | 7.44 | 0.0001 | 249 | -0.759@0m | **YES** |  |
| US_LFPR | log_return | HI_UNEMPLOYMENT | 6 | 4.07 | 0.0007 | 243 | -0.759@0m | **YES** |  |
| US_LFPR | log_return | HI_UNEMPLOYMENT | 12 | 3.17 | 0.0004 | 236 | -0.759@0m | **YES** |  |
| US_LFPR | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.195@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_EMPPOP | log_return | HI_UNEMPLOYMENT | 3 | 29.38 | 0.0000 | 249 | -0.961@0m | **YES** |  |
| US_EMPPOP | log_return | HI_UNEMPLOYMENT | 6 | 15.77 | 0.0000 | 243 | -0.961@0m | **YES** |  |
| US_EMPPOP | log_return | HI_UNEMPLOYMENT | 12 | 8.85 | 0.0000 | 236 | -0.961@0m | **YES** |  |
| US_EMPPOP | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.288@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |

## 2020 excluded (COVID sensitivity) — 62 tests

A signal that only exists because of the 2020 crash is a one-event artifact, not a relationship.

| ticker | transform | target | lags | F | p | n | best xcorr | BH pass | note |
|---|---|---|---|---|---|---|---|---|---|
| SPY | log_return | HI_UNEMPLOYMENT | 3 | 0.24 | 0.8699 | 233 | -0.192@1m | no |  |
| SPY | log_return | HI_UNEMPLOYMENT | 6 | 0.44 | 0.8507 | 224 | -0.192@1m | no |  |
| SPY | log_return | HI_UNEMPLOYMENT | 12 | 0.95 | 0.4962 | 211 | -0.192@1m | no |  |
| SPY | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.464@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| QQQ | log_return | HI_UNEMPLOYMENT | 3 | 0.31 | 0.8153 | 233 | -0.137@1m | no |  |
| QQQ | log_return | HI_UNEMPLOYMENT | 6 | 0.32 | 0.9244 | 224 | -0.137@1m | no |  |
| QQQ | log_return | HI_UNEMPLOYMENT | 12 | 0.82 | 0.6327 | 211 | -0.137@1m | no |  |
| QQQ | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.360@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| VTI | log_return | HI_UNEMPLOYMENT | 3 | 0.28 | 0.8415 | 233 | -0.183@1m | no |  |
| VTI | log_return | HI_UNEMPLOYMENT | 6 | 0.43 | 0.8588 | 224 | -0.183@1m | no |  |
| VTI | log_return | HI_UNEMPLOYMENT | 12 | 0.94 | 0.5072 | 211 | -0.183@1m | no |  |
| VTI | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.445@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLF | log_return | HI_UNEMPLOYMENT | 3 | 0.24 | 0.8709 | 233 | -0.245@0m | no |  |
| XLF | log_return | HI_UNEMPLOYMENT | 6 | 0.53 | 0.7844 | 224 | -0.245@0m | no |  |
| XLF | log_return | HI_UNEMPLOYMENT | 12 | 0.84 | 0.6141 | 211 | -0.245@0m | no |  |
| XLF | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.569@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| JETS | log_return | HI_UNEMPLOYMENT | 3 | 0.32 | 0.8101 | 110 | -0.261@7m | no |  |
| JETS | log_return | HI_UNEMPLOYMENT | 6 | — | — | — | -0.261@7m | no | insufficient aligned months |
| JETS | log_return | HI_UNEMPLOYMENT | 12 | — | — | — | -0.261@7m | no | insufficient aligned months |
| JETS | mom12 | HI_UNEMPLOYMENT | — | — | — | — | +0.370@12m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| JETS | log_return | US_UNEMPLOYMENT | 3 | 0.49 | 0.6886 | 111 | +0.144@4m | no |  |
| JETS | log_return | US_UNEMPLOYMENT | 6 | — | — | — | +0.144@4m | no | insufficient aligned months |
| JETS | log_return | US_UNEMPLOYMENT | 12 | — | — | — | +0.144@4m | no | insufficient aligned months |
| JETS | mom12 | US_UNEMPLOYMENT | — | — | — | — | -0.196@15m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLRE | log_return | HONOLULU_ZHVI | 3 | 3.01 | 0.0336 | 108 | +0.193@5m | no |  |
| XLRE | log_return | HONOLULU_ZHVI | 6 | — | — | — | +0.193@5m | no | insufficient aligned months |
| XLRE | log_return | HONOLULU_ZHVI | 12 | — | — | — | +0.193@5m | no | insufficient aligned months |
| XLRE | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.380@16m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLRE | log_return | HONOLULU_ZORI | 3 | 3.16 | 0.0278 | 108 | +0.244@2m | no |  |
| XLRE | log_return | HONOLULU_ZORI | 6 | — | — | — | +0.244@2m | no | insufficient aligned months |
| XLRE | log_return | HONOLULU_ZORI | 12 | — | — | — | +0.244@2m | no | insufficient aligned months |
| XLRE | mom12 | HONOLULU_ZORI | — | — | — | — | +0.200@18m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| VNQ | log_return | HONOLULU_ZHVI | 3 | 1.93 | 0.1261 | 237 | +0.274@9m | no |  |
| VNQ | log_return | HONOLULU_ZHVI | 6 | 1.25 | 0.2832 | 231 | +0.274@9m | no |  |
| VNQ | log_return | HONOLULU_ZHVI | 12 | 2.61 | 0.0030 | 219 | +0.274@9m | **YES** |  |
| VNQ | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.523@3m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| VNQ | log_return | HONOLULU_ZORI | 3 | 3.36 | 0.0214 | 117 | +0.252@2m | no |  |
| VNQ | log_return | HONOLULU_ZORI | 6 | 1.47 | 0.1958 | 111 | +0.252@2m | no |  |
| VNQ | log_return | HONOLULU_ZORI | 12 | — | — | — | +0.252@2m | no | insufficient aligned months |
| VNQ | mom12 | HONOLULU_ZORI | — | — | — | — | +0.144@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLE | log_return | HONOLULU_CPI | 3 | — | — | — | +0.480@2m | no | insufficient aligned months |
| XLE | log_return | HONOLULU_CPI | 6 | — | — | — | +0.480@2m | no | insufficient aligned months |
| XLE | log_return | HONOLULU_CPI | 12 | — | — | — | +0.480@2m | no | insufficient aligned months |
| XLE | mom12 | HONOLULU_CPI | — | — | — | — | +0.445@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLE | log_return | HI_ELECTRICITY | 3 | 26.32 | 0.0000 | 237 | +0.396@3m | **YES** |  |
| XLE | log_return | HI_ELECTRICITY | 6 | 15.61 | 0.0000 | 231 | +0.396@3m | **YES** |  |
| XLE | log_return | HI_ELECTRICITY | 12 | 7.08 | 0.0000 | 219 | +0.396@3m | **YES** |  |
| XLE | mom12 | HI_ELECTRICITY | — | — | — | — | +0.360@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| BOH | log_return | HI_UNEMPLOYMENT | 3 | 0.10 | 0.9617 | 233 | -0.135@7m | no |  |
| BOH | log_return | HI_UNEMPLOYMENT | 6 | 0.77 | 0.5924 | 224 | -0.135@7m | no |  |
| BOH | log_return | HI_UNEMPLOYMENT | 12 | 0.64 | 0.8082 | 211 | -0.135@7m | no |  |
| BOH | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.272@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| FHB | log_return | HI_UNEMPLOYMENT | 3 | 0.41 | 0.7484 | 94 | -0.218@7m | no |  |
| FHB | log_return | HI_UNEMPLOYMENT | 6 | — | — | — | -0.218@7m | no | insufficient aligned months |
| FHB | log_return | HI_UNEMPLOYMENT | 12 | — | — | — | -0.218@7m | no | insufficient aligned months |
| FHB | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.187@2m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HE | log_return | HI_UNEMPLOYMENT | 3 | 0.91 | 0.4387 | 233 | -0.108@3m | no |  |
| HE | log_return | HI_UNEMPLOYMENT | 6 | 0.62 | 0.7136 | 224 | -0.108@3m | no |  |
| HE | log_return | HI_UNEMPLOYMENT | 12 | 0.54 | 0.8866 | 211 | -0.108@3m | no |  |
| HE | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.135@18m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| MATX | log_return | HONOLULU_CPI | 3 | — | — | — | +0.407@3m | no | insufficient aligned months |
| MATX | log_return | HONOLULU_CPI | 6 | — | — | — | +0.407@3m | no | insufficient aligned months |
| MATX | log_return | HONOLULU_CPI | 12 | — | — | — | +0.407@3m | no | insufficient aligned months |
| MATX | mom12 | HONOLULU_CPI | — | — | — | — | +0.455@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| MATX | log_return | HI_ELECTRICITY | 3 | 5.08 | 0.0020 | 237 | +0.178@3m | **YES** |  |
| MATX | log_return | HI_ELECTRICITY | 6 | 2.44 | 0.0262 | 231 | +0.178@3m | no |  |
| MATX | log_return | HI_ELECTRICITY | 12 | 1.46 | 0.1432 | 219 | +0.178@3m | no |  |
| MATX | mom12 | HI_ELECTRICITY | — | — | — | — | +0.206@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| MATX | log_return | HONOLULU_ZHVI | 3 | 0.11 | 0.9563 | 237 | +0.152@9m | no |  |
| MATX | log_return | HONOLULU_ZHVI | 6 | 0.39 | 0.8820 | 231 | +0.152@9m | no |  |
| MATX | log_return | HONOLULU_ZHVI | 12 | 1.20 | 0.2826 | 219 | +0.152@9m | no |  |
| MATX | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.382@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HE | log_return | HI_ELECTRICITY | 3 | 0.77 | 0.5137 | 237 | +0.111@9m | no |  |
| HE | log_return | HI_ELECTRICITY | 6 | 0.81 | 0.5617 | 231 | +0.111@9m | no |  |
| HE | log_return | HI_ELECTRICITY | 12 | 0.85 | 0.5962 | 219 | +0.111@9m | no |  |
| HE | mom12 | HI_ELECTRICITY | — | — | — | — | +0.110@11m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_MORTGAGE30 | log_return | HONOLULU_ZHVI | 3 | 0.88 | 0.4511 | 297 | +0.179@0m | no |  |
| US_MORTGAGE30 | log_return | HONOLULU_ZHVI | 6 | 3.37 | 0.0032 | 291 | +0.179@0m | **YES** |  |
| US_MORTGAGE30 | log_return | HONOLULU_ZHVI | 12 | 3.52 | 0.0001 | 279 | +0.179@0m | **YES** |  |
| US_MORTGAGE30 | mom12 | HONOLULU_ZHVI | — | — | — | — | -0.267@18m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_MORTGAGE30 | log_return | HONOLULU_ZORI | 3 | 1.56 | 0.2044 | 117 | +0.213@11m | no |  |
| US_MORTGAGE30 | log_return | HONOLULU_ZORI | 6 | 0.26 | 0.9551 | 111 | +0.213@11m | no |  |
| US_MORTGAGE30 | log_return | HONOLULU_ZORI | 12 | — | — | — | +0.213@11m | no | insufficient aligned months |
| US_MORTGAGE30 | mom12 | HONOLULU_ZORI | — | — | — | — | +0.087@12m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_DGS10 | log_return | HONOLULU_ZHVI | 3 | 0.85 | 0.4662 | 297 | +0.143@0m | no |  |
| US_DGS10 | log_return | HONOLULU_ZHVI | 6 | 2.18 | 0.0452 | 291 | +0.143@0m | no |  |
| US_DGS10 | log_return | HONOLULU_ZHVI | 12 | 2.58 | 0.0030 | 279 | +0.143@0m | **YES** |  |
| US_DGS10 | mom12 | HONOLULU_ZHVI | — | — | — | — | -0.249@18m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_JOLTS | log_return | US_UNEMPLOYMENT | 3 | 10.64 | 0.0000 | 234 | -0.278@6m | **YES** |  |
| US_JOLTS | log_return | US_UNEMPLOYMENT | 6 | 6.40 | 0.0000 | 225 | -0.278@6m | **YES** |  |
| US_JOLTS | log_return | US_UNEMPLOYMENT | 12 | 2.56 | 0.0037 | 211 | -0.278@6m | **YES** |  |
| US_JOLTS | mom12 | US_UNEMPLOYMENT | — | — | — | — | -0.477@2m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_JOLTS | log_return | HI_UNEMPLOYMENT | 3 | 2.26 | 0.0824 | 233 | -0.255@5m | no |  |
| US_JOLTS | log_return | HI_UNEMPLOYMENT | 6 | 1.80 | 0.1006 | 224 | -0.255@5m | no |  |
| US_JOLTS | log_return | HI_UNEMPLOYMENT | 12 | 0.80 | 0.6530 | 211 | -0.255@5m | no |  |
| US_JOLTS | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.368@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_AHE | log_return | HI_UNEMPLOYMENT | 3 | 1.46 | 0.2279 | 219 | -0.166@0m | no |  |
| US_AHE | log_return | HI_UNEMPLOYMENT | 6 | 0.80 | 0.5713 | 210 | -0.166@0m | no |  |
| US_AHE | log_return | HI_UNEMPLOYMENT | 12 | — | — | — | -0.166@0m | no | insufficient aligned months |
| US_AHE | mom12 | HI_UNEMPLOYMENT | — | — | — | — | +0.213@1m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_LFPR | log_return | HI_UNEMPLOYMENT | 3 | 1.30 | 0.2760 | 233 | -0.104@0m | no |  |
| US_LFPR | log_return | HI_UNEMPLOYMENT | 6 | 1.17 | 0.3223 | 224 | -0.104@0m | no |  |
| US_LFPR | log_return | HI_UNEMPLOYMENT | 12 | 0.99 | 0.4555 | 211 | -0.104@0m | no |  |
| US_LFPR | mom12 | HI_UNEMPLOYMENT | — | — | — | — | +0.115@15m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_EMPPOP | log_return | HI_UNEMPLOYMENT | 3 | 0.46 | 0.7139 | 233 | -0.394@0m | no |  |
| US_EMPPOP | log_return | HI_UNEMPLOYMENT | 6 | 0.75 | 0.6086 | 224 | -0.394@0m | no |  |
| US_EMPPOP | log_return | HI_UNEMPLOYMENT | 12 | 0.61 | 0.8350 | 211 | -0.394@0m | no |  |
| US_EMPPOP | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.364@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |

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
- National-macro predictors (US_*): the screen applies log_return to whatever it is handed, so for rate-level series (US_MORTGAGE30, US_DGS10, US_LFPR, US_EMPPOP) the transform is a rough proxy for a percentage-point change. Fine for predictive precedence; these are never used as forecast inputs. Labor-participation leads that are not robust to 2020 exclusion are COVID-coincident (xcorr peaks at lag 0), not genuine leads.
