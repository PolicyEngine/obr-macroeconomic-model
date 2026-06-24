"""Stage 1c — full ONS pull into a vendored snapshot.

Fetches every exogenous-root variable the model needs and whose ONS CDID is
known: the single-series roots directly, and the compound roots by evaluating
their formula over the component CDIDs. Each raw fetch is cached so the pull is
resumable and reproducible, and the result is written as a committed snapshot
(obr_macro/seeds/ons_exogenous_snapshot.csv) that load_obr_data can merge in.

    uv run python -m obr_macro.ons_pull
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

from obr_macro.data import load_obr_data, DATA_DIR, ensure_model_code
from obr_macro.transpiler import parse_model_file
from obr_macro.ons_fetch import fetch_series

CACHE = DATA_DIR / "ons_cache"                       # gitignored, transient
SEEDS = Path(__file__).parent / "seeds"              # committed
SNAPSHOT = SEEDS / "ons_exogenous_snapshot.csv"
CDID_RE = re.compile(r"\b[A-Z][A-Z0-9]{3}\b")


def _lhs_var(lhs):
    m = re.search(r"[A-Z][A-Z0-9_]*", lhs.replace("@IDENTITY", ""))
    return m.group(0) if m else lhs


def _refs(eq):
    out = set()
    for m in re.finditer(r"v\['([A-Z0-9_]+)'\]", eq.python_expr):
        out.add(m.group(1))
    for m in re.finditer(r"_lag\('([A-Z0-9_]+)'", eq.python_expr):
        out.add(m.group(1))
    return out


def get_roots(df):
    """Return (simple {code: cdid}, compound {code: formula}) for every missing
    variable that carries an ONS code, given the loaded data frame ``df``.

    Includes endogenous variables: pulling their observed ONS series gives the
    circular fiscal/financial blocks real balancing data, which both anchors
    them (add-factors) and stops them diverging when solved.
    """
    eqs = parse_model_file(str(ensure_model_code()), include_behavioral=False)
    referenced = set().union(*(_refs(e) for e in eqs))

    present = {c for c in df.columns if df[c].notna().any()}
    missing = sorted(referenced - present)

    mdp = Path(__file__).parent.parent / "dashboard/public/data/model_data.json"
    ons = {it["code"]: (it.get("ons") or "").strip() for it in json.load(open(mdp))["items"]}

    simple, compound = {}, {}
    for v in missing:
        code = ons.get(v, "")
        if not code or code.upper() in ("", "NO CODES", "N/A", "-"):
            continue
        if re.search(r"[+\-/*()]", code) or " " in code:
            compound[v] = code        # arithmetic over several CDIDs
        else:
            simple[v] = code          # a single ONS series
    return simple, compound


def fetch_cached(cdid):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{cdid}.csv"
    if f.exists():
        s = pd.read_csv(f, index_col=0)["value"]
        s.index = pd.PeriodIndex(s.index, freq="Q")
        return s
    s, _title, _freq = fetch_series(cdid)
    if s is None or s.empty:
        return None
    s = s.dropna()
    s.rename("value").to_frame().to_csv(f)
    time.sleep(0.4)
    return s


def eval_compound(formula):
    cdids = sorted(set(CDID_RE.findall(formula)))
    ns = {}
    for c in cdids:
        try:
            s = fetch_cached(c)
        except Exception as e:
            return None, f"component {c}: {type(e).__name__}: {e}"
        if s is None:
            return None, f"missing component {c}"
        ns[c] = s
    try:
        result = eval(formula, {"__builtins__": {}}, ns)  # series arithmetic
        return result.dropna(), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def main():
    idx = load_obr_data().index                    # full (snapshot-extended) index
    df_efo = load_obr_data(merge_snapshot=False)    # EFO-only, to find what's missing
    simple, compound = get_roots(df_efo)
    print(f"roots to pull: {len(simple)} simple + {len(compound)} compound\n")
    cols = {}
    fails = []

    for i, (code, cdid) in enumerate(sorted(simple.items()), 1):
        try:
            s = fetch_cached(cdid)
        except Exception as e:
            s, err = None, f"{type(e).__name__}: {e}"
        if s is None or s.empty:
            fails.append((code, cdid, "no data"))
            print(f"  [{i}/{len(simple)}] {code:9} {cdid:6} FAIL")
            continue
        cols[code] = s.reindex(idx)
        if i % 20 == 0:
            print(f"  ...{i}/{len(simple)} simple fetched")

    print(f"simple done: {sum(1 for c in simple if c in cols)}/{len(simple)} ok\n")

    for code, formula in sorted(compound.items()):
        s, err = eval_compound(formula)
        if s is None or s.empty:
            fails.append((code, formula, err))
            print(f"  compound {code:9} = {formula:30} FAIL ({err})")
            continue
        cols[code] = s.reindex(idx)
    print(f"compound done: {sum(1 for c in compound if c in cols)}/{len(compound)} ok\n")

    SEEDS.mkdir(parents=True, exist_ok=True)
    snap = pd.DataFrame(cols).reindex(idx)
    snap.index = snap.index.astype(str)
    snap.to_csv(SNAPSHOT)
    print(f"wrote {SNAPSHOT}: {snap.shape[1]} series x {snap.shape[0]} quarters")
    cov = snap.notna().any().sum()
    print(f"series with any data: {cov}/{snap.shape[1]}")
    if fails:
        print(f"\n{len(fails)} failures:")
        for code, src, why in fails:
            print(f"   {code:9} {src:32} {why}")


if __name__ == "__main__":
    main()
