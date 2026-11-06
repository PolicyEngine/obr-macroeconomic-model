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
| RL (10-year gilt) | no | — | No sourced coefficient from Bank Rate to gilt yields was found in BoE or OBR documentation. |
| RX (sterling) | no | — | No sourced coefficient was found. Exports and imports have no equation, so sterling moves only trade prices (PXNOG, PMNOG), never volumes. |
| APH (house prices) | no | — | No sourced coefficient from Bank Rate to house prices was found in BoE or OBR documentation. |

The frame's `attrs` record which inputs moved (`monetary_conditioning_on`, with each source), which did not (`monetary_conditioning_off`), and `inflation_unemployment_note`.

## Results: +25 / +100 / −100bp, held for 4 quarters

Measured 6 Nov 2026 under the default nominal-GDP pin, with window 2025Q1–2028Q4. Every quarter of every run converged to tolerance. The +100bp rows and the −100bp conditioning row are pinned by `tests/test_monetary_conditioning.py`.

| Shock | Mode | Peak GDP (q4) | GDP q8 | GDP q12 | Peak CONS | Peak real HH income | CPI inflation | Unemployment |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| +25bp | default | −0.0145% | −0.0024% | −0.0014% | −0.024% | −0.08% | 0 | 0 |
| +25bp | conditioning | −0.0369% | −0.0124% | −0.0075% | −0.060% | −0.25% | 0 | 0 |
| +100bp | default | −0.0574% | −0.0093% | −0.0056% | −0.094% | −0.30% | 0 | 0 |
| +100bp | conditioning | −0.1475% | −0.0496% | −0.0299% | −0.242% | −0.99% | 0 | 0 |
| −100bp | default | +0.0590% | +0.0100% | +0.0060% | +0.097% | +0.31% | 0 | 0 |
| −100bp | conditioning | +0.1475% | +0.0495% | +0.0298% | +0.242% | +1.00% | 0 | 0 |

The conditioning response is proportional to size (+25bp × 4 = −0.1475%) and symmetric in sign.

The BoE benchmark is in the Bank of England's *The transmission mechanism of monetary policy* (Quarterly Bulletin 1999 Q2). It gives GDP −0.2% to −0.35% after about a year, and inflation −0.2pp to −0.4pp a year after that. With only the mortgage rate moved, GDP reaches −0.15%, below that range.

- Round 3's illustrative "all channels" run gave −0.25%, inside the range. It used unsourced pass-throughs for gilts, sterling and house prices, so it is not adopted here.
- Inflation stays at 0 in every run, so the inflation half of the benchmark cannot be compared at all.

## Audit: the retail-rate income effect

Round 3 found that moving retail rates 1:1 with Bank Rate cut real household income by 1.06% at the peak, and flagged this for audit. The audit found the following:

- **The mechanics are the OBR's equations, with nothing extra.** In the impact quarter the change in HHDI is exactly −ΔDIPHH − ΔDIPHHmf + ΔWYQC, to the pound. DIPHH (l.623) rises by £4.98bn per 100bp. DIPHHmf (l.619) enters through OSHH (l.725). WYQC (l.641) follows company profits. `tests/test_monetary_conditioning.py` checks each term against the published formula.
- **By default, the mortgage spread offsets most of the hit.** With RMORT held fixed, the spread `RMORT − R` falls 1pp. That raises OSHH by £4.15bn, offsetting 83% of the DIPHH rise, which leaves −£1.41bn. At the OBR's own 0.9 pass-through the offset is £0.41bn (8%), and HHDI falls £4.68bn (−0.97% of HHDI). Round 3's −1.06% used 1:1.
- **Interest received does not move.** DIRHH, total household interest receipts, has no equation (variables workbook row 493: exogenous). The income effect therefore counts only payments, before any gain in deposit income. `docs/published_model_review.md` H3 records this as a design choice in the OBR's code. Households hold about £2.25tn in deposits against £2.29tn of loans. A deposit-income offset would be a large conditioning judgement, and no pass-through for it is sourced, so it is not added.
- **RDEP is a minor channel.** Round 3's run with RMORT and RDEP at 1:1 gave −0.158%. RMORT at 0.9 alone gives −0.148%. RDEP and the gap between 0.9 and 1 together account for only 0.01pp.

## The cost-of-capital seed (not closed)

The chain R → RIC (l.576) → CDEBT (l.60) → RWACC (l.64) → COCU (l.68) → COC → KSTAR stops at COCU:

- COCU needs DELTA and RWACC, and RWACC needs DEBTW and NDIV. The OBR's variables workbook lists DELTA, DEBTW and NDIV as exogenous with no equation and no published data.
- COCU is therefore held at its declared seed (`full_solver.UNPUBLISHED_COST_OF_CAPITAL_SEEDS`), so COC moves only with corporation tax.
- Every Bank Rate run now carries `attrs["cost_of_capital_channel"]`, which says so.
- Tests pin that RIC moves while COCU and COC do not.

The OBR's own working file also has the business-investment equation (l.92) commented out.

Closing the gap would need two inputs:

- **DELTA.** It is possibly the published RDELTA (0.022, l.66), but whether that rate is quarterly or annual needs checking.
- **DEBTW, the debt weight in the cost of finance.** In principle it could be derived from ONS PNFC balance sheets, the way DB, DP and DV were derived in `cost_of_capital.py`.

Both are a decision for the maintainer. Neither is invented here.
