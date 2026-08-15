# OBR Macroeconomic Model Emulator

Python implementation of the OBR's published macroeconomic model, enabling policy shock analysis.

## Features

- Runs the OBR's 372 published EViews equations in Python
- Gauss-Seidel solver for simultaneous equation systems
- Policy shock analysis (fiscal multipliers, tax changes)
- Visualisation of reform impacts

## Read this before quoting a number

The emulator is honest about its own limits in code (`df.attrs` carries a
warning on every result that has one), but the limits are severe and easy to
miss. In one place:

| | |
|---|---|
| **Anchored fit to the March 2026 EFO** | GDP 0.16% MAPE, consumption 0.26% (2025Q1–2027Q4). **By construction** — the add-factors are computed as `EFO − model` and added back. It proves the anchoring machinery works, nothing about forecast skill. And only consumption is re-derived: every other term in the GDP identity is held at its EFO value, so the GDP number is the consumption number diluted by the consumption share. |
| **Free-running (add-factors off)** | GDP 4.48%, consumption 7.49%, business investment 15.73%, household income 6.27%, company profits 63.29%, current account 3.60% of GDP. 11 of 21 headline variables are computed at all; the other 10 are held at the OBR's value. See `docs/calibration_scorecard.md`. |
| **Government-consumption multiplier** | 1.00 on impact and **flat** for 12 quarters, because the shock lands directly in the expenditure identity and no second-round channel is live. The OBR's published impact multiplier for **current** spending is **0.6**, decaying to zero. This model overstates it by ~67% on impact and by more thereafter. It is accounting, not a multiplier. The model cannot produce the OBR's multiplier; `run_reform(..., published_conventions=True)` (off by default) imposes the published 0.6-fading convention as a labelled add-factor path — judgement re-applied, not a model result. |
| **Government-investment multiplier** | **No channel at all.** `IF` has no live equation in the published model, so `CGIPS → GGIPS → GGI → IF` never reaches GDP: `delta_IF` is exactly zero and the GDP residue is wrong-signed deflator noise. `run_reform` warns. The OBR's capital multiplier is 1.0. The model cannot produce it; `run_reform(..., published_conventions=True)` (off by default) imposes the published 1.0-fading convention as a labelled add-factor path — `delta_IF` stays exactly zero, because only the GDP total is imposed. |
| **Household tax multiplier** | The one channel with genuine behaviour (`dlog(CONS)` responds to real income). Year-1 average 0.17, rising to ~0.40 by quarter 12 on the March-2026 baseline (0.16 → 0.37 on the November-2025 vintage), against the OBR's 0.3 impact multiplier decaying. Right order of magnitude, wrong profile. |
| **Corporation tax** | Requires `investment_closure=True`, which is a stop-gap. It freezes `MSGVA`, `PIF` and `PIRHH` to stop an explosive accelerator — unguarded, a **zero-shock** baseline runs business investment from £94bn to £7.3tn in 11 quarters. The base-vs-shock *deviation* now converges to a steady state: the anchor add-factors are held in **log space** (the EViews convention for a `dlog` equation), so the published equation's own error-correction term pulls the deviation to `dlog(KSTAR) = −0.4·dlog(TAF)`. (Until 2026-08 the anchors were *level* add-factors, which amplified the deviation by 1.21–1.27× per quarter — `delta_IF` for +5pp hit £43.4bn by q25 with no steady state.) Measured now for a sustained +5pp rise: £0.24bn at q8, £0.38bn at q12, £0.68bn at q25, approaching a ~£0.95bn/q plateau; the error-correction root is slow (~0.958/quarter), so a 12-quarter figure is **~40% of the plateau** — `df.attrs["investment_closure_plateau_fraction"]` says where a run sits. The response size is set by `DB`, `DP`, `DV` (present values of capital allowances), now **estimated from statute and the OBR's published gilt assumption** rather than invented — see below. The OBR's corporation-tax multiplier is 0.2. |
| **Uncertainty** | None. Every result is a point estimate. |

Instrument-level guards added on top of this: shocking a variable that is
missing or NaN now raises instead of silently returning zero effect, and a
`TCPRO` shock that would push the corporation-tax rate outside `[0, 1)` is
refused — above 1 the user-cost formula has a pole and the model previously
returned a finite, unflagged "a 105% corporation tax raises investment by
£3.2bn".

## Quick Start

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

## Run All Reforms with Visualisations

```bash
uv run python -m obr_macro.reform_analysis
```

This runs five policy scenarios and generates charts in `outputs/`:
- £5bn government spending increase
- 5pp corporation tax cut
- 5pp corporation tax rise
- £10bn government investment — **dead channel**, kept so the defect is visible;
  see the table above
- £10bn spending cut (austerity)

## Data

The `data/` directory contains:
- `obr_model_code_october_2025.txt` - OBR EViews model equations (15 October 2025 version)
- `obr_model_variables_october_2025.xlsx` - OBR model variable definitions (15 October 2025 version)
- `obr_efo_march_2026_*.xlsx` - OBR forecast data (March 2026 EFO detailed forecast tables)

## Setup

```bash
uv sync
```

## How It Works

1. **Transpiler** (`transpiler.py`): Converts OBR EViews syntax to Python
2. **Solver** (`full_solver.py`): Gauss-Seidel iteration over ~370 equations
3. **Closure swap**: For shocks, DINV (inventories) becomes residual, GDP becomes endogenous
4. **Deviation mode**: Compare shocked vs baseline to isolate policy effects

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
| `DP` (PV of allowances, plant) | 0.9515 | 0.06 | full expensing (100% first-year, permanent since FA 2024) collapses the formula to `1/(1+DISCO)`; `DISCO` = 0.051, mean EFO March-2026 20-year gilt over the solve window |
| `DV` (PV of allowances, vehicles) | 0.7793 | 0.25 | `SV/(DISCO+SV)` with the statutory 18% main-rate WDA |
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
