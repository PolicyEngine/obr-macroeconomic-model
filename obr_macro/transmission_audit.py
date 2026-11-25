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

from obr_macro.reform_analysis import (
    _build_reform_template,
    apply_spending_shock,
    resolve_nominal_consistent,
    resolve_nominal_gdp_pin,
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
# Under the default (demand) closure business investment is not a behavioural
# variable: it is the listing's residual IBUS = IF - GGI - PCIH - PCLEB - IH -
# IPRL with total investment IF exogenous, so it moves only as the mirror
# image of real government investment and its deflator. It is still shown in
# the table, but it does not count towards a "transmitting" verdict there;
# run_reform labels the same government-investment shock a dead channel.
# Under the investment closure IBUS has its own equation and does count.
RESIDUAL_UNDER_STANDARD_CLOSURE = {"IBUS"}

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
    """Unsolved template for one shock: the one ``run_reform`` builds.

    This used to repeat the construction in
    ``reform_analysis._build_reform_template`` by hand, and fell behind it:
    when the nominal-GDP pin became ``run_reform``'s default closure (#42) the
    copy here stayed on the published closure, under which no quarter
    converges, so the table was a difference of two non-converged solves while
    the page said the runs were solved exactly as ``run_reform`` solves them.
    Calling the same builder keeps the two in step: the default closure (the
    pin) for the demand rows, the investment closure for corporation tax, the
    instrument exogenous on the template both runs clone, and the anchoring
    residuals frozen into both.
    """
    return _build_reform_template(var, START, END, closure == "investment")


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
    # As run_reform applies it: a government-consumption shock carries its
    # nominal legs under the default closure, so borrowing moves with it.
    pin = resolve_nominal_gdp_pin(None, shock["closure"] == "investment")
    apply_spending_shock(
        sh,
        shock["var"],
        size,
        START,
        PERIODS,
        nominal_consistent=resolve_nominal_consistent(None, shock["var"], pin),
    )

    base.solve(START, END)
    sh.solve(START, END)
    bdat, sdat = base.data, sh.data
    for run in (base, sh):
        status = (getattr(run, "last_solve_report", None) or {}).get("exit_status", {})
        row_status = [p for p, how in status.items() if how != "tol"]
        if row_status:
            raise RuntimeError(
                f"{shock['label']}: {len(row_status)} of {len(status)} quarters "
                "did not reach the solver tolerance; the audit table would be "
                "a difference of non-converged solves."
            )

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


def classify(row, closure="investment"):
    """Classify a shock's response row.

    ``closure`` is the shock's closure: under "standard" the residual
    business-investment identity is left out of the behavioural channels
    (RESIDUAL_UNDER_STANDARD_CLOSURE). The default counts every channel.

    Channels whose response clears the threshold with >=20% headroom count as
    solid; channels within ±20% of the threshold are only "marginal". A verdict
    that rests solely on marginal channels is flagged "(marginal)".
    """
    gdp = row.get("GDPM")
    gdp_moves = _material("pct", gdp)
    beh_solid, beh_marginal = [], []
    behavioural = BEHAVIOURAL
    if closure == "standard":
        behavioural = BEHAVIOURAL - RESIDUAL_UNDER_STANDARD_CLOSURE
    for code, _l, kind in PANEL:
        if code not in behavioural:
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


FRONT_MATTER = "---\nicon: material/transit-connection-variant\n---\n"


def audit():
    """Run every shock and return ``[(shock, row, verdict, channels), ...]``."""
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
        verdict, beh = classify(row, sh["closure"])
        results.append((sh, row, verdict, beh))
        print(
            f"[audit]   -> {verdict} ({len(beh)} behavioural channels: {', '.join(beh) or 'none'})",
            flush=True,
        )
    return results


def render(results):
    """The markdown page for ``docs/transmission_audit.md``."""
    cols = [lab for _c, lab, _k in PANEL]
    lines = [FRONT_MATTER]
    lines.append("# Transmission audit (Stage 1a)\n")
    lines.append(
        f"Horizon {START}–{END} ({PERIODS} quarters), final-period response "
        "vs an unchanged baseline. Each pair of runs is built and solved the "
        "way `run_reform` does it: the default closure (the nominal-GDP pin) "
        "for every row except corporation tax, which needs the investment "
        "closure; both runs around the anchored EFO baseline; every quarter "
        "of every solve converged to tolerance. Generated by "
        "`python -m obr_macro.transmission_audit`; "
        "`tests/test_model_invariants.py` checks that this page matches what "
        "the module produces.\n"
    )
    lines.append("| Shock | Verdict | " + " | ".join(cols) + " |")
    lines.append("|---|---|" + "|".join(["---"] * len(cols)) + "|")
    for sh, row, verdict, _beh in results:
        cells = [_fmt(kind, row.get(code)) for code, _l, kind in PANEL]
        lines.append(f"| {sh['label']} | **{verdict}** | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## Reading this\n")
    lines.append(
        "- **transmitting**: the shock reaches behavioural variables "
        "(consumption, investment, jobs, prices), not just the spending identity."
    )
    lines.append(
        "- **identity-only**: GDP moves but no behavioural channel does; "
        "the multiplier is missing and the result is just the mechanical add to demand."
    )
    lines.append("- **dead**: neither GDP nor any behavioural channel moves.")
    lines.append("")
    lines.append(
        "> **A 'transmitting' verdict is about wiring, not about the answer being "
        "right.** *Gov consumption* is identity-only: GDP moves by about the "
        "shock and consumption by less than the threshold, which is what a "
        "flat multiplier of 1.0 looks like. *Gov investment*, *sterling* and "
        "*oil* are dead under the default closure: trade, jobs and prices do "
        "not move at all, and GDP and consumption move by less than a "
        "hundredth of a per cent, well under the threshold below. Their "
        "*Bus. invest.* entries are not a business-investment response. "
        "Under the default closure that column "
        "is the OBR's residual identity "
        "`IBUS = IF − GGI − PCIH − PCLEB − IH − IPRL` with total investment "
        "`IF` exogenous, so it moves only as the mirror image of real "
        "government investment `GGI = 100·GGIPS/GGIDEF` and of the "
        "investment deflator behind it. It is shown, but it does not count "
        "towards the verdict; `run_reform` labels the same government-"
        "investment shock a dead channel. Under the investment closure "
        "(the corporation tax row) business investment has its own equation "
        "and does count."
    )
    lines.append("")
    lines.append(
        "> **Before 25 Nov 2026** this page was generated under the published "
        "closure, which the module had kept after the nominal-GDP pin became "
        "the default for `run_reform`. Under that closure no quarter of a "
        "demand-closure run converges ([Limits](limitations.md), solver "
        "convergence), so the table was a difference of two non-converged "
        "solves, and it had not been regenerated since October 2026. It showed "
        "sterling at −0.05% of GDP with business investment +5.55%, oil at "
        "−0.02% and +1.08%, and Bank Rate at −0.07% and −0.03%; regenerated "
        "under the same closure on the current data those read +0.03% and "
        "−0.33%, −0.00% and +0.78%, and −0.03% and −2.05%. Neither set is a "
        "model response."
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
    return "\n".join(lines)


def main():
    out = "docs/transmission_audit.md"
    with open(out, "w") as f:
        f.write(render(audit()))
    print(f"[audit] wrote {out}", flush=True)


if __name__ == "__main__":
    main()
