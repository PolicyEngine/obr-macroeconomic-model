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

## Result — forecast fit 2024–2025, projected 2026–2027, vs the OBR

| Variable | Error (held-AF forecast) | vs raw model |
|---|--:|---|
| Real GDP | 1.23% | was 3.98% |
| Consumption | 1.92% | was 6.63% |
| Company profits | 1.06% | — |
| Real household income | 5.06% | was 12.84% |
| Household income | 5.68% | now computed (was dead) |
| Unemployment rate | 0.45pp | now computed (was dead) |
| Employment | 0.00% | computed |
| Trade balance | 12.94% | now computed |
| Business investment | 18.00% | poor |
| Current account | 27.98% | **finite** (was 1e140) |

**10 of 16 headline variables computed; 7 of those within 10%.** No explosions —
the financial blocks are bounded by their real data.

## Honest status

- The macro core (GDP, consumption, profits, real income, unemployment,
  employment) forecasts within ~10% over a two-year projection. This is a
  working forecasting framework.
- Still poor: business investment (18%), trade balance (13%), current account
  (28%) — finite and in the right ballpark, but the add-factor base window or the
  block calibration needs refinement.
- A few remain passthrough (exports, imports, CPI) — exogenous in this setup,
  held at the OBR value.

The earlier "the financial blocks can't be found and diverge without data" was
wrong on both counts: most are published by ONS, and their data stabilises them.
The remaining gap is refinement, not a hard wall.
