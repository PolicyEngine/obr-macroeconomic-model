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
    GDPM_EQ,
    IBUS_EQ,
    IF_EQ,
    IBUSX_EQ,
    _ensure_ibusx_inputs,
    _stabilise_investment_closure,
)

START, END = "2025Q1", "2026Q2"  # 6-quarter horizon keeps the audit tractable
PERIODS = 6  # shock sustained across the horizon

# Panel of aggregates to watch. kind: "pct" = % change vs baseline at the final
# period; "pp" = change in percentage points (for rates).
PANEL = [
    ("GDPM", "GDP", "pct"),
    ("CONS", "Consumption", "pct"),
    ("IF", "Investment", "pct"),
    ("IBUS", "Bus. invest.", "pct"),
    ("X", "Exports", "pct"),
    ("M", "Imports", "pct"),
    ("ETLFS", "Employment", "pct"),
    ("LFSUR", "Unemp. rate", "pp"),
    ("CPI", "CPI", "pct"),
    ("APH", "House prices", "pct"),
    ("RL", "Gilt yield", "pp"),
]
# Behavioural channels (everything that is NOT a pure spending identity): if a
# shock moves GDP but none of these, the behavioural multiplier is missing.
BEHAVIOURAL = {"CONS", "IBUS", "ETLFS", "LFSUR", "CPI", "X", "M", "APH", "RL"}

# Shocks. size is absolute unless rel=True, in which case it is a fraction of the
# variable's baseline value at the start period.
SHOCKS = [
    dict(
        label="Gov consumption +£1.25bn/q", var="CGG", size=1250.0, closure="standard"
    ),
    dict(label="Gov investment +£3bn/q", var="CGIPS", size=3000.0, closure="standard"),
    dict(label="Corp tax +1pp", var="TCPRO", size=0.01, closure="investment"),
    dict(label="Bank Rate +1pp", var="R", size=1.0, closure="standard"),
    dict(
        label="Sterling -10% (ERI)", var="RX", size=-0.10, closure="standard", rel=True
    ),
    dict(label="Oil price +$10/bbl", var="PBRENT", size=10.0, closure="standard"),
]

PCT_THRESH = 0.02  # % — below this a level response counts as "no move"
PP_THRESH = 0.005  # percentage points
# A response within ±20% of its threshold is a borderline call, not a
# categorical one: such channels are reported as "marginal" rather than
# cleanly transmitting/dead (e.g. Bank Rate landing at exactly 0.02%).
MARGINAL_FRAC = 0.20


def _build(closure, var):
    """Unsolved template for one shock: same construction reform_analysis uses.

    ``var`` is made exogenous HERE, on the template both runs clone, because
    apply_shock makes it exogenous on the shocked run only. Leaving the control
    with its live equation (CGG, R and PBRENT all have one) meant the control's
    instrument drifted while the shocked run's was pinned, and the reported
    "response" was that drift: it is what put a NEGATIVE GDP response to a
    government-spending INCREASE into the committed audit table. Same rationale
    as run_fiscal_shock's control run and reform_analysis's shared template.
    """
    s = FullOBRSolver(verbose=False)
    s.swap_closure("DINV", GDPM_EQ)
    if closure == "investment":
        _ensure_ibusx_inputs(s)
        s.swap_closure("IBUSX", IBUSX_EQ)
        s.swap_closure("IBUS", IBUS_EQ)
        # IF has no live equation in the published model, so this is an
        # addition; assert that rather than relying on a sentinel name that
        # never matches (the previous "IF_PLACEHOLDER" removal was a no-op).
        assert "IF" not in s.eq_for_var, "model already has a live IF equation"
        s.swap_closure("IF", IF_EQ)
    s.make_exogenous(var)
    if closure == "investment":
        # Without this the reconstructed dlog(IBUSX) closure sits in the
        # explosive MSGVA accelerator documented in
        # _stabilise_investment_closure and the corporation-tax row is
        # meaningless (the committed table read +54% on GDP for a 1pp rise).
        _stabilise_investment_closure(s, START, END)
    s._shock_active = True
    return s


def _resp(kind, base, shock):
    if base is None or shock is None or not (np.isfinite(base) and np.isfinite(shock)):
        return None
    if kind == "pct":
        return 100.0 * (shock - base) / base if abs(base) > 1e-9 else None
    return shock - base  # pp


def _material(kind, v):
    if v is None:
        return False
    return abs(v) >= (PP_THRESH if kind == "pp" else PCT_THRESH)


def _marginal(kind, v):
    """Within ±MARGINAL_FRAC of the threshold — a borderline call either way."""
    if v is None:
        return False
    thr = PP_THRESH if kind == "pp" else PCT_THRESH
    return (1 - MARGINAL_FRAC) * thr <= abs(v) < (1 + MARGINAL_FRAC) * thr


def build_template(closure, var):
    """Unsolved template both the control and the shocked run clone."""
    return _build(closure, var)


def run_one(shock, template):
    """Run one shock against a control cloned from the SAME unsolved template.

    Both runs are solved from identical starting data, so the delta is the
    policy. Cloning an already-solved baseline instead let the shocked run
    start from the control's converged values while the control started from
    the raw seeds — a second source of the drift that dominated the old table.
    """
    base = template.clone()
    sh = template.clone()

    t0 = sh.period_idx(START)
    size = shock["size"]
    if shock.get("rel"):
        base_val = sh._get(shock["var"], t0)
        size = size * base_val if np.isfinite(base_val) else 0.0
    sh.apply_shock(shock["var"], size, START, periods=PERIODS)

    base.solve(START, END)
    sh.solve(START, END)
    bdat, sdat = base.data, sh.data

    tN = base.period_idx(END)
    row = {}
    for code, _lab, kind in PANEL:
        if code in bdat.columns and code in sdat.columns:
            row[code] = _resp(
                kind, float(bdat.iloc[tN][code]), float(sdat.iloc[tN][code])
            )
        else:
            row[code] = None
    return row


def classify(row):
    """Classify a shock's response row.

    Channels whose response clears the threshold with >=20% headroom count as
    solid; channels within ±20% of the threshold are only "marginal". A verdict
    that rests solely on marginal channels is flagged "(marginal)".
    """
    gdp = row.get("GDPM")
    gdp_moves = _material("pct", gdp)
    beh_solid, beh_marginal = [], []
    for code, _l, kind in PANEL:
        if code not in BEHAVIOURAL:
            continue
        v = row.get(code)
        if _marginal(kind, v):
            beh_marginal.append(code)
        elif _material(kind, v):
            beh_solid.append(code)
    if beh_solid:
        return "transmitting", beh_solid + beh_marginal
    if beh_marginal:
        return "transmitting (marginal)", beh_marginal
    if gdp_moves:
        return "identity-only", []
    return "dead", []


def _fmt(kind, v):
    if v is None:
        return "—"
    unit = "pp" if kind == "pp" else "%"
    return f"{v:+.2f}{unit}"


def main():
    # One unsolved template per (closure, instrument): the instrument must be
    # exogenous on the template, so templates cannot be shared across shocks
    # that use different instruments.
    templates = {}
    results = []
    for sh in SHOCKS:
        print(f"[audit] {sh['label']} ...", flush=True)
        key = (sh["closure"], sh["var"])
        if key not in templates:
            templates[key] = build_template(*key)
        row = run_one(sh, templates[key])
        verdict, beh = classify(row)
        results.append((sh, row, verdict, beh))
        print(
            f"[audit]   -> {verdict} ({len(beh)} behavioural channels: {', '.join(beh) or 'none'})",
            flush=True,
        )

    # markdown report
    cols = [lab for _c, lab, _k in PANEL]
    lines = []
    lines.append("# Transmission audit (Stage 1a)\n")
    lines.append(
        f"Horizon {START}–{END} ({PERIODS} quarters), final-period response "
        "vs an unchanged baseline. Generated by `obr_macro/transmission_audit.py`.\n"
    )
    lines.append("| Shock | Verdict | " + " | ".join(cols) + " |")
    lines.append("|---|---|" + "|".join(["---"] * len(cols)) + "|")
    for sh, row, verdict, _beh in results:
        cells = [_fmt(kind, row.get(code)) for code, _l, kind in PANEL]
        lines.append(f"| {sh['label']} | **{verdict}** | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## Reading this\n")
    lines.append(
        "- **transmitting** — the shock reaches behavioural variables "
        "(consumption, investment, jobs, prices), not just the spending identity."
    )
    lines.append(
        "- **identity-only** — GDP moves but no behavioural channel does; "
        "the multiplier is missing and the result is just the mechanical add to demand."
    )
    lines.append(
        "- **dead** — nothing moves; the shock does not propagate. These are the "
        "first channels to fix in Stage 1b."
    )
    lines.append("")
    lines.append(
        "> **A 'transmitting' verdict is about wiring, not about the answer being "
        "right.** Two rows to read with care. *Gov investment* registers as "
        "transmitting only through business investment: `IF` has no live "
        "equation, so the CGIPS chain never reaches the GDP identity and the "
        "GDP column is deflator residue of indeterminate sign, not a public "
        "investment multiplier. *Gov consumption* is correctly identity-only — "
        "GDP moves by exactly the shock and nothing behavioural responds, which "
        "is what a flat multiplier of 1.0 looks like."
    )
    lines.append("")
    lines.append(
        f"Materiality thresholds: a level response counts as a move at "
        f"|Δ| ≥ {PCT_THRESH}% and a rate response at |Δ| ≥ {PP_THRESH}pp. "
        f"Responses within ±{int(100 * MARGINAL_FRAC)}% of the threshold are "
        "borderline: a verdict resting only on such channels is flagged "
        "**(marginal)** rather than treated as categorical."
    )
    lines.append("")
    counts = {}
    for _s, _r, v, _b in results:
        counts[v] = counts.get(v, 0) + 1
    lines.append(
        "**Summary:** " + ", ".join(f"{n} {k}" for k, n in sorted(counts.items())) + "."
    )
    lines.append("")

    out = "docs/transmission_audit.md"
    with open(out, "w") as f:
        f.write("\n".join(lines))
    print(f"[audit] wrote {out}", flush=True)


if __name__ == "__main__":
    main()
