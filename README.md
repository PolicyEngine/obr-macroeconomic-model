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

# Run a corporation tax cut (-5pp)
results = run_reform(
    name="Corp Tax Cut",
    var="TCPRO",
    shock=-0.05,
    periods=12,
    investment_closure=True
)
```

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
- `obr_model_code_march_2025.txt` - OBR EViews model equations
- `obr_efo_november_2025_*.xlsx` - OBR forecast data

## Setup

```bash
uv sync
```

## How It Works

1. **Transpiler** (`transpiler.py`): Converts OBR EViews syntax to Python
2. **Solver** (`full_solver.py`): Gauss-Seidel iteration over ~370 equations
3. **Closure swap**: For shocks, DINV (inventories) becomes residual, GDP becomes endogenous
4. **Deviation mode**: Compare shocked vs baseline to isolate policy effects

## Key Variables

- `CGG` - Government consumption (exogenous)
- `TCPRO` - Corporation tax rate (exogenous)
- `CGIPS` - Central government investment, nominal (exogenous)
- `GDPM` - GDP at market prices (endogenous)
- `CONS` - Private consumption (endogenous)
- `IF` - Total investment (endogenous)
