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
| **Household tax multiplier** | The one channel with genuine behaviour (`dlog(CONS)` responds to real income). Year-1 average 0.16, rising to 0.37 by quarter 12, against the OBR's 0.3 impact multiplier decaying. Right order of magnitude, wrong profile. |
| **Corporation tax** | Requires `investment_closure=True`, which is a stop-gap. It freezes `MSGVA`, `PIF` and `PIRHH` to stop an explosive accelerator — unguarded, a **zero-shock** baseline runs business investment from £94bn to £7.3tn in 11 quarters. That guard fixes the *level*; it does **not** fix the base-vs-shock *deviation*, which compounds at 1.21–1.27× **every quarter for at least 25 quarters** and never reaches a steady state (`delta_IF` for a sustained +5pp rise: £1.0bn at q8, £2.9bn at q12, £43.4bn at q25). `run_reform` now warns on every investment-closure run, including the 12-quarter horizon all published results here use. **Read the sign, not the magnitude.** The size of the response is set by four constants (`DB`, `DP`, `DV`, `COCU`) this repo invents because the OBR's published equations for them need inputs the OBR does not publish. The OBR's corporation-tax multiplier is 0.2. |
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
    periods=4
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
    name="Corp Tax Cut",
    var="TCPRO",
    shock=-0.05,
    periods=12,
    investment_closure=True
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

### Constants this repo invents

Four constants set the entire magnitude of the corporation-tax → investment
response and appear in **no** OBR publication:

| | seeded | why it is not the OBR's |
|---|--:|---|
| `DB` | 0.18 | published equation needs `DISCO`, `IIB`, `SIB` |
| `DP` | 0.06 | needs `DISCO`, `FP`, `SP` |
| `DV` | 0.25 | needs `DISCO`, `SV` |
| `COCU` | 0.12 | needs `DELTA`, `RWACC` |

None of those inputs has an equation in the published model file or a series in
any published data source, so the OBR's equations always evaluate to NaN and
`solve_period` silently drops them: the seeds are the operative values for the
whole run, not starting guesses. They live in
`full_solver.UNPUBLISHED_COST_OF_CAPITAL_SEEDS` and are pinned by
`tests/test_calibration_constants.py`. They are declared, not fitted — no
attempt is made to tune them so a costing hits a target.

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
