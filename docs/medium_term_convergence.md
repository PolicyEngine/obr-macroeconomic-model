# Medium-term convergence: where it comes from

Raised in review (November 2026): the OBR explains the fade of its fiscal multipliers in words, not with an equation. This note measures, in our replication, which mechanism brings a shock response back to zero and which do not.

Where the figures come from:

- **Runs.** `results/convergence_decomposition.json`, written by `scripts/convergence_decomposition.py` at model commit `ab29ffb`, run locally on 21 Nov 2026. A GitHub Actions re-run gave the same values (see "Reproduce").
- **Window.** 24 quarters, 2025Q1 to 2030Q4, on the OBR's October 2026 Economic and fiscal outlook (EFO).
- **Closure.** The closure is the choice of which variable an identity solves for. The OBR's listing takes GDP as an input and solves the expenditure identity for inventories. Our runs solve it for GDP. They also use the default nominal-GDP pin: current-price GDP is the GDP deflator times real GDP (the listing's commented-out l.690), with the deflator held on the EFO path (`docs/nominal_gdp_pin.md`).
- **Solver.** Every baseline and shocked solve reached tolerance in 24 of 24 quarters.
- **Other figures.** Baseline-fit figures are quoted from the README, and equation coefficients from the OBR's published listing (`obr_macro/_data/obr_model_code_october_2025.txt`; `l.N` is a line number in it).
- **Scope.** Two shocks are measured: sustained government consumption and a sustained household tax rise. The statements below are about those two.

## The answer in four lines

- **The fade does all of it.** A sustained spending shock returns to zero only when the OBR's published convention is imposed (`published_conventions=True`). That is a judgement applied on top of the equations, not a result of them.
- **The equations do not converge to zero.** Without the fade the GDP effect of sustained spending rises from 1.01 per pound in quarter 1 to 1.05 in quarter 24 and flattens: it is still rising at quarter 24, by 0.0001 a quarter.
- **The add-factors are not a convergence mechanism for a shock.** They hold the baseline level on the EFO. Switching them off changes the spending response by less than 0.01 per pound and the household tax response by up to 0.06; neither heads to zero.
- **The one live behavioural channel converges, but to a plateau.** Consumption closes the gap to its long-run level; measured after a shock is withdrawn, the remaining effect shrinks by 9% to 10% a quarter. After a temporary shock that takes the effect back towards zero; after a permanent one it takes it to a new level.

## Three things called convergence

| Meaning | What it is | Where it comes from here |
|---|---|---|
| Solver convergence | The Gauss-Seidel iteration reaching tolerance within a quarter | The solver. Not the subject of this note |
| The baseline staying on the EFO | The level of GDP, consumption and so on tracking the OBR's forecast | The frozen add-factors (below) |
| A shock response returning to zero | The multiplier fading in the medium term | Only the imposed fade |

Terms used below:

- **Add-factor.** A residual added to an equation so that it reproduces a published value. Ours are computed as EFO minus model, then held fixed ("frozen") in both the baseline run and the shocked run.
- **Fade (taper).** The assumption that a fiscal multiplier shrinks to zero over a fixed number of years.
- **Multiplier.** GDP change per pound of the fiscal change, quoted as a positive number: GDP gained per pound spent, GDP lost per pound of tax raised.

## The OBR's convention and what we do

| | The OBR's convention | This repository |
|---|---|---|
| Source | Economic and fiscal outlook, July 2015, Box 3.2 "Fiscal multipliers"; restated in "Dynamic scoring of policy measures in OBR forecasts" (November 2023) | `obr_macro/published_conventions.py`, which cites both |
| Impact multipliers | 0.6 current spending and welfare, 1.0 capital spending, 0.35 VAT, 0.3 income tax and NICs (Box 3.2) | The same table, encoded as data. Open: the November 2023 article gives 0.45 for public services and 0.33 for tax (`docs/published_model_review.md`, G11); we use the 2015 values |
| Fade | Multipliers taper to zero over five years | `TAPER_QUARTERS = 20` |
| Stated reason | Offsetting changes in monetary policy, the exchange rate and real wages | In our runs none of the three responds to a fiscal shock: Bank Rate and the exchange rate are inputs, and the wage equations (l.232, l.589) do not evaluate. So the fade is imposed, not derived (`docs/published_model_review.md`, G2 and G9) |
| Shape between impact and zero | Not published as a formula | **Ours:** linear by quarter, 0.03 a quarter for current spending |
| Start of the fade | From announcement (since November 2015) | **Ours:** from the first shocked quarter; there is no announcement date |
| Year-one average | 0.6 is the published impact figure, which `published_conventions.py` reads as the first-year multiplier | **Ours:** 0.555, which is 0.045 (7.5%) below 0.6. It is a result of our quarterly shape: the fade starts in quarter 1 (0.60, 0.57, 0.54, 0.51). Holding 0.6 through year one would match the published figure and would change `published_conventions` output, so it is a proposal, not made here |
| Where it applies | Applied by the OBR as an adjustment to its forecast | Opt-in, off by default, and only for `CGG` and the government-investment levers. Tax levers keep the model's own response |

The convention uses the OBR's two published values: an impact multiplier of 0.6 and zero at five years. Putting 0.6 in the first quarter, the quarterly path, the start date and the year-one average that follows from them are choices made here. `df.attrs["published_conventions_note"]` states the linear shape and the start on every run that uses them; it does not quote the year-one average.

## Decomposition: a sustained spending shock

Government consumption (`CGG`) up £1,250m a quarter, held for all 24 quarters. Figures are real GDP gained per real pound of spending, averaged over each year.

| Year | Default: add-factors frozen, no fade | Add-factors off (free-running pair) | Fade imposed (`published_conventions=True`) |
|---|--:|--:|--:|
| 1 | 1.018 | 1.020 | 0.555 |
| 2 | 1.031 | 1.034 | 0.435 |
| 3 | 1.038 | 1.042 | 0.315 |
| 4 | 1.042 | 1.047 | 0.195 |
| 5 | 1.045 | 1.051 | 0.075 |
| 6 | 1.046 | 1.053 | 0.000 |

The same three runs in £m of GDP a quarter:

| Quarter | Default | Add-factors off | Fade imposed |
|---|--:|--:|--:|
| q1 | +1,266 | +1,267 | +750 |
| q4 | +1,280 | +1,283 | +637 |
| q12 | +1,300 | +1,305 | +337 |
| q20 | +1,307 | +1,314 | +37 |
| q24 | +1,307 | +1,317 | 0 |

What each column shows:

- **Default.** GDP rises by the shock plus a small second round. It does not fall back. The yearly increments shrink (0.012, 0.007, 0.004, 0.003, 0.001), so the path is flattening near 1.05. It is 1.046 at quarter 24 and still rising by 0.0001 a quarter.
- **Add-factors off.** The largest gap from the default in any quarter is 0.007 per pound (1.053 against 1.046 at quarter 24, where this run is still rising by 0.0004 a quarter). The add-factors move the level at which the equations are evaluated: baseline GDP in this run is 1.3% below the anchored baseline in quarter 1 and 11.7% below in quarter 24. That changes a nonlinear response slightly. It does not pull the response towards zero.
- **Fade imposed.** 0.60 in quarter 1, down 0.03 a quarter, zero from quarter 21. This column is `0.6 × (1 − (q − 1)/20) × shock` for quarter `q` by construction. It carries no information about the model.

## What each mechanism contributes

### Frozen add-factors

- They are computed once as EFO minus model, then applied identically to the baseline and the shocked run.
- **They make the baseline level track the EFO.** Anchored GDP has a mean absolute percentage error (MAPE) of 0.24% against the October 2026 EFO over 2025Q1 to 2027Q4, by construction (README). With them off, the README's scorecard run has a GDP MAPE of 4.24% against the EFO. That gap measures this emulator's closure and its seeded inputs. It is not an OBR forecast error. The scorecard is a separate run from this script's add-factors-off pair, whose baseline GDP is on average 4.8% below the anchored baseline over the same twelve quarters.
- **They nearly cancel in the spending response.** In the table above, removing them moves the multiplier by at most 0.007.
- **They do not fully cancel in the household tax response.** The ratio at quarter 24 is 0.46 anchored against 0.40 free-running (below), a gap of 0.06 or about 13%. A likely reason, not tested here, is that the consumption equation is in logs, so its response depends on the level of income and consumption it is measured around.
- **In neither case does the response head back to zero.**

### The fade

- The only mechanism here that returns a sustained shock's effect to zero.
- It is an add-factor on the GDP identity applied to the shocked run only, sized so that GDP lands on the convention's path.
- It overrides the model's own response, 1.01 to 1.05, with 0.6 falling to zero. The difference between the first and third columns of the table is the size of that judgement: 0.46 per pound in year 1, 1.05 by year 6.
- Consumption in the faded run is a by-product of the override (+9m in quarter 1, −6m by quarter 24) and should not be read as a result.

### Equation dynamics

- **Second round.** The GDP effect beyond the shock itself equals the consumption response to the pound: +16m in quarter 1, +50m in quarter 12, +57m in quarter 24 on a £1,250m shock. Extra nominal GDP lands in profits, a small part reaches household income, and consumption follows.
- **The only adjustment process.** The consumption equation (l.4) is an error-correction equation: consumption moves each quarter towards a long-run level set by real income, housing wealth and financial wealth. The coefficient on the gap is 0.125 and the long-run income elasticity is 0.44.
- **Measured speed.** After a shock is withdrawn the remaining GDP effect decays by 9% to 10% a quarter (each quarter is 0.91 of the one before, falling to 0.90), a half-life of about seven quarters. That is slower than the 0.125 coefficient alone would give; the difference is not decomposed here.
- **It converges to the long-run level, not to baseline.** A permanent change in income gives a permanent change in consumption.
- **What is absent.**
  - No equation responds to the output gap (the gap between actual and potential output).
  - Bank Rate is an input with no policy rule.
  - Consumer prices and the GDP deflator are inputs.
  - Total exports and total imports are inputs. The listing has an equation for imported services (l.223), but it does not evaluate in our runs and total imports do not follow it.
  - So nothing in our runs offsets a sustained demand shock.

## A temporary shock

The same £1,250m a quarter, for four quarters only, default run.

| Quarter | GDP, £m | Share of the shock |
|---|--:|--:|
| q4 (last shocked quarter) | +1,280 | 102% |
| q5 | +19 | 1.5% |
| q8 | +14 | 1.1% |
| q12 | +10 | 0.8% |
| q24 | +3 | 0.2% |

- GDP drops back in the quarter the spending stops, because the direct effect is an accounting identity.
- The residue is the consumption second round unwinding at the error-correction speed.
- This return to baseline is the withdrawal of the shock, not a fading multiplier.

## The household tax channel

A household tax rise of £1,616m a quarter (the README's 1p basic-rate costing), sustained. Figures are current-price GDP lost per pound of revenue, the basis of the OBR's 0.3.

| Year | Default | Add-factors off | OBR convention, linear fade from 0.3 (for reference; not applied to tax levers) |
|---|--:|--:|--:|
| 1 | 0.157 | 0.155 | 0.278 |
| 2 | 0.279 | 0.264 | 0.218 |
| 3 | 0.353 | 0.325 | 0.158 |
| 4 | 0.401 | 0.362 | 0.098 |
| 5 | 0.434 | 0.384 | 0.038 |
| 6 | 0.456 | 0.397 | 0.000 |

- The model's ratio rises where the OBR's falls. It is 0.10 in quarter 1, 0.37 in quarter 12 and 0.46 in quarter 24.
- It is flattening: the quarterly increment falls from 0.042 to 0.004. It has not stopped rising within six years.
- The reference column is arithmetic on the published end points with our linear shape, `0.3 × (1 − (q − 1)/20)` for quarter `q`, averaged by year. It is not a model run.

## What it would take for the model to converge by itself

Not implemented. Each would be new behaviour and would need its own opt-in flag and evidence.

- A monetary policy rule with a price response, so that Bank Rate leans against a demand shock.
- Live trade equations, so that higher demand leaks into imports and the exchange rate matters for volumes.
- A link from the output gap to wages and prices.
- A government budget constraint or fiscal rule that withdraws the stimulus.

Until one of these exists, the accurate description of these runs is: the equations give an effect that does not fade within six years, and the return to zero is the OBR's judgement re-applied.

## Reproduce

```bash
uv run python scripts/convergence_decomposition.py              # all six runs
uv run python scripts/convergence_decomposition.py --leg cgg_fade
```

- Each run takes about two to four minutes on a laptop (measured 21 Nov 2026).
- `.github/workflows/demo.yml` has a `convergence-decomposition` job (manual dispatch). It takes about 32 minutes on Actions.
- Checked on 22 Nov 2026: Actions run 44964245934 at `81ef70d` (Linux, Python 3.14) gave the same values as the committed file, made on macOS with Python 3.13. All 1,628 numeric fields are equal at the stored precision; only the commit, machine, Python version and run time differ.
- No chart: this repository has no committed-chart convention for docs, so the tables are the record.
