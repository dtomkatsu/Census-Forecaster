# Market-signal screen — 2026-08-07

Pre-registered ticker→target hypotheses (41 pairs), Granger F-tests on monthly log-returns at lags 3/6/12, BH-FDR q=0.1. 104 tests run.

**Granger ≠ causation.** A pass means the ticker's past adds predictive content beyond the target's own past. Confounders survive this screen; the Phase-3 forecaster ablation is the final arbiter. mom12 rows are descriptive cross-correlations only (overlapping windows invalidate the F-test).

## Full sample

| ticker | transform | target | lags | F | p | n | best xcorr | BH pass | note |
|---|---|---|---|---|---|---|---|---|---|
| SPY | log_return | HI_UNEMPLOYMENT | 3 | 7.82 | 0.0001 | 250 | -0.242@1m | **YES** |  |
| SPY | log_return | HI_UNEMPLOYMENT | 6 | 4.00 | 0.0008 | 244 | -0.242@1m | **YES** |  |
| SPY | log_return | HI_UNEMPLOYMENT | 12 | 2.75 | 0.0017 | 236 | -0.242@1m | **YES** |  |
| SPY | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.119@1m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| QQQ | log_return | HI_UNEMPLOYMENT | 3 | 2.90 | 0.0357 | 250 | -0.157@16m | **YES** |  |
| QQQ | log_return | HI_UNEMPLOYMENT | 6 | 1.36 | 0.2328 | 244 | -0.157@16m | no |  |
| QQQ | log_return | HI_UNEMPLOYMENT | 12 | 1.41 | 0.1648 | 236 | -0.157@16m | no |  |
| QQQ | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.102@1m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| VTI | log_return | HI_UNEMPLOYMENT | 3 | 8.42 | 0.0000 | 250 | -0.259@1m | **YES** |  |
| VTI | log_return | HI_UNEMPLOYMENT | 6 | 4.28 | 0.0004 | 244 | -0.259@1m | **YES** |  |
| VTI | log_return | HI_UNEMPLOYMENT | 12 | 2.89 | 0.0010 | 236 | -0.259@1m | **YES** |  |
| VTI | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.126@1m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLF | log_return | HI_UNEMPLOYMENT | 3 | 8.10 | 0.0000 | 250 | -0.267@1m | **YES** |  |
| XLF | log_return | HI_UNEMPLOYMENT | 6 | 4.38 | 0.0003 | 244 | -0.267@1m | **YES** |  |
| XLF | log_return | HI_UNEMPLOYMENT | 12 | 2.85 | 0.0012 | 236 | -0.267@1m | **YES** |  |
| XLF | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.096@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| JETS | log_return | HI_UNEMPLOYMENT | 3 | 15.49 | 0.0000 | 127 | -0.450@1m | **YES** |  |
| JETS | log_return | HI_UNEMPLOYMENT | 6 | 8.47 | 0.0000 | 121 | -0.450@1m | **YES** |  |
| JETS | log_return | HI_UNEMPLOYMENT | 12 | — | — | — | -0.450@1m | no | insufficient aligned months |
| JETS | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.165@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| JETS | log_return | US_UNEMPLOYMENT | 3 | 13.52 | 0.0000 | 127 | -0.447@1m | **YES** |  |
| JETS | log_return | US_UNEMPLOYMENT | 6 | 7.79 | 0.0000 | 121 | -0.447@1m | **YES** |  |
| JETS | log_return | US_UNEMPLOYMENT | 12 | — | — | — | -0.447@1m | no | insufficient aligned months |
| JETS | mom12 | US_UNEMPLOYMENT | — | — | — | — | +0.132@4m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| JETS | log_return | HI_VISITORS | 3 | 15.80 | 0.0000 | 131 | +0.467@1m | **YES** |  |
| JETS | log_return | HI_VISITORS | 6 | 9.46 | 0.0000 | 128 | +0.467@1m | **YES** |  |
| JETS | log_return | HI_VISITORS | 12 | — | — | — | +0.467@1m | no | insufficient aligned months |
| JETS | mom12 | HI_VISITORS | — | — | — | — | -0.191@4m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_VISITORS_ARRIVALS | log_return | HI_UNEMPLOYMENT | 3 | 7.46 | 0.0001 | 250 | -0.880@0m | **YES** |  |
| HI_VISITORS_ARRIVALS | log_return | HI_UNEMPLOYMENT | 6 | 4.81 | 0.0001 | 244 | -0.880@0m | **YES** |  |
| HI_VISITORS_ARRIVALS | log_return | HI_UNEMPLOYMENT | 12 | 5.73 | 0.0000 | 236 | -0.880@0m | **YES** |  |
| HI_VISITORS_ARRIVALS | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.253@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_UI_CLAIMS | log_return | HI_UNEMPLOYMENT | 3 | 205.03 | 0.0000 | 250 | +0.821@1m | **YES** |  |
| HI_UI_CLAIMS | log_return | HI_UNEMPLOYMENT | 6 | 108.91 | 0.0000 | 244 | +0.821@1m | **YES** |  |
| HI_UI_CLAIMS | log_return | HI_UNEMPLOYMENT | 12 | 56.32 | 0.0000 | 236 | +0.821@1m | **YES** |  |
| HI_UI_CLAIMS | mom12 | HI_UNEMPLOYMENT | — | — | — | — | +0.267@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_PAYROLLS | log_return | HI_UNEMPLOYMENT | 3 | 2.22 | 0.0870 | 250 | -0.948@0m | no |  |
| HI_PAYROLLS | log_return | HI_UNEMPLOYMENT | 6 | 1.19 | 0.3125 | 244 | -0.948@0m | no |  |
| HI_PAYROLLS | log_return | HI_UNEMPLOYMENT | 12 | 1.07 | 0.3878 | 236 | -0.948@0m | no |  |
| HI_PAYROLLS | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.162@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_AIR_PAX | log_return | HI_VISITORS | 3 | 1.43 | 0.2356 | 145 | +0.951@0m | no |  |
| HI_AIR_PAX | log_return | HI_VISITORS | 6 | 1.96 | 0.0755 | 142 | +0.951@0m | no |  |
| HI_AIR_PAX | log_return | HI_VISITORS | 12 | — | — | — | +0.951@0m | no | insufficient aligned months |
| HI_AIR_PAX | mom12 | HI_VISITORS | — | — | — | — | -0.195@2m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_VISITOR_SPEND | log_return | HI_UNEMPLOYMENT | 3 | 11.95 | 0.0000 | 238 | -0.326@1m | **YES** |  |
| HI_VISITOR_SPEND | log_return | HI_UNEMPLOYMENT | 6 | 8.31 | 0.0000 | 229 | -0.326@1m | **YES** |  |
| HI_VISITOR_SPEND | log_return | HI_UNEMPLOYMENT | 12 | 8.99 | 0.0000 | 215 | -0.326@1m | **YES** |  |
| HI_VISITOR_SPEND | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.220@1m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_SF_SALES | log_return | HONOLULU_ZHVI | 3 | 0.77 | 0.5101 | 218 | +0.087@10m | no |  |
| HI_SF_SALES | log_return | HONOLULU_ZHVI | 6 | 0.71 | 0.6439 | 215 | +0.087@10m | no |  |
| HI_SF_SALES | log_return | HONOLULU_ZHVI | 12 | 2.09 | 0.0197 | 209 | +0.087@10m | **YES** |  |
| HI_SF_SALES | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.414@2m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_PERMIT_UNITS | log_return | HONOLULU_ZHVI | 3 | 0.75 | 0.5236 | 314 | +0.039@6m | no |  |
| HI_PERMIT_UNITS | log_return | HONOLULU_ZHVI | 6 | 1.50 | 0.1771 | 311 | +0.039@6m | no |  |
| HI_PERMIT_UNITS | log_return | HONOLULU_ZHVI | 12 | 0.83 | 0.6163 | 305 | +0.039@6m | no |  |
| HI_PERMIT_UNITS | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.202@6m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_DOM | log_return | HONOLULU_SF_MEDIAN | 3 | 1.50 | 0.2191 | 116 | -0.310@0m | no |  |
| HI_DOM | log_return | HONOLULU_SF_MEDIAN | 6 | 1.28 | 0.2728 | 113 | -0.310@0m | no |  |
| HI_DOM | log_return | HONOLULU_SF_MEDIAN | 12 | — | — | — | -0.310@0m | no | insufficient aligned months |
| HI_DOM | mom12 | HONOLULU_SF_MEDIAN | — | — | — | — | +0.141@11m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_PRICE_CUTS | log_return | HONOLULU_SF_MEDIAN | 3 | 4.09 | 0.0085 | 116 | -0.300@3m | **YES** |  |
| HI_PRICE_CUTS | log_return | HONOLULU_SF_MEDIAN | 6 | 3.84 | 0.0017 | 113 | -0.300@3m | **YES** |  |
| HI_PRICE_CUTS | log_return | HONOLULU_SF_MEDIAN | 12 | — | — | — | -0.300@3m | no | insufficient aligned months |
| HI_PRICE_CUTS | mom12 | HONOLULU_SF_MEDIAN | — | — | — | — | -0.160@3m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_PENDING_RATIO | log_return | HONOLULU_SF_MEDIAN | 3 | 1.15 | 0.3334 | 116 | +0.159@2m | no |  |
| HI_PENDING_RATIO | log_return | HONOLULU_SF_MEDIAN | 6 | 0.78 | 0.5863 | 113 | +0.159@2m | no |  |
| HI_PENDING_RATIO | log_return | HONOLULU_SF_MEDIAN | 12 | — | — | — | +0.159@2m | no | insufficient aligned months |
| HI_PENDING_RATIO | mom12 | HONOLULU_SF_MEDIAN | — | — | — | — | +0.150@2m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_DOM | log_return | HONOLULU_ZHVI | 3 | 3.58 | 0.0163 | 116 | -0.280@1m | **YES** |  |
| HI_DOM | log_return | HONOLULU_ZHVI | 6 | 2.42 | 0.0317 | 113 | -0.280@1m | **YES** |  |
| HI_DOM | log_return | HONOLULU_ZHVI | 12 | — | — | — | -0.280@1m | no | insufficient aligned months |
| HI_DOM | mom12 | HONOLULU_ZHVI | — | — | — | — | -0.632@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_JETFUEL | log_return | HI_VISITORS | 3 | 3.80 | 0.0103 | 431 | +0.204@0m | **YES** |  |
| US_JETFUEL | log_return | HI_VISITORS | 6 | 2.70 | 0.0138 | 428 | +0.204@0m | **YES** |  |
| US_JETFUEL | log_return | HI_VISITORS | 12 | 2.85 | 0.0009 | 422 | +0.204@0m | **YES** |  |
| US_JETFUEL | mom12 | HI_VISITORS | — | — | — | — | +0.108@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_BIZ_APPS | log_return | HI_UNEMPLOYMENT | 3 | 4.46 | 0.0045 | 250 | -0.147@1m | **YES** |  |
| HI_BIZ_APPS | log_return | HI_UNEMPLOYMENT | 6 | 2.33 | 0.0334 | 244 | -0.147@1m | **YES** |  |
| HI_BIZ_APPS | log_return | HI_UNEMPLOYMENT | 12 | 2.09 | 0.0186 | 236 | -0.147@1m | **YES** |  |
| HI_BIZ_APPS | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.223@1m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLRE | log_return | HONOLULU_ZHVI | 3 | 3.71 | 0.0136 | 125 | +0.194@5m | **YES** |  |
| XLRE | log_return | HONOLULU_ZHVI | 6 | 3.46 | 0.0036 | 122 | +0.194@5m | **YES** |  |
| XLRE | log_return | HONOLULU_ZHVI | 12 | — | — | — | +0.194@5m | no | insufficient aligned months |
| XLRE | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.438@2m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLRE | log_return | HONOLULU_ZORI | 3 | 3.55 | 0.0166 | 125 | +0.274@2m | **YES** |  |
| XLRE | log_return | HONOLULU_ZORI | 6 | 1.11 | 0.3639 | 122 | +0.274@2m | no |  |
| XLRE | log_return | HONOLULU_ZORI | 12 | — | — | — | +0.274@2m | no | insufficient aligned months |
| XLRE | mom12 | HONOLULU_ZORI | — | — | — | — | +0.305@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| VNQ | log_return | HONOLULU_ZHVI | 3 | 2.31 | 0.0769 | 254 | +0.231@9m | no |  |
| VNQ | log_return | HONOLULU_ZHVI | 6 | 1.39 | 0.2183 | 251 | +0.231@9m | no |  |
| VNQ | log_return | HONOLULU_ZHVI | 12 | 2.33 | 0.0080 | 245 | +0.231@9m | **YES** |  |
| VNQ | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.492@1m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| VNQ | log_return | HONOLULU_ZORI | 3 | 3.97 | 0.0096 | 134 | +0.289@2m | **YES** |  |
| VNQ | log_return | HONOLULU_ZORI | 6 | 1.45 | 0.2015 | 131 | +0.289@2m | no |  |
| VNQ | log_return | HONOLULU_ZORI | 12 | — | — | — | +0.289@2m | no | insufficient aligned months |
| VNQ | mom12 | HONOLULU_ZORI | — | — | — | — | +0.320@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLE | log_return | HONOLULU_CPI | 3 | — | — | — | +0.363@2m | no | insufficient aligned months |
| XLE | log_return | HONOLULU_CPI | 6 | — | — | — | +0.363@2m | no | insufficient aligned months |
| XLE | log_return | HONOLULU_CPI | 12 | — | — | — | +0.363@2m | no | insufficient aligned months |
| XLE | mom12 | HONOLULU_CPI | — | — | — | — | +0.430@2m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLE | log_return | HI_ELECTRICITY | 3 | 24.54 | 0.0000 | 253 | +0.402@3m | **YES** |  |
| XLE | log_return | HI_ELECTRICITY | 6 | 15.00 | 0.0000 | 250 | +0.402@3m | **YES** |  |
| XLE | log_return | HI_ELECTRICITY | 12 | 7.39 | 0.0000 | 244 | +0.402@3m | **YES** |  |
| XLE | mom12 | HI_ELECTRICITY | — | — | — | — | +0.317@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| BOH | log_return | HI_UNEMPLOYMENT | 3 | 8.04 | 0.0000 | 250 | -0.248@1m | **YES** |  |
| BOH | log_return | HI_UNEMPLOYMENT | 6 | 5.22 | 0.0000 | 244 | -0.248@1m | **YES** |  |
| BOH | log_return | HI_UNEMPLOYMENT | 12 | 2.98 | 0.0007 | 236 | -0.248@1m | **YES** |  |
| BOH | mom12 | HI_UNEMPLOYMENT | — | — | — | — | +0.127@4m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| FHB | log_return | HI_UNEMPLOYMENT | 3 | 8.68 | 0.0000 | 111 | -0.396@1m | **YES** |  |
| FHB | log_return | HI_UNEMPLOYMENT | 6 | 5.51 | 0.0001 | 105 | -0.396@1m | **YES** |  |
| FHB | log_return | HI_UNEMPLOYMENT | 12 | — | — | — | -0.396@1m | no | insufficient aligned months |
| FHB | mom12 | HI_UNEMPLOYMENT | — | — | — | — | +0.145@4m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HE | log_return | HI_UNEMPLOYMENT | 3 | 0.44 | 0.7260 | 250 | -0.066@2m | no |  |
| HE | log_return | HI_UNEMPLOYMENT | 6 | 0.39 | 0.8852 | 244 | -0.066@2m | no |  |
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
| MATX | log_return | HONOLULU_ZHVI | 3 | 0.45 | 0.7185 | 254 | +0.172@9m | no |  |
| MATX | log_return | HONOLULU_ZHVI | 6 | 0.78 | 0.5863 | 251 | +0.172@9m | no |  |
| MATX | log_return | HONOLULU_ZHVI | 12 | 1.37 | 0.1809 | 245 | +0.172@9m | no |  |
| MATX | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.462@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HE | log_return | HI_ELECTRICITY | 3 | 0.67 | 0.5688 | 253 | -0.100@8m | no |  |
| HE | log_return | HI_ELECTRICITY | 6 | 1.05 | 0.3917 | 250 | -0.100@8m | no |  |
| HE | log_return | HI_ELECTRICITY | 12 | 0.88 | 0.5701 | 244 | -0.100@8m | no |  |
| HE | mom12 | HI_ELECTRICITY | — | — | — | — | +0.089@13m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_MORTGAGE30 | log_return | HONOLULU_ZHVI | 3 | 0.76 | 0.5201 | 314 | +0.180@0m | no |  |
| US_MORTGAGE30 | log_return | HONOLULU_ZHVI | 6 | 3.69 | 0.0015 | 311 | +0.180@0m | **YES** |  |
| US_MORTGAGE30 | log_return | HONOLULU_ZHVI | 12 | 3.32 | 0.0002 | 305 | +0.180@0m | **YES** |  |
| US_MORTGAGE30 | mom12 | HONOLULU_ZHVI | — | — | — | — | -0.312@15m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_MORTGAGE30 | log_return | HONOLULU_ZORI | 3 | 0.99 | 0.4012 | 134 | -0.177@8m | no |  |
| US_MORTGAGE30 | log_return | HONOLULU_ZORI | 6 | 0.28 | 0.9448 | 131 | -0.177@8m | no |  |
| US_MORTGAGE30 | log_return | HONOLULU_ZORI | 12 | — | — | — | -0.177@8m | no | insufficient aligned months |
| US_MORTGAGE30 | mom12 | HONOLULU_ZORI | — | — | — | — | -0.127@18m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_DGS10 | log_return | HONOLULU_ZHVI | 3 | 0.58 | 0.6256 | 314 | +0.149@0m | no |  |
| US_DGS10 | log_return | HONOLULU_ZHVI | 6 | 1.78 | 0.1035 | 311 | +0.149@0m | no |  |
| US_DGS10 | log_return | HONOLULU_ZHVI | 12 | 2.12 | 0.0157 | 305 | +0.149@0m | **YES** |  |
| US_DGS10 | mom12 | HONOLULU_ZHVI | — | — | — | — | -0.381@18m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_JOLTS | log_return | US_UNEMPLOYMENT | 3 | 6.08 | 0.0005 | 250 | -0.218@1m | **YES** |  |
| US_JOLTS | log_return | US_UNEMPLOYMENT | 6 | 4.16 | 0.0005 | 244 | -0.218@1m | **YES** |  |
| US_JOLTS | log_return | US_UNEMPLOYMENT | 12 | 2.28 | 0.0097 | 236 | -0.218@1m | **YES** |  |
| US_JOLTS | mom12 | US_UNEMPLOYMENT | — | — | — | — | -0.200@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_JOLTS | log_return | HI_UNEMPLOYMENT | 3 | 6.46 | 0.0003 | 250 | -0.228@1m | **YES** |  |
| US_JOLTS | log_return | HI_UNEMPLOYMENT | 6 | 3.73 | 0.0015 | 244 | -0.228@1m | **YES** |  |
| US_JOLTS | log_return | HI_UNEMPLOYMENT | 12 | 1.96 | 0.0295 | 236 | -0.228@1m | **YES** |  |
| US_JOLTS | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.163@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_AHE | log_return | HI_UNEMPLOYMENT | 3 | 1.96 | 0.1213 | 236 | +0.818@0m | no |  |
| US_AHE | log_return | HI_UNEMPLOYMENT | 6 | 1.67 | 0.1302 | 230 | +0.818@0m | no |  |
| US_AHE | log_return | HI_UNEMPLOYMENT | 12 | 1.52 | 0.1187 | 222 | +0.818@0m | no |  |
| US_AHE | mom12 | HI_UNEMPLOYMENT | — | — | — | — | +0.195@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_LFPR | log_return | HI_UNEMPLOYMENT | 3 | 7.47 | 0.0001 | 250 | -0.757@0m | **YES** |  |
| US_LFPR | log_return | HI_UNEMPLOYMENT | 6 | 4.07 | 0.0007 | 244 | -0.757@0m | **YES** |  |
| US_LFPR | log_return | HI_UNEMPLOYMENT | 12 | 3.17 | 0.0004 | 236 | -0.757@0m | **YES** |  |
| US_LFPR | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.195@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_EMPPOP | log_return | HI_UNEMPLOYMENT | 3 | 29.30 | 0.0000 | 250 | -0.961@0m | **YES** |  |
| US_EMPPOP | log_return | HI_UNEMPLOYMENT | 6 | 15.66 | 0.0000 | 244 | -0.961@0m | **YES** |  |
| US_EMPPOP | log_return | HI_UNEMPLOYMENT | 12 | 8.85 | 0.0000 | 236 | -0.961@0m | **YES** |  |
| US_EMPPOP | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.288@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |

## 2020 excluded (COVID sensitivity) — 93 tests

A signal that only exists because of the 2020 crash is a one-event artifact, not a relationship.

| ticker | transform | target | lags | F | p | n | best xcorr | BH pass | note |
|---|---|---|---|---|---|---|---|---|---|
| SPY | log_return | HI_UNEMPLOYMENT | 3 | 0.22 | 0.8800 | 234 | -0.192@0m | no |  |
| SPY | log_return | HI_UNEMPLOYMENT | 6 | 0.43 | 0.8609 | 225 | -0.192@0m | no |  |
| SPY | log_return | HI_UNEMPLOYMENT | 12 | 0.95 | 0.4962 | 211 | -0.192@0m | no |  |
| SPY | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.459@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| QQQ | log_return | HI_UNEMPLOYMENT | 3 | 0.26 | 0.8519 | 234 | -0.137@3m | no |  |
| QQQ | log_return | HI_UNEMPLOYMENT | 6 | 0.28 | 0.9458 | 225 | -0.137@3m | no |  |
| QQQ | log_return | HI_UNEMPLOYMENT | 12 | 0.82 | 0.6327 | 211 | -0.137@3m | no |  |
| QQQ | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.353@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| VTI | log_return | HI_UNEMPLOYMENT | 3 | 0.27 | 0.8458 | 234 | -0.179@1m | no |  |
| VTI | log_return | HI_UNEMPLOYMENT | 6 | 0.42 | 0.8661 | 225 | -0.179@1m | no |  |
| VTI | log_return | HI_UNEMPLOYMENT | 12 | 0.94 | 0.5072 | 211 | -0.179@1m | no |  |
| VTI | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.440@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLF | log_return | HI_UNEMPLOYMENT | 3 | 0.25 | 0.8612 | 234 | -0.243@1m | no |  |
| XLF | log_return | HI_UNEMPLOYMENT | 6 | 0.56 | 0.7648 | 225 | -0.243@1m | no |  |
| XLF | log_return | HI_UNEMPLOYMENT | 12 | 0.84 | 0.6141 | 211 | -0.243@1m | no |  |
| XLF | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.567@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| JETS | log_return | HI_UNEMPLOYMENT | 3 | 0.24 | 0.8649 | 111 | -0.249@7m | no |  |
| JETS | log_return | HI_UNEMPLOYMENT | 6 | — | — | — | -0.249@7m | no | insufficient aligned months |
| JETS | log_return | HI_UNEMPLOYMENT | 12 | — | — | — | -0.249@7m | no | insufficient aligned months |
| JETS | mom12 | HI_UNEMPLOYMENT | — | — | — | — | +0.377@12m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| JETS | log_return | US_UNEMPLOYMENT | 3 | 0.49 | 0.6886 | 111 | +0.144@4m | no |  |
| JETS | log_return | US_UNEMPLOYMENT | 6 | — | — | — | +0.144@4m | no | insufficient aligned months |
| JETS | log_return | US_UNEMPLOYMENT | 12 | — | — | — | +0.144@4m | no | insufficient aligned months |
| JETS | mom12 | US_UNEMPLOYMENT | — | — | — | — | -0.196@15m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| JETS | log_return | HI_VISITORS | 3 | 0.44 | 0.7273 | 115 | +0.181@13m | no |  |
| JETS | log_return | HI_VISITORS | 6 | 0.55 | 0.7687 | 109 | +0.181@13m | no |  |
| JETS | log_return | HI_VISITORS | 12 | — | — | — | +0.181@13m | no | insufficient aligned months |
| JETS | mom12 | HI_VISITORS | — | — | — | — | +0.087@11m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_VISITORS_ARRIVALS | log_return | HI_UNEMPLOYMENT | 3 | 3.08 | 0.0283 | 234 | -0.304@4m | no |  |
| HI_VISITORS_ARRIVALS | log_return | HI_UNEMPLOYMENT | 6 | 1.61 | 0.1447 | 225 | -0.304@4m | no |  |
| HI_VISITORS_ARRIVALS | log_return | HI_UNEMPLOYMENT | 12 | 1.63 | 0.0869 | 211 | -0.304@4m | no |  |
| HI_VISITORS_ARRIVALS | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.249@2m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_UI_CLAIMS | log_return | HI_UNEMPLOYMENT | 3 | 3.01 | 0.0311 | 234 | +0.184@3m | no |  |
| HI_UI_CLAIMS | log_return | HI_UNEMPLOYMENT | 6 | 4.35 | 0.0004 | 225 | +0.184@3m | **YES** |  |
| HI_UI_CLAIMS | log_return | HI_UNEMPLOYMENT | 12 | 2.01 | 0.0256 | 211 | +0.184@3m | no |  |
| HI_UI_CLAIMS | mom12 | HI_UNEMPLOYMENT | — | — | — | — | +0.439@2m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_PAYROLLS | log_return | HI_UNEMPLOYMENT | 3 | 8.48 | 0.0000 | 234 | -0.454@3m | **YES** |  |
| HI_PAYROLLS | log_return | HI_UNEMPLOYMENT | 6 | 4.21 | 0.0005 | 225 | -0.454@3m | **YES** |  |
| HI_PAYROLLS | log_return | HI_UNEMPLOYMENT | 12 | 1.23 | 0.2625 | 211 | -0.454@3m | no |  |
| HI_PAYROLLS | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.387@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_AIR_PAX | log_return | HI_VISITORS | 3 | 9.93 | 0.0000 | 129 | +0.882@0m | **YES** |  |
| HI_AIR_PAX | log_return | HI_VISITORS | 6 | 7.42 | 0.0000 | 123 | +0.882@0m | **YES** |  |
| HI_AIR_PAX | log_return | HI_VISITORS | 12 | — | — | — | +0.882@0m | no | insufficient aligned months |
| HI_AIR_PAX | mom12 | HI_VISITORS | — | — | — | — | +0.147@1m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_VISITOR_SPEND | log_return | HI_UNEMPLOYMENT | 3 | 1.59 | 0.1917 | 234 | -0.235@4m | no |  |
| HI_VISITOR_SPEND | log_return | HI_UNEMPLOYMENT | 6 | 1.37 | 0.2264 | 225 | -0.235@4m | no |  |
| HI_VISITOR_SPEND | log_return | HI_UNEMPLOYMENT | 12 | 1.67 | 0.0769 | 211 | -0.235@4m | no |  |
| HI_VISITOR_SPEND | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.228@1m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_SF_SALES | log_return | HONOLULU_ZHVI | 3 | 0.87 | 0.4583 | 202 | +0.083@11m | no |  |
| HI_SF_SALES | log_return | HONOLULU_ZHVI | 6 | 0.46 | 0.8337 | 196 | +0.083@11m | no |  |
| HI_SF_SALES | log_return | HONOLULU_ZHVI | 12 | — | — | — | +0.083@11m | no | insufficient aligned months |
| HI_SF_SALES | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.412@3m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_PERMIT_UNITS | log_return | HONOLULU_ZHVI | 3 | 0.68 | 0.5656 | 298 | +0.033@6m | no |  |
| HI_PERMIT_UNITS | log_return | HONOLULU_ZHVI | 6 | 1.08 | 0.3725 | 292 | +0.033@6m | no |  |
| HI_PERMIT_UNITS | log_return | HONOLULU_ZHVI | 12 | 0.63 | 0.8202 | 280 | +0.033@6m | no |  |
| HI_PERMIT_UNITS | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.204@6m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_DOM | log_return | HONOLULU_SF_MEDIAN | 3 | 0.68 | 0.5668 | 100 | -0.290@0m | no |  |
| HI_DOM | log_return | HONOLULU_SF_MEDIAN | 6 | — | — | — | -0.290@0m | no | insufficient aligned months |
| HI_DOM | log_return | HONOLULU_SF_MEDIAN | 12 | — | — | — | -0.290@0m | no | insufficient aligned months |
| HI_DOM | mom12 | HONOLULU_SF_MEDIAN | — | — | — | — | +0.207@11m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_PRICE_CUTS | log_return | HONOLULU_SF_MEDIAN | 3 | 3.58 | 0.0168 | 100 | +0.322@12m | **YES** |  |
| HI_PRICE_CUTS | log_return | HONOLULU_SF_MEDIAN | 6 | — | — | — | +0.322@12m | no | insufficient aligned months |
| HI_PRICE_CUTS | log_return | HONOLULU_SF_MEDIAN | 12 | — | — | — | +0.322@12m | no | insufficient aligned months |
| HI_PRICE_CUTS | mom12 | HONOLULU_SF_MEDIAN | — | — | — | — | -0.137@13m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_PENDING_RATIO | log_return | HONOLULU_SF_MEDIAN | 3 | 0.43 | 0.7338 | 100 | -0.187@4m | no |  |
| HI_PENDING_RATIO | log_return | HONOLULU_SF_MEDIAN | 6 | — | — | — | -0.187@4m | no | insufficient aligned months |
| HI_PENDING_RATIO | log_return | HONOLULU_SF_MEDIAN | 12 | — | — | — | -0.187@4m | no | insufficient aligned months |
| HI_PENDING_RATIO | mom12 | HONOLULU_SF_MEDIAN | — | — | — | — | +0.084@15m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_DOM | log_return | HONOLULU_ZHVI | 3 | 4.47 | 0.0056 | 100 | -0.388@13m | **YES** |  |
| HI_DOM | log_return | HONOLULU_ZHVI | 6 | — | — | — | -0.388@13m | no | insufficient aligned months |
| HI_DOM | log_return | HONOLULU_ZHVI | 12 | — | — | — | -0.388@13m | no | insufficient aligned months |
| HI_DOM | mom12 | HONOLULU_ZHVI | — | — | — | — | -0.678@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_JETFUEL | log_return | HI_VISITORS | 3 | 1.40 | 0.2438 | 415 | +0.179@9m | no |  |
| US_JETFUEL | log_return | HI_VISITORS | 6 | 1.39 | 0.2185 | 409 | +0.179@9m | no |  |
| US_JETFUEL | log_return | HI_VISITORS | 12 | 0.91 | 0.5373 | 397 | +0.179@9m | no |  |
| US_JETFUEL | mom12 | HI_VISITORS | — | — | — | — | -0.024@16m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HI_BIZ_APPS | log_return | HI_UNEMPLOYMENT | 3 | 0.94 | 0.4206 | 234 | -0.048@3m | no |  |
| HI_BIZ_APPS | log_return | HI_UNEMPLOYMENT | 6 | 0.84 | 0.5400 | 225 | -0.048@3m | no |  |
| HI_BIZ_APPS | log_return | HI_UNEMPLOYMENT | 12 | 0.84 | 0.6083 | 211 | -0.048@3m | no |  |
| HI_BIZ_APPS | mom12 | HI_UNEMPLOYMENT | — | — | — | — | +0.153@7m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLRE | log_return | HONOLULU_ZHVI | 3 | 2.97 | 0.0352 | 109 | +0.191@5m | no |  |
| XLRE | log_return | HONOLULU_ZHVI | 6 | — | — | — | +0.191@5m | no | insufficient aligned months |
| XLRE | log_return | HONOLULU_ZHVI | 12 | — | — | — | +0.191@5m | no | insufficient aligned months |
| XLRE | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.372@16m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLRE | log_return | HONOLULU_ZORI | 3 | 2.72 | 0.0483 | 109 | +0.255@2m | no |  |
| XLRE | log_return | HONOLULU_ZORI | 6 | — | — | — | +0.255@2m | no | insufficient aligned months |
| XLRE | log_return | HONOLULU_ZORI | 12 | — | — | — | +0.255@2m | no | insufficient aligned months |
| XLRE | mom12 | HONOLULU_ZORI | — | — | — | — | +0.205@18m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| VNQ | log_return | HONOLULU_ZHVI | 3 | 1.90 | 0.1306 | 238 | +0.274@9m | no |  |
| VNQ | log_return | HONOLULU_ZHVI | 6 | 1.22 | 0.2983 | 232 | +0.274@9m | no |  |
| VNQ | log_return | HONOLULU_ZHVI | 12 | 2.62 | 0.0029 | 220 | +0.274@9m | **YES** |  |
| VNQ | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.523@3m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| VNQ | log_return | HONOLULU_ZORI | 3 | 2.94 | 0.0362 | 118 | +0.263@2m | no |  |
| VNQ | log_return | HONOLULU_ZORI | 6 | 1.18 | 0.3218 | 112 | +0.263@2m | no |  |
| VNQ | log_return | HONOLULU_ZORI | 12 | — | — | — | +0.263@2m | no | insufficient aligned months |
| VNQ | mom12 | HONOLULU_ZORI | — | — | — | — | +0.143@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLE | log_return | HONOLULU_CPI | 3 | — | — | — | +0.480@2m | no | insufficient aligned months |
| XLE | log_return | HONOLULU_CPI | 6 | — | — | — | +0.480@2m | no | insufficient aligned months |
| XLE | log_return | HONOLULU_CPI | 12 | — | — | — | +0.480@2m | no | insufficient aligned months |
| XLE | mom12 | HONOLULU_CPI | — | — | — | — | +0.445@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| XLE | log_return | HI_ELECTRICITY | 3 | 26.32 | 0.0000 | 237 | +0.396@3m | **YES** |  |
| XLE | log_return | HI_ELECTRICITY | 6 | 15.61 | 0.0000 | 231 | +0.396@3m | **YES** |  |
| XLE | log_return | HI_ELECTRICITY | 12 | 7.08 | 0.0000 | 219 | +0.396@3m | **YES** |  |
| XLE | mom12 | HI_ELECTRICITY | — | — | — | — | +0.360@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| BOH | log_return | HI_UNEMPLOYMENT | 3 | 0.09 | 0.9673 | 234 | -0.133@7m | no |  |
| BOH | log_return | HI_UNEMPLOYMENT | 6 | 0.72 | 0.6364 | 225 | -0.133@7m | no |  |
| BOH | log_return | HI_UNEMPLOYMENT | 12 | 0.64 | 0.8082 | 211 | -0.133@7m | no |  |
| BOH | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.266@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| FHB | log_return | HI_UNEMPLOYMENT | 3 | 0.40 | 0.7559 | 95 | -0.213@7m | no |  |
| FHB | log_return | HI_UNEMPLOYMENT | 6 | — | — | — | -0.213@7m | no | insufficient aligned months |
| FHB | log_return | HI_UNEMPLOYMENT | 12 | — | — | — | -0.213@7m | no | insufficient aligned months |
| FHB | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.161@4m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HE | log_return | HI_UNEMPLOYMENT | 3 | 0.92 | 0.4316 | 234 | -0.109@3m | no |  |
| HE | log_return | HI_UNEMPLOYMENT | 6 | 0.66 | 0.6838 | 225 | -0.109@3m | no |  |
| HE | log_return | HI_UNEMPLOYMENT | 12 | 0.54 | 0.8866 | 211 | -0.109@3m | no |  |
| HE | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.140@18m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| MATX | log_return | HONOLULU_CPI | 3 | — | — | — | +0.407@3m | no | insufficient aligned months |
| MATX | log_return | HONOLULU_CPI | 6 | — | — | — | +0.407@3m | no | insufficient aligned months |
| MATX | log_return | HONOLULU_CPI | 12 | — | — | — | +0.407@3m | no | insufficient aligned months |
| MATX | mom12 | HONOLULU_CPI | — | — | — | — | +0.455@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| MATX | log_return | HI_ELECTRICITY | 3 | 5.08 | 0.0020 | 237 | +0.178@3m | **YES** |  |
| MATX | log_return | HI_ELECTRICITY | 6 | 2.44 | 0.0262 | 231 | +0.178@3m | no |  |
| MATX | log_return | HI_ELECTRICITY | 12 | 1.46 | 0.1432 | 219 | +0.178@3m | no |  |
| MATX | mom12 | HI_ELECTRICITY | — | — | — | — | +0.206@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| MATX | log_return | HONOLULU_ZHVI | 3 | 0.11 | 0.9546 | 238 | +0.153@9m | no |  |
| MATX | log_return | HONOLULU_ZHVI | 6 | 0.41 | 0.8741 | 232 | +0.153@9m | no |  |
| MATX | log_return | HONOLULU_ZHVI | 12 | 1.21 | 0.2803 | 220 | +0.153@9m | no |  |
| MATX | mom12 | HONOLULU_ZHVI | — | — | — | — | +0.377@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| HE | log_return | HI_ELECTRICITY | 3 | 0.77 | 0.5137 | 237 | +0.111@9m | no |  |
| HE | log_return | HI_ELECTRICITY | 6 | 0.81 | 0.5617 | 231 | +0.111@9m | no |  |
| HE | log_return | HI_ELECTRICITY | 12 | 0.85 | 0.5962 | 219 | +0.111@9m | no |  |
| HE | mom12 | HI_ELECTRICITY | — | — | — | — | +0.110@11m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_MORTGAGE30 | log_return | HONOLULU_ZHVI | 3 | 0.88 | 0.4526 | 298 | +0.178@0m | no |  |
| US_MORTGAGE30 | log_return | HONOLULU_ZHVI | 6 | 3.37 | 0.0032 | 292 | +0.178@0m | **YES** |  |
| US_MORTGAGE30 | log_return | HONOLULU_ZHVI | 12 | 3.51 | 0.0001 | 280 | +0.178@0m | **YES** |  |
| US_MORTGAGE30 | mom12 | HONOLULU_ZHVI | — | — | — | — | -0.267@18m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_MORTGAGE30 | log_return | HONOLULU_ZORI | 3 | 1.03 | 0.3839 | 118 | +0.201@11m | no |  |
| US_MORTGAGE30 | log_return | HONOLULU_ZORI | 6 | 0.15 | 0.9888 | 112 | +0.201@11m | no |  |
| US_MORTGAGE30 | log_return | HONOLULU_ZORI | 12 | — | — | — | +0.201@11m | no | insufficient aligned months |
| US_MORTGAGE30 | mom12 | HONOLULU_ZORI | — | — | — | — | +0.084@13m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_DGS10 | log_return | HONOLULU_ZHVI | 3 | 0.85 | 0.4700 | 298 | +0.143@0m | no |  |
| US_DGS10 | log_return | HONOLULU_ZHVI | 6 | 2.16 | 0.0472 | 292 | +0.143@0m | no |  |
| US_DGS10 | log_return | HONOLULU_ZHVI | 12 | 2.56 | 0.0033 | 280 | +0.143@0m | **YES** |  |
| US_DGS10 | mom12 | HONOLULU_ZHVI | — | — | — | — | -0.249@18m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_JOLTS | log_return | US_UNEMPLOYMENT | 3 | 10.66 | 0.0000 | 234 | -0.278@6m | **YES** |  |
| US_JOLTS | log_return | US_UNEMPLOYMENT | 6 | 6.40 | 0.0000 | 225 | -0.278@6m | **YES** |  |
| US_JOLTS | log_return | US_UNEMPLOYMENT | 12 | 2.56 | 0.0037 | 211 | -0.278@6m | **YES** |  |
| US_JOLTS | mom12 | US_UNEMPLOYMENT | — | — | — | — | -0.477@2m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_JOLTS | log_return | HI_UNEMPLOYMENT | 3 | 2.03 | 0.1102 | 234 | -0.245@5m | no |  |
| US_JOLTS | log_return | HI_UNEMPLOYMENT | 6 | 1.64 | 0.1384 | 225 | -0.245@5m | no |  |
| US_JOLTS | log_return | HI_UNEMPLOYMENT | 12 | 0.80 | 0.6530 | 211 | -0.245@5m | no |  |
| US_JOLTS | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.367@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_AHE | log_return | HI_UNEMPLOYMENT | 3 | 1.43 | 0.2337 | 220 | -0.164@0m | no |  |
| US_AHE | log_return | HI_UNEMPLOYMENT | 6 | 0.77 | 0.5967 | 211 | -0.164@0m | no |  |
| US_AHE | log_return | HI_UNEMPLOYMENT | 12 | — | — | — | -0.164@0m | no | insufficient aligned months |
| US_AHE | mom12 | HI_UNEMPLOYMENT | — | — | — | — | +0.214@1m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_LFPR | log_return | HI_UNEMPLOYMENT | 3 | 1.36 | 0.2573 | 234 | -0.111@0m | no |  |
| US_LFPR | log_return | HI_UNEMPLOYMENT | 6 | 1.21 | 0.3027 | 225 | -0.111@0m | no |  |
| US_LFPR | log_return | HI_UNEMPLOYMENT | 12 | 0.99 | 0.4555 | 211 | -0.111@0m | no |  |
| US_LFPR | mom12 | HI_UNEMPLOYMENT | — | — | — | — | +0.114@15m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |
| US_EMPPOP | log_return | HI_UNEMPLOYMENT | 3 | 0.49 | 0.6880 | 234 | -0.396@0m | no |  |
| US_EMPPOP | log_return | HI_UNEMPLOYMENT | 6 | 0.80 | 0.5674 | 225 | -0.396@0m | no |  |
| US_EMPPOP | log_return | HI_UNEMPLOYMENT | 12 | 0.61 | 0.8350 | 211 | -0.396@0m | no |  |
| US_EMPPOP | mom12 | HI_UNEMPLOYMENT | — | — | — | — | -0.366@0m | no | descriptive xcorr only (overlapping-window transform; no Granger test) |

## Annual descriptive leads (NO hypothesis tests — n≈10–15)

| ticker | target | lead (yrs) | r | n |
|---|---|---|---|---|
| SPY | LAUS_HI_UNEMPLOYMENT | 0 | +0.060 | 15 |
| SPY | LAUS_HI_UNEMPLOYMENT | 1 | +0.186 | 16 |
| SPY | LAUS_HI_UNEMPLOYMENT | 2 | -0.439 | 16 |
| SPY | LAUS_HI_UNEMPLOYMENT | 3 | +0.110 | 16 |
| JETS | LAUS_HI_UNEMPLOYMENT | 0 | -0.393 | 10 |
| JETS | LAUS_HI_UNEMPLOYMENT | 1 | +0.500 | 10 |
| JETS | LAUS_HI_UNEMPLOYMENT | 2 | -0.172 | 9 |
| JETS | LAUS_HI_UNEMPLOYMENT | 3 | +0.426 | 8 |
| BOH | SAIPE_HI_POVERTY | 0 | -0.047 | 14 |
| BOH | SAIPE_HI_POVERTY | 1 | -0.261 | 14 |
| BOH | SAIPE_HI_POVERTY | 2 | +0.302 | 14 |
| BOH | SAIPE_HI_POVERTY | 3 | -0.549 | 14 |
| XLRE | ZHVI_HONOLULU_ANNUAL | 0 | +0.044 | 10 |
| XLRE | ZHVI_HONOLULU_ANNUAL | 1 | +0.396 | 10 |
| XLRE | ZHVI_HONOLULU_ANNUAL | 2 | +0.060 | 9 |
| XLRE | ZHVI_HONOLULU_ANNUAL | 3 | +0.183 | 8 |
| VNQ | ZHVI_HONOLULU_ANNUAL | 0 | +0.204 | 20 |
| VNQ | ZHVI_HONOLULU_ANNUAL | 1 | +0.569 | 20 |
| VNQ | ZHVI_HONOLULU_ANNUAL | 2 | +0.001 | 19 |
| VNQ | ZHVI_HONOLULU_ANNUAL | 3 | +0.039 | 18 |
| MATX | ZHVI_HONOLULU_ANNUAL | 0 | +0.019 | 20 |
| MATX | ZHVI_HONOLULU_ANNUAL | 1 | +0.589 | 20 |
| MATX | ZHVI_HONOLULU_ANNUAL | 2 | -0.015 | 19 |
| MATX | ZHVI_HONOLULU_ANNUAL | 3 | +0.322 | 18 |

## Limitations

- Granger causality is predictive precedence, not causation.
- Monthly n≈130–250 depending on ticker inception; ZORI starts 2015, JETS 2015, XLRE 2015, FHB 2016.
- Annual-cadence rows are descriptive only and must never be cited as significant.
- Signals passing here still require the Phase-3 walk-forward ablation (RMSE improvement + CI90 coverage in [85%, 95%]) before touching any forecast.
- National-macro predictors (US_*): the screen applies log_return to whatever it is handed, so for rate-level series (US_MORTGAGE30, US_DGS10, US_LFPR, US_EMPPOP) the transform is a rough proxy for a percentage-point change. Fine for predictive precedence; these are never used as forecast inputs. Labor-participation leads that are not robust to 2020 exclusion are COVID-coincident (xcorr peaks at lag 0), not genuine leads.
