# Calibration panel

This directory holds the bundled multi-state calibration panel consumed
by the v3 stratified calibration layer. **Three files live here when
populated:**

| File | Purpose | Approx. size |
|---|---|---|
| `acs_panel.json` | Flat list of 1-year ACS observations across selected counties × 4 indicators × 15 years | ~1 MB |
| `county_population_2020.json` | `{geoid: pop_2020}` lookup used to classify counties into population buckets at projection time | ~5 KB |
| `manifest.json` | Composition metadata: selection seed, per-bucket county lists, fetch timestamps, per-county median CV | ~50 KB |

If these files are absent, the calibration layer falls back to the v2
behavior (Hawaii-only, single global SE inflator) and projection still
works for the existing four ACS indicators.

## Re-fetching

The panel is rebuilt by running:

```bash
CENSUS_API_KEY=<your_key> python -m census_forecaster.scripts.build_calibration_panel
```

A Census API key is **required** — the panel build issues ~3,050 API
calls (51 for the 2020 population pre-fetch, then 50 states × 4
indicators × 15 years for the panel itself). Without a key, the 500/day
unauthenticated cap makes the run take 6+ days. Get a free key at
https://api.census.gov/data/key_signup.html.

The `AcsClient` cache (default `~/.cache/census-forecaster/acs.json`)
is reused across runs, so re-fetches with the same selection seed are
near-instant after the first.

### Smoke run

For a quick check that the script is wired correctly without committing
to the full ~10-minute fetch:

```bash
CENSUS_API_KEY=<your_key> python -m census_forecaster.scripts.build_calibration_panel \
    --states 06,15,36 --small
```

This fetches just California, Hawaii, and New York with 5 counties per
bucket. Output goes to `calibration_panel_small/` rather than overwriting
the bundled panel.

## Frozen-population convention

Population bucket boundaries (50K / 200K / 1M) are evaluated against
**2020 ACS B01003_001E (5-year vintage ending 2020)** for every county.
This is *frozen* for the lifetime of the calibration vintage:

* Re-running the build script with the same seed → same county selection
  → same bucket assignments. Reproducibility guaranteed.
* When the 2030 ACS is the dominant vintage, re-freeze at 2030 pop.

Why frozen rather than year-by-year: bucket-shifting would create a
moving-target stratification — a county that grew from medium to large
between 2015 and 2024 would appear in different cells across folds,
contaminating the per-cell calibration.

## Selection composition

The default selection (seed=42) is:

* **xlarge** (pop > 1M): top 50 by 2020 population, deterministic
* **medium** (50K-200K): random sample of 50 (seed-stable)
* **small** (<50K): random sample of 50 (seed-stable)
* **Hawaii**: all 4 counties always included (15001 / 15003 / 15007 /
  15009) for backwards compatibility with v0.2 fixtures

The `large` bucket (200K-1M) is not sampled separately — it's populated
naturally by Hawaii's Honolulu County (15003) plus any xlarge-overflow
when fewer than 50 counties exceed 1M population.

## 2020 ACS hole

The 1-year ACS for **2020** was suspended due to COVID-19 data quality
issues. Folds whose target year would be 2020 (e.g. anchor=2018, h=2;
anchor=2015, h=5) are dropped silently downstream by the calibration
generator. This means cells in the `long` horizon bucket have
systematically fewer folds than `short` cells in any vintage that spans
2020. Track per-cell `n_folds` carefully when interpreting calibration
output.

## CI auto-refresh

A GitHub Actions workflow (`.github/workflows/refresh-data.yml`) runs
on the 5th of each month and auto-commits the regenerated bundled
data plus the v3 calibration JSON. The workflow needs three repository
secrets:

| Secret | Source | Purpose |
|---|---|---|
| `CENSUS_API_KEY` | https://api.census.gov/data/key_signup.html | ACS panel rebuild (rare; only when v1.5 multi-state expansion runs) |
| `BLS_API_KEY` | https://www.bls.gov/developers/api_signature_v2.htm | Multi-MSA CPI panel + v3 BLS calibration |
| `BEA_API_KEY` | https://apps.bea.gov/api/signup/ | Three BEA anchor JSONs (Hawaii personal income, Honolulu metro RPP, Hawaii state RPP housing) |

Set them via:

```bash
gh secret set BLS_API_KEY --body "<key>"
gh secret set BEA_API_KEY --body "<key>"
gh secret set CENSUS_API_KEY --body "<key>"
```

Manual runs: `gh workflow run refresh-data.yml`. The workflow exits
cleanly without committing if no data files changed since the last
refresh — running it back-to-back is a no-op.
