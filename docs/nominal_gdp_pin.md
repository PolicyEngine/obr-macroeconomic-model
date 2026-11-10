# The nominal-GDP pin (l.690)

`nominal_gdp_pin=True` (in `baseline.build`, `calibration_score.raw_solve` and
`build_scorecard`, `forecast.forecast` and `run_reform`; `--nominal-gdp-pin` on
the scorecard and forecast CLIs) swaps the l.688 nominal-GDP identity for the
OBR's commented-out l.690:

```
GDPMPS = PGDP * GDPM / 100
```

The default is the published closure. Issue #42 holds the decision on whether
to make the pin the default.

## The problem it solves

Three published equations involve nominal GDP and the investment deflator:

| Line | Equation | Status in the October 2025 code |
|---|---|---|
| l.114 | `IFPS = IF * PIF / 100` | live |
| l.337 | `PIF = (GDPMPS - CGGPS - CONSPS - DINVPS - VALPS - XPS + MPS - SDEPS) * 100 / IF` | live ("re-written to enable indirect T2 fix") |
| l.688 | `GDPMPS = TFEPS - MPS + SDEPS` | live |
| l.690 | `' GDPMPS = PGDP * GDPM / 100` | commented out |
| l.713 | `'PGDP = 100 * GDPMPS / GDPM` | commented out ("exogenised to enable indirect T2 fix") |

With l.114 and TFEPS (l.681) substituted in, l.337 and l.688 are the same
equation (published_model_review.md, G6). The pair (GDPMPS, PIF) is one
equation short. A Gauss-Seidel solve leaves PIF at whatever value it starts
from. In the de-seeded raw scorecard solve, which restarts each quarter from
the model's own previous value, PIF random-walks (106.7 → −4.6 → 317 against
an EFO path of about 105). Nominal GDP follows it, and company profits (a
residual of nominal GDP) swing by up to £235bn.

## Why the OBR commented out l.690

The listing and the OBR's documentation point the same way.

1. **The 2013 model was closed differently.** Briefing Paper No. 5 (OBR,
   October 2013) has nominal GDP as the expenditure identity
   (`GDPM£ = TFE£ – M£ + SDE£`, eq. 2.133), real GDP as an identity
   (eq. 2.139), the GDP deflator as the ratio of the two
   (`PGDP = 100*(GDP£/GDP)`, eq. 2.143) and PIF as an estimated behavioural
   equation (eq. 4.43). That system is exactly determined. l.690 was not
   needed, because PGDP was an output.
2. **The October 2025 code is in its "indirect T2 fix" configuration.** The
   OBR's own comments mark the switches: real GDP's identity is "switched off"
   (l.701–703) and DINV is its residual (l.17–19); PGDP is "exogenised"
   (l.711–713); PIF's estimated equation is commented out and PIF is
   "re-written" as the residual of nominal GDP (l.335–339). The variable
   dictionary agrees: GDPM (dict 530) and PGDP (dict 534) are "Exogenous / No
   Equation". The same pattern recurs for total investment (IF exogenous,
   IBUS residual, l.82–86), imports (M exogenous, MNOG residual, l.215) and
   spending (PSCE exogenous, CGSUBP residual, l.502). In each case a target
   the OBR forecasts outside the model is imposed, and one component is made
   the residual that absorbs it.
3. **Once GDPM and PGDP are both inputs, l.690 is redundant as an equation
   but true as a fact.** With both imposed, nominal GDP is fixed by
   definition. Keeping l.690 live alongside l.688 would give GDPMPS two
   equations. The OBR kept the expenditure form and made PIF the residual of
   it. That only determines PIF if nominal GDP is imposed as well. Briefing
   Paper No. 5 (paras 1.11–1.12) says imposed values "override" the
   placeholder equations in the code, so the most likely reading is that the
   OBR imposes its nominal-GDP forecast on GDPMPS in the working file, and
   PIF absorbs it. The release does not show this step.
4. **The published forecast obeys l.690.** In the EFO data shipped with this
   repo, `PGDP × GDPM / 100` equals GDPMPS to within 0.05% in every quarter
   from 2021Q1 to 2031Q1 (rounding). The l.337 residual reproduces the
   published PIF to within 0.3–0.7% over 2025Q1–2027Q4.

The label "T2 fix" is the OBR's and is not defined in the release or in
Briefing Paper No. 5. The reading above is inferred from the code comments and
the dictionary; it is not documented by the OBR.

## Is the pin consistent with how the OBR runs the model?

Partly, and the difference matters.

- **What matches.** In the OBR's configuration nominal GDP equals the imposed
  deflator times imposed real GDP, and PIF is the residual. The pin gives the
  same determination: PGDP is exogenous in this repo too (held at the EFO
  path), so the pin adds no assumption about the deflator. It removes the
  free PIF.
- **What differs.** This repo makes real GDP endogenous (`GDPM_EQ`, DINV held
  at its EFO path), so that shocks can move GDP. Under the pin, a shock that
  moves real GDP moves nominal GDP at an unchanged GDP deflator. Any mismatch
  between the deflators of the components (PCE, GGFCD and so on) and the fixed
  PGDP lands in PIF. That is a property of combining an endogenous GDPM with
  the OBR's exogenous PGDP; the OBR never faces it, because its GDPM is
  imposed too.
- **The alternative closure** holds PIF at its EFO path instead
  (`make_exogenous("PIF")`). l.688 then determines nominal GDP from its
  components and the implied deflator moves. This is what the investment
  closure in `reform_analysis.py` already does, for a separate reason. It is
  not the OBR's configuration, because PIF is a residual there and not an
  input. Both closures are tabled below.

The ~4.32% raw GDP error in the scorecard is a closure artifact of this
emulator (GDPM is exogenous in the OBR's published model). It is not an OBR
forecast error, under either closure.

## Results

Measured on 6 Nov 2026 on the March-2026 EFO vintage. Scripts and JSON are
in the round-2 session notes (`r2.py`, `score.json`, `forecast.json`,
`hh.json`, `cgg.json`, `r.json`, `debtu.json`).

### Raw calibration scorecard (2025Q1–2027Q4, de-seeded raw solve)

| Variable | Published closure | Nominal GDP pinned (l.690) | PIF held at EFO |
|---|--:|--:|--:|
| Real GDP (closure artifact, see above) | 4.32% | 4.16% | 4.19% |
| Consumption | 7.22% | 6.96% | 7.00% |
| Business investment | 15.28% | 8.38% | 9.80% |
| Unemployment rate | 1.01pp | 1.01pp | 1.01pp |
| RPI inflation | 1.71pp | 1.71pp | 1.71pp |
| Household income | 6.18% | 4.66% | 4.81% |
| Real household income | 5.94% | 4.42% | 4.57% |
| Company profits | 82.77% | **18.04%** | 23.71% |
| Current account (% of GDP) | 3.02 | 2.19 | 2.18 |
| Trade balance (% of GDP) | 0.69 | 0.68 | 0.68 |
| Within band | 6 of 11 | **7 of 11** | 7 of 11 |
| PIF range over the window | −4.6 to 317 | 106.8 to 114.3 | 102.7 to 107.4 (EFO) |
| `GDPMPS − PGDP·GDPM/100`, max | £337bn | 0 | £10.3bn |
| Expenditure identity gap, max | 0 | 0 | 0 |

Employment (a trivial identity) scores 0.00% in all three. Under the pin PIF
runs 3–6% above the EFO path, because real GDP does (the closure artifact).

### Held-add-factor forecast (anchored, 2026Q1–2027Q4)

The anchored forecast barely moves: real GDP 0.27% → 0.28%, consumption
0.19% both ways, unemployment 0.69pp both ways, business investment 13.32% →
10.00%, company profits 14.86% → 13.48%, current account 1.39% → 1.51% of
GDP, trade balance 0.25% both ways. Within band stays 6 of 8 (business
investment moves into band, the current account moves just out of it).

### Shock sweeps (run_reform machinery, 2025Q1–2031Q1, 25 quarters)

Every quarter of every pinned run exits on the convergence tolerance. Under
the published closure every quarter exits on the stall break (#38).

| | Published closure | Nominal GDP pinned |
|---|--:|--:|
| Household tax, rise + cut, max (% of peak) | 125% | 0.2% |
| Household tax, 4x vs 4 × 1x, max (% of peak) | 51% | 0.3% |
| Household tax, 12q rise, GDP at q24 | −853m | −93m (peak −533m at q11) |
| Household multiplier, year 1 / q11 | 0.145 / 0.342 | 0.145 / 0.330 |
| Bank Rate, peak GDP per 100bp (+25 / +100 / −100 / +200bp) | 0.138 / 0.061 / 0.064 / 0.076% | 0.058 / 0.057 / 0.059 / 0.057% |
| Bank Rate, 0.25pp × 4 vs 1pp, max (% of peak) | 180% | 1.0% |
| Bank Rate, GDP per 100bp at q8 / q16 / q24 | −0.015 / −0.012 / −0.038% | −0.008 / −0.003 / −0.001% |
| CGG +£1.25bn × 12q, rise + cut, max (% of peak) | 51% | 0.001% |
| CGG, GDP per £ of shock at q0 / q11 / q12 / q24 | 1.000 / 0.999 / 0.000 / −0.51 | 1.014 / 1.049 / 0.039 / 0.017 |
| CGG, max change in PIF | 11.3 (at q24) | 0.97 (in the window) |

Under the published closure, the +£1.25bn CGG run, the +25bp, +100bp and
+200bp Bank Rate runs all show the same late jump in PIF (about +11 index
points at q24), which moves GDP by £0.6bn. That is the free PIF, not the
shock.

**What the pin changes for a spending shock.** Under the published closure a
CGG shock is pure passthrough (multiplier 1.000), because nominal GDP does not
respond at all. CGGPS has no equation, so a real CGG shock with nominal
spending held lowers the deflator GGFCD (l.383) instead. Under the pin,
nominal GDP rises at the fixed PGDP. Wages are exogenous, so the extra
nominal income goes almost entirely to company profits (FYCPR +£1.33bn per
£1.25bn of CGG). Household income rises by about £170m a quarter,
consumption follows (+£17m on impact, +£59m by q10), and the
multiplier rises from 1.014 on impact to 1.049 by q11. When the shock ends, it
drops to 0.039 and decays to 0.017 by q24. With the real-only shock, PIF
absorbs the nominal gap (+0.94 index points per £1.25bn). Shocking CGGPS by
`shock × GGFCD/100` as well, so the shock is consistent in nominal terms,
removes the PIF move (at most 0.015) and leaves GDP almost unchanged
(1.013 → 1.042, then 0.031 at q12). So the multiplier above 1 is the model's
income side, live for the first time, and not a PIF artifact. Under the
published closure the same nominal-consistent shock is erratic: +£445m at
q16, four quarters after the shock ends, with PIF −3.6.

If the pin becomes the default, `test_temporary_government_consumption_shock_ends_when_it_ends`
and the CGG multiplier gates, which expect exactly 1.000, will need
re-pinning. A 4-quarter shock now leaves a +£19m tail (1.5%) that decays to
+£2.6m by q24.

### DEBTU (#43) on top of the pin

Adding the re-pulled DEBTU column (115 quarters to 2025Q4; snapshot not
committed) moves the pinned scorecard a little: real GDP 4.16% → 4.38%,
consumption 6.96% → 7.32%, household income 4.66% → 4.70%, real household
income 4.42% → 4.46%, company profits 18.04% → 19.39%; business investment,
the current account, the trade balance, LFSUR and RPI do not move. Within
band stays 7 of 11. Under the published closure the same column moved company
profits 82.77% → 38.17% and the current account 3.02 → 3.49% of GDP. Those
moves were PIF drift, not DEBTU.
