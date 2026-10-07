# The OBR's published macroeconomic model: a point-by-point check

This document checks a list of 53 points raised about the OBR's published macroeconomic model (the "OBR model – list of issues" note circulated in September 2026). For each point it gives:

1. **Verdict on the OBR's code:** whether the point is true of the model the OBR publishes, and why, with line references.
2. **Our adapted model:** how PolicyEngine's Python replication ([PolicyEngine/obr-macroeconomic-model](https://github.com/PolicyEngine/obr-macroeconomic-model)) handles the same point.

**Sources.** All verdicts are checked against the OBR's own published files: the EViews model code (`obr_model_code_october_2025.txt`) and the variable list (`obr_model_variables_october_2025.xlsx`), both dated 15 October 2025. On 7 October 2026 these were still the latest files on obr.uk. "l." means a line in the code file and "Dict" means a row in the variable list. A line starting with `'` is commented out in EViews and does not take part in the solve.

**What the verdicts mean.**

| Verdict | Meaning |
|---|---|
| True but openly documented | Accurate. The variable list or code comments identify this as a choice. |
| True | Accurate, and the code or variable list does not flag it as a deliberate choice. This covers both undocumented modelling choices (most entries) and errors in the code as printed (G6, G7, N5, V5); the summary below separates them. |
| Partly true | Part of the point holds; the rest is contradicted by the code or cannot be checked from it. |
| Can't be checked from the code | A claim about the OBR's forecasting process outside the model file. |

| Our adapted model | Meaning |
|---|---|
| Inherited | Our replication behaves as the OBR's code does. |
| Changed | We altered the closure or equations, explained in the entry. |
| Bypassed by accident | The equation does not run in our build, usually because an input has no published data. |
| Not applicable | The point is outside what our replication models. |

**Scope.** The published model is the OBR's framework for keeping its forecast consistent across the economy and the public finances. The OBR forecasts GDP, trade, prices and receipts using other models and judgement, then imposes them as inputs. Many points below describe that design. Whether that design is a good one is a separate question from whether the published code works as printed, and the verdicts try to keep the two apart.

## Summary

Of the 53 points, 42 are accurate descriptions of the code (22 openly documented, 20 not flagged), 8 are partly true and 3 cannot be checked from the code.

The points that identify problems in the published files (code or variable list), rather than design choices, are:

- **G7.** Unemployment is undetermined: the unemployment and participation identities (l.163, l.175) are the same equation rearranged.
- **G6.** Nominal GDP and the investment deflator are one equation short: l.337 and l.688 are the same identity.
- **N5.** Apparent sign error in the foreign-currency lending term of the corporate FISIM equation (l.637), which adds a lagged term that the neighbouring equations subtract.
- **G13.** The variable list's equation types disagree with the code for several entries (PIF, MNOG, SDI, PRODH, HWA, and the commented-out weights W1, W4, W5 and I4–I12).
- **V5 / R4.** Pre-Brexit EU contribution equations are still live.

G6 and G7 leave nominal GDP/investment deflator and unemployment/participation not uniquely determined without settings that are not in the release. The OBR's workfile may resolve these; the release does not show how.

Among the design choices, the one with the clearest behavioural consequence is H3: household interest payments respond to Bank Rate (l.623) while household interest receipts are exogenous, so in the code a rate rise lowers household income even though households receive more interest than they pay.

| # | Critic's point | Their rating | Verdict on the OBR's code | Our adapted model |
|---|---|---|---|---|
| G1 | Real GDP exogenous; inventories absorb any gap between modelled demand and imposed output. | High | True but openly documented | Changed |
| G2 | Five-year multiplier taper imposed off-model; attributed to monetary policy, exchange rate a… | High | Partly true | Changed |
| G3 | CPI has no active equation; producer prices exogenous; retail and wholesale margins computed… | High | True but openly documented | Inherited |
| G4 | Fiscal forecast uses pre-measures interest-rate curve while GDP path assumes an offsetting p… | High | Can't be checked from the code (process claim) | Not applicable |
| G5 | Taper implications for temporary measures undocumented. | Mid | Can't be checked from the code (process claim) | Changed |
| G6 | Published code does not close: nominal GDP and investment deflator defined by the same ident… | Mid | True | Inherited |
| G7 | Unemployment and participation identities duplicated; unemployment undetermined as printed. | Mid | True | Inherited |
| G8 | Two employment measures unreconciled: hours-based total drives unemployment, behavioural mar… | Mid | True | Inherited |
| G9 | Potential output exogenous; output gap computed but feeds no equation. | Mid | True but openly documented | Inherited |
| G10 | Supply effects limited to public investment and individually scored policies; demand-led hys… | Mid | Can't be checked from the code (process claim) | Inherited |
| G11 | Multiplier ranking (public services 0.45, welfare 0.6) inconsistent with model's import-cont… | Mid | Partly true | Changed, with an open discrepancy |
| G12 | Investment deflator is a residual; propagates to public and business investment volumes and … | Mid | True but openly documented | Inherited in the standard setup |
| G13 | Only comprehensive prose description dates from 2013; variable dictionary contradicts code i… | Mid | True | Not applicable |
| G14 | Bank Rate follows market curve; exchange rate held flat. | Low | Partly true | Inherited |
| G15 | Several constants expressed in nominal £m levels. | Low | True | Inherited |
| G16 | Four-quarter identities carry last historical quarterly pattern through forecast. | Low | True | Inherited |
| G17 | Ratios of interest rates in some equations unstable near zero. | Low | True | Inherited |
| G18 | Deterministic time trends extrapolated in trade-price and other equations. | Low | True | Inherited |
| G19 | Cost indices use 2009 input-output weights; gas and electricity prices listed but unused. | Low | Partly true | Inherited |
| G20 | Add factors attached to identities (household benefits, taxes, contributions). | Low | True but openly documented | Changed |
| G21 | Several computed blocks feed no equation (cost indices, relative prices, home improvements). | Low | Partly true | Changed in part |
| H1 | Single aggregate consumption function; no distributional dimension. | Mid | True but openly documented | Inherited |
| H2 | Long-run consumption elasticities sum to 0.77; consumption-to-income ratio drifts downward. | Mid | True | Inherited |
| H3 | Interest payments modelled from stocks and rates; interest receipts exogenous. | Mid | True but openly documented | Inherited |
| H4 | DB pension entitlements revalue with gilt yields, affecting consumption through financial we… | Mid | True but openly documented | Inherited |
| H5 | Mortgage debt and house prices exogenous. | Mid | True but openly documented | Inherited |
| H6 | Employer social contributions fully shifted onto wages in the long run by coefficient restri… | Mid | True | Inherited |
| H7 | Short-run income elasticity 0.10; real interest rate effect negligible. | Low | True | Inherited |
| H8 | Financial balance sheet closes on residual 'other assets'. | Low | True but openly documented | Inherited |
| H9 | Deposit equation contains highly convex exponential terms; error-correction mixes adjusted a… | Low | Partly true | Inherited |
| H10 | Insurance asset acquisition driven only by the insurance premium tax rate. | Low | True | Bypassed by accident |
| H11 | Durables user cost inside a logarithm; undefined if quarterly durable inflation is high. | Low | True | Inherited |
| N1 | Business investment equation switched off; investment is residual of exogenous total investm… | High | True but openly documented | Changed |
| N2 | Cost-of-capital block unused; capital allowances cannot affect investment in code. | Mid | Partly true | Changed |
| N3 | Financial account not linked to net lending; balance sheet not stock-flow consistent. | Mid | True | Inherited |
| N4 | Profits are income-side residual, absorbing errors from other residuals. | Mid | True but openly documented | Inherited |
| N5 | Probable sign error in FISIM equation on FX lending; implies cumulative drift in profits. | Mid | True as printed | Bypassed by accident |
| N6 | No income account; interest costs do not affect dividends or retained earnings. | Low | True | Inherited |
| N7 | Stock appreciation derived from residual inventory series. | Low | True but openly documented | Changed |
| N8 | Financial asset equation subtracts change in money holdings; rationale unclear. | Low | True | Inherited |
| F1 | No balance sheet for banks or other financial corporations; net lending calibrated. | Mid | True but openly documented | Inherited |
| F2 | No central bank balance sheet; reserves remuneration absent from code. | Mid | True but openly documented (outside the macroeconomic model's scope) | Inherited |
| F3 | Broad money is a sum of independently determined series. | Low | True but openly documented | Inherited |
| V1 | Most tax receipts exogenous; no automatic stabilisers within the code. | Mid | True but openly documented | Inherited |
| V2 | Debt interest and gilt stock exogenous; no in-code link to rates or borrowing. | Mid | True but openly documented | Inherited |
| V3 | Total current spending exogenous; product subsidies computed as residual, feeding basic pric… | Mid | True but openly documented | Bypassed by accident |
| V4 | Two exogenous government consumption series share one ONS code; equality not enforced. | Low | True | Inherited |
| V5 | EU-budget payment equations remain live; formulas dimensionally questionable. | Low | True | Inherited |
| V6 | Add factor on seasonally adjusted borrowing shifts corporate net lending without affecting d… | Low | True but openly documented | Bypassed by accident |
| R1 | Export and import volumes exogenous; world trade series maintained but unused. | High | True but openly documented | Inherited |
| R2 | Exchange rate exogenous; current account and external position feed no equation. | Mid | Partly true | Inherited |
| R3 | Services import equation only reallocates a fixed import total between goods and services. | Low | True but openly documented | Inherited |
| R4 | Secondary income retains EU-era transfer items. | Low | True | Inherited |

## General


### G1. "Real GDP exogenous; inventories absorb any gap between modelled demand and imposed output." (High)
- **Verdict:** True but openly documented
- **Why:** Dict 530 lists GDPM as "Exogenous / No Equation". The expenditure identity is commented out at l.703 (`'GDPM = TFE - M + SDE`, with the note "Switched off to enable indirect T2 fix"). The inventory change is then computed as the residual at l.19: `DINV = (GDPM + M - SDE) - CGG - CONS - VAL - IF - X`. Any movement in modelled demand therefore changes stockbuilding, not GDP.
- **Our adapted model:** Changed. `obr_macro/baseline.py` calls `swap_closure("DINV", GDPM_EQ)`, which drops the DINV residual and makes GDP the sum of its expenditure components (`GDPM_EQ` in `obr_macro/reform_analysis.py`). Demand changes then reach GDP in our version. The closure is ours, not the OBR's.

### G2. "Five-year multiplier taper imposed off-model; attributed to monetary policy, exchange rate and real wages, none of which can affect output in the model." (High)
- **Verdict:** Partly true
- **Why:** The taper is an OBR convention published outside the model file. The OBR's article "Dynamic scoring of policy measures in OBR forecasts" (November 2023) says multipliers "taper to zero over five years" because of monetary policy, the exchange rate and real wages. The code does contain the first and third channels, which reach demand components: Bank Rate R enters consumption (l.4) and durables (l.8), and real wages reach consumption via PSAVEI → WFP (l.589) → HHDI (l.654) → RHHDI. The exchange rate RX moves only prices, because exports and imports are exogenous (dict 110, 134). So the channels exist in the code and reach demand components (except the exchange rate, which reaches only prices); they cannot reach output because GDP is exogenous (G1) and the inventory residual absorbs any change. The point is true for output and overstated for the channels themselves.
- **Our adapted model:** Changed. `obr_macro/published_conventions.py` imposes the OBR's published impact multipliers with a 20-quarter taper to zero. The linear shape between impact and zero is our choice, because the OBR publishes only the end points. See methodology.

### G3. "CPI has no active equation; producer prices exogenous; retail and wholesale margins computed as residuals." (High)
- **Verdict:** True but openly documented
- **Why:** The CPI equation is commented out at l.314. Dict 185 shows CPI with "No Equation" (typed "Calibrated/technical relationship"). The producer price equation is commented out at l.286, and dict 165 lists PPIY as Exogenous. Both margins are backed out from the imposed prices: wholesale margins at l.280 (`MKGW = 100*(PPIY/(MCOST/100))/PPIYBASE`) and retail margins at l.284 (`dlog(MKR) = (dlog(CPI) - W1*dlog(CPIRENT) - (1-W1)*dlog(RPCOST))/(1-W1)`). CPI still drives the consumer expenditure deflator through l.333.
- **Our adapted model:** Inherited. CPI and PPIY are taken from the data as inputs, and the margin identities are solved as published.

### G4. "Fiscal forecast uses pre-measures interest-rate curve while GDP path assumes an offsetting policy response." (High)
- **Verdict:** Can't be checked from the code (process claim)
- **Why:** The model file holds no fiscal-forecast conditioning: Bank Rate R is exogenous (dict 459), and nothing in it records which market curve is used. The point can be settled from the conditioning-assumptions section of the relevant Economic and fiscal outlook, which gives the date of the market-curve snapshot, and from the dynamic-scoring article.
- **Our adapted model:** Not applicable. We take R as an exogenous input path and do not produce a fiscal forecast in which this choice arises.

### G5. "Taper implications for temporary measures undocumented." (Mid)
- **Verdict:** Can't be checked from the code (process claim)
- **Why:** The taper is not represented in the model file. The OBR's November 2023 dynamic-scoring article describes the taper for policy measures in general. In our reading it says nothing specific about temporary measures, but that should be confirmed against the full set of OBR costing documents.
- **Our adapted model:** Changed (convention only). `obr_macro/published_conventions.py` starts the taper at the shock start, treating announcement and implementation as the same date. It has no separate treatment for temporary measures.

### G6. "Published code does not close: nominal GDP and investment deflator defined by the same identity." (Mid)
- **Verdict:** True
- **Why:** The investment deflator at l.337 is `PIF = (GDPMPS - CGGPS - CONSPS - DINVPS - VALPS - XPS + MPS - SDEPS)*100/IF`. Substituting IFPS = IF·PIF/100 (l.114) and TFEPS (l.681) into nominal GDP at l.688 (`GDPMPS = TFEPS - MPS + SDEPS`) gives l.337 again. The two equations are one identity, so nominal GDP and PIF are not separately determined. The alternative pin, `GDPMPS = PGDP*GDPM/100` at l.690, is commented out. The "indirect T2 fix" comments suggest the OBR fixes nominal GDP in its working file in a way the published file does not show.
- **Our adapted model:** Inherited. The equations have different left-hand sides, so our duplicate-equation check does not flag them, and the iterative solver keeps whatever starting value PIF has. In a test on 2026Q1, raising the PIF starting value by 5% moved nominal GDP by about £13bn and the change persisted. When the investment closure is used, `obr_macro/reform_analysis.py` holds PIF at its baseline path, for a separate stability reason.

### G7. "Unemployment and participation identities duplicated; unemployment undetermined as printed." (Mid)
- **Verdict:** True
- **Why:** l.163 (`ULFS = (POP16*PART16/100) - ETLFS`) and l.175 (`PART16 = 100*(ULFS + ETLFS)/POP16`) are the same identity rearranged. Dict 98 and 105 type both as identities. With employment given, one of ULFS or PART16 has to be set from outside the model, and the published file does not say which.
- **Our adapted model:** Inherited. In effect our solver treats participation as given at its starting value, which comes from the data path. That is probably close to OBR practice, but it is not stated in the published file. In a test on 2026Q1, raising the PART16 starting value by 2% raised the unemployment rate from 5.4% to 7.3%, and the change persisted.

### G8. "Two employment measures unreconciled: hours-based total drives unemployment, behavioural market employment drives wage bill." (Mid)
- **Verdict:** True
- **Why:** Total employment comes from hours: `ETLFS = 1000*(HWA/AVH)` (l.153). That feeds unemployment (l.163, l.165). Market-sector employment EMS has its own estimated equation (l.145) and drives the private wage bill WFP (l.589), average earnings PSAVEI (l.232) and unit labour costs ULCPS (l.240). No equation links EMS to ETLFS or to private-sector employment EPS (l.143), and EPS feeds no other equation.
- **Our adapted model:** Inherited. Both employment measures are solved as published, with no reconciliation added.

### G9. "Potential output exogenous; output gap computed but feeds no equation." (Mid)
- **Verdict:** True but openly documented
- **Why:** Dict 551 lists trend output TRGDP as "Exogenous / No Equation". The output gap is computed at l.743 (`GAP = GDPM/TRGDP*100 - 100`), but no other equation in the file uses GAP. It is a reporting variable.
- **Our adapted model:** Inherited. TRGDP is an input path and GAP is computed but not used. Because no equation responds to the output gap, nothing in the model brings a demand shock back to zero. That is why we use the published taper convention (G2).

### G10. "Supply effects limited to public investment and individually scored policies; demand-led hysteresis excluded." (Mid)
- **Verdict:** Can't be checked from the code (process claim)
- **Why:** How far supply-side effects are scored is a methodological choice described in OBR publications, such as the dynamic-scoring article and policy costing notes. It is not set in the model file. The code is consistent with the claim: trend output is exogenous (dict 551), and no equation carries a demand shock into potential output.
- **Our adapted model:** Inherited. We have no supply-side or hysteresis channel either.

### G11. "Multiplier ranking (public services 0.45, welfare 0.6) inconsistent with model's import-content weights." (Mid)
- **Verdict:** Partly true
- **Why:** The figures match the OBR's November 2023 dynamic-scoring article: public investment 1.00, public services 0.45, welfare 0.60, tax 0.33. In the code, the import-content weights are 0.257 for consumption (l.195) and 0.094 for government consumption (l.197). On import leakage alone, public services would therefore rank above welfare, which reaches demand through consumption. However, these weights feed only the import-intensity indicator MINTY (l.209), which no other equation uses, because total imports are exogenous (dict 134). The ranking is set off-model, so it is a judgement rather than something the model's weights determine.
- **Our adapted model:** Changed, with an open discrepancy. `obr_macro/published_conventions.py` uses 0.6 for current (public services) spending, citing the OBR's July 2015 EFO Box 3.2. The OBR's 2023 article gives 0.45. This is unresolved in our repo, and the related warning text in `obr_macro/reform_analysis.py` is based on 0.6.

### G12. "Investment deflator is a residual; propagates to public and business investment volumes and public net worth." (Mid)
- **Verdict:** True but openly documented
- **Why:** PIF is the residual at l.337 ("re-written to enable indirect T2 fix"), and the estimated deflator equation is commented out at l.339. PIF feeds the government investment deflator (l.100). That gives real government investment GGI (l.96) and therefore business investment IBUS (l.84), the business investment deflator PIBUS (l.124), and public tangible assets PSTA (l.555) and net worth PSNW (l.557). Dict 198 types PIF as "Econometrically estimated", which no longer matches the code (see G13).
- **Our adapted model:** Inherited in the standard setup. Under the investment closure, `obr_macro/reform_analysis.py` holds PIF at its baseline path to stop deviations compounding through GGIDEF.

### G13. "Only comprehensive prose description dates from 2013; variable dictionary contradicts code in places." (Mid)
- **Verdict:** True
- **Why:** The OBR's model page says the released code is "a more recent version of the model than that detailed in Briefing Paper No.5", the 2013 description. The dictionary disagrees with the code in at least these places:
  - PIF (dict 198) is typed "Econometrically estimated", but its live equation is an identity (l.337).
  - MNOG (dict 130) and SDI (dict 536) are typed "Exogenous" but have live equations (l.217, l.717).
  - PRODH is typed "Exogenous" but has an identity at l.171.
  - HWA (dict 101) is typed "Identity" with no equation (l.169 is commented out).
  - The cost-index weights W1, W4, W5 and I4–I12 are typed "Identity", but their definitions are commented out (l.292–308), although W1 is used at l.284.
  - The equation cell for LFSUR (dict 99) also contains the PRODH identity.
- **Our adapted model:** Not applicable. We parse equations from the code file and do not rely on the dictionary's equation types.

### G14. "Bank Rate follows market curve; exchange rate held flat." (Low)
- **Verdict:** Partly true
- **Why:** Bank Rate R (dict 459) and the sterling effective exchange rate RX (dict 344) are both exogenous, so their paths are imposed. The model file cannot show whether RX is held flat or follows another convention, such as interest-rate parity. The conditioning-assumptions section of the relevant Economic and fiscal outlook would settle that part.
- **Our adapted model:** Inherited. Both are input paths. Our data loader forward-fills series past their last published value (`obr_macro/data.py`), so a flat RX in our databank is not evidence of the OBR's convention.

### G15. "Several constants expressed in nominal £m levels." (Low)
- **Verdict:** True
- **Why:** Several equations contain fixed cash constants that do not scale with prices or the size of the economy. Examples are l.672 (`NAFFC = -12012 + ...`), l.725 (`OSHH = 12874 + ...`), l.779 (233379.6), l.783 (−12867), l.791 (13293.71) and l.912 (`NALIC = -27362 + ...`). The relative weight of these constants changes as nominal values grow over the forecast.
- **Our adapted model:** Inherited. `docs/calibration_scorecard.md` notes that the 12874 constant in the household operating-surplus equation (l.725) explains part of our gap on that series.

### G16. "Four-quarter identities carry last historical quarterly pattern through forecast." (Low)
- **Verdict:** True
- **Why:** `PCE/PCE(-4) = CPI/CPI(-4)` (l.333) carries the last observed year's quarterly gap between the consumer expenditure deflator and CPI forward indefinitely. The same applies to the notes-and-coin equation (l.565) and the non-seasonally-adjusted financial balances (l.768, l.836). Four-quarter averages also appear at l.389, l.512 and l.514.
- **Our adapted model:** Inherited.

### G17. "Ratios of interest rates in some equations unstable near zero." (Low)
- **Verdict:** True
- **Why:** l.416, `d(CGC)/CGC(-1) = 0.21*d(ROCB)/ROCB(-1)`, scales by the proportional change in the world short rate, which becomes very large as ROCB approaches zero. l.316 uses `RMORT/RMORT(-1)` in the same way. Neither equation has a guard against rates near zero.
- **Our adapted model:** Inherited. No guard has been added.

### G18. "Deterministic time trends extrapolated in trade-price and other equations." (Low)
- **Verdict:** True
- **Why:** `@TREND` terms appear in the export price equation (l.323), the import price equation (l.327), compensation paid abroad (l.457) and households' other assets (l.799). These trends continue mechanically through the forecast period.
- **Our adapted model:** Inherited.

### G19. "Cost indices use 2009 input-output weights; gas and electricity prices listed but unused." (Low)
- **Verdict:** Partly true
- **Why:** The cost indices at l.262–276 are normalised to 2009 averages (base terms at l.248–260). That their weights come from 2009 input-output tables is plausible but cannot be confirmed from the code. Gas prices (GAS, dict 204) and wholesale electricity prices (PELEC, dict 205) are listed in the dictionary but appear nowhere in the code, not even in a commented-out line.
- **Our adapted model:** Inherited. Because the 2009 history needed for the base terms is not in our data, `obr_macro/full_solver.py` sets those normalising constants directly.

### G20. "Add factors attached to identities (household benefits, taxes, contributions)." (Low)
- **Verdict:** True but openly documented
- **Why:** `@ADD(V)` add factors are attached to the identities for social benefits SBHH (l.610), household taxes TYWHH (l.613), employee contributions EESC (l.652), public sector net borrowing PSNBCY (l.539), nominal GDP MGDPNSA (l.693) and the mortgage-interest price index PRMIP (l.317). This is consistent with the OBR's statement that tax receipts and similar fiscal forecasts are produced outside the model and imposed on it.
- **Our adapted model:** Changed. Our add factors anchor behavioural equations rather than these identities. In the anchored baseline, household disposable income is held at its published path instead (`obr_macro/baseline.py`, `_PUBLISHED_LEVEL_ANCHORS`). See methodology.

### G21. "Several computed blocks feed no equation (cost indices, relative prices, home improvements)." (Low)
- **Verdict:** Partly true
- **Why:** The cost-index block feeds nothing in practice. MCOST feeds only the wholesale margin MKGW (l.280), which no equation uses. RPCOST feeds the retail margin and CPIX (l.288), which feeds only its own 2009 base term. ICOST, XGCOST and XSCOST (l.272–276) are unused. Among relative prices, RPRICE (l.186) and PMGREL (l.213) are unused, but PMSREL (l.221) does feed services imports (l.223). Home improvements HIMPROV (l.102) feeds nothing. The cost-of-capital chain (TAF, COC, KSTAR, KGAP at l.50–76) also feeds nothing, because the business investment equation that would use it is commented out at l.92 (that line is also missing a closing parenthesis).
- **Our adapted model:** Changed in part. `obr_macro/reform_analysis.py` (`IBUSX_EQ`) reconstructs the commented-out business investment equation at l.92, with the parenthesis restored, for corporation-tax scoring. The other unused blocks are solved as published and have no effect.

## Households

References: "L" = line in the OBR's published EViews code (`obr_model_code_october_2025.txt`); "D" = row number in the OBR variable dictionary (`obr_model_variables_october_2025.xlsx`). Figures computed from the printed coefficients and our ONS snapshot (`obr_macro/seeds/ons_exogenous_snapshot.csv`, 2025Q4–2026Q1).

### H1. "Single aggregate consumption function; no distributional dimension." (Mid)
- **Verdict:** True but openly documented
- **Why:** Consumption is a single equation (l.4, `dlog(CONS)`) in aggregate real disposable income (RHHDI), housing wealth (GPW), net financial wealth (NFWPE), the change in unemployment and a real-rate term. Household income is one aggregate (l.654, HHDI), and the dictionary contains no variable that splits households by income or age. A transfer from one group of households to another that is revenue-neutral therefore leaves HHDI, and so consumption, unchanged.
- **Our adapted model:** Inherited. `obr_macro/transpiler.py` transpiles l.4 and l.654 as published.

### H2. "Long-run consumption elasticities sum to 0.77; consumption-to-income ratio drifts downward." (Mid)
- **Verdict:** True
- **Why:** The long-run coefficients in l.4 on income, housing wealth and net financial wealth are 0.4393 + 0.1059 + 0.2216 = **0.7668**, and nothing restricts them to sum to one. If income and both wealth stocks grow at a common rate g, the consumption-to-income ratio falls by about 0.23 × g in the long run. Over a normal forecast horizon the effect is small, and wealth growing faster than income offsets it. It matters more in long-run scenarios.
- **Our adapted model:** Inherited. The coefficients are used unchanged via `obr_macro/transpiler.py`.

### H3. "Interest payments modelled from stocks and rates; interest receipts exogenous." (Mid)
- **Verdict:** True but openly documented
- **Why:** Household interest payments (l.623, `DIPHH = (LHP(-1)+OLPE(-1))*((1+(0.9*R+0.2)/100)^0.25-1)`) apply 0.9 × Bank Rate to the entire mortgage and unsecured debt stock at once. That is about +£5.2bn a quarter per +1pp on current stocks. Household interest receipts (DIRHH, dict 493) and other investment income (APIIH, dict 503) are listed as exogenous. The deposit-margin term DIRHHf (l.627) responds to rates but only feeds FISIM (l.729), because the adjustment that would carry it into income (FSMADJ, l.621) is commented out. In the model a Bank Rate rise therefore lowers household income, although on the snapshot households receive slightly more interest (about £23–24bn a quarter) than they pay (about £21bn).
- **Our adapted model:** Inherited. Bank Rate comes from the EFO market-assumptions table (`obr_macro/data.py`, table 1.9), and the consumption response in `docs/transmission_audit.md` runs through the payments side only.

### H4. "DB pension entitlements revalue with gilt yields, affecting consumption through financial wealth." (Mid)
- **Verdict:** True but openly documented
- **Why:** The pension and insurance stock PIHH (l.795) revalues with weight 0.574 on `DBR = 1/(1+RL/100)^15` (l.797; dict 580, "15 year discount rate for DB pensions"). PIHH flows into gross financial wealth (l.803), then net financial wealth (l.829), then consumption (long-run coefficient 0.2216, l.4). On our figures, a 100bp rise in the gilt yield from 4.5% lowers PIHH by about 7.6% (about £228bn) and net financial wealth by about 5.2%, which lowers long-run consumption by about **1.2%**. The 0.574 weight applies to the whole pension-and-insurance stock, insurance included.
- **Our adapted model:** Inherited. The gilt yield RL is exogenous (dict 462) and is taken from the EFO path (`obr_macro/data.py`), so this channel works only when the gilt yield itself is changed.

### H5. "Mortgage debt and house prices exogenous." (Mid)
- **Verdict:** True but openly documented
- **Why:** Mortgage debt (LHP, dict 590), average house prices (APH, dict 201) and the effective mortgage rate (RMORT, dict 463) have no equation and are listed as exogenous. Unsecured debt is endogenous (DEBTU, dict 586; OLPE, l.814–816). House prices and mortgage debt therefore do not respond to interest rates or income inside the model.
- **Our adapted model:** Inherited. These series are taken as given paths (`obr_macro/data.py`), and house prices show no response to a Bank Rate change in `docs/transmission_audit.md`.

### H6. "Employer social contributions fully shifted onto wages in the long run by coefficient restriction." (Mid)
- **Verdict:** True
- **Why:** In the private-sector earnings equation (l.232), the error-correction term includes `log(1+(EMPSC(-1)/WFP(-1)))` with a coefficient fixed at one. In the long run, employer contributions are therefore fully offset by lower wages. The error-correction speed is 0.0433 a quarter (a half-life of roughly 16 quarters), and employer contributions have no short-run term, so pass-through starts at zero and builds slowly.
- **Our adapted model:** Inherited. l.232 is transpiled as published (`obr_macro/transpiler.py`).

### H7. "Short-run income elasticity 0.10; real interest rate effect negligible." (Low)
- **Verdict:** True
- **Why:** The short-run coefficient on real disposable income in l.4 is **0.103**, against 0.439 in the long run. The real-rate term is `-0.0004036*d(R(-1) - inflation)`, which applies to the *change* in the real rate: a permanent 1pp rise reduces quarterly consumption growth by about 0.04pp once and has no further effect. Interest rates affect consumption mainly through household income (H3) and wealth (H4), not through this term.
- **Our adapted model:** Inherited. The coefficients are unchanged (`obr_macro/transpiler.py`).

### H8. "Financial balance sheet closes on residual 'other assets'." (Low)
- **Verdict:** True but openly documented
- **Why:** The household balance-sheet residual (l.822, HHRES, dict 593) is the gap between household net lending and the modelled asset and liability flows. It is assigned to the other-assets adjustment (l.824, OAHHADJ, dict 597, listed as an identity). Other assets therefore close the household financial account by construction.
- **Our adapted model:** Inherited. l.822 and l.824 are transpiled as published (`obr_macro/transpiler.py`).

### H9. "Deposit equation contains highly convex exponential terms; error-correction mixes adjusted and unadjusted stocks." (Low)
- **Verdict:** Partly true
- **Why:** The household deposits equation (l.779) contains `exp(5.1811*(RDEP-R))`, `exp(0.8206*LFSUR)` and `exp(106.3011*GMF)`. In £m, the unemployment terms are about £40m and £130m at 4.5% unemployment, which is small against a stock of about £2.3tn. They rise to about £3.7bn and £50bn at 10% unemployment, so the convexity matters only in severe scenarios. The second point is correct: the left-hand side is the unadjusted change `d(DEPHHx)`, but the error-correction term uses the adjusted stock `DEPHH(-1)`, which includes the exogenous DEPHHADJ (l.781, dict 594). Past adjustments therefore stay in the error-correction term. We could not size the house-transactions term (GMF, l.777) because its inputs are not in our data snapshot.
- **Our adapted model:** Inherited. l.779–781 are transpiled as published (`obr_macro/transpiler.py`); we have not checked whether this equation solves in our runs.

### H10. "Insurance asset acquisition driven only by the insurance premium tax rate." (Low)
- **Verdict:** True
- **Why:** The equation (l.791, dict 577) is `NAINSx = 13293.71 + 0.627*NAINSx(-1) - 236267.3*SIPT(-3)`, so the lagged dependent variable and the lagged IPT rate are its only drivers. The dictionary does not give SIPT's units (dict 576). **Assuming SIPT is the standard rate as a decimal** (0.12 today), the equation's steady state is about **−£40bn a quarter**, against recent outturn of about **+£1.2bn**; matching outturn would need SIPT of about 0.054. If that assumption holds, the level of insurance acquisitions is carried mostly by the exogenous adjustment NAINSADJ (dict 596).
- **Our adapted model:** Bypassed by accident (likely). Our data pipeline (`obr_macro/data.py`, `obr_macro/seeds/`) has no source for SIPT, so the equation cannot be evaluated and NAINS appears to stay on the data path; we have not confirmed this with a solver run.

### H11. "Durables user cost inside a logarithm; undefined if quarterly durable inflation is high." (Low)
- **Verdict:** True
- **Why:** The durables equation (l.8) takes the log of a user cost: the quarterly Bank Rate (about 0.99% at R = 4), plus a quarterly depreciation term of 5.74% (from 1.25^0.25 − 1), minus quarterly durables inflation. The argument turns negative, and the log undefined, once quarterly durables inflation exceeds about **6.7%** (about 30% annualised). Durables prices follow non-oil import prices one for one (l.341, dict 199), so one possible trigger is a large, fast fall in sterling. This has not occurred in recent data, but nothing in the code guards against it.
- **Our adapted model:** Inherited. The failure mode differs: in our solver a log of a negative number returns NaN, and the equation is dropped for that period without an error (`obr_macro/full_solver.py`; see `docs/stage1b_chain_trace.md`).

## Non-financial corporations

Several items refer to the "T2 fix". This is the OBR's own label in the code ("Changed to enable indirect T2 fix", l.17, 82, 110; "Switched off…", l.702; "exogenised…", l.706). It marks the configuration in which GDP, total investment and the GDP deflator are inputs rather than model outputs.

### N1. "Business investment equation switched off; investment is residual of exogenous total investment." (High)
- **Verdict:** True but openly documented
- **Why:** Business investment is the live identity `IBUS = IF - GGI - PCIH - PCLEB - IH - IPRL` (l.84). Total investment `IF` has no equation and is listed as "Exogenous" (dict 59). The behavioural equation `dlog(IBUSX) = …` (l.92) and the identity it would replace (l.86, 112) are commented out, not deleted. The code comment labels this as part of the T2 fix (l.82). As published, l.92 also has an unclosed parenthesis, so it cannot be switched back on without editing.
- **Our adapted model:** Changed. For corporation-tax analysis we rebuild the commented equation, adding the missing parenthesis, as an "investment closure" in `obr_macro/reform_analysis.py` (`_IBUSX_SRC`, `_stabilise_investment_closure`). On our data it feeds back explosively through market-sector output (MSGVA), so that closure holds MSGVA at a reference path.

### N2. "Cost-of-capital block unused; capital allowances cannot affect investment in code." (Mid)
- **Verdict:** Partly true
- **Why:** The cost-of-capital block is present and computed. It covers the tax-adjustment factor `TAF` (l.56), the user cost `COC` (l.70), desired capital `KSTAR` (l.72), the capital gap `KGAP` (l.76) and Tobin's Q `TQ` (l.78). So "unused" overstates it. The accurate point is that its only consumer is the commented-out investment equation (l.92), and `TQ` is used nowhere. So in the published configuration, capital allowances and the corporation tax rate do not reach investment. Several inputs (`DISCO`, `DELTA` and the allowance parameters) are listed as "Exogenous" (dict 19, 36) and have no published data.
- **Our adapted model:** Changed. Re-enabling the investment equation (see N1) brings the block back into use. The missing inputs are estimated from statutory capital-allowance rates and the OBR's gilt-rate assumption in `obr_macro/cost_of_capital.py` (added August 2026), with the values held in `full_solver.UNPUBLISHED_COST_OF_CAPITAL_SEEDS`.

### N3. "Financial account not linked to net lending; balance sheet not stock-flow consistent." (Mid)
- **Verdict:** True
- **Why:** PNFC net lending `NAFIC = NAFCO - NAFFC` (l.674, dict 519) is computed but used nowhere else. The PNFC balance sheet is built separately. Liabilities come from `NALIC = -27362 + 1.513178 * IBUS * (PIF / 100)` (l.912). Assets come from `NAAIC = AIC(-1) * (GDPMPS / GDPMPS(-1) - 1)` (l.916). Nothing makes acquisitions minus liabilities equal net lending. The household sector does have such a reconciliation, through `HHRES` and `OAHHADJ` (l.822–824). The PNFC sector does not.
- **Our adapted model:** Inherited. The equations run as published.

### N4. "Profits are income-side residual, absorbing errors from other residuals." (Mid)
- **Verdict:** True but openly documented
- **Why:** Operating surplus is `OS = GDPMPS - FYEMP - MI - BPAPS - TPRODPS - SDI` (l.719). Profits are `FYCPR = OS - OSHH - OSGG - OSPC - RENTCO + SA - FISIMPS` (l.731), labelled as an identity (dict 544). This is the standard income-side derivation used in the national accounts. A consequence is that errors in its components flow straight into profits: FISIM (see N5), stock appreciation (see N7) and household operating surplus.
- **Our adapted model:** Inherited. Profits are the same residual. In our version this residual also absorbs a large calibration adjustment to household operating surplus (`OSHH`; see README).

### N5. "Probable sign error in FISIM equation on FX lending; implies cumulative drift in profits." (Mid; flagged by the critic as unverified)
- **Verdict:** True as printed (whether it affects published forecasts can't be checked)
- **Why:** FISIM is the margin banks earn on loans and deposits, counted as a service charge. Line 637 (dict 498) is printed as:

  ```
  d(DIPICf) = STLIC*(((1+(RIC-R)/100)^0.25)-1) + FXLIC*(((1+2.9/100)^0.25)-1)
            - STLIC(-1)*(((1+(RIC(-1)-R(-1))/100)^0.25)-1) + FXLIC(-1)*(((1+2.9/100)^0.25)-1)
  ```

  The sterling-loan term is a proper first difference: current value minus lagged value. The foreign-currency term adds the lagged value instead of subtracting it. Read as a change in the level `STLIC*s + FXLIC*g`, the consistent form is:

  ```
  d(DIPICf) = STLIC*(((1+(RIC-R)/100)^0.25)-1) + FXLIC*(((1+2.9/100)^0.25)-1)
            - STLIC(-1)*(((1+(RIC(-1)-R(-1))/100)^0.25)-1) - FXLIC(-1)*(((1+2.9/100)^0.25)-1)
  ```

  Neighbouring equations follow the same differencing pattern, including the foreign-currency term of the PNFC interest-paid equation `DIPIC` (l.631 and 639). With g = 1.029^0.25 − 1 ≈ 0.0072 and foreign-currency lending of about £235bn, the printed form adds about £3.3bn a quarter, cumulatively. The level is only about £2.4bn a quarter, and the consistently differenced term is tens of millions. The drift passes into total FISIM (l.729) and so lowers profits (l.731). We can't tell from the code whether the OBR offsets it with add-factors in practice.
- **Our adapted model:** Bypassed by accident. Our transpiler keeps the published sign. But the PNFC loan rate `RIC` has no data in our dataset, so the equation evaluates to missing, is skipped, and `DIPICf` stays flat. If `RIC` data are added, the sign will need correcting.

### N6. "No income account; interest costs do not affect dividends or retained earnings." (Low)
- **Verdict:** True
- **Why:** PNFC interest paid and received (`DIPIC`, `DIRIC`, `DIPICx`, l.629–639) is computed but feeds no other equation, apart from FISIM. Household dividend income depends on gross profits and an exogenous series: `log(NDIVHH) = -8.605599 + 0.8092696*log(FYCPR(-4)) + 0.6597959*log(CORP)` (l.643, dict 501). Company saving `SAVCO` (l.676) is derived from the capital account and used nowhere. There is no PNFC income account that runs from profits through interest and tax to retained earnings.
- **Our adapted model:** Inherited. In our version the dividend equation itself does not run because `CORP` is missing from the published data (README, "Known inert equations").

### N7. "Stock appreciation derived from residual inventory series." (Low)
- **Verdict:** True but openly documented
- **Why:** Stock appreciation is `SA = BV(-1) * (PINV / PINV(-1) - 1)` (l.25). The inventory price `PINV = 100 * BV / INV` (l.331) comes from the book value of inventories `BV` and their volume `INV`, which build up from `DINVPS` and `DINV` (l.21, 23). `DINV` is the expenditure-side residual of GDP (l.19), part of the T2-fix configuration (comment at l.17).
- **Our adapted model:** Changed. For policy simulations, our version replaces the inventories equation with an equation that makes GDP endogenous (`swap_closure("DINV", GDPM_EQ)` in `obr_macro/baseline.py` and `obr_macro/full_solver.py`).

### N8. "Financial asset equation subtracts change in money holdings; rationale unclear." (Low)
- **Verdict:** True
- **Why:** The equation is `AIC = AIC(-1) + (NAAIC - d(M4IC))` (l.914). The dictionary defines `AIC` as the stock of financial assets held by PNFCs (dict 634, ONS code NKWX), which on that definition would include money. Subtracting the change in money holdings does not match that definition, and no rationale is given. The variable's only use is PNFC net wealth (l.918), which feeds only Tobin's Q (l.78), and Q is used nowhere. So the equation does not affect other model outputs.
- **Our adapted model:** Inherited. The equation runs as published and has no effect on headline results.

## Financial corporations

### F1. "No balance sheet for banks or other financial corporations; net lending calibrated." (Mid)
- **Verdict:** True but openly documented
- **Why:** The code has no balance-sheet block for financial corporations. Their net lending is `NAFFC = -12012 + FISIMPS - NEAHH - BLEVY` (l.672), labelled "Calibrated/technical relationship" (dict 518). Money held by other financial corporations, `M4OFC`, is exogenous (dict 469). Bank lending to PNFCs is tracked as a liability of the PNFC sector (`STLIC`, `FXLIC`, `BLIC`, l.894–906), but not as part of a financial-sector balance sheet.
- **Our adapted model:** Inherited.

### F2. "No central bank balance sheet; reserves remuneration absent from code." (Mid)
- **Verdict:** True but openly documented (outside the macroeconomic model's scope)
- **Why:** The code has no Bank of England balance sheet, Asset Purchase Facility (APF) or interest on bank reserves. `SRES` (l.443, dict 350) is the stock of foreign-currency reserve assets, not commercial-bank reserves. `M0` just grows with nominal GDP (l.580). Central-government interest flows `DICGOP` and `CGINTRA` are exogenous (dict 244, 246) and enter the borrowing identity at l.524. That is consistent with debt interest, including APF and quantitative-tightening flows, being produced in the OBR's separate public-finance models and fed in. The OBR's March 2026 forecast tables publish APF assumptions separately (e.g. "APF annual runoff assumptions"). Whether those separate models handle reserves remuneration adequately can't be checked from this code.
- **Our adapted model:** Inherited. Debt interest stays an exogenous input.

### F3. "Broad money is a sum of independently determined series." (Low)
- **Verdict:** True but openly documented
- **Why:** Broad money is the identity `M4 = DEPHH + M4IC + M4OFC` (l.584, dict 470). Its parts are set separately: household deposits by their own equation (l.779–781), PNFC money in line with nominal GDP (l.582), and OFC money exogenously (dict 469). `M4` itself feeds no other equation, so the lack of a bank balance-sheet constraint does not affect other model outputs.
- **Our adapted model:** Inherited.

## Government


### V1. "Most tax receipts exogenous; no automatic stabilisers within the code." (Mid)
- **Verdict:** True but openly documented
- **Why:** The receipts group (Group 10) has 80 dictionary entries: 67 are labelled Exogenous, 12 are Identities and 1 is Calibrated. Each of the 12 identities is a plain sum of exogenous components: CT l.408, CETAX l.410, VED l.412, OCT l.414, PSINTR l.418, CGRENT l.420, TAXCRED l.422, INCTAXG l.424, PUBSTIW l.426, PUBSTPD l.428, PSCR l.430, NATAXES l.432. The single calibrated item is CGC (l.416, dict 316, "CG interest receipts: earnings on reserves"), which moves with the world short rate ROCB. No receipt is modelled as a tax rate times a tax base. The tax rates TPBRZ and TCPRO only affect mortgage costs (l.343) and the cost of capital (l.50–54). On the spending side, social benefits CGSB and LASBHH are exogenous (dict 239 and 237), and BENAB = 0.012 × CGSB (l.473). Public sector net borrowing is PSNBNSA = −(PSCR − PSCE − DEP) + PSNI (l.510, l.536), and every input to it is exogenous. Apart from CGC, every receipt and benefit line, and borrowing itself, is set outside the model as published. Whether the OBR adds these effects in its separate fiscal models cannot be checked from the code.
- **Our adapted model:** Inherited. Receipts and benefits stay exogenous in `obr_macro/full_solver.py`. Household tax reforms enter as a static add-factor on disposable income (`HOUSEHOLD_COSTING_VAR = "HHDI_ADDFACTOR"` in `obr_macro/reform_analysis.py`), not through a tax-base mechanism.

### V2. "Debt interest and gilt stock exogenous; no in-code link to rates or borrowing." (Mid)
- **Verdict:** True but openly documented
- **Why:** The debt interest variables DICGOP, DILAPR and DIPCOP are labelled Exogenous with no equation (dict 244, 245, 385). They enter the code only as inputs at l.504, l.524, l.526 and l.532. The gilt stocks CGGILTS and MKTIG are exogenous (dict 435–436) and lead only to PSFL (l.553) and PSNW (l.557), which no other equation uses. PSND (l.567) and GGGD (l.571) are computed but never used elsewhere. The conventional and index-linked gilt interest series DIPLDC and IILG are listed in the dictionary (dict 240–241) but do not appear in the code.
- **Our adapted model:** Inherited. Debt interest has no link to gilt yields in `obr_macro/full_solver.py`. PSND and GGGD are not computed in our runs, because their residual inputs PSNDRES and GGGDRES have no published data.

### V3. "Total current spending exogenous; product subsidies computed as residual, feeding basic prices and profits." (Mid)
- **Verdict:** True but openly documented
- **Why:** PSCE is exogenous (dict 395). CGSUBP is the residual of PSCE after the other spending lines (l.504), and the code comment at l.502 says this was "Changed to enable indirect T2 fix". CGSUBP feeds the basic-price adjustment BPAPS (l.695). BPAPS then feeds basic-price GVA (l.697), operating surplus (l.719) and corporate profits FYCPR (l.731). Any spending component that is modelled, such as CGWS, GNP4 or EUVAT, is therefore offset one-for-one by a change in subsidies, which then shows up in basic prices and profits.
- **Our adapted model:** Bypassed by accident. The CGSUBP equation is kept, but the BPAPS equation is dropped during our solve because one of its inputs (CCLACA) has no data. BPAPS stays at its data value, so the link through to basic prices and profits does not currently operate (`obr_macro/full_solver.py`).

### V4. "Two exogenous government consumption series share one ONS code; equality not enforced." (Low)
- **Verdict:** True
- **Why:** CGGPSPSF and CGGPS are both exogenous and both mapped to ONS code NMRP (dict 225–226). The identity that would tie them together is commented out (l.379–381). CGGPSPSF is used only for CGP (l.377). CGGPS feeds real government consumption, the investment deflator and nominal final expenditure (l.337, l.383, l.385, l.681). Nothing in the code keeps the two series equal.
- **Our adapted model:** Inherited. The two series differ in the data we load from 2024Q1 (146,223 vs 146,499 in 2024Q1; 166,176 vs 164,862 in 2026Q1). Our government consumption shock is applied to real CGG directly and moves neither series (`obr_macro/full_solver.py`, `obr_macro/reform_analysis.py`).

### V5. "EU-budget payment equations remain live; formulas dimensionally questionable." (Low; marked unverified by the author)
- **Verdict:** True
- **Why:** GNP4 (l.469) and EUVAT (l.471) are active equations, and unlike the other EU items they do not depend on their own past values. They set payments in proportion to UK national income and VAT receipts. Both divide a sterling amount by ECUPO, which the dictionary defines as euros per pound. That looks inverted for a currency conversion, although the calibrated constants (0.010, 0.0325, 0.8267) may absorb it. GNP4 feeds transfer debits (l.485), the subsidy residual (l.504) and central government net borrowing (l.524). The ONS data for both series is zero from 2021, but the equations as printed produce positive values whenever they are solved.
- **Our adapted model:** Inherited. This is a known open bug: our replication currently regenerates GNP4 at about £6.3–7.4bn and EUVAT at about £1.5bn a quarter after 2021, where the data is zero. This makes the current balance about £8–12bn a quarter weaker in our runs. Public sector net borrowing is unchanged because the subsidy residual offsets it. The fix is to hold both at zero in `obr_macro/full_solver.py`.

### V6. "Add factor on seasonally adjusted borrowing shifts corporate net lending without affecting debt." (Low)
- **Verdict:** True but openly documented
- **Why:** The add-factor is declared openly in the code (`@ADD(V) PSNBCY PSNBCY_A`, l.539; dict 420). Seasonally adjusted borrowing (PSNBCY) feeds only corporate net lending (NAFCO, l.670). Debt builds from the non-seasonally-adjusted measure through the net cash requirement (l.536, l.563, l.567), so the add-factor changes sector balances but not debt.
- **Our adapted model:** Bypassed by accident. PSNBCY_A has no data in our loaded databank, so the add-factor is zero in our runs. Seasonally adjusted borrowing therefore equals the non-seasonally-adjusted measure, which shifts corporate net lending (about −£23bn in 2025Q1).

## Rest of world

### R1. "Export and import volumes exogenous; world trade series maintained but unused." (High)
- **Verdict:** True but openly documented
- **Why:** Total exports X and imports M never appear on the left-hand side of any equation, and the dictionary labels both Exogenous (dict 110 and 134). Non-oil goods exports are a residual of the total (XNOG = X − XS − XOIL, l.184). The oil exports equation is commented out (l.355), even though the dictionary describes XOIL as calibrated (dict 208). World trade (WTGS, dict 117) and world GDP (WORLD, dict 118) are listed in the dictionary but do not appear anywhere in the code.
- **Our adapted model:** Inherited. Our transmission audit (`docs/transmission_audit.md`) shows exports and imports unchanged (+0.00%) under every shock tested, including a 10% sterling depreciation. Activity responds to that depreciation only through prices and wealth: consumption −0.08% over 6 quarters, and, under our GDP closure (G1), GDP −0.05%. In the OBR's own configuration GDP would not move.

### R2. "Exchange rate exogenous; current account and external position feed no equation." (Mid)
- **Verdict:** Partly true
- **Why:** The sterling effective exchange rate RX is exogenous (dict 344). However, the current balance does feed other equations. CB flows into the rest of the world's net lending (l.497), then its net acquisition of assets (l.840, l.861) and its asset stocks (l.849, l.853). Those stocks drive investment income credits and debits (l.445, l.449), which make up net investment income NIPD (l.455). NIPD feeds back into CB (l.493) and into the EU contribution GNP4 (l.469). What is true is that the net international investment position (NIIP, l.889) is not used by any other equation, and nothing feeds back to the exchange rate or to real activity.
- **Our adapted model:** Inherited. The same equations are transpiled unchanged in `obr_macro/transpiler.py` and solved in `obr_macro/full_solver.py`.

### R3. "Services import equation only reallocates a fixed import total between goods and services." (Low)
- **Verdict:** True but openly documented
- **Why:** Services imports MS are econometrically estimated (l.223). Non-oil goods imports are then the residual MNOG = M − MS − MOIL (l.217), and total imports M are exogenous. The code comment at l.215 marks this as a deliberate change ("Changed to enable indirect T2 fix"). A change in MS therefore only changes the split between goods and services; total import volumes stay fixed.
- **Our adapted model:** Inherited. The same equations are used in `obr_macro/full_solver.py`.

### R4. "Secondary income retains EU-era transfer items." (Low)
- **Verdict:** True
- **Why:** Transfer credits TRANC (l.483) and debits TRAND (l.485) still include EU items. Three of them (EUSUBPR, EUSF, ECNET, l.463–467) depend only on their own past values, so they stay at zero once the data is zero. EU subsidies on products are set to zero (EUSUBP = 0, l.461), and EU product-tax payments (EUOT) are exogenous. The two live items are GNP4 and EUVAT, which share the problem described in V5.
- **Our adapted model:** Inherited. This is the same known open bug as V5: our replication currently regenerates GNP4 and EUVAT after 2021 and adds them to transfer debits, which weakens the current balance in our runs.
