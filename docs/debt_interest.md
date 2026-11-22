# Debt interest and the debt-interest option

Raised in review: interest on public debt is exogenous. This note says what that means in our runs, what the opt-in `debt_interest=True` overlay does, and how far it can be trusted.

Every scenario figure comes from `results/debt_interest_examples.json` (`scripts/debt_interest_examples.py`, run locally on 21 Nov 2026 at commit bc6b624, October 2026 EFO, default closure; the overlay's arithmetic has not changed since). Every EFO figure comes from the detailed forecast tables committed under `obr_macro/_data/`.

## What the listing does

- Central government debt interest `DICGOP` has no equation. The OBR's variable list labels it exogenous, with local authority and public corporation interest (`DILAPR`, `DIPCOP`).
- It enters two live equations only: the spending residual (l.504) and central government net borrowing `CGNB` (l.524).
- The debt stocks `PSND` and `GGGD` (l.567, l.571) are change equations with no starting level in the databank, so they are dropped in our runs.
- Result: a reform that raises borrowing, or a higher gilt yield, leaves debt interest exactly on its data path. In our baseline that path is flat at £24.2bn a quarter from 2026Q2 (the mean of the last four published quarters of the ONS series).
- That level is not the EFO's forecast (£123.9bn for 2026-27, table 6.16): the ONS series behind `DICGOP` (interest paid to the private sector and the rest of the world) is not the same line as the EFO's, and the flat path has no forecast in it. The overlay does not touch the level. It adds a change to it.

## How the OBR forecasts debt interest

The OBR does this outside the macro model, by financing component. The October 2026 EFO tables show the method.

Terms: a **gilt** is a UK government bond. Its **coupon** is the fixed interest it pays, set by the market yield when it is issued. A **conventional** gilt pays a fixed cash coupon; an **index-linked** gilt's payments rise with RPI inflation.

- **Effective interest rate on each stock** (table 6.17). Effective rate means interest paid divided by the stock outstanding. For 2026-27: 3.34% on £1,598bn of conventional gilts in private hands, 3.90% on £3,172bn of central government gross debt.
- **Existing and new stock** (table 6.16). Interest on conventional gilts is split into the stock already issued (£47.9bn in 2026-27, falling as gilts redeem) and new issuance (£5.5bn in 2026-27, £19.1bn in 2027-28, £70.9bn by 2031-32).
- **Refinancing** (table 6.12). In 2026-27 the government issues £224.8bn of conventional gilts: £140.2bn of redemptions to refinance plus most of the cash requirement. That is 11.8% of the conventional gilt stock (£1,913bn including Bank of England holdings).
- **Market rates for new issuance** (table 1.9). The 20-year gilt yield is 5.4% to 5.7% over 2026-27 and 2027-28, well above the 3.34% effective rate on the existing stock. So what moves debt interest is the rate on new gilts and how many are issued, not the rate on the whole stock.

## `debt_interest=True`

```python
from obr_macro import run_reform

off = run_reform(name="Spending", var="CGG", shock=1250, periods=12)
on = run_reform(name="Spending", var="CGG", shock=1250, periods=12,
                debt_interest=True)
d = on.attrs["debt_interest_detail"]
d["delta_debt_interest_m"]      # extra interest, £m a quarter
d["delta_borrowing_after_m"]    # change in CGNB, interest included
on.attrs["debt_interest_off"]   # what the overlay does not move, and why
```

The overlay applies the OBR's approach to conventional gilts, as a difference between the shocked run and the baseline:

- **Stock effect.** Each quarter's extra central government borrowing (the change in `CGNB`) is financed by a gilt issued at that quarter's gilt yield `RL`. The gilt pays that coupon from then on. The extra interest is borrowed too, so it compounds.
- **Rate effect.** If the gilt yield is shocked, the gilts the EFO already plans to issue (table 6.12, a quarter of the fiscal-year figure each quarter) are issued at the changed yield. The existing stock keeps its coupons.
- **Timing.** A gilt issued during a quarter pays half a quarter's interest in that quarter and a full quarter's after.
- **Where it lands.** The interest is added to `DICGOP` and to public sector current expenditure `PSCE` by the same amount. `PSCE` is imposed in the listing and subsidies are its residual (l.504), so moving `DICGOP` alone would cut subsidies one for one and leave public sector borrowing unchanged.

Limits of use:

- Default closure only. It raises with `investment_closure=True`, `published_conventions=True`, `nominal_gdp_pin=False`, `price_passthrough=True`, `import_response=True` or `employment_response=True` (not measured there).
- A gilt-yield shock needs planned issuance for every shocked quarter. The committed tables cover 2025-26 (November 2025 EFO) to 2031-32, so a yield shock starting in 2025Q1 (fiscal year 2024-25) raises.
- Code: `obr_macro/debt_interest.py`. Tests: `tests/test_debt_interest.py`.

## Check against the EFO

The pricing rule can be tested on the EFO's own forecast: apply it to the EFO's planned conventional issuance at the EFO's 20-year yield, and compare with the EFO's interest on new conventional gilts (table 6.16).

| £bn | 2026-27 | 2027-28 | 2028-29 | 2029-30 | 2030-31 | 2031-32 |
|---|--:|--:|--:|--:|--:|--:|
| Overlay rule | 6.13 | 20.13 | 35.70 | 49.84 | 63.78 | 80.14 |
| EFO table 6.16, new stock | 5.55 | 19.12 | 33.99 | 46.66 | 58.08 | 70.85 |
| Ratio | 1.10 | 1.05 | 1.05 | 1.07 | 1.10 | 1.13 |

- The rule is 5% to 13% high in every year. Two likely reasons: the 20-year yield is above the average yield at issue (the government also issues shorter gilts), and the rule ignores new gilts that redeem inside the window.
- No coefficient was tuned to close the gap. `test_cohort_rule_against_efo_new_stock_interest` pins the measured ratios.
- This checks the pricing of new gilts. It does not check the response to a shock, for which the repo holds no published benchmark (see "What is left").

## Borrowing scenario: government consumption +£1.25bn a quarter

Sustained from 2025Q1 to 2027Q4. £m a quarter.

| | q1 | q4 | q8 | q12 | 12-quarter total |
|---|--:|--:|--:|--:|--:|
| Extra borrowing, overlay off (`CGNB`) | 1,336 | 1,364 | 1,415 | 1,419 | 16,654 |
| Extra debt interest, overlay on | 8 | 61 | 140 | 230 | 1,354 |
| Extra borrowing, overlay on | 1,344 | 1,425 | 1,554 | 1,649 | 18,008 |
| Gilt yield `RL`, % | 4.92 | 5.03 | 5.57 | 5.70 | |
| GDP, overlay off and on | +1,266 | +1,280 | +1,293 | +1,300 | |

- With the overlay off, borrowing rises by the cash cost of the spending and by nothing else.
- With it on, borrowing is 0.6% higher in q1 and 16% higher by q12, because each quarter's borrowing adds to the stock that pays interest. Over three years the interest adds 8.1% to the cost.
- GDP and consumption are identical in the two runs, to the pound. Nothing in the listing links debt interest paid to household or company income.

The same works in reverse for a tax rise. VAT +1pp (`VREC` +£2,200m a quarter) lowers borrowing by £2,200m a quarter with the overlay off; with it on, debt interest is lower by £14m / £99m / £224m / £365m at q1 / q4 / q8 / q12 (£2,170m over 12 quarters).

## Gilt-yield scenario: +1 percentage point from 2026Q2

Sustained from 2026Q2 to 2028Q4 (11 quarters, the first three fiscal years of the October 2026 EFO forecast). £m a quarter.

| | q1 | q4 | q8 | q11 | First 4 quarters (2026-27) | Next 4 (2027-28) |
|---|--:|--:|--:|--:|--:|--:|
| Extra debt interest, overlay off | 0 | 0 | 0 | 0 | 0 | 0 |
| Rate effect | 70 | 492 | 1,162 | 1,666 | 1,124 | 3,619 |
| Stock effect (interest on the interest) | 1 | 15 | 72 | 150 | 26 | 187 |
| Extra debt interest and borrowing, overlay on | 71 | 506 | 1,234 | 1,816 | 1,150 | 3,805 |

- A 1 point rise in the gilt yield adds £1.1bn to debt interest in the first year and £3.8bn in the second. It builds because only newly issued gilts carry the higher coupon: about £56bn a quarter in 2026-27 and £69bn in 2027-28.
- With the overlay off the same shock leaves debt interest and borrowing at exactly zero.
- GDP falls in both runs by the same amount (−£479m in q1, −£989m in q4). That is the listing's own channel, not the overlay:
  - l.649 sets employees' contributions to funded pension schemes `EECPP` as a return at the gilt yield on 72.9% of the household stock of pension and insurance assets `PIHH` (£2,986bn in 2026Q1), plus a fixed 5% on the rest.
  - So +1 point on `RL` raises `EECPP` by 0.729 × £2,986bn × the change in the quarterly rate, which is £5,215m a quarter (from a baseline of £38.5bn).
  - `EECPP` is part of employees' social contributions `EESC` (l.651), which is subtracted from household disposable income `HHDI` (l.654). `HHDI` falls by £5,276m in q1 and £5,328m in q4 (1.1%), and consumption and GDP follow through l.4.
  - Source: one local baseline and shocked solve on 22 Nov 2026 (flag off), which matches the arithmetic of l.649 to the pound. The GDP figures are in `results/debt_interest_examples.json`.
  - So the figure is the listing's equation as published, not a units or scaling slip in the overlay or the run. It is large next to the Bank Rate response. Whether a higher gilt yield should lower household income this way (only the contribution leg moves; the matching investment income has no equation) is reviewed separately, not here.

## What the overlay does not do

`df.attrs["debt_interest_off"]` carries this list.

| Not moved | Why |
|---|---|
| Index-linked gilts (£696bn in 2026-27, table 6.17) | Their interest follows RPI, and RPI has no link to CPI or to any shock in this model |
| Gilts held in the Bank of England's Asset Purchase Facility (£421bn) | Their net cost follows Bank Rate through the Bank's balance sheet, which the listing does not contain |
| Treasury bills and NS&I | They reprice with short rates; no sourced pass-through is in the repo |
| The gilt yield itself | It stays on the EFO path unless shocked. More borrowing does not raise it |
| The maturity mix | All new gilts are priced at the 20-year yield (5% to 13% high, see the check above) |
| Household and company income | Interest paid does not reach any income equation, so the overlay adds no GDP effect. GDP is the same with it on or off; a gilt-yield shock still moves GDP through l.649 either way (see the gilt-yield scenario) |

So a Bank Rate shock or a price shock does not move debt interest with the overlay on. Those are the two largest sensitivities left out.

## Why it is opt-in

- It is a judgement overlay: the listing holds debt interest exogenous, and the OBR forecasts it in a separate model.
- With the flag off every published figure is unchanged (`test_bridge_contract.py` asserts the default; the scenario file shows identical GDP paths).

## What is left

- **A published benchmark for the shock response.** The OBR has published debt interest ready reckoners (the effect of a 1 point rise in gilt yields, short rates and inflation) alongside its forecasts. None is in the repo's committed tables, and none was downloaded. Comparing the gilt-yield scenario with it is the natural next check.
- **Bank Rate and RPI channels**, which need the ready reckoner or the Asset Purchase Facility and index-linked stocks modelled.
- **Planned issuance for 2024-25**, so a yield shock can start in 2025Q1.
- **Combination with the investment closure, published conventions, price pass-through and the import and employment overlays**, not measured.
