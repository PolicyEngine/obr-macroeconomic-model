# OBR macroeconomic model

A Python implementation of the OBR's macroeconomic model, used for producing economic forecasts in the Economic and Fiscal Outlook. The model covers GDP, prices, the labour market, household income and consumption, investment, and the balance of payments.

**This is an independent reimplementation under active development. Outputs may differ from official OBR forecasts.** The model is calibrated to the November 2025 EFO but not all variables are fully calibrated yet — treat results with caution.

## Setup

```bash
pip install -e .
```

You'll need the OBR economy supplementary tables Excel file. Download from the [OBR website](https://obr.uk/efo/economic-and-fiscal-outlook-november-2025/) and place at `data/obr_efo_november_2025_economy.xlsx`.

## Usage

```bash
python example.py
```

This loads OBR forecast data, calibrates the model, and solves a 2025Q1-2030Q4 forecast using the Gauss-Seidel method.

## Structure

- `obr_macro/variables.py` — variable store with quarterly time indexing
- `obr_macro/equations/` — nine equation groups (prices, output, labour, consumption, investment, income, GDP, balance of payments, housing)
- `obr_macro/solver.py` — Gauss-Seidel iterative solver
- `obr_macro/calibration.py` — loads OBR EFO data and sets model variables
- `obr_macro/model.py` — top-level model class
