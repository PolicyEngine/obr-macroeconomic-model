# Roadmap: towards an open-source OBR-style forecasting engine

The long-run goal is to turn this repository from an *emulator that re-runs the
OBR's published equations* into something closer to *what the OBR actually
operates* — an open, inspectable forecasting tool built around the same model.

## What "what the OBR has" decomposes into

The OBR's setup is three layers, and they are easy to conflate:

1. **The model** — the 372 published equations. ✅ We have this, transpiled to
   Python (`obr_macro/transpiler.py`, the October 2025 model code).
2. **The engine** — EViews: it solves the simultaneous system, manages closures
   (which variables are exogenous vs endogenous), holds **add-factors**, runs
   scenarios, and does stochastic simulation. ⚠️ We have a *solver*
   (`FullOBRSolver`, Gauss–Seidel) but not the full engine.
3. **The workflow** — a forward **baseline forecast** that forecasters then bend
   with **judgement (add-factors)**, iterating with the Budget Responsibility
   Committee. ❌ This is the real gap.

The OBR's own framing — *"two forecasters using exactly the same model could end
up with very different forecasts"* — is entirely about layer 3. The model is the
skeleton; add-factors are where forecasting happens.

## Honest constraint

The OBR's *inputs* are not public: their forward exogenous assumptions and their
add-factor database are judgement, not published data. We can build machinery
equivalent to theirs, but **the baseline forecast will not match the OBR's**
unless the user supplies the same judgements. That is by design — the forecast
becomes the user's, exactly as the OBR intends.

## What we have today (Stage 0)

- The 372 equations, parsed and transpiled to Python.
- `FullOBRSolver`: Gauss–Seidel solve of the full system, with hand-wired
  closure swaps and single-variable shocks (`apply_shock`, `swap_closure`).
- `reform_analysis.run_reform`: shock-and-compare against history/EFO data.
- A Next.js dashboard (`dashboard/`) for exploring scenarios, variables and
  equations.

## Stages

Each stage is independently useful; ship in order.

### Stage 1 — Make the solve trustworthy *(current)*
Several channels do not propagate (e.g. the £10bn government-investment shock
moves nothing; the demand scenarios move GDP only through the accounting
identity). Nothing built on top can be trusted until shocks transmit correctly.

- **1a. Transmission audit** *(first step)* — a diagnostic that shocks each main
  lever and records which aggregates respond, classifying every channel as
  *transmitting*, *identity-only*, or *dead*. See
  [`transmission_audit.md`](./transmission_audit.md).
- 1b. Fix the dead/thin channels surfaced by the audit (closures, missing
  behavioural links, initialisation gaps).
- 1c. Solver robustness — a Newton/Broyden option, convergence diagnostics, and
  speed (solves are currently minutes).

### Stage 2 — A forward baseline
Extend the exogenous assumptions beyond history and solve the model *forward* to
produce a projected baseline. This is the jump from "perturb history" to
"perturb a forecast".

### Stage 3 — Add-factors (the defining OBR feature)
A per-equation override/add-factor system so a user can impose judgement on any
equation. This *is* the OBR workflow.

### Stage 4 — Closures and scenario management
Named, swappable closures (not hand-wired per experiment); saved, comparable
scenarios; editable exogenous-assumption sets.

### Stage 5 — Uncertainty
Stochastic simulation → fan charts, as in the OBR's published forecasts.

### Stage 6 — The forecaster's cockpit
The dashboard becomes the analyst workspace: edit assumptions and add-factors,
run, compare scenarios, and drill from any result back to the equations driving
it.

## Target architecture

Separate a **model-engine library** from the dashboard, with an EViews-like
"model object" API:

```python
model.solve(scenario)          # deterministic solve
model.override(var, path)      # set an exogenous assumption
model.add_factor(eq, path)     # impose judgement on an equation
model.baseline() / .scenario() # forward forecast + alternates
```

That mirrors EViews' model object. Everything in Stages 2–6 becomes a method on
that object, and the UI stays thin.

## Where we are now

Starting **Stage 1a — the transmission audit**: before fixing anything, map
which of the model's channels actually work.
