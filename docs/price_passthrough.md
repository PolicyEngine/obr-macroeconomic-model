# Prices, CPI and the price pass-through option (#60)

This note answers three questions raised in review:

- why no price moves in a default run;
- where a VAT rise lands instead;
- what `price_passthrough=True` does, and a proposal to keep it opt-in.

Where the figures come from:

- **Runs.** `results/demo_shocks.json`, rows `vat` and `vat_passthrough` (GitHub Actions run 44394699022, 18 Nov 2026, commit `a822045`, window 2025Q1 to 2027Q4). No scenario figure on this page is new.
- **Forecast.** The OBR's October 2026 Economic and fiscal outlook (EFO).
- **Closure.** The default: GDP is solved from the expenditure identity, and current-price GDP is pinned to the GDP deflator times real GDP (`docs/nominal_gdp_pin.md`).
- **Two derived figures are not in the committed file.** The baseline level of the investment deflator `PIF` (103.9 in 2025Q1, 113.8 in 2027Q4) and the split of the business-investment change (real government investment `GGI` up by the same amount) come from one local re-run of the `vat_passthrough` pair at main `ab29ffb` on 22 Nov 2026. That run reproduced every committed change it shares with the file to the third decimal (`PIF` −1.316, `IBUSX` −420.389, GDP −362.952 in q1).

## Why no price moves in a default run

Terms used below:

- **Listing**: the OBR's published model code (15 October 2025). Line numbers are `l.N`.
- **Exogenous**: taken as an input, here from the OBR's October 2026 forecast (EFO), with no equation that could move it.
- **Dropped**: the equation is in the listing but an input has no published data, so it evaluates to NaN and the variable keeps its data value (`KNOWN_NONFINITE_EQUATIONS`, `obr_macro/full_solver.py`).
- **Markup**: the gap between a price and the cost index behind it.

| Price | Listing | In our runs |
|---|---|---|
| `CPI` (consumer prices) | l.314 is commented out; the variable list says "No Equation" | Exogenous, on the EFO path |
| `PPIY` (producer prices) | l.286 is commented out | Exogenous, on its data path |
| `PGDP` (GDP deflator) | l.713 is commented out | Exogenous, on the EFO path. Under the default closure it also pins current-price GDP: `GDPMPS = PGDP*GDPM/100` (l.690) |
| `PCE` (consumer expenditure deflator) | l.333: grows with `CPI` year on year | Live, but only repeats `CPI` |
| `RPCOST`, `SCOST`, `CCOST`, `UTCOST`, `MCOST` (cost indices, l.262–l.270) | Live identities; they carry unit labour costs, import prices and indirect taxes | Dropped: their 2009 bases are unpublished |
| `MKR` (retail markup, l.284), `MKGW` (wholesale markup, l.280) | Solved backwards from the imposed `CPI` and `PPIY`, so the markup is whatever is left over | Dropped with the cost indices |
| `CPIX` (l.288: cost × markup) | Live | Dropped |
| `PSAVEI` (average earnings, l.232) | Has a term in `CPI` | Dropped, and so is the wage bill `WFP` (l.589). Wages and salaries stay on their data path |
| `PR`, `RPI` (retail prices, l.319 and l.321) | Built from `PRXMIP`, which has no equation, and mortgage payments (`PRMIP`, l.316); `CPI` does not enter | Do not follow `CPI` |
| `PIF` (investment deflator, l.337) | The residual of current-price GDP | Live. Under the default closure it absorbs any gap between pinned current-price GDP and its components |
| `PXNOG`, `PMNOG` (export and import prices of non-oil goods, l.323 and l.327) | Follow producer prices, world prices and sterling | Live, but none of their inputs responds to a domestic shock |

In short:

- The listing has cost indices that would push a tax or wage change towards consumer prices, but it imposes `CPI` and lets the retail markup take the difference (l.284; the comment above it, l.282, says the equation was "re-written to enable indirect T2 fix" and does not say more).
- Our runs inherit that. The cost block does not even evaluate, so no price responds to demand, wages, taxes or interest rates.
- Firms and households are price takers in every default run.

## Where a VAT rise lands by default

VAT +1pp is `VREC` +£2,200m a quarter.

1. `VREC` raises taxes on products: `CETAX` (l.410), then `BPAPS` (l.695), by £2,200m.
2. Current-price GDP at market prices does not rise with the tax, because `GDPMPS` is pinned to `PGDP*GDPM/100` and `PGDP` is exogenous.
3. Wages do not respond (the wage equations are dropped), so the whole tax comes out of operating surplus: `OS = GDPMPS − FYEMP − MI − BPAPS − …` (l.719). Company profits `FYCPR` (l.731) fall by £2,228m in q1: the £2,200m of tax plus almost all of the £29m fall in current-price GDP.
4. Households lose only the income withdrawn from quasi-corporations (`WYQC`, l.641), which scales with profits: household income falls by £293m and consumption by £27m in q1.
5. `CPI` does not move. In the listing the fall would show up as a lower `MKR`. In our runs `MKR` is dropped, so the same thing shows up as lower profits.

So "margins absorb the shock" is accurate, and it follows from three things being held: `CPI`, `PGDP` and wages.

## `price_passthrough=True`

```python
from obr_macro import run_reform

default = run_reform(name="VAT +1pp", var="VREC", shock=2200, periods=12)
passed = run_reform(name="VAT +1pp", var="VREC", shock=2200, periods=12,
                    price_passthrough=True)
passed.attrs["price_passthrough_detail"]["cpi_pct_delta"]  # CPI, % above baseline: about 0.4 in each quarter
passed.attrs["price_passthrough_note"]
```

What it does:

- Holds the retail markup at baseline instead of `CPI`, for the shocked run only.
- Moves `CPI` by `dlog CPI = (1 − W1) × 0.1384 × dlog(BPAPS/GVA)`.
  - 0.1384 is the listing's own weight on indirect taxes in retail costs: 11.56 in `RPCOST` (l.270) plus what `SCOST`, `CCOST` and `UTCOST` pass on.
  - `W1 = 0.084` is the rent weight in the commented-out `CPI` equation (l.314).
- `PCE` follows `CPI` (l.333), real household income falls (`RHHDI = 100*HHDI/PCE`, l.656), and the published consumption equation (l.4) responds.
- Works for `VREC` (VAT receipts) and `TXFUEL` (fuel duty) only, and not with `investment_closure=True`. Either raises an error.
- Code: `_apply_price_passthrough` and the comment above `PRICE_PASSTHROUGH_W1` in `obr_macro/reform_analysis.py`. Tests: `tests/test_price_passthrough.py`.

## VAT +1pp with and without it

£m a quarter unless stated. The ratio is current-price GDP per pound of revenue, the basis of the OBR's multiplier.

| | Default: q1 / q4 / q12 | Pass-through: q1 / q4 / q12 |
|---|--:|--:|
| `CPI` | 0 / 0 / 0 | +0.41% / +0.37% / +0.37% |
| Company profits (`FYCPR`) | −2,228 / −2,256 / −2,292 | −2,580 / −2,947 / −3,586 |
| Household income (`HHDI`, current prices) | −293 / −278 / −251 | −339 / −363 / −392 |
| Consumption and GDP (real) | −27 / −52 / −82 | −363 / −697 / −1,231 |
| Ratio | 0.013 / 0.026 / 0.043 | 0.175 / 0.345 / 0.638 |
| OBR convention (EFO July 2015 Box 3.2) | 0.35, fading | 0.35, fading |
| Receipts (`PSCR`) and borrowing (`CGNB`) | +2,200 / −2,200 every quarter | the same |
| Investment deflator (`PIF`, index points) | 0.00 / 0.00 / 0.00 | −1.32 / −1.21 / −1.26 |
| Measured business investment (`IBUSX`) | 0 / 0 / 0 | −420 / −269 / −268 |
| Real government investment (`GGI`, local re-run) | not re-run | +420 / +269 / +268 |
| Total investment (`IF`) | 0 / 0 / 0 | 0 / 0 / 0 |

How to read it:

- Pass-through moves the incidence (who bears the tax) from profits alone to profits and consumers: prices rise 0.4% and real consumption falls 13 to 15 times as far as in the default run.
- The q4 ratio (0.345) is close to the OBR's 0.35. That is not a calibration, and it does not last: the ratio keeps rising to 0.638 at q12, where the OBR's fades towards zero.
- Profits fall further with pass-through, not less. Lower real consumption lowers pinned current-price GDP, and wages still do not move, so profits take the second round too.
- The `PIF`, `IBUSX` and `GGI` rows are an accounting side effect, not an investment response. The chain is:
  - Consumer prices rise, so current-price consumption rises, while current-price GDP stays pinned to `PGDP`.
  - `PIF` is the residual of current-price GDP (l.337), so it falls: 1.1% to 1.3% across the twelve quarters, about 1.2% on average.
  - The government investment deflator follows `PIF` (l.100) and cash government investment is fixed, so real government investment `GGI` rises (l.96).
  - Business investment is total investment less the other components (l.84), so `IBUSX` falls by exactly what `GGI` rises. `IF` is unchanged to the pound.
  - The path is uneven (−219 in q2, −407 in q5) because it scales with cash government investment, which is largest in 2025Q1 and 2026Q1 on the baseline path.

## Proposal: keep the overlay opt-in

This is a proposal, not a change: the default is `False` today and this page leaves it there. It uses the test applied to `monetary_conditioning` on 18 November 2026 (`docs/decisions.md`, section 3). Any indirect-tax result would quote both runs side by side.

Both settings carry an assumption about pass-through:

- **Default.** None of the tax reaches consumer prices; profits take it. That is what the listing does.
- **Overlay.** All of it reaches consumer prices in the same quarter, with the markup fixed. That is our assumption, and its weights stand in for cost shares the OBR has not published.

Reasons to keep it opt-in:

- **The default run adds no price assumption of ours.** Its closure is this emulator's choice (`docs/nominal_gdp_pin.md`), but its prices are the listing's. With the overlay on by default, a reader would have to switch a judgement off to see that response. The other overlays are opt-in for the same reason.
- **Neither run reproduces the OBR's profile.** The default ratio is 0.013 to 0.026 in year 1, between a twenty-seventh and a thirteenth of 0.35. The overlay is 0.345 at q4 and 0.638 at q12, which is 1.8 times the OBR's impact figure, with no fade. Switching would replace a ratio below the OBR's with one above it at longer horizons.
- **The overlay moves one price and holds the others.** `PGDP`, wages and `RPI` stay on their paths. The `PIF`, `GGI` and `IBUSX` side effect in the table comes from that. The government-consumption shock had a similar side effect; #75 removed it by making the shock nominal-consistent by default.

Reasons to switch the default on:

- In the default run none of a consumption tax reaches consumer prices, and the GDP ratio is a small fraction of the OBR's convention.
- For a first-year VAT question the overlay is closer to that convention: 0.26 averaged over year 1, against 0.35 fading.

What would change the proposal:

- an OBR statement of the pass-through share and timing it assumes for indirect taxes;
- a treatment that moves `PGDP` with `CPI`, so the investment deflator no longer takes the gap;
- a sourced reason for the consumption response to fade.

## What is still missing

- No price responds to demand in any run: no live equation links prices or wages to the output gap (a Phillips curve), and none is added here.
- Wages do not respond to prices (`WFP` is dropped), so there is no wage-price second round.
- Index-linked items (benefits uprating, index-linked gilts) do not respond to the higher `CPI`.
