# Medium-term convergence: where it comes from

Raised in review (November 2026): the OBR justifies the fade of its fiscal multipliers only in words. This note measures, in our replication, which mechanism brings a shock response back to zero and which do not.

Every number is from `results/convergence_decomposition.json`, written by `scripts/convergence_decomposition.py` at model commit `ab29ffb` (October 2026 EFO, default closure: the nominal-GDP pin), run locally on 21 Nov 2026. Each run is 24 quarters, 2025Q1 to 2030Q4. Every baseline and shocked solve reached tolerance in 24 of 24 quarters.

## The answer in four lines

- **The fade does all of it.** A sustained spending shock returns to zero only when the OBR's published convention is imposed (`published_conventions=True`). That is a judgement applied on top of the equations, not a result of them.
- **The equations do not converge to zero.** Without the fade the GDP effect of sustained spending rises from 1.01 to 1.05 per pound over six years and settles there.
- **The add-factors are not a convergence mechanism for a shock.** They hold the baseline level on the EFO. Switching them off changes the spending response by less than 0.01 per pound.
- **The one live behavioural channel converges, but to a plateau.** Consumption closes a gap to its long-run level at about 9% to 10% a quarter. After a temporary shock that takes the effect back towards zero; after a permanent one it takes it to a new level.

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
| Impact multipliers | 0.6 current spending and welfare, 1.0 capital spending, 0.35 VAT, 0.3 income tax and NICs | The same table, encoded as data |
| Fade | Multipliers taper to zero over five years | `TAPER_QUARTERS = 20` |
| Stated reason | Offsetting changes in monetary policy, the exchange rate and real wages | None of these moves output in the model, so the fade is imposed, not derived (`docs/published_model_review.md`, G2 and G9) |
| Shape between impact and zero | Not published as a formula | **Ours:** linear by quarter, 0.03 a quarter for current spending |
| Start of the fade | From announcement (since November 2015) | **Ours:** from the first shocked quarter; there is no announcement date |
| Year-one average | 0.6 is the published impact figure | **Ours:** 0.555, because the quarterly fade starts in quarter 1 (0.60, 0.57, 0.54, 0.51) |
| Where it applies | Applied by the OBR as an adjustment to its forecast | Opt-in, off by default, and only for `CGG` and the government-investment levers. Tax levers keep the model's own response |

The convention reproduces the OBR's published end points. The quarterly path, the start date and the year-one average are choices made here, and are labelled as such in `df.attrs` on every run that uses them.

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

- **Default.** GDP rises by the shock plus a small second round. It does not fall back. The yearly increments shrink (0.012, 0.007, 0.004, 0.003, 0.001), so the path is flattening at about 1.05.
- **Add-factors off.** The largest gap from the default in any quarter is 0.007 per pound. The add-factors move the level at which the equations are evaluated, which changes a nonlinear response slightly. They do not pull the response towards zero.
- **Fade imposed.** 0.60 in quarter 1, down 0.03 a quarter, zero from quarter 21. This column is `0.6 × (1 − q/20) × shock` by construction. It carries no information about the model.

## What each mechanism contributes

### Frozen add-factors

- They are computed once as EFO minus model, then applied identically to the baseline and the shocked run.
- **They make the baseline level track the EFO.** Anchored GDP is within 0.24% of the October 2026 EFO over 2025Q1 to 2027Q4, by construction (README). With them off, the same equations drift 4.24% away. That gap measures this emulator's closure and its seeded inputs. It is not an OBR forecast error.
- **They cancel in a shock response.** In the table above, removing them moves the multiplier by at most 0.007.
- For the household tax shock the gap is larger (0.46 anchored against 0.40 free-running at quarter 24, below), because that response depends on the level of income and consumption it is measured around. In neither case does the response head back to zero.

### The fade

- The only mechanism here that returns a sustained shock's effect to zero.
- It is an add-factor on the GDP identity applied to the shocked run only, sized so that GDP lands on the convention's path.
- It overrides the model's own response, 1.01 to 1.05, with 0.6 falling to zero. The difference between the first and third columns of the table is the size of that judgement: 0.46 per pound in year 1, 1.05 by year 6.
- Consumption in the faded run is a by-product of the override (+9m in quarter 1, −6m by quarter 24) and should not be read as a result.

### Equation dynamics

- **Second round.** The GDP effect beyond the shock itself equals the consumption response to the pound: +16m in quarter 1, +50m in quarter 12, +57m in quarter 24 on a £1,250m shock. Extra nominal GDP lands in profits, a small part reaches household income, and consumption follows.
- **The only adjustment process.** The consumption equation (line 4 of the OBR's listing) is an error-correction equation: each quarter consumption closes 12.5% of the gap to a long-run level set by real income and household wealth (long-run income elasticity 0.44).
- **Measured speed.** After a shock is withdrawn the remaining GDP effect decays by 9% to 10% a quarter (ratio 0.91 falling to 0.90), a half-life of about seven quarters.
- **It converges to the long-run level, not to baseline.** A permanent change in income gives a permanent change in consumption.
- **What is absent.** No equation responds to the output gap, Bank Rate is an input with no policy rule, prices are inputs, and exports and imports have no equation. So nothing in the equations offsets a sustained demand shock.

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
- The reference column is arithmetic on the published end points with our linear shape, `0.3 × (1 − q/20)` averaged by year. It is not a model run.

## What it would take for the model to converge by itself

Not implemented. Each would be new behaviour and would need its own opt-in flag and evidence.

- A monetary policy rule with a price response, so that Bank Rate leans against a demand shock.
- Live trade equations, so that higher demand leaks into imports and the exchange rate matters for volumes.
- A link from the output gap to wages and prices.
- A government budget constraint or fiscal rule that withdraws the stimulus.

Until one of these exists, the honest description is: the equations give a permanent effect, and the return to zero is the OBR's judgement re-applied.

## Reproduce

```bash
uv run python scripts/convergence_decomposition.py              # all six runs
uv run python scripts/convergence_decomposition.py --leg cgg_fade
```

- Each run takes about two to four minutes on a laptop (measured 21 Nov 2026).
- `.github/workflows/demo.yml` has a `convergence-decomposition` job (manual dispatch).
- No chart: this repository has no committed-chart convention for docs, so the tables are the record.
