"""Stage 1c scoping — what data is actually missing, and is it fetchable?

Stage 1c's probe showed the blocker is data coverage: ~400 variables the
equations reference are absent from the loaded EFO data. This splits that set
into:

  - endogenous-missing : has its own equation -> would compute once its inputs
                         exist (no external data needed; unblocked by the roots),
  - exogenous-missing   : no equation -> genuinely needs an external value,
      * with an ONS code   -> fetchable from ONS,
      * without an ONS code -> a policy / calibration constant to be set.

Fast (no forward solve — just parse + data load).

Run from the repo root:
    uv run python -m obr_macro.stage1c_scope
"""

from __future__ import annotations

import json
import re

from obr_macro.data import load_obr_data, DATA_DIR, ensure_model_code
from obr_macro.transpiler import parse_model_file


def lhs_var(lhs):
    m = re.search(r"[A-Z][A-Z0-9_]*", lhs.replace("@IDENTITY", ""))
    return m.group(0) if m else lhs


def referenced_vars(eq):
    out = set()
    for m in re.finditer(r"v\['([A-Z0-9_]+)'\]", eq.python_expr):
        out.add(m.group(1))
    for m in re.finditer(r"_lag\('([A-Z0-9_]+)'", eq.python_expr):
        out.add(m.group(1))
    return out


def main():
    eqs = parse_model_file(str(ensure_model_code()), include_behavioral=False)
    has_eq = {lhs_var(eq.lhs) for eq in eqs}
    referenced = set()
    for eq in eqs:
        referenced |= referenced_vars(eq)

    df = load_obr_data()
    present = {c for c in df.columns if df[c].notna().any()}

    missing = sorted(referenced - present)
    endo_missing = [v for v in missing if v in has_eq]
    exo_missing = [v for v in missing if v not in has_eq]

    # ONS codes from the variables glossary
    ons = {}
    mdp = DATA_DIR.parent / "obr_macro/seeds/model_glossary.json"
    if mdp.exists():
        for it in json.load(open(mdp))["items"]:
            ons[it["code"]] = (it.get("ons") or "").strip()

    def has_ons(v):
        code = ons.get(v, "")
        return bool(code) and code.upper() not in ("", "NO CODES", "N/A", "-")

    exo_with_ons = [v for v in exo_missing if has_ons(v)]
    exo_without_ons = [v for v in exo_missing if not has_ons(v)]
    # simple (single series) vs compound (sum/diff) ONS codes
    exo_simple = [v for v in exo_with_ons if not re.search(r"[+\-/]", ons[v])]
    exo_compound = [v for v in exo_with_ons if re.search(r"[+\-/]", ons[v])]

    print(
        f"equations: {len(eqs)} | referenced vars: {len(referenced)} | present in data: {len(present)}"
    )
    print(f"MISSING referenced vars: {len(missing)}")
    print(f"  endogenous (would compute once inputs exist): {len(endo_missing)}")
    print(f"  exogenous ROOTS (need external value):         {len(exo_missing)}")
    print(
        f"      - with ONS code (fetchable):  {len(exo_with_ons)}  "
        f"(simple {len(exo_simple)}, compound {len(exo_compound)})"
    )
    print(f"      - no ONS code (policy/calib): {len(exo_without_ons)}")

    print("\nEXOGENOUS ROOTS with a simple ONS series (the first data to pull):")
    for v in exo_simple:
        print(
            f"   {v:12} {ons[v]:18} {next((it['desc'] for it in json.load(open(mdp))['items'] if it['code'] == v), '')[:48]}"
        )

    print("\nEXOGENOUS ROOTS with compound ONS codes (need construction):")
    print("   " + ", ".join(f"{v}={ons[v]}" for v in exo_compound[:25]))

    print("\nEXOGENOUS ROOTS with NO ONS code (policy/calibration constants):")
    print("   " + ", ".join(exo_without_ons))


if __name__ == "__main__":
    main()
