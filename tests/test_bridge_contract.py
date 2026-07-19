"""Contract tests for the public API consumed by downstream callers.

``run_reform`` is this repo's half of the microsimulation bridge: an externally
costed reform (e.g. a PolicyEngine static-costing revenue path, one value per
quarter) goes in as ``shock``, and the returned DataFrame is what the consumer
(PolicyEngine Macro's ScoreResult) reads to build a score. That consumer lives
in another repository, so nothing in *this* repo's CI previously failed if the
column names, their arithmetic relationships, the period labelling or the
keyword-argument names changed. Renaming ``delta_gdp_bn`` or emitting
``period`` as a Period object rather than "2025Q1" would break the bridge
silently and be caught only downstream, after release.

These tests pin that surface. They are hermetic: the expensive solver build is
monkeypatched out with a fake template (the same device as
tests/test_apply_shock.py), so they run in milliseconds on every PR — which is
the point, since the slow suites only run post-merge.

They deliberately assert the *contract*, not the economics: the numeric
invariants here are exact identities between reported columns, not tolerances.
"""

import inspect

import numpy as np
import pandas as pd
import pytest

import obr_macro
from obr_macro.full_solver import FullOBRSolver

# The exact schema downstream consumers read. Order is part of the contract:
# the frame is serialised to records/CSV for the MCP server.
EXPECTED_COLUMNS = [
    "period",
    "reform",
    "delta_gdp_m",
    "delta_gdp_bn",
    "pct_gdp",
    "delta_cons_m",
    "delta_if_m",
]

# Keyword names callers pass by name. Renaming any of these is a breaking change.
EXPECTED_RUN_REFORM_KWARGS = [
    "name",
    "var",
    "shock",
    "start",
    "end",
    "periods",
    "investment_closure",
]


# --- Package surface --------------------------------------------------------


def test_public_exports_are_stable_and_importable():
    """Everything promised by __all__ must actually exist on the package."""
    expected = {
        "load_obr_data",
        "DATA_DIR",
        "parse_model_file",
        "ParsedEquation",
        "FullOBRSolver",
        "run_reform",
        "run_five_reforms",
    }
    assert set(obr_macro.__all__) >= expected, "public export removed from __all__"
    for name in obr_macro.__all__:
        assert hasattr(obr_macro, name), f"__all__ promises {name}, not importable"


def test_run_reform_keyword_names_are_stable():
    sig = inspect.signature(obr_macro.run_reform)
    assert list(sig.parameters) == EXPECTED_RUN_REFORM_KWARGS


def test_run_reform_defaults_are_stable():
    """Callers rely on the default horizon; a silent change moves every score."""
    sig = inspect.signature(obr_macro.run_reform)
    assert sig.parameters["start"].default == "2025Q1"
    assert sig.parameters["end"].default == "2027Q4"
    assert sig.parameters["periods"].default == 12
    assert sig.parameters["investment_closure"].default is False


# --- Fake template: a solvable stand-in with a plausible shock response ------


class _BridgeTemplate:
    """Minimal run_reform template whose GDP responds linearly to the shock.

    ``clone()`` hands back a bare solver; ``solve()`` is a no-op, so whatever
    ``apply_shock`` wrote into the shocked clone's frame stays there. GDPM is
    seeded from the shocked variable so the delta columns carry real numbers
    and their arithmetic relationships can be checked.
    """

    VAR = "CGG"
    BASE = 1000.0

    def __init__(self, periods: int = 8):
        index = pd.period_range("2025Q1", periods=periods, freq="Q")
        proto = FullOBRSolver.__new__(FullOBRSolver)
        proto.verbose = False
        proto.equations = []
        proto._build_equation_index()
        proto.data = pd.DataFrame(
            {
                self.VAR: [self.BASE] * periods,
                "CONS": [self.BASE] * periods,
                "IF": [self.BASE] * periods,
            },
            index=index,
        )
        proto.index = index
        self._proto = proto

    def clone(self):
        import copy

        c = copy.copy(self._proto)
        c.data = self._proto.data.copy()

        def _solve(start, end, _c=c):
            # GDPM tracks the (possibly shocked) spending variable, so a shock
            # of +X in a quarter shows up as delta_gdp_m == +X.
            _c.data["GDPM"] = _c.data[self.VAR] * 10.0

        c.solve = _solve
        return c


@pytest.fixture
def bridge(monkeypatch):
    from obr_macro import reform_analysis

    monkeypatch.setattr(
        reform_analysis, "_build_reform_template", lambda *a, **k: _BridgeTemplate()
    )
    return reform_analysis


# --- Output schema ----------------------------------------------------------


def test_output_columns_exact_and_ordered(bridge):
    df = bridge.run_reform("r", "CGG", 100.0, "2025Q1", "2025Q4", periods=4)
    assert list(df.columns) == EXPECTED_COLUMNS


def test_output_row_count_matches_start_end_window(bridge):
    """One row per quarter in [start, end] inclusive — independent of how many
    quarters the shock itself runs for."""
    df = bridge.run_reform("r", "CGG", 100.0, "2025Q1", "2025Q4", periods=2)
    assert len(df) == 4
    df8 = bridge.run_reform("r", "CGG", 100.0, "2025Q1", "2026Q4", periods=2)
    assert len(df8) == 8


def test_period_column_is_quarter_string_not_period_object(bridge):
    """``period`` must serialise as "2025Q1" strings — a pandas Period object
    survives in-process but breaks JSON serialisation at the MCP boundary."""
    df = bridge.run_reform("r", "CGG", 100.0, "2025Q1", "2025Q4", periods=4)
    assert list(df["period"]) == ["2025Q1", "2025Q2", "2025Q3", "2025Q4"]
    assert df["period"].map(type).eq(str).all()


def test_numeric_columns_are_float_dtype(bridge):
    df = bridge.run_reform("r", "CGG", 100.0, "2025Q1", "2025Q4", periods=4)
    for col in EXPECTED_COLUMNS[2:]:
        assert np.issubdtype(df[col].dtype, np.floating), f"{col} is not float"


def test_reform_name_is_echoed_verbatim(bridge):
    df = bridge.run_reform("VAT +1pp", "CGG", 100.0, "2025Q1", "2025Q4", periods=4)
    assert list(df["reform"].unique()) == ["VAT +1pp"]


# --- Arithmetic relationships between reported columns ----------------------


def test_bn_column_is_exactly_millions_over_1000(bridge):
    """Downstream sums the £bn column; a unit drift here is a 1000x error."""
    df = bridge.run_reform("r", "CGG", 250.0, "2025Q1", "2025Q4", periods=4)
    assert np.allclose(df["delta_gdp_bn"], df["delta_gdp_m"] / 1000.0, rtol=0, atol=0)


def test_pct_gdp_is_consistent_with_delta_and_baseline(bridge):
    """pct_gdp must be the delta as a percentage of the *baseline* GDP level."""
    df = bridge.run_reform("r", "CGG", 250.0, "2025Q1", "2025Q4", periods=4)
    baseline_gdp = _BridgeTemplate.BASE * 10.0
    assert np.allclose(df["pct_gdp"], 100 * df["delta_gdp_m"] / baseline_gdp)


def test_zero_shock_gives_all_zero_deltas(bridge):
    """The bridge's null case: costing a reform at zero must score as zero."""
    df = bridge.run_reform("null", "CGG", 0.0, "2025Q1", "2025Q4", periods=4)
    for col in EXPECTED_COLUMNS[2:]:
        assert df[col].abs().max() == 0.0, f"{col} nonzero under a zero shock"


def test_all_outputs_are_finite(bridge):
    df = bridge.run_reform("r", "CGG", 100.0, "2025Q1", "2025Q4", periods=4)
    for col in EXPECTED_COLUMNS[2:]:
        assert np.isfinite(df[col].to_numpy()).all(), f"{col} has NaN/inf"


# --- Costed-path semantics (the microsim hand-off) --------------------------


def test_costed_path_maps_quarter_by_quarter(bridge):
    """A per-quarter costing path is the microsim hand-off format: quarter i of
    the path must land in quarter i of the results, with no shifting."""
    path = [100.0, 200.0, 300.0, 400.0]
    df = bridge.run_reform("costed", "CGG", path, "2025Q1", "2025Q4")
    assert list(df["delta_gdp_m"]) == [1000.0, 2000.0, 3000.0, 4000.0]


def test_costed_path_shorter_than_window_pads_with_zero(bridge):
    """A 2-quarter costing over a 4-quarter window leaves the tail at zero —
    the shock stops, it does not persist or wrap."""
    df = bridge.run_reform("costed", "CGG", [100.0, 200.0], "2025Q1", "2025Q4")
    assert list(df["delta_gdp_m"]) == [1000.0, 2000.0, 0.0, 0.0]


def test_costed_path_length_overrides_periods(bridge):
    """``periods`` is documented as ignored for a sequence; pin it, because a
    caller that passes both must not get a silently truncated costing."""
    df = bridge.run_reform(
        "costed", "CGG", [100.0, 200.0, 300.0], "2025Q1", "2025Q4", periods=1
    )
    assert list(df["delta_gdp_m"]) == [1000.0, 2000.0, 3000.0, 0.0]


def test_negative_costed_path_is_signed_through(bridge):
    """A revenue-raising reform arrives as a negative path; the sign must
    survive to the output rather than being taken as a magnitude."""
    df = bridge.run_reform("raise", "CGG", [-100.0, -200.0], "2025Q1", "2025Q2")
    assert list(df["delta_gdp_m"]) == [-1000.0, -2000.0]


def test_costed_path_is_linear_in_scale(bridge):
    """Doubling the costing doubles the scored delta under the fake linear
    template — pins that run_reform does not rescale or clip the input path."""
    a = bridge.run_reform("a", "CGG", [100.0, 200.0], "2025Q1", "2025Q2")
    b = bridge.run_reform("b", "CGG", [200.0, 400.0], "2025Q1", "2025Q2")
    assert np.allclose(b["delta_gdp_m"].to_numpy(), 2 * a["delta_gdp_m"].to_numpy())


# --- Fail-fast contract -----------------------------------------------------


@pytest.mark.parametrize(
    "bad,exc",
    [
        ("1250", TypeError),  # a stringified costing
        (b"1250", TypeError),
        (True, TypeError),
        ({"2025Q1": 1.0}, TypeError),  # a quarter->value mapping
        ([1.0, None], TypeError),  # a gap in the costing path
        ([1.0, "2"], TypeError),
        ([], ValueError),  # an empty costing
    ],
)
def test_malformed_costings_raise_not_silently_coerced(bridge, bad, exc):
    """A malformed costing must raise, never be coerced into a plausible-looking
    score. Silent coercion is the failure mode that produces confident wrong
    numbers downstream."""
    with pytest.raises(exc):
        bridge.run_reform("bad", "CGG", bad, "2025Q1", "2025Q4")


def test_unknown_start_quarter_raises(bridge):
    with pytest.raises(KeyError):
        bridge.run_reform("bad", "CGG", [1.0], "1900Q1", "1900Q4")
