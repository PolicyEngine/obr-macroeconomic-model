# Demo script

Six shocks that show what the emulator does and where it stops. Every number below comes from `results/demo_shocks.json`, produced by `scripts/demo_shocks.py` on GitHub Actions (run 43866056708, 16 Nov 2026, commit 5eccd49 on the October 2026 EFO re-anchor branch). That hash is a branch commit; after merging, rerun `.github/workflows/demo.yml` and update it. The baseline is the OBR's October 2026 EFO. The window still starts in 2025Q1 so the figures compare like for like with the March 2026 runs; 2025Q1–2026Q2 are now outturn quarters in that EFO, so read those quarters as counterfactual history.

**Closure.** Rows 1–4 and 6 use the default closure, the nominal-GDP pin. It sets current-price GDP equal to real GDP times the GDP deflator (the OBR's commented-out l.690), with the deflator on the OBR's forecast path. Row 5 uses the investment closure, which cannot be combined with the pin and holds the investment deflator instead. Every shock is sustained from 2025Q1 to the end of the window (2027Q4) unless stated otherwise. All baseline and shocked solves converged to tolerance in 12 of 12 quarters. "Converged" covers the equations that evaluate: 82 of the 372 are dropped because their inputs are missing, and they keep their data values.

**Units.** GDP is chained-volume £m per quarter. For the tax rows (2–4) the ratio column is current-price GDP per pound of current-price revenue, the basis of the OBR's multipliers. Rows 1 and 1b are real GDP per real pound of spending.

To regenerate: `uv run python scripts/demo_shocks.py` (about 25 minutes of solves; allow 35 for the Actions job in `.github/workflows/demo.yml`).

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

| # | Shock (`var`, size per quarter) | GDP £m: q1 / q4 / q12 | Ratio | Published benchmark |
|---|---|--:|--:|---|
| 1 | Government consumption (`CGG`, +1,250) | +1,267 / +1,283 / +1,310 | 1.01 / 1.03 / 1.05 | OBR 0.6, fading |
| 1b | Same, `published_conventions=True` | +750 / +637 / +337 | 0.60 / 0.51 / 0.27 | imposed OBR 0.6 convention |
| 2 | Income tax basic rate +1p (`TYEM`, 1,725) | −161 / −335 / −569 | 0.10 / 0.21 / 0.38 | OBR 0.3, fading |
| 3 | Employee NICs +1pp (`EENIC`, 1,337.5) | −125 / −259 / −441 | 0.10 / 0.21 / 0.38 | OBR 0.3, fading |
| 4 | VAT +1pp (`VREC`, 2,200) | −27 / −52 / −83 | 0.013 / 0.026 / 0.043 | OBR 0.35, fading |
| 5 | Corporation tax rate +5pp (`TCPRO`, +0.05, `investment_closure=True`) | 0 / −78 / −384 | n/a | no sourced OBR multiplier |
| 6 | Bank Rate +1pp for 4 quarters (`R`, +1.0, `periods=4`) | −128 / −406 / −41 | peak −0.057% of GDP (q4) | BoE −0.2% to −0.35% after about a year |
| 6b | Same, `monetary_conditioning=True` | −432 / −1,051 / −219 | peak −0.149% of GDP (q4) | BoE −0.2% to −0.35% after about a year |

Ratios are at q1 / q4 / q12.

Sizes come from HMRC's ready reckoner (June 2025, 2026-27 column, divided by four): £6.9bn a year for 1p on the basic rate, £5.35bn for 1pp on employee NICs, £8.8bn for 1pp of VAT. These are 2026-27 yields applied as a flat path from 2025Q1. The README's household row uses £1,616m a quarter for the same 1p; the ratios are the same (0.38 at q12).

The OBR multipliers are the interim OBR's June 2010 estimates, restated in EFO July 2015 Box 3.2, all tapering over five years. The Bank of England range is for a 1pp rise held for one year, from its 1999 Quarterly Bulletin ("The transmission mechanism of monetary policy"), which is the same experiment as row 6.

Receipts (`PSCR`) and central government net borrowing (`CGNB`) move one for one with the revenue in rows 2–4 (+1,725 / −1,725 for income tax; +1,337.5 / −1,337.5 for NICs; +2,200 / −2,200 for VAT, every quarter). There is no second round: lower consumption does not reduce other receipts. In rows 1 and 6 `PSCR` and `CGNB` do not move at all, so the extra government consumption does not appear in borrowing and borrowing does not respond to Bank Rate. Imports do not respond either: in rows 2–4 and 6 the GDP change equals the consumption change to the pound.

## One line on each

1. **Government consumption.** GDP rises by the shock and a little more (1.01 on impact, 1.05 by q12), because the shock enters the expenditure identity directly. Extra nominal GDP lands in profits, and a small part reaches consumption (+17m in q1, +60m by q12). This is accounting, not a multiplier: the OBR's figure is 0.6, fading. `published_conventions=True` imposes that convention as a labelled judgement adjustment (add-factor) path: 0.60 on impact, falling by 0.03 a quarter.
2. **Income tax.** The main live behavioural channel: household income to consumption. Household income falls by the revenue, and the published consumption equation lowers spending. Current-price GDP per pound is 0.10 on impact, 0.21 at q4 and 0.38 at q12 (0.16 averaged over year 1). The OBR's 0.3 is an impact multiplier that fades to zero. The order of magnitude is right but the profile is the reverse: consumption adjusts gradually to lower income, and nothing in the published equations (no output gap closing, no monetary response) pulls it back.
3. **NICs.** The same channel as income tax and the same ratios.
4. **VAT.** Receipts and borrowing move one for one, but GDP barely moves (0.026 at q4, 0.043 at q12). CPI is exogenous in the OBR's listing, so the model cannot pass VAT into prices. The tax lands on profits, and only the income the self-employed and partnerships draw from their businesses (quasi-corporation withdrawals), which follows profits, reaches households.
5. **Corporation tax rate.** Works through the cost of capital under the investment closure. Nothing moves in q1–q2, because the investment equation responds to the capital gap with a lag. Business investment then falls by 78m at q4, 240m at q8 and 384m at q12 (0.5% of its level), and GDP by the same amount (384m at q12, 0.05% of GDP). The run is 40% of the way to its plateau after 12 quarters (`df.attrs["investment_closure_plateau_fraction"]` = 0.40); the plateau is about £0.96bn a quarter, 1.2% of business investment. The OBR multiplier table this repo encodes has no corporation-tax row, so there is no sourced benchmark.
6. **Bank Rate.** Works through household interest flows and consumption only; corporate interest and the cost of capital do not respond (`df.attrs["cost_of_capital_channel"]`). The peak is −0.057% of GDP at q4. With `monetary_conditioning=True`, which moves the mortgage rate at the 0.9 pass-through in the OBR's own household-interest equation (line 623 of the listing), it is −0.149%. Both are smaller than the Bank of England's −0.2% to −0.35%: about a quarter of it unconditioned, about half with the mortgage rate moved.

## Caveats to state out loud

- **The model reproduces the OBR's equations, not its judgements.** Where the OBR adds a channel by judgement (price pass-through, monetary transmission, a multiplier convention), the emulator has no equation for it.
- **The default closure is this emulator's choice.** Under the closure as published, no quarter converges in a demand-closure run; the nominal-GDP pin is the OBR's own commented-out identity, switched on.
- **Government investment has no channel.** `IF` has no live equation in the OBR's listing, so a government-investment shock (`CGIPS`) leaves GDP unchanged, against the OBR's capital multiplier of 1.0. `run_reform` warns when you try.
- **VAT (#60).** The OBR's 0.35 is a judgement, not an output of its listing. #60 measured that passing the VAT rise into CPI (CPI raised 0.46% and held) makes the published consumption equation give 0.27–0.29 averaged over year 1 and 0.35–0.38 at q4, then keep rising to 0.64–0.72 by q12. The match with 0.35 at q4 is not a calibration, and the profile overshoots. That run is not repeated here.
- **Bank Rate.** About −0.16% is the ceiling even with mortgage and deposit rates both moved (measured in the 14 Nov review, not rerun here), because investment, sterling, house prices and gilt yields have no interest-rate equation (`docs/monetary_conditioning.md`). This is a property of the published equations, not a solver fault.
- **Household-tax ratio basis (#63).** Quote the current-price ratio (0.21 / 0.38) against the OBR's 0.3. Real GDP per pound of current-price revenue (0.19 / 0.33 in this run) mixes two bases and understates by the GDP deflator (a factor of 1.06 to 1.14 here).
- **Free-running scorecard.** The ~4% free-running GDP error in the README is a closure artifact of this emulator (GDP made endogenous, unpublished inputs seeded). It is not an OBR forecast error, and should not be presented as one.
- **Point estimates only.** There are no confidence bands.

## What not to run live, and what to say if asked

- **Government investment (`CGIPS`).** GDP does not move (see the caveat above). The README's reform CLI keeps it as a labelled dead channel.
- **Corporation tax as receipts (`NNSCTP`).** Receipts and borrowing move (+900 / −900) and GDP by exactly zero. Use `TCPRO` with the investment closure (row 5) instead.
- **The published closure (`nominal_gdp_pin=False`) in a demand-closure run.** No quarter converges. Row 5 also has `nominal_gdp_pin=False` but converges, because the investment closure holds the investment deflator.
- **Hosted results.** Do not show them until the hosted server's model pin moves from e4d7faa to current main: they come from the published closure (no quarter converges, CGG exactly 1.00) and will not match this page. That applies to `obr_shock` as well as `score_reform`. After the pin moves, start `score_reform` through `start_job` before the session: a 5-year score takes about 12 minutes (tracked in the hosted-server repo, #243).
- **Fuel duty** is supported (`TXFUEL`; +5% = 300 a quarter gives GDP −7 at q4, −11 at q12), but it is the VAT story at a seventh of the size.

## Business-investment bracket (#61)

- #61 corrects the business-investment equation's bracket and is on main. Corporation-tax deltas (row 5) were unchanged to the pound by it; only the unguarded zero-shock level path in the README moved.

## October 2026 EFO re-anchor

- Moving the baseline from the March 2026 EFO to the October 2026 EFO changes the shock figures by revision size only: GDP deltas by at most £9m a quarter (row 6b q4), the household ratio from 0.37 to 0.38 at q12, VAT from 0.044 to 0.043 at q12. Every baseline and shocked solve still converges in 12 of 12 quarters, and the same 82 equations are dropped.
