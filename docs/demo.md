# Demo script

Six shocks that show what the emulator does and where it stops. Every number below comes from `results/demo_shocks.json`. It was produced by `scripts/demo_shocks.py` on GitHub Actions (run 43716065096, 15 Nov 2026), on main after #54, #55, #57 and #58, under the default closure (the nominal-GDP pin). Every shock is sustained from 2025Q1 to the end of the window (2027Q4) unless stated otherwise. All baseline and shocked solves converged to tolerance in 12 of 12 quarters. GDP is chained-volume £m per quarter; the ratio column is current-price GDP per pound of current-price revenue, the basis of the OBR's multipliers.

To regenerate: `uv run python scripts/demo_shocks.py` (about 35 minutes; run it on Actions with `.github/workflows/demo.yml`).

## Setup for the room

```bash
uv sync
uv run python
```

```python
from obr_macro import run_reform
df = run_reform(name="demo", var="CGG", shock=1250, periods=12)
df[["period", "delta_gdp_m", "pct_gdp"]]
df.attrs["solver_converged"]   # True
```

The first `run_reform` call builds the model template and takes a few minutes; the README Quick Start (three calls) took about five minutes on a laptop. Run one call before the session starts.

## The shocks

| # | Shock (`var`, size per quarter) | GDP £m: q1 / q4 / q12 | Ratio q4 / q12 | Published benchmark |
|---|---|--:|--:|---|
| 1 | Government consumption (`CGG`, +1,250) | +1,267 / +1,283 / +1,311 | 1.01 / 1.05 (real) | OBR 0.6, fading |
| 1b | Same, `published_conventions=True` | +750 / +637 / +337 | 0.60 / 0.27 (real) | imposed OBR 0.6 convention |
| 2 | Income tax basic rate +1p (`TYEM`, 1,725) | −160 / −332 / −569 | 0.21 / 0.37 | OBR 0.3, fading |
| 3 | Employee NICs +1pp (`EENIC`, 1,337.5) | −124 / −257 / −441 | 0.21 / 0.37 | OBR 0.3, fading |
| 4 | VAT +1pp (`VREC`, 2,200) | −28 / −55 / −89 | 0.027 / 0.046 | OBR 0.35 |
| 5 | Corporation tax rate +5pp (`TCPRO`, +0.05, `investment_closure=True`) | 0 / −77 / −382 | n/a | no sourced OBR multiplier |
| 6 | Bank Rate +1pp for 4 quarters (`R`, +1.0, `periods=4`) | −129 / −405 / −41 | peak −0.057% of GDP (q4) | BoE −0.2% to −0.35% |
| 6b | Same, `monetary_conditioning=True` | −430 / −1,042 / −219 | peak −0.147% of GDP (q4) | BoE −0.2% to −0.35% |

Sizes come from HMRC's ready reckoner (June 2025, 2026-27, divided by four): £6.9bn a year for 1p on the basic rate, £5.35bn for 1pp on employee NICs, £8.8bn for 1pp of VAT.

Receipts (`PSCR`) and central government net borrowing (`CGNB`) move one for one with the revenue in rows 2–4 (+1,725 / −1,725 for income tax; +1,337.5 / −1,337.5 for NICs; +2,200 / −2,200 for VAT, every quarter).

## One line on each

1. **Government consumption.** GDP rises by the shock and a little more (1.01 on impact, 1.05 by q12), because the shock enters the expenditure identity directly. Extra nominal GDP lands in profits, and a small part reaches consumption (+17m to +61m). This is accounting, not a multiplier: the OBR's figure is 0.6, fading. `published_conventions=True` imposes that convention as a labelled add-factor path (0.60 on impact, falling by 0.03 a quarter).
2. **Income tax.** The one live behavioural channel. Household income falls by the revenue, and the published consumption equation lowers spending. Current-price GDP per pound is 0.21 at q4 and 0.37 at q12, against the OBR's 0.3 fading. The order of magnitude is right; the profile builds up instead of tapering (#50).
3. **NICs.** The same channel as income tax and the same ratios (0.21 / 0.37).
4. **VAT.** Receipts and borrowing move one for one, but GDP barely moves (0.027 at q4, 0.046 at q12). CPI is exogenous in the OBR's listing, so the model cannot pass VAT into prices. The tax lands on profits, and only the quasi-corporation withdrawals that follow profits reach households.
5. **Corporation tax rate.** Works through the cost of capital under the investment closure. Business investment falls by 77m at q4, 239m at q8 and 382m at q12. The run is 40% of the way to its plateau after 12 quarters (`df.attrs["investment_closure_plateau_fraction"]` = 0.40). The OBR multiplier table this repo encodes has no corporation-tax row, so there is no sourced benchmark.
6. **Bank Rate.** Works through consumption and household and corporate interest flows only. The peak is −0.057% of GDP at q4. With `monetary_conditioning=True`, which moves the mortgage rate at the OBR's own l.623 pass-through, it is −0.147%. Both are below the Bank of England's −0.2% to −0.35%.

## Caveats to state out loud

- **The model reproduces the OBR's equations, not its judgements.** Where the OBR adds a channel by judgement (price pass-through, monetary transmission, a multiplier convention), the emulator has no equation for it.
- **VAT (#60).** The OBR's 0.35 is an imposed convention (EFO July 2015, Box 3.2), not an output of its listing. #60 measured that passing the VAT rise into CPI makes the published consumption equation give 0.35 at q4. That run is not repeated here.
- **Bank Rate.** About −0.16% is the ceiling even with mortgage and deposit rates both moved (measured in the 14 Nov review, not rerun here), because investment, sterling, house prices and gilt yields have no interest-rate equation (`docs/monetary_conditioning.md`). This is a property of the published equations, not a solver fault.
- **Household-tax ratio basis (#63).** Quote the current-price ratio (0.21 / 0.37) against the OBR's 0.3. Real GDP per pound of current-price revenue (0.19 / 0.33 in this run) mixes two bases and understates by PGDP/100.
- **Free-running scorecard.** The ~4% free-running GDP error in the README is a closure artifact of this emulator (GDP made endogenous, unpublished inputs seeded). It is not an OBR forecast error, and should not be presented as one.
- **Point estimates only.** There are no confidence bands.

## What not to show

- **Government investment (`CGIPS`).** `IF` has no live equation, so GDP does not move. `run_reform` warns, and the README's reform CLI keeps it as a labelled dead channel.
- **Corporation tax as receipts (`NNSCTP`).** Receipts and borrowing move (+900 / −900) and GDP by exactly zero. Use `TCPRO` with the investment closure (row 5) instead.
- **The published closure (`nominal_gdp_pin=False`).** No quarter converges under it.
- **Hosted `score_reform` live.** On the hosted server a 5-year OBR score takes about 12 minutes (macro #243): the PolicyEngine microsimulation takes 2–3 minutes per year. Start it through `start_job` before the session, or show `obr_shock` instead. Until the hosted pin moves from e4d7faa to current main, hosted results come from the published closure (no quarter converges, CGG exactly 1.00), so they will not match this page.
- **Fuel duty** is supported (`TXFUEL`; +5% = 300 a quarter gives GDP −7 at q4, −12 at q12), but it is the VAT story at a seventh of the size.

## Pending changes that move these numbers

- #65 holds the ended EU payments at zero. It does not change the GDP rows above. It removes the extra 74 a quarter that a VAT rise currently books as an EU payment, and it moves the free-running scorecard (current account 2.19% → 1.19% of GDP).
- #66 puts the household-tax ratio on the current-price basis in the README and in `run_reform`'s output. The figures above already use that basis.
- #61 corrects the business-investment equation's bracket. Corporation-tax deltas (row 5) are unchanged to the pound.
