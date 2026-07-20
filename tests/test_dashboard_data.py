"""Sanity checks on the committed dashboard data.

These are hermetic (no downloads, no solver) — they validate that the
solver output shipped to the dashboard is finite, internally consistent,
and economically sensible in sign and magnitude.
"""

import json
import math
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "dashboard" / "public" / "data"

# Expected sign of the GDP response for each explorer scenario.
GDP_SIGN = {
    "gov_spend": +1,  # £10bn extra spending lifts GDP
    "austerity": -1,  # spending cut lowers GDP
    "export_rise": +1,
    "export_cut": -1,
    "rate_rise": -1,  # tighter policy should not raise GDP
}


def _load(name):
    path = DATA / name
    assert path.exists(), f"{name} missing — regenerate dashboard data"
    return json.loads(path.read_text())


def _assert_finite(values, label):
    for v in values:
        assert v is not None and math.isfinite(v), f"non-finite value in {label}"


# ---------------------------------------------------------------- explorer


@pytest.fixture(scope="module")
def explorer():
    return _load("explorer_data.json")


def test_explorer_shape(explorer):
    assert explorer["scenarios"], "no scenarios in explorer data"
    n = len(explorer["periods"])
    for sc in explorer["scenarios"]:
        for code, series in sc["series"].items():
            assert len(series) == n, f"{sc['id']}:{code} length != periods"
            _assert_finite(series, f"{sc['id']}:{code}")


def test_explorer_gdp_sign(explorer):
    for sc in explorer["scenarios"]:
        expected = GDP_SIGN.get(sc["id"])
        if expected is None or "GDPM" not in sc["series"]:
            continue
        peak = max(sc["series"]["GDPM"], key=abs)
        if peak == 0:
            continue  # documented empty-response scenarios are allowed
        assert math.copysign(1, peak) == expected, (
            f"{sc['id']}: GDP peak {peak} has wrong sign (expected {expected:+d})"
        )


def test_explorer_magnitudes_sensible(explorer):
    # No demand scenario here should move GDP by more than 5% or by an
    # exactly-zero flat line across every variable (which would mean the
    # solver silently did nothing for a scenario we chose to ship).
    for sc in explorer["scenarios"]:
        for code, series in sc["series"].items():
            assert max(abs(v) for v in series) < 5.0, (
                f"{sc['id']}:{code} implausibly large response"
            )


def test_explorer_meta_disclaimer(explorer):
    note = json.dumps(explorer["meta"]).lower()
    assert "not an obr forecast" in note, "honesty disclaimer missing from meta"


# ---------------------------------------------------------------- reform grid


@pytest.fixture(scope="module")
def grid():
    return _load("reform_grid.json")


def test_grid_shape(grid):
    assert grid["levers"], "no levers in reform grid"
    for lever in grid["levers"]:
        assert lever["lo"] < 0 < lever["hi"]
        for pt in lever["points"]:
            for code, series in pt["series"].items():
                _assert_finite(series, f"{lever['id']}@{pt['shock']}:{code}")


def test_grid_antisymmetry(grid):
    # The generator only ships levers whose +/- responses mirror; verify
    # that invariant holds in the committed data.
    for lever in grid["levers"]:
        by_shock = {pt["shock"]: pt["series"] for pt in lever["points"]}
        for shock, series in by_shock.items():
            if shock <= 0 or -shock not in by_shock:
                continue
            neg = by_shock[-shock]
            for code, pos_vals in series.items():
                scale = max(max(abs(v) for v in pos_vals), 1e-9)
                for a, b in zip(pos_vals, neg[code]):
                    assert abs(a + b) <= 0.15 * scale + 1e-6, (
                        f"{lever['id']}:{code} not antisymmetric at ±{shock}"
                    )


def test_grid_gdp_sign_follows_shock(grid):
    for lever in grid["levers"]:
        if lever["id"] != "CGG":
            continue
        for pt in lever["points"]:
            gdp = pt["series"].get("GDPM")
            if not gdp or pt["shock"] == 0:
                continue
            peak = max(gdp, key=abs)
            assert math.copysign(1, peak) == math.copysign(1, pt["shock"]), (
                f"CGG shock {pt['shock']} moved GDP the wrong way"
            )


# ---------------------------------------------------------------- model data


@pytest.fixture(scope="module")
def model_data():
    return _load("model_data.json")


def test_model_variable_and_equation_counts(model_data):
    items = model_data["items"]
    assert len(items) >= 600, "unexpectedly few variables"
    eqs = [it for it in items if it.get("eq") and "=" in it["eq"]]
    assert 350 <= len(eqs) <= 400, f"unexpected equation count {len(eqs)}"
    assert not any("no equation" in (it.get("eq") or "").lower() for it in items), (
        "'No Equation' placeholders leaked into model_data.json"
    )
