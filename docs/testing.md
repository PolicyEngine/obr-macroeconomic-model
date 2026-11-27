---
icon: material/test-tube
---

# Testing

The tests live in [`tests/`](https://github.com/PolicyEngine/obr-macroeconomic-model/tree/main/tests). They come in two speeds: fast tests that need no model solve, and slow tests that build and solve the full 372-equation model.

## :material-play: Running the tests { #running-the-tests }

The fast suite runs in about 20 seconds on a laptop (two of its tests build the model):

```bash
uv run --group chat pytest -q
```

The `chat` dependency group is included so the chat-agent tests run; without it they are skipped.

Slow tests are marked `slow` (the marker is declared in `pyproject.toml`). [`tests/conftest.py`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/tests/conftest.py) skips them unless you pass `--runslow`:

```bash
uv run --group chat pytest -q --runslow
```

The full slow suite builds and solves the model many times. On GitHub Actions the full run took 20 to 32 minutes per Python version on 3.11 to 3.13, and the structural invariants job 12 minutes (run 45516457605, 25 Nov 2026). Before the solver read each period's row once instead of once per column, the same jobs took 1 hour 45 minutes to 2 hours 55 minutes and about 76 minutes. To run one slow file:

```bash
uv run pytest -q --runslow tests/test_sign_conventions.py
```

## :material-source-branch-check: Continuous integration { #continuous-integration }

### `ci.yml`

[`.github/workflows/ci.yml`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/.github/workflows/ci.yml) runs on every pull request, on pushes to `main`, nightly, weekly (Mondays) and on manual dispatch. In-flight runs for the same pull request are cancelled when a newer push arrives.

| Job | When | What it does |
|---|---|---|
| Lint & format | Every run | `ruff check` and `ruff format --check` on `obr_macro` and `tests`. |
| Fast tests (hermetic) | Every run | `uv sync --locked --group chat`, then `uv run --group chat pytest -q`. No network, no solve. |
| Wheel builds and ships its data assets | Every run | Builds the wheel, installs it in a clean environment outside the checkout, checks that every data file is in the installed package and that the listing parses to more than 300 equations. A hard gate. |
| Structural invariants | Not on pull requests: pushes to `main`, nightly, weekly and manual runs | `pytest --runslow` on `test_model_invariants.py`, `test_stress.py`, `test_solver.py`, `test_nominal_gdp_pin.py` and `test_tax_scenarios.py`. A hard gate. Includes the HMRC ready-reckoner check on the basic-rate costing and the calibration-scorecard regression check. |
| Committed outputs are fresh | Not on pull requests: pushes to `main`, nightly, weekly and manual runs | `pytest --runslow` on `test_forecast_docs.py`, `test_dashboard_fresh.py` and `test_demo_shocks_fresh.py`: reruns the forecast CLI, the dashboard generators and the demo battery's `run_reform` calls and compares them with the documented and committed figures. A hard gate. |
| Calibration scorecard | Not on pull requests | Runs `python -m obr_macro.calibration_score` (the free-running model against the OBR's Economic and fiscal outlook, EFO) under the default closure and under the published closure, and publishes the result as a job summary and artefact. Report only: it never fails the build. |
| Extended validation | Weekly and on manual dispatch | The full suite with `--runslow` on Python 3.11, 3.12 and 3.13. A hard gate when it runs. |

### `demo.yml`

[`.github/workflows/demo.yml`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/.github/workflows/demo.yml) runs only on manual dispatch and never gates a pull request. Its five jobs regenerate results files and upload them as workflow artefacts:

- `demo-shocks`: `scripts/demo_shocks.py`, writing `results/demo_shocks.json`;
- `readme-cli`: `python -m obr_macro.reform_analysis`, uploading its log and `outputs/`;
- `site-figures`: `scripts/site_figures.py`, writing `results/site_figures.json`;
- `convergence-decomposition`: `scripts/convergence_decomposition.py`, writing `results/convergence_decomposition.json`;
- `dashboard-data`: the three generators in `dashboard/`, writing `dashboard/public/data/*.json`.

The workflow does not commit anything. To update a results file, download the artefact and commit it.

### `notify-macromod.yml`

[`.github/workflows/notify-macromod.yml`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/.github/workflows/notify-macromod.yml) runs on every push to `main`. It sends a repository-dispatch event to the PolicyEngine Macro repository so that it can redeploy the hosted server with the new model. It runs no tests.

## :material-refresh: Regenerating results files { #regenerating-results-files }

Each file in `results/` is written by one script in [`scripts/`](https://github.com/PolicyEngine/obr-macroeconomic-model/tree/main/scripts). All are heavy, because each figure is a full solve.

| Results file | Script | Where it runs |
|---|---|---|
| `results/demo_shocks.json` | `scripts/demo_shocks.py` | `demo.yml` (about 60 solves; about four minutes on a laptop, 25 Nov 2026; 45 to 55 minutes on Actions before that) |
| `results/site_figures.json` | `scripts/site_figures.py` | `demo.yml` |
| `results/convergence_decomposition.json` | `scripts/convergence_decomposition.py` | `demo.yml` |
| `results/demand_overlays.json` | `scripts/demand_overlays.py` | Locally |
| `results/debt_interest_examples.json` | `scripts/debt_interest_examples.py` | Locally |

The dashboard data in `dashboard/public/data` (which the chat agent also reads) is written by three generators in `dashboard/`:

| File | Generator | Cost on a laptop (26 Nov 2026) |
|---|---|---|
| `model_data.json` and its copy `obr_macro/seeds/model_glossary.json` | `uv run python dashboard/gen_model_data.py` | About a second |
| `explorer_data.json` | `uv run python dashboard/gen_explorer_data.py` | About four minutes (15 solves) |
| `reform_grid.json` | `uv run python -m dashboard.gen_reform_grid` | About half a minute (10 solves) |

Run any of them with `uv run python scripts/<name>.py`. Each file records the script that wrote it; all but `convergence_decomposition.json` also record the commit, machine and Python version. `scripts/unguarded_ibusx.py` prints the unguarded business-investment path quoted on [how it works](how-it-works.md#the-investment-closure); it writes no file. [Data and results](data.md) describes what each file contains.

## :material-clipboard-check: What each test file checks { #what-each-test-file-checks }

"Speed" says whether the file is fast (no solve), slow (every test needs `--runslow`) or mixed (fast tests plus some marked slow).

### Support files

| File | What it does |
|---|---|
| `__init__.py` | Makes `tests` a package. |
| `conftest.py` | Adds the `--runslow` option and skips tests marked `slow` without it. |

### Solver and transpiler

| File | Speed | What it checks |
|---|---|---|
| `test_transpiler.py` | Fast | EViews-to-Python conversion and left-hand-side algebra. |
| `test_apply_shock.py` | Fast | `FullOBRSolver.apply_shock`: scalar and per-quarter shocks, and refusal of missing or non-finite variables, on a tiny synthetic frame. |
| `test_solver.py` | Slow | Smoke tests: data loads, the listing parses, the solver builds and solves, fiscal, corporation tax and household-costing shocks run with the documented sign. |
| `test_receipts_identities.py` | Mixed | The receipts identities close on their data path and the guard against silently dropped equations works (issue #56). |
| `test_ibusx_equation.py` | Fast | Where the restored bracket goes in the reconstructed `dlog(IBUSX)` equation. |
| `test_eu_payments.py` | Mixed | The ended EU budget payments `GNP4` and `EUVAT` stay at zero from 2021 instead of being regenerated (issue #62). |

### Model invariants and scenarios

| File | Speed | What it checks |
|---|---|---|
| `test_model_invariants.py` | Slow | Behavioural invariants: baseline and shock symmetry, left-hand-side parsing, no silent failures. |
| `test_sign_conventions.py` | Slow | Each lever moves the economy in the direction theory expects, above a noise floor; known defects (dead or inert channels) are pinned so a fix shows up. |
| `test_stress.py` | Slow | Robustness under extreme shocks, several instruments at once, long horizons and boundary cases: finite, deterministic, correctly signed, not explosive. |
| `test_tax_scenarios.py` | Slow | Income tax, NICs, VAT, corporation tax and fuel duty sized with HMRC's ready reckoner: convergence, signs, receipts and borrowing moving one for one, GDP per pound raised. |
| `test_nominal_gdp_pin.py` | Mixed | The nominal-GDP pin (issue #42): closure rules and its effect on convergence and results. |
| `test_result_labels.py` | Mixed | The `df.attrs` labels describe the instrument actually shocked (the "mechanical passthrough" label only on terms of the expenditure identity). |
| `test_calibration_constants.py` | Mixed | Published constants are seeded at their published values; `DB`, `DP`, `DV` match their derivation and `COCU` stays a declared seed. |
| `test_calibration_report.py` | Fast | The calibration scorecard leaves passthrough variables out of its accuracy count and states what it does not validate. |
| `test_scoring.py` | Fast | The error bands and the three error metrics used by the scorecards. |

### Overlays

| File | Speed | What it checks |
|---|---|---|
| `test_published_conventions.py` | Mixed | The encoded OBR multiplier table, and that `published_conventions=True` imposes it only on the identity and dead channels and labels the result. |
| `test_monetary_conditioning.py` | Mixed | `monetary_conditioning=True`, the retail-rate income audit and the cost-of-capital seed (issue #50). |
| `test_price_passthrough.py` | Mixed | `price_passthrough=True` for VAT and fuel duty (issue #60), and government investment under the investment closure. |
| `test_demand_overlays.py` | Mixed | `import_response=True` and `employment_response=True`; defaults unchanged. |
| `test_debt_interest.py` | Mixed | `debt_interest=True`: financing of extra borrowing and repricing of planned issuance; default unchanged. |
| `test_gilt_yield_channel.py` | Mixed | `RL` is the 20-year gilt yield, and a gilt-yield shock reaches GDP only through the listing's l.649. |

### Data

| File | Speed | What it checks |
|---|---|---|
| `test_efo_ground_truth.py` | Fast | The EFO loader against the publication itself: published identities hold, pinned spot values match, and the November 2025 and October 2026 vintages agree to revision size. |
| `test_ons_pull.py` | Fast | Compound ONS series built from several CDIDs, including lags, with the network replaced by synthetic series. |
| `test_ons_vintage.py` | Fast | The ONS vintage recorded per series (#49): the latest release wins when a CDID is in several datasets, each fetch records its date, and the manifest's `pulled` date is the oldest fetch, not the write date. |

### Packaging and public interface

| File | Speed | What it checks |
|---|---|---|
| `test_packaging.py` | Fast | Every shipped data file matches a package-data rule, so it survives installation; dependencies cover the imports. |
| `test_bridge_contract.py` | Fast | The public `run_reform` interface that downstream callers rely on: exports, keyword names and defaults, column names and order, period format, and costed-path handling. |

### Chat and dashboard

| File | Speed | What it checks |
|---|---|---|
| `test_chat_agent.py` | Fast | The chat agent's tool loop, with a mock HTTP transport (no API key, no network). Skipped without the `chat` dependency group. |
| `test_dashboard_data.py` | Fast | The committed dashboard data is finite, internally consistent and sensible in sign and size. |
| `test_dashboard_fresh.py` | Mixed | The committed dashboard data matches the model in the tree. Fast: the glossary is rebuilt and compared byte for byte, and the explorer and the reform grid record the fingerprint of the current input data and the generators' current labels. Slow: every scenario and the grid are solved again and compared. |

### Documented and committed outputs

| File | Speed | What it checks |
|---|---|---|
| `test_forecast_docs.py` | Slow | The table, counts and repeated figures in [forecasting framework](forecasting_framework.md), and the fit summary in the chat agent, against the output of `python -m obr_macro.forecast` under both closures. |
| `test_demo_shocks_fresh.py` | Slow | `results/demo_shocks.json` against `run_reform` as it is now: the four stored series and every label of all 15 shocks. |
