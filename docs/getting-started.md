# Getting started

This page takes you from a fresh checkout to a first reform result, and explains what comes back.

## Install

You need Python 3.11 or later and [uv](https://docs.astral.sh/uv/). From the repository root:

```bash
uv sync
```

This installs the package and its locked dependencies (`uv.lock`). The OBR model listing, the variable list, the EFO workbooks and the ONS snapshot all ship inside the package, so nothing is downloaded at run time. [Data and results](data.md) describes those files.

## Your first reform

Start Python with `uv run python` and run:

```python
from obr_macro import run_reform

df = run_reform(name="demo", var="CGG", shock=1250, periods=12)
df[["period", "delta_gdp_m", "pct_gdp"]]
df.attrs["solver_converged"]   # True
```

This raises real government consumption (`CGG`) by £1,250m a quarter for 12 quarters, from 2025Q1, and reports how GDP differs from the baseline in each quarter of the default window, 2025Q1 to 2027Q4.

`run_reform` builds the model, solves a baseline and a shocked copy, and returns the difference. The baseline is anchored to the OBR's October 2026 Economic and fiscal outlook (EFO), the OBR's twice-yearly forecast. [How it works](how-it-works.md) explains the steps.

### How long it takes

Each `run_reform` call builds and solves the model twice over 12 quarters. The first call also builds the model template, which is most of the cost; later calls with the same structure reuse it. The README's three Quick Start calls took about five minutes on a laptop (Apple silicon, measured 15 Nov 2026). Run one call before you need results in a hurry.

## Reading the output

`run_reform` returns a pandas DataFrame with one row per quarter from `start` to `end`. The columns are fixed (a test, `tests/test_bridge_contract.py`, pins their names and order):

| Column | Meaning |
|---|---|
| `period` | Quarter, as a string such as `"2025Q1"` |
| `reform` | The `name` you passed |
| `delta_gdp_m` | Change in real GDP (`GDPM`), chained-volume £m in that quarter |
| `delta_gdp_bn` | The same in £bn (`delta_gdp_m / 1000`) |
| `pct_gdp` | The change as a percentage of baseline GDP in that quarter |
| `delta_cons_m` | Change in real household consumption (`CONS`), £m |
| `delta_if_m` | Change in real total investment (`IF`), £m |

Every delta is shocked run minus baseline in the same quarter, so positive means the variable is higher than it would otherwise be. Values are per quarter, not cumulative.

### Reading `df.attrs`

`df.attrs` is a dictionary attached to the DataFrame. It records how the result was produced and carries any warning that applies. Read it before quoting a number.

Always set:

| Key | Meaning |
|---|---|
| `solver_converged` | `True` if every quarter of both solves reached the tolerance |
| `solver_nonconverged_periods`, `solver_exit_status`, `solver_eq_failures` | Per-quarter detail on the two solves |
| `shock_quarters`, `shock_quarters_beyond_horizon` | How many quarters the shock lasts, and how many fall after `end` |
| `nominal_gdp_pin`, `nominal_consistent` | Which closure options were used ([options](options.md)) |
| `published_conventions`, `monetary_conditioning`, `price_passthrough`, `import_response`, `employment_response`, `debt_interest` | Whether each judgement overlay was on |

Set when they apply:

| Key | When |
|---|---|
| `solver_warning`, `horizon_warning` | Some quarters did not converge, or the shock runs past `end` |
| `mechanical_passthrough`, `multiplier_warning` | The shocked variable enters the GDP identity directly, so the GDP change is accounting, not a multiplier |
| `dead_channel`, `dead_channel_warning` | The instrument has no route to GDP (government investment under the default closure) |
| `transmission_note`, `obr_published_impact_multiplier` | How the instrument reaches GDP, and the OBR's published multipliers for comparison |
| `costing_sign_convention`, `delta_hhdi_m`, `delta_rhhdi_m`, `delta_gdpmps_m`, `gdp_deflator`, `gdp_per_revenue_current_price`, `gdp_per_revenue_real`, `gdp_per_revenue_basis_note` | `var="HHDI_ADDFACTOR"`: the sign convention, the household income change and GDP per pound of revenue on both bases |
| `investment_closure_plateau_fraction` and other `investment_closure_...` keys | `investment_closure=True`: how far the response has got towards its long-run level |
| `cost_of_capital_channel`, `inflation_unemployment_note` | `var="R"`: what Bank Rate does not reach |
| `convention`, `published_conventions_note` | `published_conventions=True` |
| `..._note`, `..._detail` for each overlay | That overlay was on |

A household costing, for example, reports the change in household income and both versions of the GDP-per-pound ratio:

```python
df = run_reform(
    name="Household tax reform",
    var="HHDI_ADDFACTOR",
    shock=[250, 500, 750, 1000],   # £m a quarter; positive = revenue raised
    start="2025Q1",
    end="2025Q4",
)
df[["period", "delta_cons_m", "delta_gdp_m"]]
df.attrs["delta_hhdi_m"]
df.attrs["gdp_per_revenue_current_price"]
```

More calls, with sign conventions and published results, are on the [worked examples](examples.md) page. Every option is on the [options](options.md) page.

## Run the five standard reforms with charts

```bash
uv run python -m obr_macro.reform_analysis
```

This runs `run_five_reforms()`, which calls `run_reform` five times over the default window, each for 12 quarters:

| Reform | Call |
|---|---|
| £5bn a year government spending | `CGG`, +1,250 a quarter |
| 5pp corporation tax cut | `TCPRO`, −0.05, `investment_closure=True` |
| 5pp corporation tax rise | `TCPRO`, +0.05, `investment_closure=True` |
| £10bn a year government investment | `CGIPS`, +3,000 a quarter, default closure. This is the dead channel: `IF` does not move. It is kept so the defect stays visible. |
| £10bn a year spending cut | `CGG`, −2,500 a quarter |

It writes `reform_results.csv` and four charts to `outputs/` at the repository root (gitignored): `reform_gdp_impact.png`, `reform_gdp_pct.png`, `reform_comparison.png` and `reform_spending_vs_tax.png`. It then prints the final-quarter GDP change for each reform. The government-investment run prints the dead-channel warning. The `readme-cli` job in `.github/workflows/demo.yml` runs this command on GitHub Actions and uploads the log and `outputs/`.

## Optional: the chat server

`chat/` holds a small local web app in which a Claude agent answers questions about the emulator. The agent's tools read the pre-computed dashboard data in `dashboard/public/data/*.json`; they do not run the solver, so answers are quick. It needs an Anthropic API key in a `.env` file at the repository root and the optional dependencies:

```bash
uv sync --locked --group chat
uv run --group chat uvicorn chat.server:app --reload --port 8000
```

Then open `http://localhost:8000`. The server listens on `127.0.0.1` only. Setup details and limits are in [`chat/README.md`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/chat/README.md).

## Optional: the dashboard

`dashboard/` is a Next.js web app with five tabs: About, How it works, Explore scenarios, Variables (a searchable glossary) and Equations (the published EViews code beside the transpiled Python). To run it locally:

```bash
cd dashboard
npm install
npm run dev      # http://localhost:3000
```

It reads three JSON files in `dashboard/public/data/`, generated by `dashboard/gen_model_data.py`, `gen_explorer_data.py` and `gen_reform_grid.py`. See [`dashboard/README.md`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/dashboard/README.md).

!!! warning "Dashboard and chat numbers are an older vintage"
    The committed scenario files were generated on 6 Nov 2026 against the March 2026 EFO and have not been regenerated since the October 2026 re-anchor ([`dashboard/README.md`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/dashboard/README.md)). The chat agent reads the same files. Their numbers therefore differ from `results/` and from these docs. `results/` is the source of record.
