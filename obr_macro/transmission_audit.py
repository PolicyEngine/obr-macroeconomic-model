"""Stage 1a — transmission audit.

Shocks each main exogenous lever of the model in turn and records how a panel of
key macro aggregates responds, then classifies every channel as:

  - transmitting   : the shock reaches behavioural variables beyond the
                     accounting identity (consumption, investment, jobs, prices),
  - identity-only  : only GDP and its directly-shocked component move — the
                     behavioural multiplier is missing,
  - dead           : nothing moves (the shock does not propagate at all).

The point is diagnostic: you cannot trust a forecast built on channels that do
not work, so map them before fixing anything.

Run from the repo root (slow — a full solve per shock):
    uv run python -m obr_macro.transmission_audit
"""
from __future__ import annotations

import numpy as np

from obr_macro.full_solver import FullOBRSolver
from obr_macro.reform_analysis import (
    GDPM_EQ, IBUS_EQ, IF_EQ, IBUSX_EQ, _ensure_ibusx_inputs,
)

START, END = "2025Q1", "2026Q2"   # 6-quarter horizon keeps the audit tractable
PERIODS = 6                         # shock sustained across the horizon

# Panel of aggregates to watch. kind: "pct" = % change vs baseline at the final
# period; "pp" = change in percentage points (for rates).
PANEL = [
    ("GDPM",  "GDP",            "pct"),
    ("CONS",  "Consumption",    "pct"),
    ("IF",    "Investment",     "pct"),
    ("IBUS",  "Bus. invest.",   "pct"),
    ("X",     "Exports",        "pct"),
    ("M",     "Imports",        "pct"),
    ("ETLFS", "Employment",     "pct"),
    ("LFSUR", "Unemp. rate",    "pp"),
    ("CPI",   "CPI",            "pct"),
    ("APH",   "House prices",   "pct"),
    ("RL",    "Gilt yield",     "pp"),
]
# Behavioural channels (everything that is NOT a pure spending identity): if a
# shock moves GDP but none of these, the behavioural multiplier is missing.
BEHAVIOURAL = {"CONS", "IBUS", "ETLFS", "LFSUR", "CPI", "X", "M", "APH", "RL"}

# Shocks. size is absolute unless rel=True, in which case it is a fraction of the
# variable's baseline value at the start period.
SHOCKS = [
    dict(label="Gov consumption +£1.25bn/q", var="CGG",   size=1250.0, closure="standard"),
    dict(label="Gov investment +£3bn/q",     var="CGIPS", size=3000.0, closure="standard"),
    dict(label="Corp tax +1pp",              var="TCPRO", size=0.01,   closure="investment"),
    dict(label="Bank Rate +1pp",             var="R",     size=1.0,    closure="standard"),
    dict(label="Sterling -10% (ERI)",        var="RX",    size=-0.10,  closure="standard", rel=True),
    dict(label="Oil price +$10/bbl",         var="PBRENT", size=10.0,  closure="standard"),
]

PCT_THRESH = 0.02   # % — below this a level response counts as "no move"
PP_THRESH = 0.005   # percentage points


def _build(closure):
    s = FullOBRSolver(verbose=False)
    s.swap_closure("DINV", GDPM_EQ)
    if closure == "investment":
        _ensure_ibusx_inputs(s)
        s.swap_closure("IBUSX", IBUSX_EQ)
        s.swap_closure("IBUS", IBUS_EQ)
        s.swap_closure("IF_PLACEHOLDER", IF_EQ)
    return s


def _resp(kind, base, shock):
    if base is None or shock is None or not (np.isfinite(base) and np.isfinite(shock)):
        return None
    if kind == "pct":
        return 100.0 * (shock - base) / base if abs(base) > 1e-9 else None
    return shock - base   # pp


def _material(kind, v):
    if v is None:
        return False
    return abs(v) >= (PP_THRESH if kind == "pp" else PCT_THRESH)


def build_baseline(closure):
    base = _build(closure)
    base._shock_active = True
    base.solve(START, END)
    return base


def run_one(shock, base):
    """Run one shock against an already-solved baseline (cloned, not rebuilt)."""
    bdat = base.data

    sh = base.clone()
    t0 = sh.period_idx(START)
    size = shock["size"]
    if shock.get("rel"):
        base_val = sh._get(shock["var"], t0)
        size = size * base_val if np.isfinite(base_val) else 0.0
    sh.apply_shock(shock["var"], size, START, periods=PERIODS)
    sh.solve(START, END)
    sdat = sh.data

    tN = base.period_idx(END)
    row = {}
    for code, _lab, kind in PANEL:
        if code in bdat.columns and code in sdat.columns:
            row[code] = _resp(kind, float(bdat.iloc[tN][code]), float(sdat.iloc[tN][code]))
        else:
            row[code] = None
    return row


def classify(row):
    gdp = row.get("GDPM")
    gdp_moves = _material("pct", gdp)
    beh = [code for code, _l, kind in PANEL
           if code in BEHAVIOURAL and _material(kind, row.get(code))]
    if not gdp_moves and not beh:
        return "dead", beh
    if gdp_moves and not beh:
        return "identity-only", beh
    return "transmitting", beh


def _fmt(kind, v):
    if v is None:
        return "—"
    unit = "pp" if kind == "pp" else "%"
    return f"{v:+.2f}{unit}"


def main():
    baselines = {}  # one solved baseline per closure, reused across shocks
    results = []
    for sh in SHOCKS:
        print(f"[audit] {sh['label']} ...", flush=True)
        if sh["closure"] not in baselines:
            baselines[sh["closure"]] = build_baseline(sh["closure"])
        row = run_one(sh, baselines[sh["closure"]])
        verdict, beh = classify(row)
        results.append((sh, row, verdict, beh))
        print(f"[audit]   -> {verdict} ({len(beh)} behavioural channels: {', '.join(beh) or 'none'})",
              flush=True)

    # markdown report
    cols = [lab for _c, lab, _k in PANEL]
    lines = []
    lines.append("# Transmission audit (Stage 1a)\n")
    lines.append(f"Horizon {START}–{END} ({PERIODS} quarters), final-period response "
                 "vs an unchanged baseline. Generated by `obr_macro/transmission_audit.py`.\n")
    lines.append("| Shock | Verdict | " + " | ".join(cols) + " |")
    lines.append("|---|---|" + "|".join(["---"] * len(cols)) + "|")
    for sh, row, verdict, _beh in results:
        cells = [_fmt(kind, row.get(code)) for code, _l, kind in PANEL]
        lines.append(f"| {sh['label']} | **{verdict}** | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## Reading this\n")
    lines.append("- **transmitting** — the shock reaches behavioural variables "
                 "(consumption, investment, jobs, prices), not just the spending identity.")
    lines.append("- **identity-only** — GDP moves but no behavioural channel does; "
                 "the multiplier is missing and the result is just the mechanical add to demand.")
    lines.append("- **dead** — nothing moves; the shock does not propagate. These are the "
                 "first channels to fix in Stage 1b.")
    lines.append("")
    counts = {}
    for _s, _r, v, _b in results:
        counts[v] = counts.get(v, 0) + 1
    lines.append("**Summary:** " + ", ".join(f"{n} {k}" for k, n in sorted(counts.items())) + ".")
    lines.append("")

    out = "docs/transmission_audit.md"
    with open(out, "w") as f:
        f.write("\n".join(lines))
    print(f"[audit] wrote {out}", flush=True)


if __name__ == "__main__":
    main()
