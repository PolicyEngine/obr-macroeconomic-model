# Bank Rate and the monetary-conditioning option (#50)

## What Bank Rate reaches in the OBR's model

In the OBR's October 2025 listing, Bank Rate `R` reaches two places:

- the real-rate term in consumption (l.4);
- the interest flows in household and corporate income: DIPHH l.623, DIPHHmf l.619, DIRHHf l.627 and RIC l.576.

The mortgage rate RMORT, the deposit rate RDEP, gilt yields RL, sterling RX and house prices APH have no equation. They are the OBR's conditioning assumptions, which it sets by judgement or from market curves. Exports and imports have no equation either. CPI (l.314) and PGDP (l.713) are commented out. Unemployment LFSUR (l.165) has no rate or demand term. **CPI and unemployment therefore do not respond to Bank Rate in this model, by design, in either mode below.**

By default the conditioning inputs stay at the EFO path. A Bank Rate shock then moves GDP by about 0.057% per 100bp. That is a consequence of the model's structure and closure, not an estimate of the effect of monetary policy.

## `monetary_conditioning=True`

`run_reform("…", "R", shock, monetary_conditioning=True)` also moves the conditioning inputs with `R`, but only where a pass-through coefficient can be sourced. It is a labelled judgement overlay, like `published_conventions`, not model dynamics. The default is `False` and leaves the results unchanged. Any other `var` raises an error.

| Input | Moved? | Pass-through | Source / reason |
|---|---|---|---|
| RMORT (mortgage rate) | yes | 0.9pp per 1pp, same quarter | OBR model code l.623 assumes the effective rate on the household loan stock is `0.9*R + 0.2`. This is the OBR's own assumption, not a BoE estimate for new mortgages. Without it, holding RMORT fixed while R rises makes the l.619 spread `(RMORT − R)` fall. That produces an offsetting rise in operating surplus OSHH (l.725), which contradicts l.623. |
| RDEP (deposit rate) | no | — | No point estimate. In a March 2019 speech, BoE MPC member Michael Saunders put sight-deposit pass-through at over 80% on average in earlier tightening cycles, but around 40% in 2017–18. |
| RL (20-year gilt yield) | no | — | No sourced coefficient from Bank Rate to gilt yields was found in BoE or OBR documentation. `RL` is the 20-year yield: the OBR's variables workbook (row 462) calls it "Long rates: 20 year gilt yield", and it is loaded from the EFO table 1.9 column "Long-term interest rates (20-year gilts)". |
| RX (sterling) | no | — | No sourced coefficient was found. Exports and imports have no equation, so sterling moves only trade prices (PXNOG, PMNOG), never volumes. |
| APH (house prices) | no | — | No sourced coefficient from Bank Rate to house prices was found in BoE or OBR documentation. |

### Why the default stays `False` (decided 18 Nov 2026)

Making `monetary_conditioning=True` the default was considered and rejected. The figures are the `bank_rate` and `bank_rate_conditioned` rows of `results/demo_shocks.json` (October 2026 EFO, +1pp for four quarters: peak −0.057% and −0.149% of GDP at q4). The reasons, strongest first:

- **A default run should not carry a behavioural assumption.** The overlay moves a *different* variable, the mortgage rate, by an assumed pass-through coefficient (0.9). The OBR's listing treats retail rates as conditioning assumptions set outside the model, so with the overlay on by default the plain `R` run would stop being the listing's own response, and a reader would have to know to switch a judgement off to see it. The other two overlays (`published_conventions`, `price_passthrough`) are opt-in for the same reason. This is not the same as the nominal-consistent `CGG` shock adopted the same day (`docs/decisions.md`), which is on by default: that moves the nominal side of the *same* transaction at the data deflator, with no coefficient and no behavioural assumption.
- **Both modes stay below the BoE benchmark** (−0.2% to −0.35%), and CPI and unemployment respond in neither, so the choice of default does not turn the Bank Rate channel into a monetary-policy estimate. It would multiply the reported GDP effect by 2.6 without that.
- **The overlay completes the payments side only.** It makes interest paid consistent with the OBR's l.623, but interest received, DIRHH, has no equation and does not move in either mode (see the audit below). The conditioned run therefore books the whole rise in household interest payments, £4.68bn a quarter per 100bp, with no rise in deposit income, although households hold about £2.25tn of deposits against £2.29tn of loans. An illustration of how much that could matter, not a model result: if the 40% to 80% pass-through that Michael Saunders cited for *sight* deposits (table above) applied to the whole deposit stock, interest income would rise by roughly £2.3bn to £4.5bn a quarter (2,250,000 × 1% ÷ 4 × pass-through), leaving a net fall of about £0.2bn to £2.4bn. The default run's £1.41bn would sit inside that range. Time deposits reprice differently and no pass-through for the whole stock is sourced, so the illustration shows only that the conditioned run is not obviously nearer the net household effect than the default.

`tests/test_bridge_contract.py` asserts that the default is `False`. That is a consequence of the decision, not a reason for it: the test would be changed with the default.

What would change the decision: a sourced pass-through from Bank Rate to the effective deposit rate (so both sides of the household interest account can move together), or an OBR statement of how it conditions RMORT and RDEP on Bank Rate.

The frame's `attrs` record which inputs moved (`monetary_conditioning_on`, with each source), which did not (`monetary_conditioning_off`), and `inflation_unemployment_note`.

## Results: +25 / +100 / −100bp, held for 4 quarters

Measured 6 Nov 2026 on the March 2026 EFO under the default nominal-GDP pin, with window 2025Q1–2028Q4. Every quarter of every run converged to tolerance. On the October 2026 EFO (demo battery, 16 Nov 2026, window 2025Q1–2027Q4) the +100bp peaks are −0.057% default and −0.149% with conditioning (`results/demo_shocks.json`); the table is not re-run. The +100bp rows and the −100bp conditioning row are pinned by `tests/test_monetary_conditioning.py`.

| Shock | Mode | Peak GDP (q4) | GDP q8 | GDP q12 | Peak CONS | Peak real HH income | CPI inflation | Unemployment |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| +25bp | default | −0.0145% | −0.0024% | −0.0014% | −0.024% | −0.08% | 0 | 0 |
| +25bp | conditioning | −0.0369% | −0.0124% | −0.0075% | −0.060% | −0.25% | 0 | 0 |
| +100bp | default | −0.0574% | −0.0093% | −0.0056% | −0.094% | −0.30% | 0 | 0 |
| +100bp | conditioning | −0.1475% | −0.0496% | −0.0299% | −0.242% | −0.99% | 0 | 0 |
| −100bp | default | +0.0590% | +0.0100% | +0.0060% | +0.097% | +0.31% | 0 | 0 |
| −100bp | conditioning | +0.1475% | +0.0495% | +0.0298% | +0.242% | +1.00% | 0 | 0 |

The conditioning response is proportional to size (+25bp × 4 = −0.1475%) and symmetric in sign.

The BoE benchmark is in the Bank of England's *The transmission mechanism of monetary policy* (Quarterly Bulletin 1999 Q2). It gives GDP −0.2% to −0.35% after about a year, and inflation −0.2pp to −0.4pp a year after that. With only the mortgage rate moved, GDP reaches −0.15%, below that range. The conditioning run is the reading consistent with the OBR's own listing on interest paid (the 0.9 mortgage pass-through is its l.623 coefficient); the default run, which holds the mortgage rate at the EFO path, is the smaller of the two. Neither moves interest received, so neither is a bound on the full effect (see "Why the default stays `False`" above).

- Round 3's illustrative "all channels" run gave −0.25%, inside the range. It used unsourced pass-throughs for gilts, sterling and house prices, so it is not adopted here.
- Inflation stays at 0 in every run, so the inflation half of the benchmark cannot be compared at all.

## Audit: the retail-rate income effect

Round 3 found that moving retail rates 1:1 with Bank Rate cut real household income by 1.06% at the peak, and flagged this for audit. The audit found the following:

- **The mechanics are the OBR's equations, with nothing extra.** In the impact quarter the change in HHDI is exactly −ΔDIPHH − ΔDIPHHmf + ΔWYQC, to the pound. DIPHH (l.623) rises by £4.98bn per 100bp. DIPHHmf (l.619) enters through OSHH (l.725). WYQC (l.641) follows company profits. `tests/test_monetary_conditioning.py` checks each term against the published formula.
- **By default, the mortgage spread offsets most of the hit.** With RMORT held fixed, the spread `RMORT − R` falls 1pp. That raises OSHH by £4.15bn, offsetting 83% of the DIPHH rise, which leaves −£1.41bn. At the OBR's own 0.9 pass-through the offset is £0.41bn (8%), and HHDI falls £4.68bn (−0.97% of HHDI). Round 3's −1.06% used 1:1.
- **Interest received does not move.** DIRHH, total household interest receipts, has no equation (variables workbook row 493: exogenous). The income effect therefore counts only payments, before any gain in deposit income. `docs/published_model_review.md` H3 records this as a design choice in the OBR's code. Households hold about £2.25tn in deposits against £2.29tn of loans. A deposit-income offset would be a large conditioning judgement, and no pass-through for it is sourced, so it is not added.
- **RDEP is a minor channel.** Round 3's run with RMORT and RDEP at 1:1 gave −0.158%. RMORT at 0.9 alone gives −0.148%. RDEP and the gap between 0.9 and 1 together account for only 0.01pp.

## The cost-of-capital seed (not closed)

The chain R → RIC (l.576) → CDEBT (l.60) → RWACC (l.64) → COCU (l.68) → COC → KSTAR is broken in two places.

- **RIC is NaN.** RIC, the effective rate on bank lending to PNFCs, is NaN over the whole solve window in both closures. CDEBT and RWACC are NaN with it. l.576 is an error-correction equation in RIC(−1), so a missing starting value carries through every quarter. Why the starting value is missing has not been traced yet. R therefore reaches neither the corporate interest flows (DIPIC, DIRIC) nor the cost of capital. This was measured on 6 Nov 2026 and corrects round 3's statement that "RIC moves".
- **COCU is a seed.** COCU needs DELTA and RWACC, and RWACC needs DEBTW and NDIV. The OBR's variables workbook lists DELTA, DEBTW and NDIV as exogenous with no equation and no published data, so COCU is held at its declared seed (`full_solver.UNPUBLISHED_COST_OF_CAPITAL_SEEDS`).

Every Bank Rate run carries `attrs["cost_of_capital_channel"]`, which says so. Tests pin both breaks. Under the investment closure, COCU, COC, KSTAR, IBUSX, DIPIC and DIRIC move by exactly 0 for +100bp.

The OBR's own working file also has the business-investment equation (l.92) commented out.

Closing the gap would need two inputs:

- **DELTA.** It is possibly the published RDELTA (0.022, l.66), but whether that rate is quarterly or annual needs checking.
- **DEBTW, the debt weight in the cost of finance.** In principle it could be derived from ONS PNFC balance sheets, the way DB, DP and DV were derived in `cost_of_capital.py`.

Both are a decision for the maintainer. Neither is invented here.

## A gilt-yield shock (`RL`) and the pension-contribution channel

`RL` is the 20-year gilt yield (variables workbook row 462; EFO table 1.9, "Long-term interest rates (20-year gilts)"). It has no equation and Bank Rate does not move it. Shocked on its own, it moves GDP more than Bank Rate does. This section records why. Reviewed 22 Nov 2026.

**What the run shows.** +1 point on `RL`, sustained from 2026Q2, default closure, October 2026 EFO, window 2026Q2–2028Q4. £m a quarter; every quarter of both solves converged to tolerance.

| | q1 | q4 | q11 |
|---|--:|--:|--:|
| `EECPP` (l.649) | +5,215 | +5,203 | +5,195 |
| Household disposable income `HHDI` | −5,276 | −5,328 | −5,389 |
| Consumption = GDP | −479 | −989 | −1,627 |
| GDP, % of baseline | −0.067% | −0.138% | −0.224% |
| Same window, Bank Rate +1 point sustained: `HHDI` | −1,408 | −1,425 | −1,386 |
| Same window, Bank Rate +1 point sustained: GDP | −127 | −400 | −478 |

**Where it comes from.**

- One equation carries it. The listing's l.649 is `EECPP = ((1 + RL/100)^0.25 − 1) × PIHH(−1) × 0.729 + ((1 + 0.05)^0.25 − 1) × PIHH(−1) × 0.271`. `EECPP` is "Employees' contributions to funded pension schemes" (variables workbook row 506). Its ONS codes include the household contribution supplements (D.614): the investment return on pension funds, booked as if households received it and paid it back in as a contribution. `PIHH` is the household stock of pension and insurance assets, £2.98tn.
- The size is the listing's arithmetic: 0.729 × £2.98tn × a quarter of one point = £5.2bn a quarter. The run reproduces l.649 to the pound (`tests/test_gilt_yield_channel.py`).
- `EECPP` is deducted from income through employees' social contributions `EESC` (l.651), which the `HHDI` identity subtracts. So `HHDI` falls one for one.
- Nothing on the receipts side moves with it. In the national accounts the supplement is matched by property income attributed to pension holders. In the listing that income sits in `APIIH` ("Other investment income", row 503), which has no equation, and interest received `DIRHH` has none either. Property income `PIRHH` moves by only −£61m, a second-round effect through profits. This is the same one-sided pattern as the household interest account above.
- The pension adjustment `NEAHH` (l.660) rises by the same £5.2bn, so `HHDI + NEAHH`, the resources the saving ratio is measured on, barely move. Consumption falls only because the consumption equation (l.4) uses `HHDI` before that adjustment.

**Verdict.** This is the published listing's behaviour, reproduced correctly. It is not a units or scaling error in this repo and not a seed error: the coefficient, the stock and the rate are the listing's and the published data. No code is changed.

**How to read it.**

- It is not an estimate of what gilt yields do to the economy. It is an accounting entry with one leg modelled. An OBR forecaster would set `APIIH` alongside `RL` by judgement; this repo has no sourced rule for that, so none is added.
- It is larger than the default Bank Rate response because nothing offsets it. The whole £5.2bn on £2.18tn of pension assets (0.729 × `PIHH`) comes off income. For Bank Rate the mortgage spread offsets 83% of the rise in interest paid, which leaves £1.41bn.
- The listing's other gilt-yield leg is not in the figure. A higher yield also revalues the pension stock down (l.795 through `DBR`, l.797), but `PIHH` is held on its data path here (`docs/published_model_review.md`, H4). Arithmetic on the listing's coefficients, not a run: +1 point lowers `DBR` by 13.2%, so `PIHH` would fall about 7.6% (£226bn) in the first quarter. With the smaller stock, `EECPP` would be up about £1.8bn a quarter from the second quarter, not £5.2bn, and lower wealth would pull consumption down separately. The net effect in the full listing was not measured.
- The debt-interest overlay proposed in #80 adds a public-finances effect of `RL` and leaves this GDP figure unchanged.

**Left open: the baseline level of `EECPP`.** Over 2019Q1–2026Q1 l.649 gives 15% to 77% more than the ONS series (`L8PE + L8Q2 + L8LQ`, all three codes loaded). The baseline therefore steps from £26,865m in 2026Q1 (data) to £38,488m in 2026Q2 (equation). This does not affect the shock response above, which depends on `PIHH(−1)` and not on the level of `EECPP`. Anchoring the level would move baseline household income, so it is not done here.
