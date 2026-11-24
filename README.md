# OBR macroeconomic model in Python

PolicyEngine's open Python replication of the macroeconomic model that the Office for Budget Responsibility (OBR) publishes. It reads the OBR's own EViews listing, translates every equation into Python, solves the system quarter by quarter, and scores policy shocks: government spending, taxes, Bank Rate and gilt yields.

**Documentation: https://policyengine.github.io/obr-macroeconomic-model/**

It is a research and teaching tool. It is not the OBR's forecast, and it does not reproduce the OBR's judgements or unpublished inputs.

## Read this before quoting a number

- **The baseline matches the OBR's forecast by construction.** Add-factors are computed as forecast minus model and added back. GDP then tracks the October 2026 Economic and Fiscal Outlook (EFO) to 0.24% (2025Q1 to 2027Q4). That shows the anchoring works, not that the model forecasts well.
- **Without the add-factors the model drifts.** On the same path, the free-running GDP error is 4.24%. That gap belongs to this emulator, not to the OBR: in the OBR's model GDP is an input, so their model cannot miss it.
- **Several channels are accounting, not behaviour.**
  - The government-consumption multiplier is about 1.0, against the OBR's published 0.6.
  - Government investment does not reach GDP under the default closure.
  - Prices, unemployment and debt interest do not respond unless you switch on a labelled overlay.
- **Every result is a point estimate.** There are no uncertainty bands.

The full list, channel by channel with the measured numbers, is in [docs/limitations.md](docs/limitations.md).

## Install

Needs Python 3.11 or later and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/PolicyEngine/obr-macroeconomic-model.git
cd obr-macroeconomic-model
uv sync
```

## Quick start

```python
from obr_macro import run_reform

# Government consumption +£1.25bn a quarter for four quarters
results = run_reform(name="Fiscal stimulus", var="CGG", shock=1250, periods=4)
print(results[["period", "delta_gdp_bn", "pct_gdp"]])

# An externally costed household tax reform, quarterly £m.
# Positive = revenue raised = household disposable income falls.
results = run_reform(
    name="Household tax reform",
    var="HHDI_ADDFACTOR",
    shock=[250, 500, 750, 1000],
    start="2025Q1",
    end="2025Q4",
)
print(results[["period", "delta_cons_m", "delta_gdp_m"]])

# A 5 percentage point corporation tax cut (needs the investment closure)
results = run_reform(
    name="Corporation tax cut", var="TCPRO", shock=-0.05, periods=12,
    investment_closure=True,
)
```

Run it with `uv run python`. Each `run_reform` call builds and solves the model twice over 12 quarters. The three calls take about five minutes on a laptop, most of it the first template build. Every result carries its warnings and labels in `results.attrs`.

To run five example reforms and save charts to `outputs/`:

```bash
uv run python -m obr_macro.reform_analysis
```

## How it works

1. **Transpiler** (`obr_macro/transpiler.py`) turns the OBR's EViews equations into Python expressions.
2. **Solver** (`obr_macro/full_solver.py`) solves all equations each quarter by Gauss-Seidel iteration (repeated passes until values stop changing).
3. **Closure swap.** In the OBR's model GDP is an input and inventories balance the expenditure identity. Here inventories are held at the EFO path and GDP is solved from the identity, so demand shocks move GDP. By default nominal GDP is also pinned to real GDP times the deflator, using a line the OBR publishes commented out.
4. **Anchoring.** Add-factors make the baseline reproduce the EFO.
5. **Deviation mode.** A reform is scored as the shocked run minus the baseline. Both use the same add-factors, so they cancel in the difference.

Opt-in overlays add labelled judgement where the published equations are silent: `published_conventions`, `price_passthrough`, `monetary_conditioning`, `import_response`, `employment_response`, `debt_interest` and `investment_closure`. All are off by default. See [docs/options.md](docs/options.md).

## What is in the repository

| Path | What it holds |
|---|---|
| `obr_macro/` | The package: transpiler, solver, reform runner (`reform_analysis.py`), overlays, data loading |
| `obr_macro/_data/` | The OBR's model listing and variable list (15 October 2025) and EFO tables (October 2026, and November 2025 as a cross-check) |
| `obr_macro/seeds/` | ONS series for inputs the OBR does not publish, with a manifest |
| `tests/` | The test suite: fast tests run on every pull request, slow full-solve tests run on `main`, nightly and weekly |
| `scripts/` | Scripts that regenerate the files in `results/` |
| `results/` | Committed outputs that the docs and the PolicyEngine macro site quote |
| `docs/` | The documentation site's pages: methods, limits, validation, decisions |
| `dashboard/` | A Next.js dashboard for exploring scenarios, variables and equations |
| `chat/` | An optional local chat server that answers questions from precomputed model data |
| `changelog.d/` | One file per change, the change log of record |

## Documentation

The site at **https://policyengine.github.io/obr-macroeconomic-model/** is built from `docs/` and has:

- [Getting started](docs/getting-started.md), [How it works](docs/how-it-works.md), [Options and overlays](docs/options.md), [Worked examples](docs/examples.md)
- [Limits](docs/limitations.md): what not to quote, and why
- Methods: [forecasting framework](docs/forecasting_framework.md), [nominal GDP pin](docs/nominal_gdp_pin.md), [medium-term convergence](docs/medium_term_convergence.md), [transmission audit](docs/transmission_audit.md), [demand overlays](docs/demand_overlays.md), [price pass-through](docs/price_passthrough.md), [monetary conditioning](docs/monetary_conditioning.md), [debt interest](docs/debt_interest.md)
- Validation: [testing](docs/testing.md), [calibration scorecard](docs/calibration_scorecard.md), [line-by-line review of the published model](docs/published_model_review.md)
- [Data and results](docs/data.md), [modelling decisions](docs/decisions.md), [roadmap](docs/ROADMAP.md), [API reference](docs/api.md)

To preview the site locally:

```bash
uvx --with "mkdocstrings[python]==0.26.1" --with "mkdocstrings-python==1.11.1" --with "mkdocs-autorefs==1.2.0" --from "mkdocs-material==9.5.39" mkdocs serve
```

## Tests

```bash
uv run --group chat pytest -q            # fast suite, a few minutes
uv run --group chat pytest -q --runslow  # adds full-solve tests, hours
```

CI (`.github/workflows/ci.yml`) runs lint, the fast suite and a wheel check on every pull request and push to `main`; the full-solve invariants on `main`, nightly and weekly; and the extended suite on Python 3.11 to 3.13 weekly. `.github/workflows/demo.yml` (manual) regenerates the demo results as downloadable artefacts, which are then committed by hand. See [docs/testing.md](docs/testing.md).

## Contributing

Work on a branch and open a pull request. Add a `changelog.d/<slug>.<type>.md` file (type `added`, `changed`, `fixed` or `removed`) saying in a sentence or two what changed and why. Every number quoted in the docs should trace to a file in `results/` or a test.

## Licence

Code in this repository is released under the [MIT License](LICENSE). Original text and figures are released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) with attribution to PolicyEngine. Third-party data and materials keep their own terms.
