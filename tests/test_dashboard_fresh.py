"""The committed dashboard and chat data against the model that is in the tree.

``dashboard/public/data`` holds three precomputed files. The dashboard reads
all three; the chat agent (``chat/agent.py``) reads ``model_data.json`` and
``explorer_data.json`` and has no data of its own. ``test_dashboard_data.py``
checks that the files are well formed. Nothing checked that they still match
the model: after the October 2026 re-anchor the explorer and the reform grid
went three weeks without being regenerated, and the explorer's note described
scenarios as dropped that the file contained.

Fast, on every run:

- ``model_data.json`` and its packaged copy ``obr_macro/seeds/model_glossary.json``
  are rebuilt from the OBR variables workbook and compared byte for byte;
- the explorer and the reform grid record the fingerprint of the packaged
  input data they were generated from (``obr_macro.data.input_fingerprint``),
  which must equal the fingerprint of the files now in the tree;
- their scenario and lever lists, labels and notes must be the ones the
  generators would write.

Slow (``--runslow``, about five minutes): every explorer scenario and the
whole reform grid are solved again and compared with the committed numbers.
That is the check that catches a change to the model code, which the
fingerprint cannot see.

To fix a failure, regenerate from the repo root and commit the result:

    uv run python dashboard/gen_model_data.py
    uv run python dashboard/gen_explorer_data.py
    uv run python -m dashboard.gen_reform_grid
"""

import importlib.util
import json
import math
from pathlib import Path

import pytest

from obr_macro.data import input_fingerprint

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dashboard" / "public" / "data"

# The files store deltas rounded to four decimal places (GBP 0.1m, 0.0001pp).
# The demo battery regenerated on macOS arm64 on 26 Nov 2026 matched the
# committed Linux x86-64 run to all three stored decimals of GBP m, so half a
# unit in the third place of GBP bn is well clear of platform noise and well
# below the drift this guards against (GBP 1m to 22m after the October 2026
# re-anchor).
ATOL = 5e-4


def _generator(name):
    """Import a generator script from dashboard/, which is not a package."""
    spec = importlib.util.spec_from_file_location(
        f"_dashboard_{name}", ROOT / "dashboard" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load(name):
    return json.loads((DATA / name).read_text())


def _assert_series_close(got, want, where):
    assert sorted(got) == sorted(want), (
        f"{where}: the generator now keeps {sorted(got)}, the committed file "
        f"has {sorted(want)}"
    )
    for code, new in got.items():
        old = want[code]
        assert len(new) == len(old), f"{where}:{code} length changed"
        worst = max(abs(a - b) for a, b in zip(new, old))
        assert worst <= ATOL, (
            f"{where}:{code} differs from the committed file by up to "
            f"{worst:.4f} (first quarter {old[0]} committed, {new[0]} now). "
            "Regenerate the dashboard data (see this file's docstring)."
        )


EXPLORER = _generator("gen_explorer_data")

# ------------------------------------------------------------------ fast


def test_model_data_and_its_packaged_copy_match_the_generator():
    gen = _generator("gen_model_data")
    payload, n_eq = gen.build()
    text = gen.serialise(payload)
    assert n_eq > 300, f"only {n_eq} equations transpiled"
    for path in (gen.OUT, gen.SEED):
        assert path.read_text() == text, (
            f"{path.relative_to(ROOT)} is not what dashboard/gen_model_data.py "
            "writes: run `uv run python dashboard/gen_model_data.py`"
        )


@pytest.mark.parametrize("name", ["explorer_data.json", "reform_grid.json"])
def test_solved_files_were_generated_from_the_inputs_in_the_tree(name):
    recorded = _load(name)["meta"].get("inputs_sha256")
    assert recorded == input_fingerprint(), (
        f"{name} was generated from different input data (model listing, EFO "
        "workbooks or ONS snapshot) from what is in obr_macro/_data and "
        "obr_macro/seeds now. Regenerate it (see this file's docstring)."
    )


def test_explorer_scenarios_and_note_are_the_generators():
    gen = EXPLORER
    data = _load("explorer_data.json")
    assert data["meta"]["note"] == gen.NOTE
    assert (data["meta"]["start"], data["meta"]["end"]) == (gen.START, gen.END)
    want = [
        (sc["id"], sc["name"], sc["tag"], sc["var"], sc["shocklab"])
        for sc in gen.SCENARIOS
    ]
    got = [
        (sc["id"], sc["name"], sc["tag"], sc["var"], sc["shock"])
        for sc in data["scenarios"]
    ]
    # The generator drops a scenario only when no channel survives its
    # guards; every scenario it defines is in the committed file today.
    assert got == want
    assert data["variables"] == [
        {"code": c, "label": lbl, "unit": u} for c, lbl, u, _ in gen.VARS
    ]


def test_reform_grid_levers_and_note_are_the_generators():
    gen = _generator("gen_reform_grid")
    data = _load("reform_grid.json")
    assert data["meta"]["note"] == gen.NOTE
    assert (data["meta"]["start"], data["meta"]["end"]) == (gen.START, gen.END)
    keys = ("id", "name", "var", "unit", "lo", "hi", "step", "desc")
    assert [{k: lev[k] for k in keys} for lev in data["levers"]] == [
        {k: lev[k] for k in keys} for lev in gen.LEVERS
    ]
    for lev in data["levers"]:
        assert [pt["shock"] for pt in lev["points"]] == [lev["lo"], lev["hi"]]


# ------------------------------------------------------------------ slow


@pytest.mark.slow
@pytest.mark.parametrize("scenario", EXPLORER.SCENARIOS, ids=lambda sc: sc["id"])
def test_explorer_scenario_reproduces(scenario):
    committed = _load("explorer_data.json")
    want = next(sc for sc in committed["scenarios"] if sc["id"] == scenario["id"])
    periods, series = EXPLORER.run_scenario(scenario)
    assert periods == committed["periods"]
    _assert_series_close(series, want["series"], f"explorer {scenario['id']}")


@pytest.mark.slow
def test_reform_grid_reproduces():
    committed = _load("reform_grid.json")
    data = _generator("gen_reform_grid").build_data()
    assert data["periods"] == committed["periods"]
    assert [lev["id"] for lev in data["levers"]] == [
        lev["id"] for lev in committed["levers"]
    ]
    for new, old in zip(data["levers"], committed["levers"]):
        for pt_new, pt_old in zip(new["points"], old["points"]):
            assert pt_new["shock"] == pt_old["shock"]
            for series in pt_new["series"].values():
                assert all(math.isfinite(v) for v in series)
            _assert_series_close(
                pt_new["series"],
                pt_old["series"],
                f"reform grid {new['id']} at {pt_new['shock']}",
            )
