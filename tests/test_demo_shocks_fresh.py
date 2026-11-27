"""``results/demo_shocks.json`` against ``run_reform`` as it is now.

Every number in docs/demo.md comes from that file, and each shock's ``attrs``
block is a copy of the labels ``run_reform`` attaches to its result. The file
is written by ``scripts/demo_shocks.py`` and nothing reran it when the code
changed: by 26 Nov 2026 the committed labels lagged the code (the gilt-yield
note still said "10-year" after the code moved to "20-year", and three
overlay flags added since were missing) although every number was unchanged.

This reruns each ``run_reform`` call of the battery and compares the four
series the script stores from it, and every label, with the committed file.
It does not rerun the script's rebuilt baseline/shocked pairs (the receipts
and household columns); ``tests/test_tax_scenarios.py`` solves those for the
tax rows.

Slow: 15 ``run_reform`` calls, about three minutes. To fix a failure:

    uv run python scripts/demo_shocks.py

and compare the numbers before committing: a label-only difference is safe to
commit, a changed number means docs/demo.md needs updating too.
"""

import importlib.util
import json
import warnings
from pathlib import Path

import pytest

from obr_macro import run_reform

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[1]

# The file stores the series rounded to three decimals of GBP m (and of a
# percentage point). The macOS arm64 run of 26 Nov 2026 matched the committed
# Linux x86-64 run on every stored value, so this is clear of platform noise.
SERIES_ATOL = 2e-3
# Unrounded floats inside the labels (solver residuals, fitted elasticities)
# differ between platforms from about the tenth significant figure.
ATTR_RTOL = 1e-6


def _script():
    spec = importlib.util.spec_from_file_location(
        "_demo_shocks_script", ROOT / "scripts" / "demo_shocks.py"
    )
    module = importlib.util.module_from_spec(spec)
    with warnings.catch_warnings():
        # The script silences warnings at import; keep that out of the session.
        spec.loader.exec_module(module)
    return module


SCRIPT = _script()
KEYS = [shock[0] for shock in SCRIPT.SHOCKS]


@pytest.fixture(scope="module")
def committed():
    return json.loads((ROOT / "results" / "demo_shocks.json").read_text())["shocks"]


def _differences(old, new, path=""):
    """Paths at which two JSON values differ, floats compared loosely."""
    if isinstance(old, dict) and isinstance(new, dict):
        out = []
        for key in sorted(set(old) | set(new)):
            where = f"{path}.{key}" if path else key
            if key not in new:
                out.append(f"{where}: in the committed file, no longer set")
            elif key not in old:
                out.append(f"{where}: set by run_reform, not in the committed file")
            else:
                out.extend(_differences(old[key], new[key], where))
        return out
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        out = []
        for i, (a, b) in enumerate(zip(old, new)):
            out.extend(_differences(a, b, f"{path}[{i}]"))
        return out
    numeric = (int, float)
    if (
        isinstance(old, numeric)
        and isinstance(new, numeric)
        and not isinstance(old, bool)
        and not isinstance(new, bool)
    ):
        if abs(old - new) <= 1e-9 + ATTR_RTOL * max(abs(old), abs(new)):
            return []
    elif old == new:
        return []
    return [f"{path}: committed {old!r}, now {new!r}"]


def test_the_battery_and_the_committed_file_list_the_same_shocks(committed):
    assert list(committed) == KEYS


@pytest.mark.parametrize("key", KEYS)
def test_run_reform_reproduces_the_committed_shock(committed, key):
    _, label, var, shock, periods, kwargs = next(
        s for s in SCRIPT.SHOCKS if s[0] == key
    )
    want = committed[key]
    assert (want["label"], want["var"], want["shock"], want["kwargs"]) == (
        label,
        var,
        shock,
        kwargs,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = run_reform(name=key, var=var, shock=shock, periods=periods, **kwargs)

    assert df["period"].tolist() == want["periods"]
    for col, old in want["run_reform"].items():
        new = [float(x) for x in df[col]]
        worst = max(abs(a - b) for a, b in zip(new, old))
        assert worst <= SERIES_ATOL, (
            f"{key}: {col} differs from results/demo_shocks.json by up to "
            f"{worst:.3f} (first quarter {old[0]} committed, {new[0]:.3f} now). "
            "Rerun scripts/demo_shocks.py and update docs/demo.md."
        )

    labels = json.loads(json.dumps(SCRIPT._attrs(df)))
    diffs = _differences(want["attrs"], labels)
    assert not diffs, (
        f"{key}: the labels in results/demo_shocks.json lag run_reform. Rerun "
        "scripts/demo_shocks.py.\n  " + "\n  ".join(diffs)
    )
