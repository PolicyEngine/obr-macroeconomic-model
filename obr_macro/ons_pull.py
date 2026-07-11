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

import pandas as pd

from obr_macro.data import load_obr_data, DATA_DIR, ensure_model_code
from obr_macro.transpiler import parse_model_file
from obr_macro.ons_fetch import fetch_series

CACHE = DATA_DIR / "ons_cache"  # gitignored, transient
SEEDS = Path(__file__).parent / "seeds"  # committed
SNAPSHOT = SEEDS / "ons_exogenous_snapshot.csv"
MANIFEST = SEEDS / "snapshot_manifest.json"
CDID_RE = re.compile(r"\b[A-Z][A-Z0-9]{3}\b")
# Compound glossary formulas may only contain CDIDs and simple arithmetic.
FORMULA_RE = re.compile(r"[A-Za-z0-9_ +\-*/().]+")


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

    mdp = Path(__file__).parent / "seeds/model_glossary.json"
    ons = {
        it["code"]: (it.get("ons") or "").strip()
        for it in json.load(open(mdp))["items"]
    }

    simple, compound = {}, {}
    for v in missing:
        code = ons.get(v, "")
        if not code or code.upper() in ("", "NO CODES", "N/A", "-"):
            continue
        if re.search(r"[+\-/*()]", code) or " " in code:
            compound[v] = code  # arithmetic over several CDIDs
        else:
            simple[v] = code  # a single ONS series
    return simple, compound


def fetch_cached(cdid):
    """Fetch a CDID with an on-disk cache. Returns (series, meta).

    The cache stores the already-aggregated quarterly values plus a meta
    sidecar (title/dataset/frequency/aggregation). A cache entry without the
    meta sidecar predates the typed flow/stock aggregation fix and is treated
    as a miss so it gets re-fetched with the correct aggregation.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{cdid}.csv"
    mf = CACHE / f"{cdid}.meta.json"
    if f.exists() and mf.exists():
        s = pd.read_csv(f, index_col=0)["value"]
        s.index = pd.PeriodIndex(s.index, freq="Q")
        return s, json.load(open(mf))
    s, meta = fetch_series(cdid)
    if s is None or s.empty:
        return None, meta
    s = s.dropna()
    s.rename("value").to_frame().to_csv(f)
    json.dump(meta, open(mf, "w"), indent=1)
    time.sleep(0.4)
    return s, meta


def eval_compound(formula):
    """Evaluate a glossary arithmetic formula over its component CDIDs.

    Returns (series, error, component_metas). The formula is validated against
    a strict allowlist (CDIDs, digits, whitespace and + - * / parentheses,
    no '**') before it is eval'd with builtins stripped.
    """
    if not FORMULA_RE.fullmatch(formula) or "**" in formula:
        return None, f"formula rejected by allowlist: {formula!r}", []
    cdids = sorted(set(CDID_RE.findall(formula)))
    ns = {}
    metas = []
    for c in cdids:
        try:
            s, meta = fetch_cached(c)
        except Exception as e:
            return None, f"component {c}: {type(e).__name__}: {e}", metas
        if s is None:
            return None, f"missing component {c}", metas
        ns[c] = s
        metas.append(meta)
    try:
        result = eval(formula, {"__builtins__": {}}, ns)  # series arithmetic
        return result.dropna(), None, metas
    except Exception as e:
        return None, f"{type(e).__name__}: {e}", metas


def main():
    idx = load_obr_data().index  # full (snapshot-extended) index
    df_efo = load_obr_data(merge_snapshot=False)  # EFO-only, to find what's missing
    simple, compound = get_roots(df_efo)
    print(f"roots to pull: {len(simple)} simple + {len(compound)} compound\n")
    cols = {}
    fails = []
    manifest = {}

    for i, (code, cdid) in enumerate(sorted(simple.items()), 1):
        err = None
        try:
            s, meta = fetch_cached(cdid)
        except Exception as e:
            s, meta, err = None, None, f"{type(e).__name__}: {e}"
        if s is None or s.empty:
            why = err or "no data"
            fails.append((code, cdid, why))
            print(f"  [{i}/{len(simple)}] {code:9} {cdid:6} FAIL ({why})")
            continue
        cols[code] = s.reindex(idx)
        manifest[code] = {
            "cdid": cdid,
            "dataset": meta.get("dataset", ""),
            "title": meta.get("title", ""),
            "source_freq": meta.get("source_freq"),
            "aggregation": meta.get("aggregation"),
            "type": meta.get("type"),
        }
        if i % 20 == 0:
            print(f"  ...{i}/{len(simple)} simple fetched")

    print(f"simple done: {sum(1 for c in simple if c in cols)}/{len(simple)} ok\n")

    for code, formula in sorted(compound.items()):
        s, err, metas = eval_compound(formula)
        if s is None or s.empty:
            fails.append((code, formula, err))
            print(f"  compound {code:9} = {formula:30} FAIL ({err})")
            continue
        cols[code] = s.reindex(idx)
        manifest[code] = {
            "formula": formula,
            "components": [
                {
                    "cdid": m.get("cdid"),
                    "dataset": m.get("dataset", ""),
                    "title": m.get("title", ""),
                    "source_freq": m.get("source_freq"),
                    "aggregation": m.get("aggregation"),
                    "type": m.get("type"),
                }
                for m in metas
            ],
        }
    print(
        f"compound done: {sum(1 for c in compound if c in cols)}/{len(compound)} ok\n"
    )

    SEEDS.mkdir(parents=True, exist_ok=True)
    snap = pd.DataFrame(cols).reindex(idx)
    snap.index = snap.index.astype(str)
    snap.to_csv(SNAPSHOT)
    with open(MANIFEST, "w") as fh:
        json.dump(
            {
                "pulled": pd.Timestamp.now().strftime("%Y-%m-%d"),
                "n_series": len(manifest),
                "series": manifest,
            },
            fh,
            indent=1,
            sort_keys=True,
        )
    print(f"wrote {SNAPSHOT}: {snap.shape[1]} series x {snap.shape[0]} quarters")
    print(f"wrote {MANIFEST}: {len(manifest)} series")
    cov = snap.notna().any().sum()
    print(f"series with any data: {cov}/{snap.shape[1]}")
    if fails:
        print(f"\n{len(fails)} failures:")
        for code, src, why in fails:
            print(f"   {code:9} {src:32} {why}")


if __name__ == "__main__":
    main()
