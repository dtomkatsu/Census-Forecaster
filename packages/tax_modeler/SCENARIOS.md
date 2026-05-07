# Authoring scenarios

This guide shows how to (1) add a new Hawaii bill scenario to the existing
registry, and (2) extend the package to a new state.

## Part 1 — Adding a new Hawaii bill

A "scenario" is a `TaxSystemConfig` describing brackets, standard
deduction, and personal exemption for a target year.
`TaxSystemRegistry` exposes one factory per supported bill.

### Step 1: register the system

`packages/tax_modeler/src/tax_modeler/config/tax_system_config.py` already
contains factories like `get_act46_system(year)`, `get_sb3125_cd1_system(year)`,
`get_hb2306_orig_system(year)`.  Add a sibling with the same shape:

```python
@classmethod
def get_my_bill_system(cls, year: int) -> TaxSystemConfig:
    """My Bill (HB XXXX): brief description of bracket changes."""
    return TaxSystemConfig(
        name=f"my_bill_{year}",
        year=year,
        bracket_year=year,                 # selects bracket CSV vintage
        standard_deduction_year=year,      # selects SD CSV vintage
        personal_exemption=cls.PERSONAL_EXEMPTIONS.get(year, 1200),
        description="HB XXXX: increases top bracket to 13% for income > $1M",
    )
```

If your bill introduces brackets that don't exist in any current CSV,
add a new column to `data/tax_tables/hawaii_2022/hawaii_tax_brackets_master_all.csv`
and reference it via `bracket_year`.

### Step 2: optionally add credit overlays

Bill-specific credit changes (REEC caps, CGEC sunsets, TCRA
acceleration, etc.) live in `tax_modeler/scenarios/`.  Use
`scenarios/sb3125_cd1_credits.py` as a template.  Each module exposes a
`compute_credit_overlay(year, **kwargs)` that returns a dict of credit
deltas.

### Step 3: compare against a baseline

```python
from tax_modeler import TaxCalculator, TaxSystemRegistry, compare_systems

calc = TaxCalculator()
baseline = TaxSystemRegistry.get_act46_system(2027)
my_bill  = TaxSystemRegistry.get_my_bill_system(2027)

cmp = compare_systems(projected_units, baseline, my_bill, calculator=calc)
print(cmp)
```

`compare_systems` returns a DataFrame with revenue under both systems
and the delta.

### Step 4: write a forecast script

Mirror `forecast_sb3125_cd1.py` at the repo root.  After this refactor,
those scripts no longer need `sys.path.insert` hacks — they just import
from the installed `tax_modeler` package.

## Part 2 — Extending to a new state

The package is currently Hawaii-only but the heavy hardcodes are
collected behind `tax_modeler.config.state_config.StateConfig`.  Adding a
new state is roughly:

### Step 1: define the state config

Add a sibling of `HAWAII` in
`packages/tax_modeler/src/tax_modeler/config/state_config.py`:

```python
OREGON = StateConfig(
    name="Oregon",
    state_fips="41",
    default_geoid="41051",            # Multnomah County (Portland) as state-proxy
    cg_cap_rate=0.0,                  # Oregon has no CG cap; skip cap math
    pease_threshold_single=...,       # ORS-specific thresholds
    pease_threshold_mfs=...,
    personal_exemption_year_inflection=...,
    tax_table_dir=_PACKAGE_ROOT / "data" / "tax_tables" / "oregon_2022",
    available_bracket_years=(2020, 2024, 2026),
)
```

### Step 2: bundle the state's tax tables

Drop bracket and standard-deduction CSVs into the directory pointed at by
`tax_table_dir`.  Schema must match Hawaii's:

- `<state>_tax_brackets_master_all.csv` — one column per bracket-year vintage.
- `<state>_standard_deductions_by_year.csv` — SDs by filing status × year.

### Step 3: add a state-specific liability path (if needed)

Hawaii's bracket-walk is generic enough that any progressive-bracket state
can reuse it.  States with extra wrinkles (e.g. an alternative minimum
tax, a kicker rebate) need a sibling of `liability/hawaii.py` that
implements the wrinkle and routes through `liability/__init__.py`.

The Hawaii capital-gains cap (HRS §235-16, 7.25%) is already
parameterized via `state_config.cg_cap_rate` — set to `0.0` for states
without a CG cap and the cap branch is skipped.

### Step 4: add a state-specific calibration target loader

`year_recalibrator.project_and_recalibrate` takes a calibration-target
loader.  Today it defaults to Hawaii's COR projections.  An Oregon
plug-in would supply Oregon Department of Revenue projections via the
same callable interface.

### Step 5: add bill-specific scenarios

Create `tax_modeler/scenarios/oregon/` for Oregon bills, mirroring the
existing Hawaii scenario modules.

### What does *not* need to change

- `TaxCalculator` — generic bracket math, parameterized by config.
- `TaxUnitConstructor` — works on any state's PUMS as long as the schema
  matches Census ACS.
- `RevenueEstimator` — pure aggregation, state-agnostic.
- IPF rake calibration internals — accept any target dictionary.
- Federal EITC / CTC — federal law, no state customization.

## Smoke tests

Every scenario should be exercised by at least one smoke test on the
synthetic fixture.  Add a test under `tests/tax_modeler/smoke/` that
calls your scenario through `compare_systems` or `run_pipeline` and
asserts the revenue delta has the expected sign.  See
`tests/tax_modeler/smoke/test_e2e_smoke.py` for the pattern.
