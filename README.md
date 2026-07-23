# OBR Macroeconomic Model Emulator

Python implementation of the OBR's published macroeconomic model, enabling policy shock analysis.

## Features

- Runs the OBR's 372 published EViews equations in Python
- Gauss-Seidel solver for simultaneous equation systems
- Policy shock analysis (fiscal multipliers, tax changes)
- Visualisation of reform impacts

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
- £10bn government investment
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
