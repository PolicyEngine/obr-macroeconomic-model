---
icon: material/lightbulb-on
---

# Worked examples

One example per policy channel. Each gives the exact call, the sign convention, what the result means and the headline numbers. Every number is copied from a committed results file or doc page, named beside it. If a run is shown without numbers, no committed file holds its result.

The results files are [`results/demo_shocks.json`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/results/demo_shocks.json), [`results/site_figures.json`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/results/site_figures.json), [`results/demand_overlays.json`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/results/demand_overlays.json) and [`results/debt_interest_examples.json`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/results/debt_interest_examples.json). [Data and results](data.md) says which script writes each one. Ratios marked "demo.md" are quoted from the [demo guide](demo.md), which computes them from `results/demo_shocks.json`.

All runs use the default window, 2025Q1 to 2027Q4 (12 quarters), unless the code says otherwise. "q1 / q4 / q12" means the first, fourth and twelfth quarter of the window. GDP, consumption and investment changes are in chained-volume (real) £m per quarter. Line numbers such as l.649 refer to lines of the OBR's published model listing. The EFO is the OBR's Economic and fiscal outlook, the forecast the baseline is anchored to. An add-factor is a fixed term added to an equation to move its result onto a chosen path.

!!! note "Two sign conventions to keep apart"
    - **Output columns.** `delta_gdp_m`, `delta_cons_m` and `delta_if_m` are shocked run minus baseline. Positive means the variable rises.
    - **Shock values.** A shock is added to the variable (`var += shock`). For receipts variables (`TYEM`, `VREC`, `TXFUEL`, `NNSCTP`) positive means more tax collected. For the household costing instrument `HHDI_ADDFACTOR` positive means revenue raised, so household disposable income falls.

Before quoting any of these numbers, read [Limits](limitations.md). The results are point estimates from this emulator, not OBR forecasts.

## :material-office-building: Government consumption { #government-consumption }

```python
from obr_macro import run_reform

df = run_reform(name="Gov consumption", var="CGG", shock=1250, periods=12)
```

**Sign convention.** `shock=1250` raises real government consumption by £1,250m a quarter for 12 quarters. Positive `delta_gdp_m` means GDP rises.

**Result** (`results/demo_shocks.json`, key `cgg`; ratios from [demo.md](demo.md)):

| | q1 | q4 | q12 |
|---|--:|--:|--:|
| GDP, £m | +1,266 | +1,280 | +1,300 |
| Real GDP per real £ of spending | 1.01 | 1.02 | 1.04 |
| Consumption, £m | +16 | +30 | +50 |
| Central government net borrowing (`CGNB`), £m | +1,336 | +1,364 | +1,419 |

**What it means.** Government consumption is a term of the expenditure identity, so GDP rises one for one with the shock. The small extra comes from nominal GDP landing in company profits, a little of which reaches household income and consumption. This is accounting, not a multiplier. The OBR's published impact multiplier for current spending is 0.6, fading to zero; the model cannot produce that profile ([Limits](limitations.md)). Borrowing rises by the cash cost because the default shock also moves the nominal spending totals; receipts have no equation and do not respond.

**Variants.**

- `nominal_consistent=False` moves real spending only. GDP is close to the default (+1,267 / +1,283 / +1,309 £m), but `CGNB` does not move at all (0 in every quarter) (`results/demo_shocks.json`, key `cgg_real_only`). See [the nominal-GDP pin](nominal_gdp_pin.md).
- `published_conventions=True` imposes the OBR's published 0.6 convention as a labelled add-factor path: GDP +750 / +637 / +337 £m, ratio 0.60 / 0.51 / 0.27 (`results/demo_shocks.json`, key `cgg_conventions`; ratios from [demo.md](demo.md)). This is judgement imposed on the model, not a model result.
- `import_response=True` lets imports respond. It was measured on a larger shock, 1% of baseline real GDP each quarter (£7,032m to £7,241m, listed under `shock_m` in `results/demand_overlays.json`):

```python
import json

# Run from the repository root, where results/ lives.
path = json.load(open("results/demand_overlays.json"))["shocks"]["cgg_1pct_gdp"]["shock_m"]
default = run_reform(name="CGG 1% of GDP", var="CGG", shock=path)
leaky = run_reform(name="CGG 1% of GDP, imports", var="CGG", shock=path, import_response=True)
```

GDP per pound of shock is 1.013 / 1.024 / 1.039 at q1 / q4 / q12 by default and 0.909 / 0.907 / 0.918 with the overlay (`results/demand_overlays.json`, `cgg_1pct_gdp.default.gdp_per_pound` and `cgg_1pct_gdp.import_response.gdp_per_pound`). The goods leg of the overlay rests on an assumed unit elasticity; see [demand overlays](demand_overlays.md).

## :material-hand-coin: Welfare { #welfare }

```python
df = run_reform(name="Benefits", var="CGSB", shock=1000, periods=12)
```

**Sign convention.** `CGSB` is central government social benefits in current prices (nominal £m a quarter). Positive means more is paid out. Positive `delta_gdp_m` means GDP rises.

**Result** (one local solve, 25 Nov 2026, pinned by `tests/test_solver.py`; no committed results file holds this run):

| | q1 | q4 | q12 |
|---|--:|--:|--:|
| GDP, £m | +92 | +191 | +323 |
| Current-price GDP per £ of benefits | 0.10 | 0.21 | 0.37 |
| Household disposable income (`HHDI`), £m | +1,001 | +1,013 | +1,028 |
| Central government net borrowing (`CGNB`), £m | +1,000 | +1,000 | +1,000 |

**What it means.** Benefits raise household income by about their size, and consumption responds through the published consumption equation, as for a household tax cut. The OBR's welfare multiplier is 0.6 on impact, fading; the model gives 0.10 on impact and builds up ([Limits](limitations.md)). Borrowing rises by the shock because the default shock also moves public sector current expenditure `PSCE` (`df.attrs["nominal_consistent_legs"]` is `["PSCE"]`). Other current grants (`CGOTR`) work the same way.

**Variant.** `nominal_consistent=False` leaves `PSCE` at baseline. The listing then lowers subsidies by the shock: `CGNB` does not move, profits fall by £917m in q1, and GDP is +80 / +167 / +286 £m. The run carries `df.attrs["subsidy_residual_warning"]`. Do not use it to cost a benefit change.

## :material-crane: Government investment { #government-investment }

### Default closure: no channel

```python
df = run_reform(name="Gov investment", var="CGIPS", shock=3000,
                start="2026Q1", end="2027Q4", periods=8)
```

**Sign convention.** `CGIPS` is central government investment in current prices (nominal £m a quarter). Positive means more investment.

**Result** (`results/site_figures.json`, `cgips_size_sweep`, key `3000`; window 2026Q1 to 2027Q4):

- Total investment `IF`: exactly 0 in every quarter.
- GDP: −2 £m in the first quarter, −15 £m in the eighth.
- Measured business investment `IBUSX`: −2,807 £m on average, 0.936 of the shock with the opposite sign.

**What it means.** `IF` has no live equation in the published listing, so the chain from government investment to GDP stops before the expenditure identity. The small GDP change is noise of indeterminate sign, not a multiplier. `run_reform` sets `df.attrs["dead_channel"] = True` and issues a warning that names the two labelled routes below.

### With `investment_closure=True`

```python
df = run_reform(name="Gov investment, IF identity", var="CGIPS", shock=3000,
                periods=12, investment_closure=True)
```

**Sign convention.** As above: `CGIPS` in nominal £m a quarter, positive = more investment; positive `delta_gdp_m` means GDP rises.

**Result** (`results/demo_shocks.json`, key `cgips_investment_closure`):

| | q1 | q4 | q12 |
|---|--:|--:|--:|
| GDP, £m | +3,075 | +2,901 | +2,903 |
| Real GDP per nominal £ | 1.03 | 0.97 | 0.97 |

Ratios from [demo.md](demo.md). The closure switches on the listing's commented-out `IF` identity, so GDP moves about one for one with real government investment. There is no taper and no crowding-out; the result is labelled identity passthrough. The OBR's capital-spending multiplier is 1.0 on impact, tapering.

`published_conventions=True` (without the investment closure) instead imposes the OBR's 1.0-tapering convention as a labelled add-factor path. No committed results file holds that run.

## :material-home-account: Household tax { #household-tax }

### Externally costed path: `HHDI_ADDFACTOR`

```python
df = run_reform(name="1p basic rate", var="HHDI_ADDFACTOR", shock=1616, periods=12)
```

**Sign convention.** Values are quarterly £m of static revenue. **Positive = revenue raised = household disposable income falls.** `df.attrs["costing_sign_convention"]` repeats this. Positive `delta_gdp_m` means GDP rises, so a tax rise gives negative values.

**Result** (`results/demo_shocks.json`, key `household_costing`; £1,616m a quarter is a static costing of 1p on the basic rate):

| | q1 | q4 | q12 |
|---|--:|--:|--:|
| GDP, £m | −151 | −313 | −529 |
| Current-price GDP per £ of revenue (`gdp_per_revenue_current_price`) | 0.099 | 0.211 | 0.374 |
| Real GDP per £ of revenue (`gdp_per_revenue_real`) | 0.093 | 0.194 | 0.328 |
| Household disposable income (`HHDI`), £m | −1,637 | −1,657 | −1,681 |

**What it means.** This is the model's one channel with real behaviour: the published consumption equation responds to real household income. Compare the current-price ratio with the OBR's 0.3 impact multiplier for income tax and NICs; the real-basis ratio mixes two bases ([Limits](limitations.md)). The order of magnitude is right but the profile builds where the OBR's fades. This instrument moves household income only: receipts and borrowing do not move (`CGNB` change 0 in every quarter).

A per-quarter path is accepted too; its length overrides `periods`:

```python
df = run_reform(name="Phased reform", var="HHDI_ADDFACTOR",
                shock=[250, 500, 750, 1000], start="2025Q1", end="2025Q4")
df.attrs["delta_hhdi_m"]   # change in household disposable income, £m
```

### Through receipts: `TYEM`

```python
df = run_reform(name="1p basic rate, receipts", var="TYEM", shock=1725, periods=12)
```

**Sign convention.** `TYEM` is income tax receipts in £m a quarter. Positive = more tax collected. £1,725m is HMRC's ready-reckoner yield for 1p on the basic rate, divided by four.

**Result** (`results/demo_shocks.json`, key `income_tax`): GDP −161 / −335 / −565 £m at q1 / q4 / q12; current-price ratio 0.10 / 0.21 / 0.37 ([demo.md](demo.md)). Receipts (`PSCR`) rise by +1,725 and `CGNB` falls by −1,725 every quarter. Use `TYEM` when you also want receipts and borrowing to move; `HHDI_ADDFACTOR` moves household income only. Employee NICs (`EENIC`) work through the same channel with the same ratios.

## :material-cart-percent: VAT { #vat }

### Default

```python
df = run_reform(name="VAT +1pp", var="VREC", shock=2200, periods=12)
```

**Sign convention.** `VREC` is VAT receipts in £m a quarter; positive = more tax collected. £2,200m is HMRC's yield for 1 percentage point on the standard rate, divided by four.

**Result** (`results/demo_shocks.json`, key `vat`): GDP −27 / −52 / −82 £m at q1 / q4 / q12; current-price ratio 0.013 / 0.026 / 0.043 ([demo.md](demo.md)). `PSCR` +2,200 and `CGNB` −2,200 every quarter.

**What it means.** CPI is exogenous in the published listing, so the tax cannot reach prices. It lands on profits, and only the part of profits that households draw from their businesses reaches consumption. The OBR's VAT multiplier is 0.35, fading.

### With `price_passthrough=True`

```python
df = run_reform(name="VAT +1pp, pass-through", var="VREC", shock=2200,
                periods=12, price_passthrough=True)
```

**Sign convention.** As above: positive `VREC` = more VAT collected; positive `delta_gdp_m` means GDP rises, so the rise gives negative values.

**Result** (`results/demo_shocks.json`, key `vat_passthrough`): GDP −363 / −697 / −1,231 £m; current-price ratio 0.175 / 0.345 / 0.638 at q1 / q4 / q12 ([demo.md](demo.md)). CPI is 0.41% higher in q1 (`price_passthrough_detail.cpi_pct_delta`, first value 0.4078).

**What it means.** The overlay passes the tax into CPI through the listing's own cost-push weights, with the retail markup held at baseline. That is a labelled judgement overlay, not the shipped listing. The q4 ratio is close to the OBR's 0.35, but the response keeps building because nothing in the published equations makes consumption fade. See [price pass-through](price_passthrough.md). Fuel duty (`TXFUEL`) accepts the same option.

## :material-factory: Corporation tax { #corporation-tax }

### Rate change: `TCPRO` with the investment closure

```python
df = run_reform(name="CT +5pp", var="TCPRO", shock=0.05, periods=12,
                investment_closure=True)
```

**Sign convention.** `TCPRO` is the corporation tax rate as a fraction, so `0.05` is +5 percentage points. Positive = higher rate. A shock that would push the rate outside `[0, 1)` is refused. Positive `delta_if_m` means investment rises.

**Result** (`results/demo_shocks.json`, key `corporation_tax_rate`):

| | q1 | q4 | q8 | q12 |
|---|--:|--:|--:|--:|
| GDP, £m | 0 | −78 | −240 | −384 |
| Total investment `IF`, £m | 0 | −78 | −240 | −384 |

`df.attrs["investment_closure_plateau_fraction"]` is 0.398: after 12 quarters the response is about 40% of the way to its long-run level, which the README puts at about £0.96bn a quarter.

**What it means.** The rate works through the cost of capital into business investment, with a lag, so nothing moves in the first two quarters. The investment closure is a stop-gap: it freezes `MSGVA`, `PIF` and `PIRHH` to stop an explosive loop, and it turns the nominal-GDP pin off ([how it works](how-it-works.md)). The tax raises no receipts in this run (`PSCR` and `CGNB` change 0). The multiplier table this repo encodes has no corporation-tax row, so there is no sourced benchmark. A cut is the same call with `shock=-0.05`; no committed results file holds it.

### Receipts only: `NNSCTP`

```python
df = run_reform(name="CT receipts", var="NNSCTP", shock=900, periods=12)
```

**Sign convention.** `NNSCTP` is corporation tax receipts in £m a quarter; positive = more tax collected. £900m is HMRC's yield for 1 percentage point, divided by four.

**Result** (`results/demo_shocks.json`, key `corporation_tax_receipts`): GDP changes by exactly 0. `PSCR` +900 and `CGNB` −900 every quarter. Corporation tax receipts have no route to demand in the default closure.

## :material-bank: Bank Rate { #bank-rate }

```python
df = run_reform(name="Bank Rate +1pp, 4 quarters", var="R", shock=1.0, periods=4)
cond = run_reform(name="Bank Rate +1pp, conditioned", var="R", shock=1.0, periods=4,
                  monetary_conditioning=True)
```

**Sign convention.** `R` is Bank Rate in percentage points; `shock=1.0` is a 1 point rise, here held for four quarters. Positive `delta_gdp_m` means GDP rises, so a rise gives negative values.

**Result** (`results/demo_shocks.json`, keys `bank_rate` and `bank_rate_conditioned`):

| | q1 | q4 | q12 | Peak, % of GDP |
|---|--:|--:|--:|--:|
| Default, GDP £m | −128 | −406 | −40 | −0.057 (q4) |
| `monetary_conditioning=True`, GDP £m | −432 | −1,051 | −217 | −0.149 (q4) |

**What it means.** Bank Rate reaches consumption and household interest flows only. Corporate interest, the cost of capital, CPI and unemployment do not respond. `monetary_conditioning=True` also moves the mortgage rate at the 0.9 pass-through in the OBR's own household-interest equation; it is a labelled judgement overlay. Both peaks are below the Bank of England's −0.2% to −0.35% for the same experiment. See [monetary conditioning](monetary_conditioning.md).

**Sustained for 12 quarters** (`periods=12`), the default run gives GDP −128 / −406 / −472 / −500 £m at q1 / q4 / q8 / q12, and a 1 point cut gives +134 / +418 / +489 / +519 £m (`results/site_figures.json`, `bank_rate`). Do not mix these with the four-quarter figures above.

## :material-chart-line: Gilt yield and debt interest { #gilt-yield-and-debt-interest }

Debt interest has no equation in the listing. `debt_interest=True` adds a labelled overlay that finances extra borrowing with gilts at the 20-year gilt yield and reprices planned gilt issuance when the yield is shocked. See [debt interest](debt_interest.md).

### Borrowing: government consumption with debt interest

```python
df = run_reform(name="CGG with debt interest", var="CGG", shock=1250,
                periods=12, debt_interest=True)
df.attrs["debt_interest_detail"]["delta_debt_interest_m"]
```

**Sign convention.** Positive `delta_debt_interest_m` means the government pays more interest; it adds to borrowing.

**Result** (`results/debt_interest_examples.json`, scenario `cgg`):

- Extra debt interest: +8 / +61 / +230 £m at q1 / q4 / q12.
- Borrowing change: +1,344 / +1,425 / +1,649 £m with the overlay, against +1,336 / +1,364 / +1,419 £m without.
- GDP: identical with the overlay on and off (+1,266 / +1,280 / +1,300 £m).

The same overlay on the VAT rise above lowers interest, by −14 / −99 / −365 £m at q1 / q4 / q12, because borrowing is lower (scenario `vat`).

### Gilt yield: `RL`

```python
df = run_reform(name="Gilt yield +1pp", var="RL", shock=1.0,
                start="2026Q2", end="2028Q4", periods=11, debt_interest=True)
```

**Sign convention.** `RL` is the 20-year gilt yield in percentage points; `shock=1.0` is a 1 point rise. Positive `delta_gdp_m` means GDP rises.

The window starts in 2026Q2, the first quarter of the October 2026 EFO's first forecast fiscal year, so planned issuance comes from that EFO's table 6.12 alone. With `debt_interest=True`, a yield shock in a quarter outside the fiscal years the committed tables cover raises an error; the default start, 2025Q1, falls in 2024-25 and does.

**Result** (`results/debt_interest_examples.json`, scenario `gilt_yield`):

- Extra debt interest: +71 £m in 2026Q2, rising to +1,816 £m in 2028Q4. Over the first year it adds £1.1bn and over the second £3.8bn ([Limits](limitations.md) and [debt interest](debt_interest.md)). Almost all of it is repricing of new gilts (`rate_effect_m`), not the cost of extra debt (`stock_effect_m`).
- GDP: −479 £m in 2026Q2, −1,627 £m in 2028Q4, the same with the overlay off. The yield reaches GDP through the listing's own equation l.649, not through the overlay.

The overlay covers conventional gilts only and is off by default.
