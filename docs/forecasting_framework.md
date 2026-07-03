# Forecasting framework (held add-factors)

The OBR's own method, now implemented: compute add-factors (residuals) over a
base window of recent data, **hold them constant**, and project the model
forward. The forecast is the model's structural dynamics anchored by the held
add-factors — a genuine forecast, not a reproduction of the input.
(`obr_macro/forecast.py`.)

## The data that made it work

The dead/exploding financial blocks turned out to be **findable**: of the 261
endogenous variables the model referenced but the EFO did not publish, **199 had
ONS codes**. Pulling their observed series (`ons_pull.py`, now widened to all
findable variables → **348-series snapshot**) gave the circular fiscal/financial
sub-blocks real balancing data. They stopped diverging.

## Result — forecast fit, base 2024Q1–2025Q4, projected 2026Q1–2027Q4, vs the OBR

Net balances scored as % of GDP; everything else as MAPE (%) or abs pp.

| Variable | Error (held-AF forecast) | band |
|---|--:|---|
| Real GDP | 2.22% | within |
| Consumption | 3.55% | within |
| Employment | 0.00% | **trivial identity** |
| Unemployment rate | 0.75pp | within |
| Real household income | 12.00% | over |
| Household income | 11.57% | over |
| Business investment | 17.85% | **over** |
| Company profits | 47.42% | **over** |
| Trade balance | 0.11% of GDP | within |
| Current account | 0.88% of GDP | within |

**10 of 16 headline variables computed; 6 of those within 10% (net balances as
% of GDP).** No explosions — the financial blocks are bounded by their real data.

## Two honesty caveats on this headline

1. **Jump-off dependency.** The forecast is initialised at the EFO values it is
   then scored against (the solver seeds each period from the published series).
   That flatters the fit: a neutral jump-off (starting from the model's own prior
   solution) scores worse, and business investment in particular fails the band.
   The number here is best read as "how far the held-add-factor dynamics drift
   from the OBR path once anchored at it", not a from-scratch forecast.
2. **Employment is a trivial identity** (`ETLFS = HWA/AVH`, both passthrough
   inputs), not an independent behavioural channel — so the "within band" count
   includes one free pass.

## Honest status

- The macro core (GDP, consumption, unemployment) forecasts within ~10% over a
  two-year projection. This is a working forecasting framework for those channels.
- **Over band: business investment (~18%), company profits (~47%), household
  income (~12%).** These are finite and in the right ballpark but not usable yet.
- A few remain passthrough (exports, imports, CPI) — exogenous in this setup,
  held at the OBR value.

### Why these numbers regressed from earlier versions of this doc

Earlier drafts of this file reported a much better fit (GDP 1.2%, business
investment 7.4%, "10/10 within band"). Those figures rested on two bugs since
fixed, and correcting them is what moved the scores:

- **Fiscal-input seasonality.** Non-seasonally-adjusted cash series were held
  flat at their *last observed quarter* across the whole forecast — e.g. CGT
  frozen at its £22.5bn Q1 peak instead of its ~£6bn quarterly average. That
  frozen level fortuitously sat near the EFO on some channels. Extrapolating at
  the trailing annual mean (the correct deseasonalised level) removed that free
  alignment.
- **Silently-dead equations revived.** The mixed-case financial-account block,
  `CGC`, and the ratio-lag deflators were being dropped by parser bugs and
  silently skipped. They are now alive — but *not yet add-factor calibrated*, so
  they currently pull business investment and profits off band.

So the honest position is: the framework is sound, the earlier headline was
fragile, and the remaining gap is per-block add-factor calibration on equations
that are now (correctly) live rather than silently dead.

## Tuning the three poor channels (forecast_tune.py) — historical

> The three subsections below record the investigation that led to the earlier
> (now superseded) headline. The specific percentages predate the
> seasonality/parsing fixes; read them as method, not current scores.

Swept the add-factor window (8q/4q/2q/1q) and the investment closure to push
business investment, trade balance and current account under 10%. Result —
**a global knob can't do it:**

| config | Bus. inv. | Trade bal. | Curr. acc. | within 10% |
|---|--:|--:|--:|--:|
| mean 8q | 18.0% | 12.9% | 28.0% | 7/10 |
| mean 4q | 11.1% | 20.4% | 26.7% | 7/10 |
| mean 2q | 19.5% | 28.1% | 35.0% | 7/10 |
| last 1q | 13.4% | 97.4% | 51.6% | 7/10 |
| + investment closure | 350%+ | 29%+ | 35%+ | 5/11 |

- The **investment closure backfires** (business investment → +350%) — drop it.
- Windows **conflict**: investment wants 4q (→11%), trade balance wants 8q (→13%),
  current account is ~27% either way. The 7/10 hit rate never improves.

**The three are structural, not tuning.** Business investment (volatile), the
trade-volume split (exports/imports are passthrough), and the investment-income/
financial-flow block behind the current account need per-block calibration, not a
global add-factor setting. The forecasting core stays at 7/10 within 10%.

## Structural fix: the @TREND lambda bug (8/10 within 10%)

Tracing the trade balance found a real bug: the transpiler emits `@TREND` as
`_trend(t, 'base')` (two args) but the solver's context lambdas were
`lambda base:` (one arg), so **every @TREND equation threw and was silently
skipped** — including both trade-price deflators (`dlog(PXNOG)`, `dlog(PMNOG)`),
which froze flat while the OBR's deflators inflated. Fixing the lambda signatures
(and proxying the absent world-price assumption `WPG` with producer prices so the
deflator equations have finite inputs) revived them:

| Variable | before | after |
|---|--:|--:|
| Business investment | 18.0% | **7.4%** |
| Trade balance | 12.9% | **10.8%** |
| Current account | 28.0% | **17.8%** |
| **within 10%** | 7/10 | **8/10** |

Held add-factors are intentionally not applied to the @recode/@TREND equations:
they overshoot (trade balance 29% with them vs 11% without), so those equations
project structurally. Trade balance (10.8%) and current account (17.8%) remain
just over — the residual gap is the financial/investment-income block. 6/6 tests
pass.

## Net balances are scored as % of GDP

Trade balance and current account look poor under a %-error against a tiny *net*
balance (a difference of two ~£240bn gross flows) — a 0.3% miss on gross exports
becomes ~10% on the £7bn trade balance. Scored the way the OBR reports them, as a
share of GDP, both sit well inside normal tolerance (current account 0.88% of
GDP, trade balance 0.11% of GDP). This is a legitimate metric — **but it is now
applied consistently in both the forecast scorecard and the raw calibration
scorecard** (`calibration_score.py`), not only where it improves a headline.

> **Superseded:** earlier revisions of this doc concluded "**10/10** of the
> computed macro core within band" on the strength of these %-of-GDP balances
> *plus* a set of channel scores (GDP 1.3%, business investment 7.4%, profits
> 5.4%) that have since been shown to depend on the fiscal-seasonality data bug
> and the silently-dead equations described above. With both fixed, the current
> honest count is **6/10 within band** (see the result table at the top). The
> %-of-GDP scoring of the net balances stands; the "10/10" headline does not.
