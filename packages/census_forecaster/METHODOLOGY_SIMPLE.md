# ACS Forecasting Methodology — Plain-Language Guide

> **Maintenance note:** this document explains the forecasting methodology
> in plain language, for anyone (human or AI) who wants the "how does this
> actually work" story without reading formulas. **Whenever the ensemble
> design, feature set, lag scheme, or anchor logic changes in the code,
> update this document in the same commit.** It should never describe a
> mechanism the code no longer has. The precise technical version — formulas,
> parameter values, backtest numbers — lives in the root `METHODOLOGY.md`;
> this doc is the companion explanation, not a replacement for it.

## What this forecasts

Census-Forecaster predicts around 16 Census/ACS measurements — median
household income, median rent, median home value, poverty rate,
unemployment rate, education levels, homeownership rate, vacancy rate,
in-migration rate, and a few others — for individual **counties**, looking
1 to 5 years into the future.

Every prediction is for one specific county in one specific year. There is
no state-level output anywhere in this system — Hawaii's statewide numbers
(seen elsewhere in this repo, e.g. the poverty dashboard) come from a
completely separate system in `tax_modeler` that sums individual weighted
household records; they are not built by averaging these county forecasts.

## Why the training data isn't just Hawaii

Hawaii only has a handful of counties — nowhere near enough real-world
examples for a pattern-finding model to learn from reliably. So the
training data for the tree-based method (below) deliberately pools **147
counties from a stratified, multi-state sample across the whole US** — not
just Hawaii's own. The model is even told which state each training county
belongs to, so it knows it's looking at a mix of different places. Once
trained on that broad pool, the model is pointed specifically at Hawaii's
own counties to produce the forecasts this project actually uses.

## Three methods blended together

No single method makes the final call — three different approaches each
produce a guess, and the guesses get blended:

1. **Damped trend** — looks at one county's own history and assumes growth
   continues, but gradually slows down. Robust when there isn't much data.
2. **AR(1) on log differences** — more responsive to recent
   year-over-year moves, but noisier.
3. **A tree-based pattern-finder** (gradient boosting) — the only one of
   the three that looks across *all* counties and *all* measurements at
   once, rather than one county in isolation. This one is optional and
   off by default; someone has to deliberately turn it on for a given
   forecast run.

The three guesses aren't just averaged — each one also reports how
confident it is, and the final blended forecast leans more heavily on
whichever method has been more trustworthy for that particular measurement
and situation.

## The tree-based method, in plain terms

Picture a stack of very simple rulebooks, each one only good at fixing
what the rulebook before it got wrong:

1. Start with the dumbest possible guess — just the average.
2. Measure how wrong that guess was for each example. That gap
   (`actual − guess`) is called the **residual**.
3. Train a small tree whose only job is to predict *that residual* — not
   the real answer, just how far off the last guess was, and which way to
   nudge it.
4. Shrink that tree's suggested correction by a small factor (the
   "learning rate") before adding it to the running total, so no single
   tree overcorrects.
5. Recompute the residual using the updated total, train a new tree on
   *that* leftover error, and repeat — hundreds of times.

The final prediction is just the starting average plus the sum of all
those small, shrunk corrections. No single tree is smart on its own;
stacking hundreds of them, each cleaning up what the last one missed,
produces something accurate.

One more detail: the tree isn't even predicting the raw future number
directly. It predicts *how much the number is expected to grow* between a
known starting year and the target year — a growth amount, applied on top
of the last known real value.

### What years get used for training

Every year gets used, not just one. For every county, every valid
starting year from **2010** up through a "cutoff" year, and every horizon
(1 to 5 years ahead), one training example gets created. In normal use the
cutoff is just the most recent year with real data. When testing whether
the method is any good, the cutoff gets deliberately set to some past
year, and the model is only allowed to see data through that point —
mimicking what someone standing in the past would have actually known —
so its guess can be checked against what really happened afterward.

## What the tree model is allowed to look at (the features)

Two different treatments, depending on the measurement:

- **County-level measurements that don't have a natural "rate of change"
  concept** — building permits, the poverty rate, the unemployment rate —
  get a **3-year lag window**: this year's value, last year's, two years
  back, plus the average of whichever of those exist. This lets the model
  see the recent trajectory, not just the latest snapshot.
- **National measurements** — inflation, national unemployment, wages,
  job openings, mortgage rates — get **year-over-year change** instead of
  the raw lag window. The reason: many of these (like the national price
  index) climb almost every single year no matter what, so the raw level
  is nearly a stand-in for "what year is it" — feeding that in barely
  teaches the model anything new, since it already knows the year. The
  *change* from last year is real, independent information the year alone
  doesn't carry. (A couple of these — the unemployment rate, wage growth —
  don't have that "always climbs" problem, so they get both the level
  and the change.)

Everything that touches the model is **annual**, never monthly. Even
data BLS or other sources publish monthly, weekly, or daily gets collapsed
to a single calendar-year average before it ever becomes a feature. This
is deliberate ("no-peeking"): a year's average is fully known well before
the model is asked to forecast anything beyond that year, so there's no
benefit to — and no risk from — feeding in finer-grained timing.

## BLS data plays three distinct roles

1. **As a county-level lag feature** — BLS's county unemployment rate
   (LAUS) is one of the three measurements that gets the 3-year lag
   treatment described above.
2. **As a national change feature** — several BLS national series
   (inflation subindexes, wages, national unemployment, job openings) feed
   the tree model as year-over-year change, for the reasons above.
3. **As a macro "anchor"** — a different, more direct role, used only for
   money-denominated forecasts (income, rent, home value). Here, BLS's
   QCEW wage data (a real, measured payroll-record total, not a survey
   estimate) gets blended *directly* into the final income forecast,
   alongside a couple of other independent price/wage measures. The blend
   isn't a fixed split — whichever source has historically proven more
   accurate for that specific measurement gets more weight. This anchor
   role doesn't apply to non-dollar measurements like the poverty rate,
   since there's no equivalent "real measured total" to anchor those to.

Separately from all of this, there's also a genuine **publication-delay**
concept for BLS data — nothing to do with the modeling above. Honolulu's
regional inflation data is only published every other month, and even
those releases land about six weeks after the reference month ends. The
code explicitly tracks this so it never assumes data exists before BLS has
actually released it.

### A fourth role: forecasting BLS data itself, at true monthly resolution

Everything above is about BLS data feeding *into* the annual county
forecasts. Separately, there's a dedicated module
(`bls/projection.py`) that does the reverse: it forecasts a BLS CPI
series forward in time, month by month, using the same damped-trend idea
but tuned for monthly (and Honolulu's actual bimonthly) cadence, with its
own calibrated confidence band. In production this is used to convert a
dollar figure from one month's price basis to another's, feeding directly
into `tax_modeler`'s income projection. It is specifically built and
validated for CPI — nothing in this repo uses it to forecast, say, future
unemployment or wages the same way; those series only ever appear as
*inputs* to other forecasts, never as something this module predicts
forward on its own.

## Where stock-market data fits in

A separate part of this package tracks a small, deliberately
**pre-registered** list of stocks and ETFs — broad market funds (SPY,
QQQ), sector funds whose industry maps onto something Hawaii-specific
(airlines for tourism employment, REIT funds for home values and rent,
energy for imported fuel costs), and a few Hawaii-listed companies
directly (Bank of Hawaii, Hawaiian Electric, Matson shipping). Each one
is registered up front with a specific, written-down economic reason it
might lead a Hawaii number — e.g., "airline stock prices embed forward
bookings, and Hawaii's tourism jobs follow visitor arrivals, so airline
prices should move before the unemployment rate does."

**Getting from "might lead" to "actually used" requires passing a real
statistical test, not just a plausible story.** Every pre-registered
pair gets a lead-lag (Granger) test — does this ticker's past genuinely
add predictive information beyond the target's own history? — corrected
for the fact that many pairs are being tested at once (so a few "hits" by
pure chance don't get treated as real), and re-checked with 2020 removed
entirely, so a signal that only looks real because of the one-time
COVID shock doesn't get to count. Only pairs that survive both checks
become real candidates.

**A worked example of that screening actually biting (August 2026).**
The energy and shipping hypotheses were being tested against a price
series labelled "Honolulu" that turned out to be **Los Angeles** — a
mislabelling caught elsewhere in the repo but missed in this one file.
Pointed at the real Hawaii price series, those tests could no longer run
at all, because the genuine Hawaii inflation number is only published
every *other* month and the test needs consecutive months. The fix was
to bring in a new data source — the US Energy Information
Administration's Hawaii electricity price, which *is* monthly and goes
back to 2001 — and test against that instead. The relationship came back
much stronger than the mislabelled version had shown (energy stock
prices lead Hawaii electricity prices by about 3 months). Worth noting
as the pattern: the honest fix temporarily *removed* evidence, and only
new data restored it.

**Survivors get compressed into three simple, national numbers, updated
once a year:** an energy signal, a shipping signal, and a real-estate
signal — each just "how much did the relevant stock(s) move over the
past 12 months, as of last June." June specifically, so the signal only
ever reflects information that was actually available while that year's
Census survey was still being conducted — never anything from later in
the year peeking backward. These three numbers are what actually reach
the tree-based forecasting model discussed earlier, as three more
national, same-for-every-county features.

**The reverse direction — does BLS/Census data help forecast *stock*
prices — was also tested directly, and it failed.** The reasoning going
in: by the time government economic data gets published, financial
markets have typically already priced in the news, so feeding that data
into a stock forecast shouldn't help (this is the standard
efficient-markets expectation). The repo actually ran this experiment —
using census, BLS, and Zillow data to try to improve return forecasts for
the tracked stocks — and confirmed the expected result: it made the
forecasts *worse*, not better. So no economic data of any kind is used to
predict where a stock's price is headed in this codebase.

**What the stock-price forecaster (a separate "tracker" report, not
connected to the county forecasts) *does* borrow from BLS is the
forecasting technique, not any data.** It reuses the exact same
damped-trend math built for CPI, applied only to a stock's own price
history — no economic series enters that calculation at all. And its
output — "where does the trend put this stock in 6 months" — is
explicitly never fed back into the county forecasts either; only
*already-realized*, historical stock-price movement (the June-to-June
momentum numbers above) ever reaches the forecasting model. A predicted
future stock price is never used as if it were a known fact.

## How this connects to the tax-forecasting side of the repo

Census-Forecaster's county-level forecasts aren't just an academic
exercise — they're the engine behind the SB 3125 / HB 2306 revenue and
distributional forecasts in `tax_modeler`. Specifically, three of the ACS
measurements get consumed downstream:

- **Median household income** — used to age every individual (weighted)
  Hawaii household record forward from a base survey year to a future tax
  year, county by county. This is the mechanism underneath every
  `forecast_sb3125_*` script.
- **Median home value** — used to scale itemized-deduction assumptions
  (mortgage interest, property tax) forward as home values change.
- **Top-quintile income share** — used to capture how much income is
  concentrating among top earners over time, which matters a lot for
  Hawaii specifically since a small share of filers generate the large
  majority of state income-tax revenue.

So the county-level lag features, the national change features, the
gradient-boosting method, and the BLS anchor blend described above all
ultimately shape one number: how fast Hawaii county incomes (and home
values, and income concentration) are assumed to grow — which is the
single biggest input into every tax-revenue forecast in this repository.
