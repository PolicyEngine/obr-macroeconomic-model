"""Stage 1b — trace the income -> consumption chain after a demand shock.

A government-consumption rise lifts GDP by the spending identity, but the audit
showed it never reaches consumption (no multiplier). This walks the chain the
model would need to use:

    CGG (shock) -> GDP/output -> market-sector GVA -> employment -> incomes
                -> household disposable income -> real income (RHHDI) -> CONS

and prints the baseline-vs-shocked response of each link, so the first link that
does not move marks the break. It also runs the solver's diagnose_period to list
the equations that are being silently skipped (errored or NaN), which is the
suspected cause.

Run from the repo root:
    uv run python -m obr_macro.diagnose_chain
"""

from __future__ import annotations

import numpy as np

from obr_macro.full_solver import FullOBRSolver
from obr_macro.reform_analysis import GDPM_EQ

START, END = "2025Q1", "2026Q2"

# The income -> consumption chain, in causal order. Labels for the report.
CHAIN = [
    ("CGG", "Government consumption (shock)"),
    ("GDPM", "GDP (expenditure)"),
    ("GVAFC", "GVA at factor cost"),
    ("MSGVA", "Market-sector GVA"),
    ("GGVA", "Government GVA"),
    ("EMS", "Market-sector employees"),
    ("ETLFS", "Employment (LFS)"),
    ("LFSUR", "Unemployment rate  [CONS driver]"),
    ("WFP", "Wages & salaries"),
    ("COMP", "Compensation of employees"),
    ("FYEMP", "Labour income"),
    ("HHDI", "Household disposable income"),
    ("RHHDI", "Real household income  [CONS driver]"),
    ("CONS", "Household consumption (target)"),
]


def build():
    s = FullOBRSolver(verbose=False)
    s.swap_closure("DINV", GDPM_EQ)
    return s


def main():
    base = build()
    # The baseline must share the shocked run's structure: apply_shock makes
    # CGG exogenous on the shocked solver, so remove its equation here too —
    # otherwise the live dlog(CGG) equation moves baseline CGG and the
    # reported base-vs-shock delta mixes model drift into the shock response
    # (same rationale as run_fiscal_shock's control run).
    base.make_exogenous("CGG")
    base._shock_active = True
    base.solve(START, END)
    bdat = base.data.copy()

    sh = build()
    sh.apply_shock("CGG", 1250.0, START, periods=6)
    sh.solve(START, END)
    sdat = sh.data.copy()

    t0 = base.period_idx(START)
    tN = base.period_idx(END)

    lines = []
    lines.append("# Stage 1b — income -> consumption chain trace\n")
    lines.append(
        "Government consumption +£1.25bn/q (standard closure). "
        f"Baseline vs shocked, final period ({END}). "
        "The first link that does not move is where the multiplier breaks.\n"
    )
    lines.append("| Link | Variable | Baseline | Shocked | Change | % |")
    lines.append("|---|---|--:|--:|--:|--:|")

    break_at = None
    for code, label in CHAIN:
        if code not in bdat.columns or code not in sdat.columns:
            lines.append(f"| {label} | `{code}` | — | — | _absent_ | — |")
            continue
        b = float(bdat.iloc[tN][code])
        s = float(sdat.iloc[tN][code])
        d = s - b
        pct = (100 * d / b) if abs(b) > 1e-9 and np.isfinite(b) else float("nan")
        moved = abs(pct) >= 0.02 if np.isfinite(pct) else False
        if break_at is None and code not in ("CGG", "GDPM") and not moved:
            break_at = (code, label)
        flag = "" if moved or code in ("CGG", "GDPM") else "  ⟵ flat"
        pct_s = f"{pct:+.3f}%" if np.isfinite(pct) else "—"
        lines.append(
            f"| {label} | `{code}` | {b:,.1f} | {s:,.1f} | {d:+,.1f} | {pct_s}{flag} |"
        )

    lines.append("")
    if break_at:
        lines.append(
            f"**Chain breaks at `{break_at[0]}`** ({break_at[1]}): the shock reaches GDP "
            "but the first behavioural link above does not respond.\n"
        )

    # --- silent-skip diagnosis on the shocked solver at the first shocked period ---
    skips = sh.diagnose_period(t0)
    chain_codes = {c for c, _ in CHAIN}
    lines.append(f"## Silently-skipped equations at {START}\n")
    lines.append(
        f"`solve_period` drops these (error or NaN) instead of solving them — "
        f"**{len(skips)} of {len(sh.equations)} equations**.\n"
    )
    chain_skips = [s for s in skips if s["var"] in chain_codes]
    if chain_skips:
        lines.append("### On the income/consumption chain")
        lines.append("| Variable | Status | Reason |")
        lines.append("|---|---|---|")
        for s in chain_skips:
            lines.append(
                f"| `{s['var']}` ({s['lhs']}) | {s['status']} | {s['reason']} |"
            )
        lines.append("")
    # most common NaN inputs across all skips
    from collections import Counter

    blames = Counter()
    for s in skips:
        if s["status"] == "nonfinite" and s["reason"].startswith("NaN inputs:"):
            for nm in s["reason"].split(":", 1)[1].split(","):
                blames[nm.strip()] += 1
    if blames:
        lines.append(
            "### Most common missing inputs (NaN) across all skipped equations"
        )
        lines.append("| Input | # equations it blocks |")
        lines.append("|---|--:|")
        for nm, n in blames.most_common(15):
            lines.append(f"| `{nm}` | {n} |")
        lines.append("")

    out = "docs/stage1b_chain_trace.md"
    with open(out, "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))
    print(f"\n[diagnose] wrote {out}", flush=True)


if __name__ == "__main__":
    main()
