# Imports and employment: what the listing does, and two opt-in overlays

Two points raised in review of the OBR's October 2025 listing:

- total imports and non-oil goods imports are fixed, so a domestic expansion lowers non-oil goods imports;
- employment is an input, not derived from GDP.

Both are confirmed below in this replication. Each has an opt-in overlay in `run_reform`, off by default. Every figure is from `results/demand_overlays.json` (`scripts/demand_overlays.py`, run locally on 22 Nov 2026 at 4c572fc, October 2026 EFO, window 2025Q1–2027Q4, default nominal-GDP pin). Every quarter of every run converged.

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
| Non-oil goods `MNOG` | `(MNOG_base + MOIL_base) × MGTFE / MGTFE_base − MOIL`: all goods imports, oil included, per unit of import-weighted demand held at baseline; non-oil goods are that total less the oil imports the listing computes | weights: l.211 (0.176 consumption, 0.064 government consumption, 0.175 investment, 0.410 goods exports). **The elasticity of 1 is our assumption.** The listing has no estimated goods-import equation |
| Total `M` | `MNOG + MS + MOIL` (l.217 inverted) | identity |

- Why l.211 is the goods import content: its weights and the services weights of l.219 sum to the total import-content weights of l.195–l.201 (0.176 + 0.081 = 0.257 for consumption, 0.064 + 0.030 = 0.094 for government consumption). A test checks this.
- Why the goods total includes oil: the total weights are scaled against all imports, oil included (`MINTY`, l.209), and the variable list calls `MGTFE` "final demand weighted by import intensity (goods)". In the baseline, goods imports with oil are 1.04 to 1.06 times `MGTFE`; without oil, 0.92 to 0.97.
- Oil is counted once. Until 22 Nov 2026 the overlay scaled non-oil goods alone and added the listing's oil response on top. Oil demand has an elasticity of 1.9 to non-oil output (l.353), so total goods imports ran £110m to £190m a quarter above the unit-elastic path from q2 on. Now the goods total is unit-elastic and the listing's oil equation only sets the split between oil and non-oil.
- No other source was used. An estimated goods-import elasticity from OBR or ONS documentation would replace the assumption; none is in this repo and none was downloaded.

Same shock, with the overlay. £m a quarter.

| Series | q1 | q2 | q4 | q12 |
|---|--:|--:|--:|--:|
| Total imports `M` | +723 | +794 | +809 | +850 |
| Services `MS` | +241 | +297 | +301 | +310 |
| Oil `MOIL` | 0 | +225 | +185 | +168 |
| Non-oil goods `MNOG` | +482 | +272 | +324 | +372 |
| Goods including oil | +482 | +497 | +508 | +539 |
| Imports as a share of the shock | 10.3% | 11.3% | 11.5% | 11.7% |
| GDP per pound of shock | 0.909 | 0.902 | 0.907 | 0.918 |
| Consumption | +81 | +105 | +151 | +253 |

- Without the overlay consumption rises by +90 / +117 / +169 / +285.
- For a 1p basic-rate rise (£1,616m a quarter) the overlay lowers imports by £41m at q1 and £151m at q12, and current-price GDP per pound of revenue at q12 goes from 0.37 to 0.26.

### What it is not

- Not the OBR's current-spending multiplier (0.6, fading). Leakage of 9% to 12% takes the figure to 0.90 to 0.93, and nothing makes it fade.
- Import prices and exports do not respond. Relative prices are held at baseline in l.223.
- Non-oil goods imports jump at q1 and fall back at q2 (+482, then +272). Oil imports respond with a one-quarter lag (l.353), so in q1 the whole goods response lands on non-oil goods. The goods total is smooth.
- The services leg and the inverted identity rest on the listing alone. The goods leg rests on the unit-elasticity assumption and carries about two-thirds of the response (£482m to £539m of £723m to £850m).
- Sensitivity, goods elasticity 0 (only the listing's own equations respond; not an option of `run_reform`): imports rise by £241m / £302m / £312m at q1 / q4 / q12 (2% to 4% of the shock) and GDP per pound is 0.978 / 0.980 / 0.995. So the assumption accounts for about 0.07 of the fall in GDP per pound, and the listing's services equation for about 0.04.
- Measured under the default nominal-GDP pin only; `nominal_gdp_pin=False` is refused. The nominal side (investment deflator, borrowing) was not checked with the overlay on.
- It cannot be combined with `published_conventions`, the investment closure, `price_passthrough` or `monetary_conditioning` (none was measured with it).

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
| | employment + imports | −3.0 | −6.9 | −9.8 | +0.027 | −411 |
| Government consumption +1% of GDP | default | 0 | 0 | 0 | 0 | +7,527 |
| | employment | −1.5 | +2.5 | +7.0 | −0.019 | +7,580 |
| | employment + imports | −14.4 | −19.7 | −19.4 | +0.054 | +6,601 |

### Read the government-consumption rows with care

- The listing's labour demand covers the market sector only.
- Government GVA rises with government consumption (l.760, `GGVA/GGVA(-1) = CGG/CGG(-1)`) from a level this repo seeds at 20% of GDP. It takes 94% to 96% of the shock, so market sector GVA moves by −£257m to +£33m on a £7bn shock.
- Government employment has no equation.
- So the overlay returns close to nothing for a spending shock, and the sign is wrong for part of the window: employment **falls** by 0.8 to 1.9 thousand from q2 to q5 while spending rises by 1% of GDP, then rises to +7.0 thousand by q12.
- Neither move is an output effect. The market sector GVA deflator `PMSGVA` jumps by about 1.3% with the shock, the real product wage `PSAVEI/PMSGVA` falls by 0.95% on impact and 0.2% by q12, and the wage term of l.145 lifts `EMS`.
- With imports also responding, GDP rises by less than government GVA, market sector GVA falls and employment falls in every quarter from q2, by up to 19.7 thousand. A spending increase that lowers employment is an artefact of the missing government employment link, not a finding.
- That is a property of the listing and of our GVA seed, not an estimate of the jobs effect of public spending. A run with `var="CGG"` carries `employment_response_warning` in `df.attrs`, which says this in plain words.

## Reproduce

```bash
uv run python scripts/demand_overlays.py          # about seven minutes
uv run pytest --runslow tests/test_demand_overlays.py
```
