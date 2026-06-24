# Stage 1c — the real blocker is data coverage

Stage 1b found ~290/371 equations silently skipped. Stage 1c's probe showed why:
the carry-forward seeding unblocked **0** equations, because the blocking inputs
have **no history at all** — they are never loaded.

## The finding

The emulator's `load_obr_data()` reads ~125 published aggregates from the four
EFO detailed-forecast spreadsheets. But the model's 372 equations reference
**514** distinct variables. The gap is the disaggregated National-Accounts and
fiscal "plumbing" the equations operate on.

| | count | meaning |
|---|--:|---|
| Referenced by equations | 514 | |
| Present in loaded data | 125 | the EFO aggregates |
| **Missing** | **457** | |
| — endogenous (has an equation) | 261 | computes for free once inputs exist |
| — exogenous roots (need a value) | 196 | the actual data task |
| &nbsp;&nbsp;• with ONS code, single series | 111 | direct ONS pull |
| &nbsp;&nbsp;• with ONS code, compound formula | 40 | pull + construct |
| &nbsp;&nbsp;• no ONS code (policy/calibration) | 45 | set by hand |

So the model does not run because it is **starved of its exogenous inputs**, not
because the equations or closures are wrong. Populate the ~196 roots and the 261
endogenous variables resolve through the equations.

## The plan (Stage 1c proper)

1. **Pull the 111 single-series ONS roots** by their codes (e.g. `CGIPS=NMES`
   CG gross fixed capital formation, `PPIY=GB7S` producer output prices,
   `POPAL=EBAQ` population, `EMPNIC=CEAN` employer NICs, `VREC=EYOO` net VAT).
   Build an ONS time-series loader, align to the model's quarterly index, merge
   into `load_obr_data()`.
2. **Construct the 40 compound roots** from their formulas
   (e.g. `EENIC=AIIH-CEAN`, `ERCG=(NMAI*1000/C9K9)*(4/52)`).
3. **Set the 45 policy/calibration constants** (several the solver already seeds,
   e.g. `TCPRO`). Base-year `*BASE` constants follow from their base variable.
4. **Re-run the transmission audit** (`obr_macro/transmission_audit.py`) — it is
   the regression test. Watch dead/identity-only flip to transmitting.

## Why this is the right next step

This is the single highest-leverage task in the roadmap: it is the difference
between running ~22% of the model and running all of it. It is also well-defined
— a finite list of ONS series with known codes — and is exactly how the OBR
populates the model in EViews. The scoping script
(`obr_macro/stage1c_scope.py`) prints the full lists and can regenerate them as
the data lands.
