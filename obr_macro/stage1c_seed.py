"""Stage 1c — seed the missing exogenous / base-year inputs.

Stage 1b showed ~290/371 equations are silently skipped because their inputs are
NaN. This:
  1. classifies every blocking variable (has an equation? how much history?),
  2. applies a seeding strategy (carry exogenous series forward/back; set
     *BASE calibration constants from their base variable; seed remaining
     endogenous NaNs so Gauss-Seidel can start),
  3. measures how many equations the seeding unblocks (diagnose skip count
     before vs after) at the first forecast period — a fast proxy that needs no
     forward solve.

Run from the repo root:
    uv run python -m obr_macro.stage1c_seed
"""
from __future__ import annotations

import re
from collections import Counter

import numpy as np

from obr_macro.full_solver import FullOBRSolver

PROBE = "2025Q1"


def referenced_vars(eq):
    out = set()
    for m in re.finditer(r"v\['([A-Z0-9_]+)'\]", eq.python_expr):
        out.add(m.group(1))
    for m in re.finditer(r"_lag\('([A-Z0-9_]+)'", eq.python_expr):
        out.add(m.group(1))
    return out


def seed_inputs(solver):
    """Make the model's inputs finite. Returns a short summary of what it did."""
    data = solver.data
    has_eq = {solver._extract_lhs_var(eq.lhs) for eq in solver.equations}

    # 1) carry every series with any history forward then back (exogenous held
    #    flat; endogenous get a finite Gauss-Seidel starting seed).
    n_filled = int(data.isna().any().sum())
    data[:] = data.ffill().bfill()

    # 2) *BASE calibration constants: set to their base variable's last finite
    #    value (a constant), so ratios like PMNOG/PMNOGBASE are well defined.
    base_set = []
    for col in list(data.columns):
        if col.endswith("BASE") and data[col].isna().all():
            base = col[:-4]
            if base in data.columns and data[base].notna().any():
                data[col] = float(data[base].dropna().iloc[-1])
                base_set.append(col)

    # 3) anything still entirely NaN and exogenous: leave at NaN but record it —
    #    these genuinely need real data (Stage 1c follow-up).
    still_missing = [c for c in data.columns if data[c].isna().all()]

    solver.data = data
    return {
        "cols_filled": n_filled,
        "base_constants_set": base_set,
        "still_missing": still_missing,
        "has_eq": has_eq,
    }


def main():
    s = FullOBRSolver(verbose=False)
    t = s.period_idx(PROBE)
    has_eq = {s._extract_lhs_var(eq.lhs) for eq in s.equations}

    before = s.diagnose_period(t)
    print(f"[1c] before seeding: {len(before)} / {len(s.equations)} equations skipped at {PROBE}")

    # classify the blocking NaN inputs
    blockers = Counter()
    for d in before:
        if d["status"] == "nonfinite" and d["reason"].startswith("NaN inputs:"):
            for nm in d["reason"].split(":", 1)[1].split(","):
                blockers[nm.strip()] += 1
    print("\n[1c] top blocking inputs (var | #eqs blocked | has_equation | #finite history):")
    for nm, n in blockers.most_common(25):
        finite = int(s.data[nm].notna().sum()) if nm in s.data.columns else "no-col"
        print(f"      {nm:14} {n:3}   eq={'Y' if nm in has_eq else 'n'}   hist={finite}")

    summary = seed_inputs(s)
    after = s.diagnose_period(t)
    print(f"\n[1c] after seeding: {len(after)} / {len(s.equations)} equations skipped "
          f"(was {len(before)}) -> unblocked {len(before) - len(after)}")
    print(f"[1c] columns with any NaN filled: {summary['cols_filled']}")
    print(f"[1c] *BASE constants set: {len(summary['base_constants_set'])} "
          f"-> {', '.join(summary['base_constants_set'][:12])}{' ...' if len(summary['base_constants_set'])>12 else ''}")
    print(f"[1c] still entirely-missing columns: {len(summary['still_missing'])} "
          f"-> {', '.join(summary['still_missing'][:20])}{' ...' if len(summary['still_missing'])>20 else ''}")

    # of the still-missing, which are referenced by equations (genuinely needed)?
    referenced = set()
    for eq in s.equations:
        referenced |= referenced_vars(eq)
    needed_missing = sorted(set(summary["still_missing"]) & referenced)
    print(f"\n[1c] still-missing AND referenced by an equation ({len(needed_missing)}): "
          f"{', '.join(needed_missing)}")


if __name__ == "__main__":
    main()
