---
icon: material/database
---

# Data and results

This page lists the data the package ships, the versions it is pinned to, the code that loads it, and the committed results files with the script that makes each one.

## :material-pin: Pins { #pins }

| What | Version | Where |
|---|---|---|
| Model | The OBR's EViews model listing and variable list, 15 October 2025. Still the latest on obr.uk on 16 Nov 2026. | `obr_macro/_data/` |
| Baseline | The OBR's October 2026 Economic and fiscal outlook (EFO) detailed forecast tables, published 28 Oct 2026. | `obr_macro/_data/` |
| Unpublished inputs | 355 ONS series pulled on 11 Jul 2026, 8 recovered on 22 Sep 2026 (the manifest records the series count and both dates). | `obr_macro/seeds/` |
| Software | Python 3.11 or later; dependencies locked in `uv.lock`. | repository root |

## :material-package-variant: Data shipped in the package { #data-shipped-in-the-package }

### `obr_macro/_data/`

These files ship inside the package (the `package-data` rules in `pyproject.toml`), so an installed copy needs no download.

| File | What it is |
|---|---|
| `obr_model_code_october_2025.txt` | The OBR's model equations in EViews code, 15 October 2025 version. |
| `obr_model_variables_october_2025.xlsx` | The OBR's variable list for that model: names, definitions, units. |
| `obr_efo_october_2026_economy.xlsx`, `_receipts.xlsx`, `_expenditure.xlsx`, `_aggregates.xlsx` | October 2026 EFO detailed forecast tables. These are the baseline. |
| `obr_efo_november_2025_economy.xlsx`, `_receipts.xlsx`, `_expenditure.xlsx`, `_aggregates.xlsx` | November 2025 EFO tables, kept as a cross-vintage check (`tests/test_efo_ground_truth.py`). The debt-interest overlay's planned gilt issuance for 2025-26 is taken from them, and `tests/test_debt_interest.py` re-reads them to check it. |

### `obr_macro/seeds/`

The OBR model needs many inputs that the OBR does not publish. Where an ONS series exists, the repo pulled it once and committed the result.

| File | What it is |
|---|---|
| `ons_exogenous_snapshot.csv` | Quarterly values of the ONS series used as model inputs, one column per model variable. |
| `snapshot_manifest.json` | For each series: the ONS code (CDID), dataset, title, source frequency, how it was converted to quarterly, and whether it is a flow or a stock. Also the series count and the pull and recovery dates. |
| `model_glossary.json` | The OBR variable glossary by model group, with each variable's description and ONS code where known. `ons_pull.py` uses it to find what to fetch. |

Inputs with no ONS series and no published value are seeded in `full_solver.py`; [how it works](how-it-works.md#constants-this-repo-supplies) lists the ones that matter.

## :material-code-braces: Code that loads and refreshes the data { #code-that-loads-and-refreshes-the-data }

### `obr_macro/data.py`

- `load_obr_data()` reads the EFO workbooks into one quarterly databank in model units (£m for money, per cent for rates, index for prices). Before reading a table it checks the table title and key column headers, so a re-laid-out workbook fails loudly instead of loading the wrong column.
- It then merges the ONS snapshot. Beyond each series' last observation the value is held at its trailing four-quarter mean (not the last value, which would freeze one season of a seasonal series). Internal gaps are filled forward; a late-starting series is back-filled by at most four quarters.
- It derives variables the tables do not give directly (for example deflators such as `PIF = 100 × IFPS / IF`), and puts the forecast 16+ population on the path the EFO implies, `POP16 = 100 × (ULFSU + ETLFS) / PART16`.
- `ensure_model_code()` and `ensure_downloaded()` download the model and EFO files from obr.uk only if they are missing, and reject an HTML or truncated download.
- `DATA_DIR` is a `data/` folder at the repository root if one exists (gitignored, a legacy location), otherwise `obr_macro/_data/`.

### `obr_macro/ons_fetch.py`

Fetches one ONS time series by its CDID. It finds the series through the ONS search API, downloads it from the ONS website's JSON endpoint, and converts monthly or annual data to quarterly: cash flows are summed (an annual flow is divided by four), while stocks, indices and rates are averaged (an annual value is held flat across the quarters).

### `obr_macro/ons_pull.py`

Rebuilds the snapshot. It finds every input variable the model needs that has a known CDID, fetches single series directly and builds compound ones from the glossary formula over their component series. Each raw fetch is cached (in `data/ons_cache/` in a checkout, otherwise `~/.cache/obr_macro/ons_cache/`) so a pull can resume. It writes `ons_exogenous_snapshot.csv` and `snapshot_manifest.json`. Since #49 a new pull records, for each series, the ONS release date and the date it was fetched; when a CDID sits in several ONS datasets it takes the latest release, then the longest history. The manifest's `pulled` date is the oldest fetch, `written` is when the file was written, and `fetched_unknown` counts cache entries from before fetch dates were recorded. Cache entries never expire, so delete the cache folder to force a fresh pull. The committed manifest predates this and has no per-series dates. Run it with `uv run python -m obr_macro.ons_pull`. It needs network access, and a new pull changes model results, so it is not run routinely.

## :material-file-chart: Results files { #results-files }

The committed files in [`results/`](https://github.com/PolicyEngine/obr-macroeconomic-model/tree/main/results) are the source of record for the numbers in these docs. Each records the script that produced it; all but `convergence_decomposition.json` also record the commit, machine and Python version. [Testing](testing.md#regenerating-results-files) explains how to regenerate them.

| File | Made by | Contents | Used by |
|---|---|---|---|
| [`demo_shocks.json`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/results/demo_shocks.json) | [`scripts/demo_shocks.py`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/scripts/demo_shocks.py), on Actions (`demo.yml`) | The standard shock battery: government consumption, income tax, NICs, VAT, fuel duty, corporation tax, Bank Rate and government investment, with and without overlays. `run_reform` output and attrs, plus receipts, borrowing and household income from a rebuilt pair. | [Demo guide](demo.md), [worked examples](examples.md) |
| [`site_figures.json`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/results/site_figures.json) | [`scripts/site_figures.py`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/scripts/site_figures.py), on Actions | Figures quoted on the PolicyEngine macro site: anchored fit to 2031Q1, sustained Bank Rate rise and cut, corporation tax +5pp, government-investment size sweep. | [Limits](limitations.md), [worked examples](examples.md) |
| [`convergence_decomposition.json`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/results/convergence_decomposition.json) | [`scripts/convergence_decomposition.py`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/scripts/convergence_decomposition.py), on Actions | 24-quarter runs separating the add-factors, the imposed fade and the equations' own dynamics. | [Medium-term convergence](medium_term_convergence.md) |
| [`demand_overlays.json`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/results/demand_overlays.json) | [`scripts/demand_overlays.py`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/scripts/demand_overlays.py), locally | Government consumption +1% of GDP and the 1p household tax, each run with no overlay, imports, employment and both. | [Demand overlays](demand_overlays.md) |
| [`debt_interest_examples.json`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/results/debt_interest_examples.json) | [`scripts/debt_interest_examples.py`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/scripts/debt_interest_examples.py), locally | Government consumption, VAT and a gilt-yield rise, each with the debt-interest overlay off and on. | [Debt interest](debt_interest.md) |

[`scripts/unguarded_ibusx.py`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/scripts/unguarded_ibusx.py) prints the unguarded business-investment path quoted on [how it works](how-it-works.md#the-investment-closure); it writes no file.

The dashboard's own data files in `dashboard/public/data/` come from separate generators and solve a slightly different experiment; see [getting started](getting-started.md#optional-the-dashboard) and [testing](testing.md#regenerating-results-files).
