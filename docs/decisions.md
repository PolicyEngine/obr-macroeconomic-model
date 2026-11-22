# Decisions

Dated modelling decisions, the evidence behind each, and what was left out.
Newest first.

## 22 November 2026 (Fable 5.2 review round)

Three items left open by the 21 November round. No default and no published
figure changes.

### 1. `published_conventions` stays on the July 2015 multipliers (G11)

- **The question.** `obr_macro/published_conventions.py` imposes 0.6 for
  current spending, from the OBR's July 2015 EFO Box 3.2. The review
  (`published_model_review.md`, G11) records that the OBR's November 2023
  dynamic-scoring article gives 0.45 for public services and 0.33 for tax,
  with capital (1.00) and welfare (0.60) the same in both.
- **Decision.** Keep the 2015 set for every impact value. The 2023 article
  stays the source for the taper wording only. No default changes.
- **Why.**
  - One table, one vintage. All five impact values (0.6, 1.0, 0.6, 0.35,
    0.3) come from Box 3.2. Swapping one of them would mix vintages.
  - Figures quoted elsewhere are on this basis: `docs/demo.md` row 1b
    (+750 / +637 / +337 for a 1,250 shock), `results/demo_shocks.json` and
    the comparison text in `run_reform`.
  - The 2023 values were not re-read this round. This repo records them in
    two places, the review doc and `tests/test_tax_scenarios.py`, and the
    second gives tax as 0.33 in year 0, 0.30 in year 1 and 0.23 in year 2.
    So for tax, 0.3 (2015) and 0.33 (2023, year 0) are close and may be the
    same judgement on a different year index. Whether the 0.45 for public
    services is a year-0 figure on the same footing as 0.6 cannot be
    settled from files in this repo.
- **What it means for a reader.** The opt-in `published_conventions=True`
  path for `CGG` is the 2015 convention. On 0.45 it would be a quarter
  smaller (0.45 / 0.6): +563 on impact for a 1,250 shock, against +750.
  That is arithmetic, not a run. The capital path would not change.
- **What would change it.** A check of the 2023 article's table against
  Box 3.2 on a like-for-like year, then a switch of the whole table to the
  2023 vintage in one change, with before and after for every figure that
  quotes it.

### 2. `RL` is the 20-year gilt yield

- **Evidence.** The OBR's variables workbook (row 462) says "Long rates: 20
  year gilt yield". The loader reads EFO table 1.9, column "Long-term
  interest rates (20-year gilts)", sourced there to Bank of England series
  IUQALNPY.
- **Decision.** The loaded series is right and is not changed. The text
  that said 10-year (`monetary_conditioning.md` and the
  `monetary_conditioning_off` note) now says 20-year.
- **Left.** `results/demo_shocks.json` still carries the old note string
  until the demo workflow next regenerates it. No number in it is affected.

### 3. The gilt-yield response is the listing's, not a bug

- **The question.** +1 point on `RL` lowers GDP by £479m in the first
  quarter and £989m in the fourth, more than Bank Rate.
- **Finding.** l.649 scales employees' pension contributions `EECPP` with
  `RL` on a £2.98tn stock, which takes £5.2bn a quarter off household
  income. The run matches l.649 to the pound. The matching income (`APIIH`)
  has no equation, so only one leg moves.
- **Decision.** No code change and no overlay. Documented in
  `monetary_conditioning.md` ("A gilt-yield shock") and pinned by
  `tests/test_gilt_yield_channel.py`.
- **Left.** The baseline level of `EECPP` steps up at the first solved
  quarter (£26,865m to £38,488m) because l.649 over-predicts the ONS
  series. Fixing that would move baseline household income; it needs its
  own before and after.

## 21 November 2026 (imports and employment)

Two points raised in review: imports do not respond to demand, and
employment is an input. Both are confirmed in `demand_overlays.md`. Each
gets an opt-in overlay; no default changes and no published figure moves.

| Question | Decision | Why |
|---|---|---|
| Make imports respond by default | No. Opt-in `import_response` | The goods elasticity is an assumption. Defaults carry no behavioural assumption (section 3 below) |
| Goods-import elasticity | 1, kept and labelled, on the listing's l.211 import-content weights | The listing has no estimated goods-import equation. Its weights are the only published source in the repo. The services elasticity (1.079, l.223) was not carried over to goods |
| Oil in the goods leg (22 Nov review) | Counted once: goods imports including oil are unit-elastic to `MGTFE`; non-oil goods are that total less the listing's oil imports | The listing does not settle whether the l.211 weights cover oil (for: they sum with the services weights to totals scaled on all imports; against: the export term and the relative price beside it are non-oil). This form cannot double count under either reading. Cost if the weights are non-oil: total imports £107m–£186m a quarter lower from q2 than under the earlier form |
| Drop the goods leg, keep services (22 Nov review) | No. Kept, labelled | With oil netted off, the leg needs one number beyond the listing's weights, and it is stated. Dropping it means an elasticity of 0, also an assumption, and a less plausible one. The elasticity-0 run is in `results/demand_overlays.json` so the reader sees what rests on it |
| Services imports | The listing's l.223 in deviation form | Its missing inputs (`PMSREL`, `SPECX`) cancel against the baseline, so no data is invented |
| Link employment to GDP | Opt-in `employment_response`, through the listing's l.145 | The only labour-demand equation in the listing. The bridge to total employment is an assumption |
| Okun-type rule | Not added | No coefficient in the listing and no OBR or ONS source in the repo; nothing was downloaded |

- Measured for government consumption of 1% of GDP: GDP per pound 1.01–1.04
  by default, 0.90–0.93 with `import_response` (0.97–1.00 with the goods
  elasticity set to 0, so the assumption carries about 0.07).
- The employment overlay gives −14,500 jobs at quarter 12 for a 1p
  basic-rate rise. For government consumption it is near zero and
  wrong-signed in places (employment falls by 0.8 to 1.9 thousand from
  quarter 2 to quarter 5, and by up to 19.7 thousand with imports on),
  because government GVA takes almost all of that shock and government
  employment has no equation. The run carries a warning that says so.
- Left open: an estimated goods-import elasticity and a government
  employment link, each needing a source outside the repo.

## 18 November 2026 (Fable 5.2 review round)

The 17 November review (#72) left three code changes open, each of which
changes a default or moves figures the PolicyEngine Macro site quotes. Each
was decided on a run. Two are adopted, in their own pull requests; one is
rejected here. Sections 1 and 2 describe those pull requests: until they
merge, main still has the behaviour in their "before" columns.

| Change | Decision | Where |
|---|---|---|
| Anchor unemployment to the EFO ("anchor `PART16`") | Adopted, as a population fix | implemented in #74, merged 18 Nov 2026 (6f21531) |
| Nominal-consistent government-consumption shock | Adopted as the default for `CGG` | implemented in #75, merged 18 Nov 2026 (0e44ec8) |
| Default `monetary_conditioning=True` | Rejected | this note, `monetary_conditioning.md` |
| Regenerate `fig_outturn` on the current ONS vintage | Not possible from this repo | this note |

### 1. Unemployment tracks the EFO: fix the population, not the participation rate (adopted, #74)

**What was proposed.** Anchor the participation rate `PART16` so the
anchored unemployment rate stops draining (3.75% against the EFO's 5.07% at
2027Q4, 1.05% against 4.17% by 2031Q1).

**What the run showed.** `PART16` was already on the EFO path in every
quarter, and so was employment. Making `PART16` exogenous changed nothing,
to the last digit. The series that was off was the 16+ population `POP16`:
beyond its last ONS observation (2026Q1, 56.6m) it was held at its trailing
four-quarter mean, 56.4m, like every other snapshot series, while the EFO's
employment kept rising. The labour-force identity
`ULFS = POP16·PART16/100 − ETLFS` (l.163) then removed the difference from
unemployment.

**The fix.** The EFO publishes unemployment, employment and the
participation rate. The listing's l.175 gives the population they imply,
`POP16 = 100·(ULFSU + ETLFS)/PART16`. Over 2019Q1–2026Q1 that equals the
ONS series to 1 part in 100,000, so it is a derivation, not a judgement.
The forecast tail of `POP16` now uses it. Published observations are
untouched.

**Why adopt it.** The flat population was an extrapolation artefact that
contradicted three published EFO series. The fix uses only published
inputs and the model's own identity.

**What it moves** (October 2026 EFO, default closure):

| Figure | Before | After |
|---|---|---|
| Anchored unemployment, 2027Q4 / 2031Q1 (EFO 5.07% / 4.17%) | 3.75% / 1.05% | 5.07% / 4.17% |
| Anchored GDP MAPE, 2025Q1–2027Q4 / to 2031Q1 | 0.44% / 0.77% | 0.24% / 0.45% |
| Anchored consumption MAPE, 2025Q1–2027Q4 | 0.72% | 0.40% |
| Anchored GDP gap at 2031Q1 | 1.24% | 0.77% |
| Free-running GDP / consumption MAPE | 4.05% / 6.92% | 4.24% / 7.23% |
| Free-running unemployment | 1.17pp | 0.62pp |
| Free-running company profits | 11.66% | 12.88% |
| Free-running lines within band | 8 of 11 | 9 of 11 |
| Held-add-factor forecast: GDP / consumption | 0.35% / 0.39% | 0.63% / 0.85% |
| Bank Rate +100bp, GDP at q8 / q12 (£m) | −474.9 / −503.1 | −472.2 / −499.6 |

The anchored fit improves and the free-running and held-add-factor fits of
GDP and consumption get slightly worse, for one reason: the consumption
equation (l.4) carries −0.0084·d(LFSUR), so a draining unemployment rate
had been lifting consumption. That lift was the artefact. Reform deltas in
the first four quarters do not move; later quarters move by under 1%.

**What it is not.** Not an unemployment forecast. Nothing in the listing
moves unemployment when a policy changes; a reform still leaves `LFSUR`
exactly at baseline.

### 2. Government-consumption shock is nominal-consistent by default (adopted, #75)

**What was proposed.** Make a `CGG` shock move nominal spending too, so
borrowing moves.

**What the run showed.** `CGG` is real government consumption. The listing
imposes the nominal totals (the "indirect T2 fix"), so a real-only shock
raises real spending with nominal spending held: the government deflator
falls 0.9 index points per £1.25bn, no borrowing aggregate moves at all,
and under the nominal-GDP pin the investment deflator absorbs the gap, so
measured business investment reads +16% to +24% of the shock with no
investment response behind it. Moving nominal consumption `CGGPS` alone
removes the investment artefact but still moves no borrowing. Moving
`CGGPS` and its public-finances counterpart `CGGPSPSF` moves procurement,
but the subsidy residual (l.504) offsets it one for one. Borrowing moves
only when public sector current expenditure `PSCE` moves as well.

**The change.** A default `CGG` shock under the nominal-GDP pin also moves
`CGGPS`, `CGGPSPSF` and `PSCE` by the cash cost, shock × baseline
`CGGPS/CGG`. `nominal_consistent=False` gives the real-only shock.

**Why adopt it.** A spending increase that costs nothing in cash is not
the experiment anyone asks for, and the real-only shock reports an
investment response that is deflator arithmetic. The consistent shock
changes the GDP answer by under 1% and makes the fiscal side add up.

**What it moves** (+£1.25bn a quarter of `CGG` for 12 quarters from 2025Q1;
before/after figures for q1 / q4 / q12 are in #75 and
`results/demo_shocks.json`): the GDP multiplier goes from 1.01–1.05 to
1.01–1.04; central government net borrowing and public sector net
borrowing go from exactly zero to the cash cost (about £1.34bn to £1.42bn
a quarter); IBUSX goes from about +£200m to +£295m a quarter to within £4m
of zero.

**What it is not.** Not a fiscal multiplier with a financing response:
receipts have no equation in the listing and do not move.

### 3. `monetary_conditioning` stays opt-in (rejected)

**What was proposed.** Default `monetary_conditioning=True`, so a Bank Rate
shock moves the mortgage rate at the OBR's l.623 pass-through (GDP −0.149%
per 100bp at the peak instead of −0.057%).

**Decision.** Rejected. The full reasoning and arithmetic are in
`monetary_conditioning.md`, "Why the default stays `False`". In short,
strongest reason first:

- A default run should not carry a behavioural assumption. The overlay
  moves a different variable, the mortgage rate, by an assumed pass-through
  coefficient (0.9); the listing treats retail rates as conditioning
  assumptions set outside the model. The other two overlays are opt-in for
  the same reason. The nominal-consistent `CGG` shock in section 2 is a
  different kind of thing: it moves the nominal side of the same
  transaction at the data deflator, with no coefficient.
- Both modes are below the Bank of England benchmark, and CPI and
  unemployment respond in neither. Switching would multiply the reported
  GDP effect by 2.6 without making it an estimate.
- The overlay makes interest paid consistent with l.623 but leaves interest
  received unmoved (it has no equation), so it books the full £4.68bn a
  quarter rise in household interest payments against no rise in income on
  about £2.25tn of deposits. An illustration in the note, using a
  sight-deposit pass-through range for the whole stock, puts the net fall
  at about £0.2bn to £2.4bn a quarter, with the default's £1.41bn inside
  it. That is not a model result; it shows only that the conditioned run
  is not obviously nearer the net household effect.

The docs keep quoting both runs side by side (`results/demo_shocks.json`,
rows `bank_rate` and `bank_rate_conditioned`). The wording that called the
default run "a lower bound" is corrected: neither run bounds the full
effect.

**What would change it.** A sourced pass-through from Bank Rate to the
effective deposit rate, or an OBR statement of how it conditions retail
rates on Bank Rate.

### 4. `fig_outturn` on the current ONS vintage (not possible from this repo)

The outturn chart, its script (`papers/obr-macro/figures/fig_outturn.py`),
its data file and its vintage pin (`validation/figures/chart_data.json`)
all live in PolicyEngine/macro, not here (checked with a code search of
the organisation and a read of a local PolicyEngine/macro working copy on
a round branch, not main). That script's docstring says it refuses to run
on anything but the November 2025 EFO study it documents and that the
site's chart takes its ONS column from the pinned vintage file. Nothing in
this repository generates or feeds the figure, and the ONS snapshot
vendored here was pulled on 11 July 2026, so it could not supply a current
vintage without a new download. The regeneration belongs with the site
work in PolicyEngine/macro.
