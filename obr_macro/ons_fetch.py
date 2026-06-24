"""ONS time-series fetcher (Stage 1c proof-of-concept).

Resolves a model variable's ONS CDID to a series and returns it on a quarterly
PeriodIndex, ready to merge into the model data. The old api.ons.gov.uk was
retired (Nov 2024); this uses the beta search API to resolve a CDID to its
timeseries URI, then the website `/data` JSON endpoint.

    uv run python -m obr_macro.ons_fetch
"""
from __future__ import annotations

import json
import time
import urllib.request

import numpy as np
import pandas as pd

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_SEARCH = "https://api.beta.ons.gov.uk/v1/search?q={cdid}&content_type=timeseries&limit=10"
_DATA = "https://www.ons.gov.uk{uri}/data"

# A handful of model variables -> CDID, for the proof of concept.
POC = {
    "CGIPS":  "NMES",   # CG gross fixed capital formation (£m)
    "PPIY":   "GB7S",   # producer output price index
    "POPAL":  "EBAQ",   # population, all ages
    "EMPNIC": "CEAN",   # employers' NICs (£m)
    "VREC":   "EYOO",   # net VAT receipts (£m)
}


def _get_json(url, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # ONS intermittently 502s; back off and retry
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def resolve_uris(cdid):
    d = _get_json(_SEARCH.format(cdid=cdid))
    uris = []
    for it in d.get("items", []):
        u = (it.get("uri") or "").strip("/")
        parts = u.split("/")
        if len(parts) >= 2 and parts[-2].lower() == cdid.lower():
            uris.append("/" + u)
    return uris


def fetch_series(cdid):
    """Return (Series on quarterly PeriodIndex, title, freq) for a CDID."""
    best = None
    best_n = -1
    for uri in resolve_uris(cdid):
        try:
            d = _get_json(_DATA.format(uri=uri))
        except Exception:
            continue
        n = len(d.get("quarters", [])) or len(d.get("months", [])) or len(d.get("years", []))
        if n > best_n:
            best_n, best = n, d
    if best is None:
        return None, None, None

    title = best.get("description", {}).get("title", cdid)
    q, m, y = best.get("quarters", []), best.get("months", []), best.get("years", [])

    if q:
        idx, vals = [], []
        for o in q:
            try:
                p = pd.Period(f"{o['year']}{o['quarter']}", freq="Q")
                v = float(o["value"])
            except Exception:
                continue  # keep idx and vals in lock-step (skip empty values)
            idx.append(p)
            vals.append(v)
        if not idx:
            return None, title, None
        return pd.Series(vals, index=pd.PeriodIndex(idx, freq="Q")).sort_index(), title, "quarterly"

    if m:
        idx, vals = [], []
        for o in m:
            try:
                p = pd.Period(f"{o['year']}-{o['month'][:3]}", freq="M")
                v = float(o["value"])
            except Exception:
                continue
            idx.append(p)
            vals.append(v)
        if not idx:
            return None, title, None
        s = pd.Series(vals, index=pd.PeriodIndex(idx, freq="M")).sort_index()
        return s.resample("Q").mean(), title, "monthly->Q mean"

    if y:
        idx, vals = [], []
        for o in y:
            try:
                yr = int(o["year"])
                v = float(o["value"])
            except Exception:
                continue
            idx.append(yr)
            vals.append(v)
        if not idx:
            return None, title, None
        ys = pd.Series(vals, index=idx).sort_index()
        # annual -> hold flat across the four quarters of each year
        recs = {}
        for yr, val in ys.items():
            for qn in range(1, 5):
                recs[pd.Period(f"{yr}Q{qn}", freq="Q")] = val
        return pd.Series(recs).sort_index(), title, "annual->Q (held flat)"

    return None, title, None


def main():
    print(f"Fetching {len(POC)} ONS series via the beta search + website data endpoints\n")
    for code, cdid in POC.items():
        try:
            s, title, freq = fetch_series(cdid)
        except Exception as e:
            print(f"  {code:7} ({cdid})  FAILED: {type(e).__name__}: {e}")
            continue
        if s is None or s.empty:
            print(f"  {code:7} ({cdid})  no data")
            continue
        s = s.dropna()
        tail = ", ".join(f"{p}={v:,.0f}" for p, v in s.tail(3).items())
        print(f"  {code:7} ({cdid})  {freq:22}  {len(s):3} obs  {s.index.min()}..{s.index.max()}")
        print(f"           {title[:60]}")
        print(f"           latest: {tail}\n")


if __name__ == "__main__":
    main()
