# OBR Macroeconomic Model Emulator

Python implementation of the OBR's published macroeconomic model, enabling policy shock analysis.

## Features

- Parses all 372 equations in the OBR's published EViews model code and solves them in Python.
  Not all of them run: in the pinned reform solve over 2025Q1–2027Q4, 82 are dropped in at least
  one quarter because an input has no data, so the equation evaluates to NaN (each must be listed in
  `KNOWN_NONFINITE_EQUATIONS`, `obr_macro/full_solver.py`, or the solve raises); several headline variables
  (investment, trade, prices, earnings) have no live equation and pass through at the OBR's
  value. The business-investment equation `dlog(IBUSX)` is reconstructed from a line the OBR
  publishes commented out, and under the investment closure `MSGVA`, `PIF` and `PIRHH` are
  frozen to keep it stable (see the table below).
- Gauss-Seidel solver for simultaneous equation systems
- Policy shock analysis (fiscal multipliers, tax changes)
- Visualisation of reform impacts

## Read this before quoting a number

The emulator is honest about its own limits in code (`df.attrs` carries a
warning on every result that has one), but the limits are severe and easy to
miss. In one place:

| | |
|---|---|
| **Anchored fit to the October 2026 EFO** | GDP 0.44% MAPE, consumption 0.72% (2025Q1–2027Q4; 0.30% and 0.49% against the March 2026 EFO). **By construction** — the add-factors are computed as `EFO − model` and added back. It proves the anchoring machinery works, nothing about forecast skill. And only consumption is re-derived: every other term in the GDP identity is held at its EFO value, so the GDP number is the consumption number diluted by the consumption share. **Unemployment is not anchored**: the anchored rate drifts to 3.75% against the EFO's 5.07% at 2027Q4 and 1.05% against 4.17% by 2031Q1, and the anchored GDP gap grows to 1.24% by 2031Q1 (`results/site_figures.json`). The labour-force identities `ULFS` (l.163) and `PART16` (l.175) are one identity written twice, so nothing holds participation on the EFO path. |
| **Reform baseline** | `run_reform` scores every reform around this anchored baseline: the add-factors are frozen into the baseline *and* the shocked run, so they set the level and cancel in the delta. Its own baseline solve tracks the EFO to GDP 0.46%, consumption 0.76%, household income 0.00% under the default nominal-GDP pin (October 2026 EFO; 0.31% and 0.51% on the March 2026 EFO) (0.03% under the published closure, the previous default) (household income and, under the investment closure, total investment are held on the EFO by a level add-factor rather than by deleting their identities, so reforms can still move them). Before 2026-10 the reform baseline silently ran free — 4.35% off on GDP. |
| **Free-running (add-factors off)** | GDP 4.05%, consumption 6.92%, business investment 7.34%, household income 3.08%, company profits 11.66%, current account 0.91% of GDP (October 2026 EFO, 16 Nov 2026, after household taxes `TYWHH` were held on their data path: their ONS components are not seasonally adjusted, and the gap had put a −11% to −13% first-quarter dip into household income), under the default nominal-GDP pin (the OBR's commented-out l.690, `GDPMPS = PGDP*GDPM/100`; see `docs/nominal_gdp_pin.md`). Under the published closure, the previous default (still available as `nominal_gdp_pin=False`), the same solve gives GDP 3.82%, consumption 6.55%, business investment 22.13%, household income 3.69%, company profits 47.74% and current account 1.03% of GDP (before `TYWHH` was closed: 4.51%, 7.67%, 18.21%, 6.51%, 109.96% and 3.32%; on the March 2026 EFO: 4.14%, 6.92%, 17.19%, 5.97%, 43.64% and 2.11%; before the receipts identities went live, #56: 4.32%, 7.22%, 15.28%, 6.18%, 82.77% and 3.02%); its company-profits and current-account figures measure solver drift, not fit ([#42](https://github.com/PolicyEngine/obr-macroeconomic-model/issues/42)): nominal GDP and the investment deflator `PIF` are one identity written twice (l.337/l.688), so `PIF` random-walks under the de-seeded solve and profits, a residual of nominal GDP, swing with it. 11 of 21 headline variables are computed at all; the other 10 are held at the OBR's value. This gap is a property of **this emulator**, not an OBR forecast error: in the OBR's own model GDP is an input (the expenditure identity solves for inventories), so their model cannot miss it. What the gap measures is this repo's closure swap (GDP made endogenous) plus the OBR inputs and constants that are not published and had to be pulled from the ONS or seeded. The ended EU budget payments `GNP4` and `EUVAT` are held at zero from 2021 ([#62](https://github.com/PolicyEngine/obr-macroeconomic-model/issues/62)); with them regenerated, the default-closure current account read 2.19% of GDP and company profits 17.90%. See `docs/calibration_scorecard.md`. |
| **Government-consumption multiplier** | 1.01 on impact, drifting up to 1.05 by quarter 12 under the default nominal-GDP pin (1.00 and flat under the published closure, the previous default), because the shock lands directly in the expenditure identity. The only second round is that the extra nominal GDP lands in company profits (wages are exogenous) and a small part reaches household income and consumption (+£17m to +£60m on a £1.25bn/quarter shock). The OBR's published impact multiplier for **current** spending is **0.6**, decaying to zero. This model overstates it by ~69% on impact and by more thereafter. It is accounting, not a multiplier. The model cannot produce the OBR's multiplier; `run_reform(..., published_conventions=True)` (off by default) imposes the published 0.6-fading convention as a labelled add-factor path — judgement re-applied, not a model result. **Borrowing does not move**: `CGNB` (l.524) reads nominal pay and procurement (`CGWS`, `CGP`), and the nominal spending identity `CGGPS` (l.381) is commented out, so a real `CGG` shock leaves receipts and borrowing unchanged. |
| **Government-investment multiplier** | **No channel under the default closure.** `IF` has no live equation in the published model, so `CGIPS → GGIPS → GGI → IF` never reaches GDP: `delta_IF` is exactly zero and the GDP residue is wrong-signed deflator noise. `run_reform` warns and names two labelled routes. `investment_closure=True` switches on the listing's commented-out `IF` identity (l.86), and +£3bn a quarter then moves GDP by +£3.08bn / +£2.90bn / +£2.93bn at q1 / q4 / q12: identity passthrough at about 1.0 per real pound, with no taper and no crowding-out, labelled `mechanical_passthrough` (the nominal-GDP pin is off under that closure). `published_conventions=True` instead imposes the OBR's 1.0-fading convention as a labelled add-factor path. The OBR's capital multiplier is 1.0 on impact, tapering. |
| **VAT and fuel duty** | By default a VAT rise reaches GDP only as a tax on profits: current-price GDP per pound of 0.013 / 0.026 / 0.043 at q1 / q4 / q12, against the OBR's 0.35, fading. CPI is exogenous in the listing: l.314 is commented out and the retail markup absorbs the tax (l.284). The opt-in `run_reform(..., price_passthrough=True)` passes the tax into CPI through the listing's own cost-push weights (total indirect-tax weight 13.84 in `RPCOST`, l.270), with the markup held at baseline. VAT +1pp then lifts CPI by about 0.4% and gives 0.175 / 0.345 / 0.643 at q1 / q4 / q12 (0.26 averaged over year 1). That is close to the OBR at q4 but keeps building after, because nothing in the published equations makes consumption fade. It is a labelled judgement overlay, not the shipped listing ([#60](https://github.com/PolicyEngine/obr-macroeconomic-model/issues/60)). |
| **Household tax multiplier** | The one channel with genuine behaviour (`dlog(CONS)` responds to real income). For a 1p basic-rate rise (£1,616m/quarter from 2025Q1, sustained; PolicyEngine's static costing, against HMRC's £1,725m used in `docs/demo.md`, which gives the same ratios) current-price GDP per pound of revenue averages 0.16 in year 1, rising to 0.38 by quarter 12 under the default nominal-GDP pin, against the OBR's 0.3 impact multiplier decaying. That is the OBR's like-for-like basis. Real GDP per pound of current-price revenue, which this row used to quote, is 0.146 and 0.33: it mixes two bases and is smaller by PGDP/100 (1.08 in year 1, 1.14 at quarter 12; [#63](https://github.com/PolicyEngine/obr-macroeconomic-model/issues/63)). `run_reform` reports both per quarter in `df.attrs["gdp_per_revenue_current_price"]` and `df.attrs["gdp_per_revenue_real"]`. Right order of magnitude, wrong profile. The household costing (`HHDI_ADDFACTOR`) moves household income only; receipts and borrowing do not move. Shock `TYEM` to move them too (±1,725 a quarter for HMRC's 1p). |
| **Corporation tax** | Requires `investment_closure=True`, which is a stop-gap. It freezes `MSGVA`, `PIF` and `PIRHH` to stop an explosive accelerator — unguarded, a **zero-shock** baseline runs business investment from £86bn in 2025Q1 to £522bn in 2027Q4 under the default nominal-GDP pin (£586bn under the published closure; £94bn to £8.0tn before the equation's bracket was corrected, [#59](https://github.com/PolicyEngine/obr-macroeconomic-model/issues/59); re-measured 15 Nov 2026 on the March 2026 EFO; reproduce with `scripts/unguarded_ibusx.py`). The base-vs-shock *deviation* now converges to a steady state: the anchor add-factors are held in **log space** (the EViews convention for a `dlog` equation), so the published equation's own error-correction term pulls the deviation to `dlog(KSTAR) = −0.4·dlog(TAF)`. (Until 2026-08 the anchors were *level* add-factors, which amplified the deviation by 1.21–1.27× per quarter — `delta_IF` for +5pp hit £43.4bn by q25 with no steady state.) Measured now for a sustained +5pp rise: £0.24bn at q8, £0.38bn at q12, £0.68bn at q25, approaching a ~£0.96bn/q plateau; the error-correction root is slow (~0.958/quarter), so a 12-quarter figure is **~40% of the plateau** — `df.attrs["investment_closure_plateau_fraction"]` says where a run sits. The response size is set by `DB`, `DP`, `DV` (present values of capital allowances), now **estimated from statute and the OBR's published gilt assumption** rather than invented — see below. No OBR corporation-tax multiplier is quoted here: the multiplier table this repo encodes from EFO July 2015 Box 3.2 (`obr_macro/published_conventions.py`) has no corporation-tax row, so the response has no sourced benchmark. A `TCPRO` shock moves the cost of capital only: receipts and borrowing do not move (a static yield would be about £4.5bn a quarter for +5pp). |
| **Bank Rate** | Wired to consumption and household interest flows only (`test_bank_rate_response_is_consumption_only`); corporate interest and the cost of capital do not respond (`test_corporate_lending_rate_is_not_evaluated_under_the_default_closure`). Inflation and unemployment respond by exactly zero. A +1pp rise held for four quarters lowers GDP by 0.149% at the peak with `monetary_conditioning=True`, which moves the mortgage rate at the OBR's own l.623 pass-through and is the reading consistent with the listing, and by 0.057% in the default run, which holds the mortgage rate. Household interest received has no equation and moves in neither run, so neither is a bound on the full effect; the default stays the one-variable shock (decision of 18 Nov 2026, `docs/monetary_conditioning.md`). Both are below the Bank of England's −0.2% to −0.35% after about a year for the same experiment (*The transmission mechanism of monetary policy*, Quarterly Bulletin 1999 Q2). Under the default nominal-GDP pin the response is proportional and symmetric (peak −0.0145% for +25bp, −0.0574% for +100bp, +0.0590% for −100bp, measured on the March 2026 EFO). Under the published closure (`nominal_gdp_pin=False`) it is not, because a late PIF jump dominates small shocks ([#50](https://github.com/PolicyEngine/obr-macroeconomic-model/issues/50)). Retail rates, gilts, sterling and house prices are OBR conditioning inputs with no equation; the opt-in `run_reform(..., monetary_conditioning=True)` moves the mortgage rate with Bank Rate at the OBR's own l.623 pass-through (0.9) and leaves the unsourced channels off. It is a labelled judgement overlay, not model dynamics; CPI and unemployment still do not respond, by design. See `docs/monetary_conditioning.md`. |
| **Solver convergence** | Under the default closure (the nominal-GDP pin) every quarter converges to the tolerance. On the October 2026 EFO (16 Nov 2026) every baseline and shocked solve in the demo battery exits on tolerance in 12 of 12 quarters, and the anchored solve has no non-converged quarter to 2032Q1. Measured on 11 Nov 2026 (March 2026 EFO) over 2025Q1–2031Q1: 25 of 25 quarters exit on tolerance in the baseline and the shocked solve for government consumption, the household tax, Bank Rate and government investment, and in the published-conventions solve; a corporation-tax run under the investment closure also gives 25 of 25. `df.attrs["solver_exit_status"]` reports it per run. "Converged" covers the equations that evaluate: those with missing inputs are dropped and keep their data values. Under the published closure (`nominal_gdp_pin=False`) no quarter converges: Gauss-Seidel exits on the stall break in every quarter, zero-shock runs included, because the nominal-GDP / `PIF` pair above is undetermined and extra iterations let `PIF` wander ([#50](https://github.com/PolicyEngine/obr-macroeconomic-model/issues/50), [#42](https://github.com/PolicyEngine/obr-macroeconomic-model/issues/42)). A delta under that closure is a difference of two non-converged solves. |
| **Uncertainty** | None. Every result is a point estimate. |

Instrument-level guards added on top of this: shocking a variable that is
missing or NaN now raises instead of silently returning zero effect, and a
`TCPRO` shock that would push the corporation-tax rate outside `[0, 1)` is
refused — above 1 the user-cost formula has a pole and the model previously
returned a finite, unflagged "a 105% corporation tax raises investment by
£3.2bn".

## Quick Start

Install with `uv sync` (see Setup), then run the snippet with `uv run python`. Each `run_reform` call builds and solves the model twice over 12 quarters; the three calls below take about five minutes on a laptop (measured 15 Nov 2026, Apple silicon), most of it the first template build.

```python
from obr_macro import FullOBRSolver, run_reform

# Run a £5bn government spending shock
results = run_reform(
    name="Fiscal Stimulus",
    var="CGG",
    shock=1250,  # £1.25bn per quarter
    periods=4,
)
print(results[["period", "delta_gdp_bn", "pct_gdp"]])

# Apply an externally costed household reform. Values are quarterly £m:
# positive = revenue raised = household disposable income falls.
results = run_reform(
    name="Household tax reform",
    var="HHDI_ADDFACTOR",
    shock=[250, 500, 750, 1000],
    start="2025Q1",
    end="2025Q4",
)
print(results[["period", "delta_cons_m", "delta_gdp_m"]])
print(results.attrs["delta_hhdi_m"])

# Run a corporation tax cut (-5pp)
results = run_reform(
    name="Corp Tax Cut", var="TCPRO", shock=-0.05, periods=12, investment_closure=True
)
```

Quarterly household-costing paths are near-linear for ordinary policy sizes,
but not mathematically additive: the OBR consumption equation contains log
differences and an error-correction term. Tests bound the departure from the
sum of isolated quarterly impulses to 0.05% for £100m–£400m quarterly shocks.
That is additivity across quarters for small shocks inside the window, not
size-linearity or sign symmetry: at £1.6bn a quarter, under the default
nominal-GDP pin, the rise-plus-cut residual is 0.2% of the peak and the
4x-versus-4×1x gap 0.3% (`docs/nominal_gdp_pin.md`; 125% and 51% under the
published closure).

## Run All Reforms with Visualisations

```bash
uv run python -m obr_macro.reform_analysis
```

This runs five policy scenarios and generates charts in `outputs/`:
- £5bn government spending increase
- 5pp corporation tax cut
- 5pp corporation tax rise
- £10bn government investment — **dead channel** under the default closure, kept so the defect is visible (`investment_closure=True` gives it the listing's `IF` identity);
  see the table above
- £10bn spending cut (austerity)

## Data

The `obr_macro/_data/` directory (shipped inside the package) contains:
- `obr_model_code_october_2025.txt` - OBR EViews model equations (15 October 2025 version)
- `obr_model_variables_october_2025.xlsx` - OBR model variable definitions (15 October 2025 version)
- `obr_efo_october_2026_*.xlsx` - OBR forecast data (October 2026 EFO detailed forecast tables)
- `obr_efo_november_2025_*.xlsx` - the November 2025 EFO tables, kept as a cross-vintage check (the March 2026 tables were replaced by October 2026)

## Pins, results and validation

**Pins**
- Model: the OBR's EViews listing and variable list, 15 October 2025 (`obr_macro/_data/`). Still the latest on obr.uk on 16 Nov 2026.
- Baseline: the OBR's October 2026 EFO detailed forecast tables (published 28 Oct 2026).
- Unpublished inputs: 355 ONS series pulled on 11 Jul 2026, 8 recovered on 22 Sep 2026 (`obr_macro/seeds/ons_exogenous_snapshot.csv`, `snapshot_manifest.json`).
- Python 3.11 or later; dependencies locked in `uv.lock`.

**Results**
- `results/demo_shocks.json`: the demo battery that every number in `docs/demo.md` comes from.
- `results/site_figures.json`: the figures the PolicyEngine macro site quotes.
- Both are regenerated on GitHub Actions by `.github/workflows/demo.yml` (manual dispatch).
- `scripts/unguarded_ibusx.py` reproduces the unguarded business-investment path quoted in the corporation-tax row.

**Validation**
- `tests/`: the fast suite runs on every push and pull request.
- `.github/workflows/ci.yml` adds:
  - the full-solve structural invariants (a hard gate, nightly);
  - the extended slow suite on Python 3.11–3.13 (weekly);
  - a report-only calibration scorecard.
- `docs/calibration_scorecard.md`: raw-model fit against the EFO.
- `docs/published_model_review.md`: a line-by-line check of the OBR's listing.
- `docs/transmission_audit.md`: which shocks reach which variables.
- `docs/decisions.md`: dated modelling decisions, adopted and rejected, with the run behind each.
- `docs/history/`: superseded investigation notes.

**Limits**
- The table under "Read this before quoting a number" lists them.
- Every result is a point estimate.
- The free-running error measures this emulator, not the OBR's forecast.
- Opt-in overlays (`published_conventions`, `monetary_conditioning`, `price_passthrough`) are labelled judgement, not model dynamics.

## Setup

```bash
uv sync
```

## How It Works

1. **Transpiler** (`transpiler.py`): Converts OBR EViews syntax to Python
2. **Solver** (`full_solver.py`): Gauss-Seidel iteration over ~370 equations
3. **Closure swap**: In the OBR file GDP is an input and inventories (`DINV`) are the balancing item of the
   expenditure identity (`DINV = GDPM + M − SDE − CGG − CONS − VAL − IF − X`). To let a demand shock move GDP,
   `swap_closure` deletes that `DINV` equation, holds `DINV` exogenous at its EFO path, and adds the identity
   `GDPM = CGG + CONS + IF + DINV + VAL + X − M + SDE`, so GDP becomes endogenous
4. **Deviation mode**: Solve a baseline and a shocked run from the same anchored template (add-factors applied in both) and difference them to isolate policy effects

### Constants this repo supplies (estimated where possible)

Four constants set the entire magnitude of the corporation-tax → investment
response. The OBR publishes their equations but not the equations' inputs
(`DISCO`, `IIB`, `SIB`, `FP`, `SP`, `SV`, `DELTA`, `RWACC` have no equation
and no data in any published artefact), so the published equations always
evaluate to NaN and `solve_period` silently drops them: the seeds are the
operative values for the whole run, not starting guesses.

Since 2026-08 the three allowance PVs are **estimated from published sources**
(statutory capital-allowance rates + the OBR's own EFO long-gilt assumption,
run through the OBR's published formulas — derivation committed as
`obr_macro/cost_of_capital.py`, reproduce with
`python -m obr_macro.cost_of_capital`):

| | now | was | basis |
|---|--:|--:|---|
| `DB` (PV of allowances, buildings) | 0.0 | 0.18 | the OBR's own equation zeroes it after 2011Q2 (Industrial Buildings Allowance abolished April 2011); no unpublished input needed |
| `DP` (PV of allowances, plant) | 0.9492 | 0.06 | full expensing (100% first-year, permanent since FA 2024) collapses the formula to `1/(1+DISCO)`; `DISCO` = 0.0535, mean EFO October-2026 20-year gilt over the solve window |
| `DV` (PV of allowances, vehicles) | 0.7709 | 0.25 | `SV/(DISCO+SV)` with the statutory 18% main-rate WDA |
| `COCU` (pre-tax user cost) | 0.12 | 0.12 | **kept as a declared seed**: its level provably cancels in the corporation-tax deviation (doubling it moves a 12q `delta_IF` path by <1e-10), and its equation needs a 1970Q1 rebasing anchor predating every committed series — no estimate can beat it on evidence |

The old `DB`/`DP`/`DV` numbers were statutory writing-down **rates** mislabeled
and pasted in as present **values** (with the asset classes swapped — the OBR's
variables workbook defines `DB`=buildings, `DP`=plant, `DV`=vehicles), which
overstated `(1−D)` and hence the corporation-tax response roughly 2.4×. The
seeds live in `full_solver.UNPUBLISHED_COST_OF_CAPITAL_SEEDS` and are pinned to
their derivation by `tests/test_calibration_constants.py`. They are estimated,
not fitted — no attempt is made to tune them so a costing hits a target.

Two more level anchors are worth knowing about, both legitimate (each is
anchored to *published* data, and each applies identically to the baseline and
every shocked clone so it cancels in a delta) but both large:

- `OSHH` (households' operating surplus) carries an add-factor of ~£41bn
  against a level of ~£79bn — **55% of the series is the add-factor**, because
  the OBR's base constant `12874` and its `PRENT` vintage are unpublished.
  Held flat at the last four quarters' mean for the whole forecast.
- `GGVA` (government GVA) is seeded at **20% of GDP**, an uncited round number.
  The published equation is a ratio (`GGVA/GGVA(-1) = CGG/CGG(-1)`) and so
  inherits whatever level the seed sets; that level then determines
  `MSGVA = GVA − GGVA`, the driver of the investment accelerator.

### Known inert equations

`log(HHTFA)` and `log(NDIVHH)` now parse correctly (they previously had no LHS
branch at all), but both remain frozen because their exogenous inputs `MAJGDP`
and `CORP` are absent from the published databank. The corporate-profits →
household-dividend-income channel (`FYCPR → NDIVHH → PIRHH → HHDI`) is therefore
still inert. See `docs/forecasting_framework.md`.

## Key Variables

- `CGG` - Government consumption (exogenous)
- `TCPRO` - Corporation tax rate (exogenous)
- `HHDI_ADDFACTOR` - Virtual household-reform instrument; quarterly £m of
  static revenue raised (positive values reduce disposable income)
- `CGIPS` - Central government investment, nominal (exogenous)
- `GDPM` - GDP at market prices (endogenous)
- `CONS` - Private consumption (endogenous)
- `IF` - Total investment (endogenous)

## License

Code in this repository is released under the [MIT License](LICENSE). Original text and figures are released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) with attribution to PolicyEngine. Third-party data and materials keep their own terms.
