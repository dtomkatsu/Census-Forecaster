"""Build the bundled multi-state calibration panel.

This script fetches a stratified sample of US counties from the Census
ACS API and persists three bundled JSON files in
`src/census_forecaster/data/calibration_panel/`:

* `acs_panel.json` — flat list of 1-year ACS observations across the
  selected counties × 4 indicators × 15 years (2010-2024). The
  calibration generator reads this to run multi-horizon walk-forward
  back-tests.
* `county_population_2020.json` — `{geoid: population_2020}` lookup,
  used at projection time to classify a county into a population bucket.
  Frozen at 2020 so bucket assignments don't drift between calibration
  vintages.
* `manifest.json` — composition metadata (selection seed, per-bucket
  county lists, fetch timestamps, per-county median CV for future use).

Selection logic
---------------
1. Fetch B01003_001E (total population) for every county nationwide
   using the **5-year ACS ending 2020** (1-year 2020 was suspended).
   This is one call per state (state-batched), 51 calls total.
2. Sort by population. Pick:
   - Top 50 by 2020 pop (xlarge bucket: pop > 1M; if fewer than 50
     such counties exist, fill from the next bucket down).
   - Random sample of 50 from the medium bucket (50K-200K pop).
   - Random sample of 50 from the small bucket (<50K pop).
3. The 4 Hawaii counties (15001/15003/15007/15009) are always included
   regardless of bucket — preserves backwards compatibility with the
   v0.2 Hawaii-only test fixtures and reproducibility of prior results.
4. Selection is seeded (default seed=42) for deterministic re-runs.

Cost
----
Total Census API calls: ~3,050
* 51 (population pre-fetch, state-batched)
* 50 states × 4 indicators × 15 years = 3,000 (panel fetch, state-batched)

A Census API key is REQUIRED. Without one, the unauthenticated 500/day
cap makes this take 6+ days; with a key, runtime is ~5-10 minutes
(network-bound). Set `CENSUS_API_KEY` in your environment before running.

Re-fetching
-----------
The script reuses the AcsClient cache (default
`~/.cache/census-forecaster/acs.json`) so re-runs of the same panel
selection are near-instant. Pass `--cache <dir>` to override.

Usage
-----
    CENSUS_API_KEY=<key> python -m census_forecaster.scripts.build_calibration_panel
    CENSUS_API_KEY=<key> python -m census_forecaster.scripts.build_calibration_panel --states 06,15,36 --dry-run

Add `--small` for a quick 15-county smoke run without committing the
full panel; the output goes to `<panel_dir>_small/` instead.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Iterable, Optional, Sequence

from ..acs.client import AcsClient
from ..acs.strata import classify_pop, POP_BUCKET_BOUNDS
from ..models import AcsObservation


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

# 50 states + DC. Skipping PR, VI, GU, AS, MP (different ACS coverage).
STATE_FIPS: tuple[str, ...] = (
    "01", "02", "04", "05", "06", "08", "09", "10", "11", "12",
    "13", "15", "16", "17", "18", "19", "20", "21", "22", "23",
    "24", "25", "26", "27", "28", "29", "30", "31", "32", "33",
    "34", "35", "36", "37", "38", "39", "40", "41", "42", "44",
    "45", "46", "47", "48", "49", "50", "51", "53", "54", "55", "56",
)

# Hawaii counties — always included regardless of bucket sampling, so
# the v0.2 Hawaii fixtures and tests stay reproducible against the v3
# panel. These will appear in their natural bucket: 15003 = large,
# 15001 = medium, 15007 = medium, 15009 = small.
HAWAII_COUNTIES: tuple[str, ...] = ("15001", "15003", "15007", "15009")

# Indicators we calibrate against — the four ACS dollar-denominated
# series the v0.2 calibration covers.
INDICATORS: tuple[str, ...] = (
    "B19013_001E",  # Median household income
    "B25058_001E",  # Median contract rent
    "B25064_001E",  # Median gross rent
    "B25077_001E",  # Median home value
)

# Year range. 2010 is the first year of stable post-redesign 1-year
# ACS for small geographies; 2024 is the latest released as of v3.
PANEL_YEARS: tuple[int, ...] = tuple(range(2010, 2025))

# Sampling targets per bucket.
DEFAULT_SAMPLE_TARGETS: dict[str, int] = {
    "xlarge": 50,
    "medium": 50,
    "small":  50,
}
# `large` (200K-1M) isn't sampled separately — Hawaii's 15003 plus any
# xlarge-overflow naturally lands here. The bucket still receives data
# from the natural distribution of selected counties.

# Default RNG seed — change only when intentionally rebuilding the
# panel composition.
DEFAULT_SEED: int = 42


# -----------------------------------------------------------------------------
# Population pre-fetch
# -----------------------------------------------------------------------------

def fetch_2020_population(
    client: AcsClient,
    states: Sequence[str] = STATE_FIPS,
    verbose: bool = True,
) -> dict[str, int]:
    """Fetch 2020 total population per county across the listed states.

    Uses the 5-year vintage ending 2020 (B01003_001E) — 1-year 2020 was
    suspended, and 5-year is more stable for the small-county tail.

    Returns
    -------
    dict mapping 5-char county GEOID → population (int).
    """
    out: dict[str, int] = {}
    for st in states:
        if verbose:
            print(f"[pop] fetching state {st}", file=sys.stderr)
        rows = client.fetch_table(
            year=2020,
            vintage="5y",
            indicators=("B01003_001E",),
            geo_scope=f"for=county:*&in=state:{st}",
        )
        for r in rows:
            geoid = f"{r['state']}{r['county']}"
            try:
                pop = int(float(r["B01003_001E"]))
            except (KeyError, TypeError, ValueError):
                continue
            if pop < 0:  # suppression sentinel
                continue
            out[geoid] = pop
    return out


# -----------------------------------------------------------------------------
# County selection
# -----------------------------------------------------------------------------

def select_counties(
    populations: dict[str, int],
    targets: dict[str, int] = DEFAULT_SAMPLE_TARGETS,
    must_include: Sequence[str] = HAWAII_COUNTIES,
    seed: int = DEFAULT_SEED,
) -> dict[str, list[str]]:
    """Stratified-sample counties by population bucket.

    Returns
    -------
    dict mapping bucket name → sorted list of selected GEOIDs. The
    `must_include` set is added unconditionally.

    Determinism: with a fixed seed, the selection is reproducible across
    runs. Re-running without changing the seed will pick the same
    counties.
    """
    rng = random.Random(seed)
    by_bucket: dict[str, list[str]] = defaultdict(list)
    for geoid, pop in populations.items():
        b = classify_pop(pop)
        if b is not None:
            by_bucket[b].append(geoid)

    chosen: dict[str, set[str]] = defaultdict(set)

    # Always-include set
    for geoid in must_include:
        b = classify_pop(populations.get(geoid, -1))
        if b is None:
            # Hawaii county not in pre-fetched populations? Shouldn't
            # happen; warn and skip.
            print(f"[select] WARN: must-include {geoid} has no 2020 pop",
                  file=sys.stderr)
            continue
        chosen[b].add(geoid)

    # Sample per bucket
    for bucket_name, target in targets.items():
        candidates = sorted(by_bucket.get(bucket_name, []))
        # Subtract already-chosen
        remaining = [g for g in candidates if g not in chosen[bucket_name]]
        if bucket_name == "xlarge":
            # Top-N by population, deterministic (no random sample needed)
            ranked = sorted(remaining, key=lambda g: populations[g], reverse=True)
            picks = ranked[: target - len(chosen[bucket_name])]
        else:
            n_to_pick = max(0, target - len(chosen[bucket_name]))
            n_to_pick = min(n_to_pick, len(remaining))
            picks = rng.sample(remaining, n_to_pick) if remaining else []
        chosen[bucket_name].update(picks)

    return {b: sorted(s) for b, s in chosen.items()}


# -----------------------------------------------------------------------------
# Panel fetch
# -----------------------------------------------------------------------------

def fetch_panel_observations(
    client: AcsClient,
    selected: dict[str, list[str]],
    indicators: Sequence[str] = INDICATORS,
    years: Sequence[int] = PANEL_YEARS,
    verbose: bool = True,
) -> list[AcsObservation]:
    """Fetch all 1-year ACS observations for the selected counties.

    State-batched: one API call per (state, indicator, year), then
    filter the response down to the selected counties post-hoc. Skips
    any state that has no selected counties.
    """
    selected_geoids: set[str] = set()
    for gs in selected.values():
        selected_geoids.update(gs)

    states_needed = sorted({g[:2] for g in selected_geoids})

    out: list[AcsObservation] = []
    total_calls = len(states_needed) * len(indicators) * len(years)
    call_idx = 0
    for state_fips in states_needed:
        for indicator in indicators:
            obs = client.fetch_series(
                indicator=indicator,
                years=tuple(years),
                vintage="1y",
                state_fips=state_fips,
                county_fips=None,  # all counties in state, filter post-hoc
            )
            call_idx += len(years)
            kept_in_state = 0
            for o in obs:
                if o.geoid in selected_geoids:
                    out.append(o)
                    kept_in_state += 1
            if verbose:
                pct = 100.0 * call_idx / max(total_calls, 1)
                print(f"[panel] state={state_fips} ind={indicator} "
                      f"kept={kept_in_state} ({pct:.0f}%)", file=sys.stderr)
    return out


# -----------------------------------------------------------------------------
# Per-county median CV (diagnostic, not consumed by v3)
# -----------------------------------------------------------------------------

def compute_median_cv(
    observations: Iterable[AcsObservation],
) -> dict[str, dict[str, float]]:
    """Compute per-(geoid, indicator) median coefficient of variation.

    CV = SE / |estimate| where SE = MOE / 1.645 (Census 90% Z constant).
    The result is exposed in the manifest for future iterations that
    might switch to indicator-specific bucket boundaries based on
    observed sampling noise rather than 2020 population.
    """
    import statistics
    by_key: dict[tuple[str, str], list[float]] = defaultdict(list)
    for o in observations:
        if o.estimate <= 0:
            continue
        if o.moe is None or o.moe < 0:
            continue
        try:
            cv = (o.moe / 1.645) / abs(o.estimate)
        except (TypeError, ZeroDivisionError):
            continue
        if cv != cv:  # NaN
            continue
        by_key[(o.geoid, o.indicator)].append(cv)
    nested: dict[str, dict[str, float]] = defaultdict(dict)
    for (geoid, ind), cvs in by_key.items():
        if cvs:
            nested[geoid][ind] = statistics.median(cvs)
    return dict(nested)


# -----------------------------------------------------------------------------
# Persistence
# -----------------------------------------------------------------------------

def write_panel_files(
    panel_dir: Path,
    populations: dict[str, int],
    selected: dict[str, list[str]],
    observations: Sequence[AcsObservation],
    median_cv: dict[str, dict[str, float]],
    seed: int,
    targets: dict[str, int],
) -> None:
    """Persist the three bundled files atomically (write-temp + rename)."""
    panel_dir.mkdir(parents=True, exist_ok=True)
    now = date.today().isoformat()

    # 1. ACS panel
    panel_path = panel_dir / "acs_panel.json"
    panel_payload = {
        "version": 1,
        "fetch_date": now,
        "vintages": ["1y"],
        "year_range": [min(o.year for o in observations),
                       max(o.year for o in observations)] if observations else [None, None],
        "indicators": list(INDICATORS),
        "observations": [
            {
                "estimate": o.estimate,
                "moe": o.moe,
                "year": o.year,
                "vintage": o.vintage,
                "geoid": o.geoid,
                "indicator": o.indicator,
            }
            for o in observations
        ],
    }
    _atomic_write_json(panel_path, panel_payload)

    # 2. Population lookup (only the selected geoids — keeps the file small)
    selected_geoids: set[str] = set()
    for gs in selected.values():
        selected_geoids.update(gs)
    pop_payload = {
        "version": 1,
        "vintage": "5y",
        "end_year": 2020,
        "indicator": "B01003_001E",
        "populations": {g: populations[g] for g in sorted(selected_geoids) if g in populations},
    }
    _atomic_write_json(panel_dir / "county_population_2020.json", pop_payload)

    # 3. Manifest
    manifest_payload = {
        "version": 1,
        "build_date": now,
        "selection_seed": seed,
        "selection_targets": dict(targets),
        "selection_method": (
            "xlarge: top-N by 2020 pop; medium/small: deterministic random "
            f"sample seeded with {seed}; Hawaii counties always included"
        ),
        "buckets": {
            bucket: {
                "count": len(geoids),
                "geoids": geoids,
            }
            for bucket, geoids in selected.items()
        },
        "totals": {
            "counties": sum(len(gs) for gs in selected.values()),
            "observations": len(observations),
            "indicators": len(INDICATORS),
            "year_range": [min(PANEL_YEARS), max(PANEL_YEARS)],
        },
        "median_cv_by_county_indicator": median_cv,
        "notes": {
            "frozen_pop": (
                "Population bucket assignments use 2020 ACS B01003_001E "
                "(5-year vintage). Frozen for the lifetime of the calibration "
                "vintage; re-run this script to refresh."
            ),
            "suspended_2020_1y": (
                "1-year ACS was suspended for 2020 due to COVID data quality. "
                "Folds with target_year=2020 are dropped silently downstream."
            ),
        },
    }
    _atomic_write_json(panel_dir / "manifest.json", manifest_payload)


def _atomic_write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    tmp.replace(path)


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def _default_panel_dir() -> Path:
    """Bundled location inside the package."""
    return Path(__file__).resolve().parent.parent / "data" / "calibration_panel"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the v3 calibration panel from the Census ACS API.",
    )
    parser.add_argument(
        "--out", type=Path, default=_default_panel_dir(),
        help="Output directory for bundled JSON files.",
    )
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_SEED,
        help="RNG seed for stratified sampling (default 42).",
    )
    parser.add_argument(
        "--states", type=str, default=None,
        help="Comma-separated state FIPS to fetch (default all 50+DC). "
             "Useful with --dry-run for quick testing.",
    )
    parser.add_argument(
        "--small", action="store_true",
        help="Quick smoke run: 5 from each bucket, write to a _small "
             "subdirectory next to --out. Implies a tiny panel.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run population pre-fetch and selection only; don't fetch "
             "the full panel or write files.",
    )
    parser.add_argument(
        "--cache", type=Path, default=None,
        help="Path to AcsClient cache file (overrides default).",
    )
    args = parser.parse_args(argv)

    api_key = os.environ.get("CENSUS_API_KEY")
    if not api_key:
        print(
            "ERROR: CENSUS_API_KEY environment variable is not set. "
            "A Census API key is required for the panel fetch (~3,000 calls). "
            "Get one free at https://api.census.gov/data/key_signup.html",
            file=sys.stderr,
        )
        return 2

    cache_path = args.cache if args.cache else None
    client = AcsClient(
        cache_path=cache_path or AcsClient.__init__.__defaults__[0],  # type: ignore[index]
        api_key=api_key,
    )

    states = (
        tuple(s.strip() for s in args.states.split(",") if s.strip())
        if args.states else STATE_FIPS
    )

    targets = (
        {"xlarge": 5, "medium": 5, "small": 5}
        if args.small else dict(DEFAULT_SAMPLE_TARGETS)
    )

    print(f"[main] panel build starting; states={len(states)}, "
          f"targets={targets}, seed={args.seed}", file=sys.stderr)

    populations = fetch_2020_population(client, states=states)
    print(f"[main] fetched {len(populations)} county populations", file=sys.stderr)

    selected = select_counties(
        populations=populations,
        targets=targets,
        must_include=HAWAII_COUNTIES if "15" in states else (),
        seed=args.seed,
    )
    total_selected = sum(len(g) for g in selected.values())
    print(f"[main] selected {total_selected} counties:", file=sys.stderr)
    for bucket, geoids in selected.items():
        print(f"       {bucket}: {len(geoids)}", file=sys.stderr)

    if args.dry_run:
        print("[main] --dry-run: skipping panel fetch and write", file=sys.stderr)
        return 0

    observations = fetch_panel_observations(
        client=client,
        selected=selected,
        indicators=INDICATORS,
        years=PANEL_YEARS,
    )
    print(f"[main] fetched {len(observations)} observations total", file=sys.stderr)

    median_cv = compute_median_cv(observations)

    out_dir = args.out
    if args.small:
        out_dir = out_dir.parent / (out_dir.name + "_small")
    write_panel_files(
        panel_dir=out_dir,
        populations=populations,
        selected=selected,
        observations=observations,
        median_cv=median_cv,
        seed=args.seed,
        targets=targets,
    )
    print(f"[main] wrote panel files to {out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
