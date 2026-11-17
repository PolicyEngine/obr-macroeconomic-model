# Stage 1b — income -> consumption chain trace

Government consumption +£1.25bn/q (standard closure). Baseline vs shocked, final period (2026Q2). The first link that does not move is where the multiplier breaks.

| Link | Variable | Baseline | Shocked | Change | % |
|---|---|--:|--:|--:|--:|
| Government consumption (shock) | `CGG` | 152,785.1 | 153,723.7 | +938.6 | +0.614% |
| GDP (expenditure) | `GDPM` | 688,686.7 | 689,625.3 | +938.6 | +0.136% |
| GVA at factor cost | `GVAFC` | 697,119.7 | 697,119.7 | +0.0 | +0.000%  ⟵ flat |
| Market-sector GVA | `MSGVA` | 441,138.3 | 441,050.0 | -88.3 | -0.020% |
| Government GVA | `GGVA` | 144,245.3 | 145,131.5 | +886.2 | +0.614% |
| Market-sector employees | `EMS` | 27,453,775.8 | 27,453,775.8 | +0.0 | +0.000%  ⟵ flat |
| Employment (LFS) | `ETLFS` | 34,317.2 | 34,317.2 | +0.0 | +0.000%  ⟵ flat |
| Unemployment rate  [CONS driver] | `LFSUR` | 5.0 | 5.0 | +0.0 | +0.000%  ⟵ flat |
| Wages & salaries | `WFP` | 320,707.4 | 320,707.4 | +0.0 | +0.000%  ⟵ flat |
| Compensation of employees | `COMP` | 392,602.6 | 392,602.6 | +0.0 | +0.000%  ⟵ flat |
| Labour income | `FYEMP` | 392,602.6 | 392,602.6 | +0.0 | +0.000%  ⟵ flat |
| Household disposable income | `HHDI` | 504,166.9 | 504,166.9 | +0.0 | +0.000%  ⟵ flat |
| Real household income  [CONS driver] | `RHHDI` | 400,354.3 | 400,354.3 | +0.0 | +0.000%  ⟵ flat |
| Household consumption (target) | `CONS` | 408,342.3 | 408,342.3 | +0.0 | +0.000%  ⟵ flat |

**Chain breaks at `GVAFC`** (GVA at factor cost): the shock reaches GDP but the first behavioural link above does not respond.

## Silently-skipped equations at 2025Q1

`solve_period` drops these (error or NaN) instead of solving them — **290 of 371 equations**.

### On the income/consumption chain
| Variable | Status | Reason |
|---|---|---|
| `EMS` (dlog(EMS)) | nonfinite | NaN inputs: PMSGVA(-1), PSAVEI(-1) |
| `LFSUR` (LFSUR) | nonfinite | NaN inputs: ULFS |
| `WFP` (WFP) | nonfinite | NaN inputs: ADJW, CGWADJ, ECG, ELA, ERCG, ERLA, LAWADJ, PSAVEI |
| `HHDI` (HHDI) | nonfinite | NaN inputs: EECOMPC, EECOMPD, EESC, FSMADJ, HHISC, HHSB, MI, NMTRHH, OSHH, PIPHH, PIRHH, SBHH, TYWHH |

### Most common missing inputs (NaN) across all skipped equations
| Input | # equations it blocks |
|---|--:|
| `PMNOG` | 11 |
| `PMS` | 9 |
| `CGWS` | 8 |
| `TXRATEBASE` | 8 |
| `PPIY` | 8 |
| `PPIYBASE` | 8 |
| `KCGPSO` | 7 |
| `LAWS` | 7 |
| `PMNOGBASE` | 7 |
| `PMSBASE` | 7 |
| `SCOST` | 7 |
| `CGIPS` | 6 |
| `KLA` | 6 |
| `LAIPS` | 6 |
| `POP16` | 6 |
