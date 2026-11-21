# Imports and employment: what the listing does, and two opt-in overlays

Two points raised in review of the OBR's October 2025 listing:

- total imports and non-oil goods imports are fixed, so a domestic expansion lowers non-oil goods imports;
- employment is an input, not derived from GDP.

Both are confirmed below in this replication. Each has an opt-in overlay in `run_reform`, off by default. Every figure is from `results/demand_overlays.json` (`scripts/demand_overlays.py`, run locally on 21 Nov 2026, October 2026 EFO, window 2025Q1–2027Q4, default nominal-GDP pin). Every quarter of every run converged.

## Imports

### What the listing does

| Series | Equation | In this replication |
|---|---|---|
| Total imports `M` | none (dictionary: exogenous) | held at the EFO path |
| Services `MS` | estimated, l.223: import-weighted demand `MSTFE` (l.219), relative price `PMSREL`, specialisation index `SPECX` | dropped: `PMSREL` needs the stockbuilding deflator `PINV`, which needs inventory stocks, and `SPECX` has no data. `MS` stays at the EFO path |
| Oil `MOIL` | l.358, `TDOIL + XOIL − NSGVA`; oil demand `TDOIL` (l.353) responds to lagged non-oil GVA | live |
| Non-oil goods `MNOG` | residual, l.217: `M − MS − MOIL` | live |

- The import-content weights of l.195–l.211 feed only the indicator `MINTY` (l.209). No equation uses them to set imports.
- So imports never leak: a pound of extra demand is a pound of extra GDP.

### Government consumption +1% of GDP, default run

`CGG` raised by 1% of baseline real GDP (£7.03bn a quarter in 2025Q1, £7.24bn in 2027Q4), for 12 quarters. Changes from baseline, £m a quarter.

| Series | q1 | q2 | q4 | q12 |
|---|--:|--:|--:|--:|
| Total imports `M` | 0 | 0 | 0 | 0 |
| Services `MS` | 0 | 0 | 0 | 0 |
| Oil `MOIL` | 0 | +251 | +202 | +190 |
| Non-oil goods `MNOG` | 0 | −251 | −202 | −190 |
| GDP per pound of shock | 1.013 | 1.017 | 1.024 | 1.039 |

- Non-oil goods imports fall, as the review said, but here the cause is oil, not services.
- In the OBR's own build l.223 is live. Applying it to this run's demand path (a partial calculation, no feedback) gives services +£242m at q1 and +£314m at q12, and so non-oil goods −£242m at q1, −£549m at q2 and −£503m at q12.

### `import_response=True`

`run_reform(..., import_response=True)` changes three equations on the shocked run only. Each is a deviation from the solved baseline, so the baseline is untouched.

| Series | Overlay | Source |
|---|---|---|
| Services `MS` | l.223 in deviation form. The equation is linear in logs, so the price, specialisation, dummy and constant terms cancel when held at baseline. That leaves the published `MSTFE` and lagged-`MS` coefficients: 0.82 on impact, long-run elasticity 1.079 | the listing's own estimated equation |
| Non-oil goods `MNOG` | `MNOG_base × MGTFE / MGTFE_base`: goods imports per unit of import-weighted demand held at baseline | weights: l.211 (0.176 consumption, 0.064 government consumption, 0.175 investment, 0.410 goods exports). **The elasticity of 1 is our assumption.** The listing has no estimated goods-import equation |
| Total `M` | `MNOG + MS + MOIL` (l.217 inverted) | identity |

- Why l.211 is the goods import content: its weights and the services weights of l.219 sum to the total import-content weights of l.195–l.201 (0.176 + 0.081 = 0.257 for consumption, 0.064 + 0.030 = 0.094 for government consumption). A test checks this.
- No other source was used. An estimated goods-import elasticity from OBR or ONS documentation would replace the assumption; none is in this repo and none was downloaded.

Same shock, with the overlay. £m a quarter.

| Series | q1 | q2 | q4 | q12 |
|---|--:|--:|--:|--:|
| Total imports `M` | +669 | +980 | +940 | +966 |
| Services `MS` | +241 | +297 | +301 | +310 |
| Oil `MOIL` | 0 | +227 | +183 | +165 |
| Non-oil goods `MNOG` | +428 | +456 | +457 | +492 |
| Imports as a share of the shock | 9.5% | 13.9% | 13.3% | 13.3% |
| GDP per pound of shock | 0.916 | 0.876 | 0.888 | 0.901 |
| Consumption | +81 | +103 | +148 | +248 |

- Without the overlay consumption rises by +90 / +117 / +169 / +285.
- For a 1p basic-rate rise (£1,616m a quarter) the overlay lowers imports by £38m at q1 and £152m at q12, and current-price GDP per pound of revenue at q12 goes from 0.37 to 0.26.

### What it is not

- Not the OBR's current-spending multiplier (0.6, fading). Leakage of 10% to 14% takes the figure to about 0.9, and nothing makes it fade.
- Import prices and exports do not respond. Relative prices are held at baseline in l.223.
- Oil imports already responded in the listing; with the overlay they now add to total imports.
- It cannot be combined with `published_conventions` or the investment closure.

## Employment

### What the listing does

| Series | Equation | In this replication |
|---|---|---|
| Total employment `ETLFS` | l.153, `1000 × HWA / AVH` | live, but hours `HWA` (l.169 is commented out) and average hours `AVH` are EFO inputs |
| Unemployment `ULFS`, rate `LFSUR` | l.163 and l.165, from population, participation and `ETLFS` | live; reproduces the EFO, and moves with nothing |
| Market sector employment `EMS` | estimated, l.145: lagged market sector GVA `MSGVA` (short-run 0.171, long-run elasticity 1 closing at 0.6% a quarter) and the real product wage | live |
| General government employment `EGG` | none | held at the EFO path |
| Private wage bill `WFP` | l.589, uses `EMS` | dropped (`ADJW` has no data), so employment does not reach household income |

- No equation links `EMS` to `ETLFS`. A shock moves `EMS` and leaves total employment, unemployment and hours exactly unchanged.

### `employment_response=True`

`run_reform(..., employment_response=True)` adds one equation on the shocked run: `HWA = HWA_base × (1 + (EMS − EMS_base) / ETLFS_base)`.

- The change in `EMS` passes one for one to `ETLFS`, with average hours held. Unemployment then follows from l.163 with participation and population held.
- The `EMS` equation is the OBR's. **The one-for-one bridge is our assumption.**
- It reaches consumption through the unemployment term of l.4 (−0.0084 per point) and earnings through l.232. It does not reach the wage bill or household income.
- No Okun coefficient (a rule of thumb linking unemployment to GDP) is used: none is in the listing, and no OBR or ONS source for one is in this repo.

### Results

Changes from baseline. Employment in thousands, unemployment rate in percentage points.

| Shock | Mode | Employment q4 | q8 | q12 | Unemployment rate q12 | GDP q12, £m |
|---|---|--:|--:|--:|--:|--:|
| 1p basic rate, £1,616m a quarter | default | 0 | 0 | 0 | 0 | −529 |
| | employment | −4.2 | −10.1 | −14.5 | +0.040 | −609 |
| | employment + imports | −3.0 | −6.9 | −9.8 | +0.027 | −410 |
| Government consumption +1% of GDP | default | 0 | 0 | 0 | 0 | +7,527 |
| | employment | −1.5 | +2.5 | +7.0 | −0.019 | +7,580 |
| | employment + imports | −16.1 | −23.0 | −23.2 | +0.064 | +6,468 |

### Read the government-consumption rows with care

- The listing's labour demand covers the market sector only.
- Government GVA rises with government consumption (l.760, `GGVA/GGVA(-1) = CGG/CGG(-1)`) from a level this repo seeds at 20% of GDP. It takes 94% to 96% of the shock, so market sector GVA moves by −£257m to +£33m on a £7bn shock.
- Government employment has no equation.
- So the overlay returns close to nothing for a spending shock: at most 7,000 jobs for 1% of GDP. With imports also responding, GDP rises by less than government GVA, market sector GVA falls and employment falls by 23,000.
- That is a property of the listing and of our GVA seed, not an estimate of the jobs effect of public spending. A run with `var="CGG"` carries `employment_response_warning` in `df.attrs`.

## Reproduce

```bash
uv run python scripts/demand_overlays.py          # about six minutes
uv run pytest --runslow tests/test_demand_overlays.py
```
