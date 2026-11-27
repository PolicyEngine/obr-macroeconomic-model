"""Fast tests for FullOBRSolver.apply_shock (no model download or build).

Builds a bare solver instance via __new__ with a tiny synthetic frame, so the
scalar/path shock semantics are covered in milliseconds. The full-solve
equivalence check lives in tests/test_solver.py (slow).
"""

import warnings

import pandas as pd
import pytest

from obr_macro.full_solver import FullOBRSolver


def _bare_solver(periods: int = 8) -> FullOBRSolver:
    """Minimal solver instance: synthetic quarterly frame, no equations."""
    solver = FullOBRSolver.__new__(FullOBRSolver)
    solver.verbose = False
    solver.equations = []
    solver._build_equation_index()
    index = pd.period_range("2025Q1", periods=periods, freq="Q")
    solver.data = pd.DataFrame({"CGG": [100.0] * periods}, index=index)
    solver.index = solver.data.index
    return solver


def test_scalar_shock_applies_constant():
    s = _bare_solver()
    s.apply_shock("CGG", 10, "2025Q2", periods=3)
    assert list(s.data["CGG"]) == [100, 110, 110, 110, 100, 100, 100, 100]
    assert s._shock_active


def test_path_shock_applies_per_quarter():
    s = _bare_solver()
    s.apply_shock("CGG", [1.0, 2.0, 3.0], "2025Q1")
    assert list(s.data["CGG"]) == [101, 102, 103, 100, 100, 100, 100, 100]


def test_path_length_overrides_periods():
    s = _bare_solver()
    s.apply_shock("CGG", [5.0, 5.0], "2025Q1", periods=8)
    assert list(s.data["CGG"]) == [105, 105, 100, 100, 100, 100, 100, 100]


def test_path_truncates_at_data_end():
    s = _bare_solver(periods=2)
    s.apply_shock("CGG", [1.0, 2.0, 3.0, 4.0], "2025Q1")
    assert list(s.data["CGG"]) == [101, 102]


class _CountingFrame:
    """Stands in for solver.data and counts row reads through ``.iloc``."""

    def __init__(self, frame):
        self._frame = frame
        self.iloc_reads = 0

    @property
    def iloc(self):
        self.iloc_reads += 1
        return self._frame.iloc

    @property
    def columns(self):
        return self._frame.columns


def test_build_context_reads_the_period_row_once():
    """The evaluation context holds every column's value at period t, and
    builds it from a single row read.

    ``data.iloc[t]`` assembles a new Series from every column. Reading it
    once per column costs one row build per column per context, and the
    solver builds a context in every Gauss-Seidel iteration and for every
    historical period at build time: on the full model (653 columns) that
    was about 0.1s per context and about 90% of a template build.
    """
    s = _bare_solver()
    s.data["GDPM"] = [float(i) for i in range(8)]
    s.data["FLAG"] = [0, 1] * 4  # an integer column: the row upcasts to float
    s.data["GAP"] = float("nan")
    frame = s.data
    expected = {col: frame.iloc[5][col] for col in frame.columns}

    s.data = _CountingFrame(frame)
    ctx = s._build_context(5)
    assert s.data.iloc_reads == 1

    v = ctx["v"]
    assert list(v) == list(frame.columns)
    for col, want in expected.items():
        assert type(v[col]) is type(want), col
        assert v[col] == want or (want != want and v[col] != v[col]), col
    assert v["CGG"] == 100.0 and v["GDPM"] == 5.0 and v["FLAG"] == 1.0
    assert ctx["t"] == 5
    # A fresh dict each time: writing to it leaves the data alone.
    v["GDPM"] = -1.0
    assert frame["GDPM"].iloc[5] == 5.0
    assert s._build_context(5)["v"]["GDPM"] == 5.0


def test_empty_path_raises():
    s = _bare_solver()
    with pytest.raises(ValueError):
        s.apply_shock("CGG", [], "2025Q1")


def test_numpy_scalars_and_0d_arrays_are_scalars():
    import numpy as np

    from obr_macro.full_solver import is_scalar_shock, shock_path

    for s in (np.int64(10), np.float32(10.0), np.float64(10.0), np.array(10.0)):
        assert is_scalar_shock(s)
        assert shock_path(s, 3) == [10.0, 10.0, 10.0]
    solver = _bare_solver()
    solver.apply_shock("CGG", np.int64(10), "2025Q1", periods=2)
    assert list(solver.data["CGG"]) == [110, 110, 100, 100, 100, 100, 100, 100]


def test_numpy_array_and_series_paths():
    import numpy as np
    import pandas as pd

    from obr_macro.full_solver import is_scalar_shock, shock_path

    for path in (np.array([1.0, 2.0]), pd.Series([1.0, 2.0])):
        assert not is_scalar_shock(path)
        assert shock_path(path, 8) == [1.0, 2.0]


def test_bool_str_and_mapping_shocks_rejected():
    from obr_macro.full_solver import shock_path

    for bad in (True, "1250", b"1250", {"2025Q1": 1.0}):
        with pytest.raises(TypeError):
            shock_path(bad, 4)


def test_shocking_an_unknown_variable_raises():
    """A mistyped or never-populated instrument used to create an all-NaN
    column: the run then completed and reported a delta of exactly zero for
    every variable, which is indistinguishable from 'this policy does
    nothing'. It must fail loudly instead."""
    s = _bare_solver()
    with pytest.raises(KeyError, match="no such variable"):
        s.apply_shock("TYPOVAR", 1250, "2025Q1", periods=4)
    assert "TYPOVAR" not in s.data.columns, "failed shock left a column behind"


def test_shocking_a_nan_variable_raises():
    """Same failure mode via a different route: the column exists but the
    model never populated it, so level + shock is still NaN."""
    import numpy as np

    s = _bare_solver()
    s.data["EMPTY"] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        s.apply_shock("EMPTY", 1250, "2025Q1", periods=4)


def test_shock_guard_reports_only_the_shocked_window():
    """A variable that is NaN outside the shocked quarters is still shockable —
    the guard must not over-reject."""
    import numpy as np

    s = _bare_solver()
    s.data["PARTIAL"] = [np.nan, np.nan, 100.0, 100.0, np.nan, np.nan, np.nan, np.nan]
    s.apply_shock("PARTIAL", 10.0, "2025Q3", periods=2)
    assert list(s.data["PARTIAL"])[2:4] == [110.0, 110.0]


def test_shock_guard_runs_before_state_mutation():
    """The guard must join the other pre-mutation validations, not fire after
    make_exogenous has already stripped an equation."""
    s = _bare_solver()
    s.equations = ["SENTINEL-EQUATION"]
    s._shock_active = False
    with pytest.raises(KeyError):
        s.apply_shock("TYPOVAR", 1.0, "2025Q1")
    assert s.equations == ["SENTINEL-EQUATION"]
    assert s._shock_active is False


def test_invalid_shock_does_not_mutate_solver_state():
    """Validation happens before make_exogenous/_shock_active (review #10.2)."""
    s = _bare_solver()
    s.equations = ["SENTINEL-EQUATION"]
    s._shock_active = False
    with pytest.raises(ValueError):
        s.apply_shock("CGG", [], "2025Q1")
    with pytest.raises(TypeError):
        s.apply_shock("CGG", True, "2025Q1")
    with pytest.raises(KeyError):
        s.apply_shock("CGG", [1.0], "1900Q1")
    assert s.equations == ["SENTINEL-EQUATION"], "equation removed on invalid input"
    assert s._shock_active is False, "_shock_active set on invalid input"


class _FakeTemplate:
    """Minimal run_reform template: bare solvers with a no-op solve."""

    def __init__(self):
        self._proto = _bare_solver()
        for col in ("GDPM", "CONS", "IF", "HHDI", "RHHDI"):
            self._proto.data[col] = 1000.0

    def clone(self):
        import copy

        c = copy.copy(self._proto)
        c.data = self._proto.data.copy()
        c.solve = lambda start, end: None
        return c


def test_run_reform_normalizes_paths_fast(monkeypatch):
    """run_reform's path normalization and results window, no model build."""
    from obr_macro import reform_analysis

    monkeypatch.setattr(
        reform_analysis, "_build_reform_template", lambda *a, **k: _FakeTemplate()
    )
    df = reform_analysis.run_reform(
        name="path",
        var="GDPM",
        shock=[1.0, 2.0, 3.0],
        start="2025Q1",
        end="2025Q4",
        periods=12,
    )
    assert list(df["delta_gdp_m"]) == [1.0, 2.0, 3.0, 0.0]
    assert list(df["reform"].unique()) == ["path"]


def test_household_costing_path_becomes_negative_hhdi_addfactors():
    """Positive revenue costings reduce HHDI quarter by quarter."""
    from obr_macro.reform_analysis import _apply_household_costing

    s = _bare_solver()
    s.data["HHDI"] = 500_000.0
    s.add_factors = {("HHDI", 0): 7.0}
    s.eq_for_var = {"HHDI": object()}

    _apply_household_costing(s, [100.0, -25.0], "2025Q1", periods=12)

    assert s.add_factors[("HHDI", 0)] == -93.0
    assert s.add_factors[("HHDI", 1)] == 25.0
    assert s._shock_active


def test_household_costing_requires_live_hhdi_equation():
    from obr_macro.reform_analysis import _apply_household_costing

    s = _bare_solver()
    s.add_factors = {}
    with pytest.raises(RuntimeError, match="endogenous HHDI identity"):
        _apply_household_costing(s, [100.0], "2025Q1", periods=1)


def test_0d_arrays_of_bool_or_string_rejected():
    import numpy as np

    from obr_macro.full_solver import is_scalar_shock, shock_path

    for bad in (np.array(True), np.array("1250")):
        assert not is_scalar_shock(bad)
        with pytest.raises(TypeError):
            shock_path(bad, 4)


def test_non_numeric_path_elements_rejected():
    import numpy as np

    from obr_macro.full_solver import shock_path

    for bad in (
        [1.0, "2"],
        [1.0, b"2"],
        [True, 1.0],
        [1.0, None],
        np.array([True, False]),
    ):
        with pytest.raises(TypeError):
            shock_path(bad, 4)


def test_numeric_key_mappings_rejected():
    """Any Mapping is refused — pinned with a non-dict-subclass Mapping, so
    narrowing the check back to concrete dict fails this test."""
    from collections import OrderedDict, UserDict

    from obr_macro.full_solver import shock_path

    for mapping in (OrderedDict({0: 1.0, 1: 2.0}), UserDict({0: 1.0})):
        with pytest.raises(TypeError):
            shock_path(mapping, 4)


def test_fraction_and_decimal_are_numeric():
    """Stdlib real numbers the parent code accepted via float() still work,
    as scalars and as path elements (round-3 review)."""
    from decimal import Decimal
    from fractions import Fraction

    from obr_macro.full_solver import is_scalar_shock, shock_path

    for s in (Fraction(5, 2), Decimal("2.5")):
        assert is_scalar_shock(s)
        assert shock_path(s, 2) == [2.5, 2.5]
    assert shock_path([Fraction(1, 2), Decimal("1.5")], 8) == [0.5, 1.5]


def test_run_reform_validates_before_template_build(monkeypatch):
    """The early-validation branch must fire BEFORE the expensive template
    build — this test fails if that branch is removed (the sentinel raises)."""
    from obr_macro import reform_analysis

    def sentinel(*a, **k):
        raise AssertionError("template built before shock validation")

    monkeypatch.setattr(reform_analysis, "_build_reform_template", sentinel)
    with pytest.raises(TypeError):
        reform_analysis.run_reform(
            name="bad", var="CGG", shock="1250", start="2025Q1", end="2025Q4"
        )
    with pytest.raises(ValueError):
        reform_analysis.run_reform(
            name="bad", var="CGG", shock=[], start="2025Q1", end="2025Q4"
        )


def _eq(lhs: str):
    """Minimal ParsedEquation with the given LHS."""
    from obr_macro.transpiler import ParsedEquation

    return ParsedEquation(
        lhs=lhs,
        rhs="0",
        original=f"{lhs} = 0",
        equation_type="identity",
        python_expr="0.0",
    )


def test_unparsed_lhs_warns_once_per_process():
    """A non-identifier LHS (e.g. 'HHTFA+X') must warn ONCE, not on every
    index rebuild — clone()/make_exogenous()/swap_closure() each rebuild the
    index, which previously flooded stderr during a normal shock run."""
    from obr_macro import full_solver

    full_solver.reset_model_warnings()
    s = _bare_solver()
    s.equations = [_eq("HHTFA+X")]

    with pytest.warns(UserWarning, match="non-identifier"):
        s._build_equation_index()

    # Every subsequent rebuild must be silent.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        for _ in range(5):
            s._build_equation_index()


def test_unparsed_lhs_recorded_for_inspection():
    """Silencing the repeat warnings must not lose the information: the
    offending LHS stays discoverable on the solver after every rebuild."""
    from obr_macro import full_solver

    full_solver.reset_model_warnings()
    s = _bare_solver()
    s.equations = [_eq("HHTFA+X"), _eq("NDIVHH+Y")]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s._build_equation_index()
        s._build_equation_index()  # rebuild: still recorded, just not re-warned

    assert s.unparsed_lhs == {
        "HHTFA+X": "HHTFA+X",
        "NDIVHH+Y": "NDIVHH+Y",
    }


def test_log_lhs_no_longer_unparsed():
    """The two published log(X) equations parse to real column names now, so
    they must not be reported as unparsed (regression guard for #14)."""
    from obr_macro import full_solver

    full_solver.reset_model_warnings()
    s = _bare_solver()
    s.equations = [_eq("log(HHTFA)"), _eq("log(NDIVHH)")]

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        s._build_equation_index()

    assert s.unparsed_lhs == {}
    assert set(s.eq_for_var) == {"HHTFA", "NDIVHH"}


def test_log_lhs_equations_get_anchoring_residuals():
    """The published file has two `log(X) = ...` equations (HHTFA, NDIVHH).
    _compute_residuals used to keep only ratio, dlog and d forms, so those two
    would run raw inside every anchored solve, and freeze_anchoring's "log"
    branch was dead code. A log equation must get a residual like any other
    behavioural form: actual minus exp(rhs)."""
    from obr_macro.transpiler import ParsedEquation

    s = _bare_solver()
    s.data["X"] = 10.0
    s.data["Z"] = 8.0
    s.equations = [
        ParsedEquation(
            lhs="log(X)",
            rhs="log(Z)",
            original="log(X) = log(Z)",
            equation_type="estimated",
            python_expr="np.log(v['Z'])",
        )
    ]
    s._build_equation_index()
    s._code_cache = {}
    s._compute_residuals()
    assert s.residuals, "log(X) equation got no anchoring residual"
    assert all(k[0] == "X" for k in s.residuals)
    assert all(abs(r - 2.0) < 1e-12 for r in s.residuals.values())


# --- Nominal-consistent government-consumption shock -------------------------


def _spending_solver(periods: int = 8):
    """A bare solver carrying CGG and the nominal totals a CGG shock moves."""
    s = _bare_solver(periods)
    s.data["CGGPS"] = [110.0, 112.0, 114.0, 116.0] * (periods // 4)
    s.data["CGGPSPSF"] = 120.0
    s.data["PSCE"] = 300.0
    s.data["CGNB"] = 50.0
    return s


def test_spending_shock_moves_the_nominal_legs_by_the_cash_cost():
    from obr_macro.reform_analysis import NOMINAL_SPENDING_LEGS, apply_spending_shock

    s = _spending_solver()
    legs = apply_spending_shock(s, "CGG", 10.0, "2025Q1", periods=4)
    assert legs == list(NOMINAL_SPENDING_LEGS["CGG"]) == ["CGGPS", "CGGPSPSF", "PSCE"]
    # cash = shock x baseline CGGPS/CGG, quarter by quarter
    cash = [11.0, 11.2, 11.4, 11.6]
    assert list(s.data["CGG"][:5]) == [110, 110, 110, 110, 100]
    for leg, base in (("CGGPSPSF", 120.0), ("PSCE", 300.0)):
        assert list(s.data[leg][:4]) == pytest.approx([base + c for c in cash])
        assert list(s.data[leg][4:]) == [base] * 4
    assert list(s.data["CGGPS"][:4]) == pytest.approx(
        [110 + 11.0, 112 + 11.2, 114 + 11.4, 116 + 11.6]
    )
    # the implied government deflator is unchanged by construction
    assert list((s.data["CGGPS"] / s.data["CGG"])[:4]) == pytest.approx(
        [1.10, 1.12, 1.14, 1.16]
    )


def test_spending_shock_per_quarter_path_and_real_only_mode():
    from obr_macro.reform_analysis import apply_spending_shock

    s = _spending_solver()
    apply_spending_shock(s, "CGG", [10.0, -20.0], "2025Q1")
    assert list(s.data["PSCE"][:3]) == pytest.approx([311.0, 300 - 22.4, 300.0])

    real_only = _spending_solver()
    legs = apply_spending_shock(
        real_only, "CGG", 10.0, "2025Q1", periods=4, nominal_consistent=False
    )
    assert legs == []
    assert list(real_only.data["PSCE"]) == [300.0] * 8
    assert list(real_only.data["CGGPS"]) == [110.0, 112.0, 114.0, 116.0] * 2


def test_spending_shock_refuses_a_half_applied_nominal_leg():
    """A missing leg must raise, not be skipped: a shock with CGGPS moved but
    PSCE held reports a borrowing delta that is neither mode."""
    from obr_macro.reform_analysis import apply_spending_shock

    s = _spending_solver()
    s.data = s.data.drop(columns=["PSCE"])
    with pytest.raises(KeyError, match="PSCE"):
        apply_spending_shock(s, "CGG", 10.0, "2025Q1", periods=4)


def test_cash_spending_line_moves_psce_by_the_shock_itself():
    """Social benefits (CGSB) and other current grants (CGOTR) are cash lines
    of public sector current expenditure. Their only leg is PSCE, moved by
    the shock itself and not by the CGGPS/CGG price ratio a real CGG shock
    uses (#88)."""
    from obr_macro.reform_analysis import NOMINAL_SPENDING_LEGS, apply_spending_shock

    for var in ("CGSB", "CGOTR"):
        s = _spending_solver()
        s.data[var] = 70.0
        legs = apply_spending_shock(s, var, [10.0, -20.0, 5.0], "2025Q2")
        assert legs == list(NOMINAL_SPENDING_LEGS[var]) == ["PSCE"]
        assert list(s.data[var][:5]) == [70.0, 80.0, 50.0, 75.0, 70.0]
        assert list(s.data["PSCE"][:5]) == [300.0, 310.0, 280.0, 305.0, 300.0]
        # Nominal government consumption is not part of a transfer.
        assert list(s.data["CGGPS"]) == [110.0, 112.0, 114.0, 116.0] * 2
        assert list(s.data["CGGPSPSF"]) == [120.0] * 8

        alone = _spending_solver()
        alone.data[var] = 70.0
        legs = apply_spending_shock(
            alone, var, 10.0, "2025Q1", periods=4, nominal_consistent=False
        )
        assert legs == []
        assert list(alone.data["PSCE"]) == [300.0] * 8

        missing = _spending_solver()
        missing.data[var] = 70.0
        missing.data = missing.data.drop(columns=["PSCE"])
        with pytest.raises(KeyError, match="PSCE"):
            apply_spending_shock(missing, var, 10.0, "2025Q1", periods=4)


def test_cash_spending_lines_default_like_government_consumption():
    """CGSB and CGOTR follow the same default rule as CGG: the PSCE leg is on
    under the nominal-GDP pin and off otherwise, and an explicit choice is
    honoured (#88). Lines without a leg stay off."""
    from obr_macro.reform_analysis import resolve_nominal_consistent

    for var in ("CGSB", "CGOTR"):
        assert resolve_nominal_consistent(None, var, True) is True
        assert resolve_nominal_consistent(None, var, False) is False
        assert resolve_nominal_consistent(False, var, True) is False
        assert resolve_nominal_consistent(True, var, False) is True
    assert resolve_nominal_consistent(None, "DICGOP", True) is False


def test_subsidy_residual_lines_are_the_terms_of_the_listing():
    """PSCE_RESIDUAL_LINES is every term the listing subtracts from PSCE to
    get subsidies (l.504). If the OBR changes that line, the set must follow."""
    import re
    from importlib import resources

    from obr_macro.reform_analysis import (
        NOMINAL_SPENDING_LEGS,
        PROCUREMENT_RESIDUAL_LINES,
        PSCE_RESIDUAL_LINES,
    )

    listing = (
        resources.files("obr_macro")
        .joinpath("_data/obr_model_code_october_2025.txt")
        .read_text()
    )
    (line,) = [ln for ln in listing.splitlines() if re.match(r"CGSUBP\s+=", ln)]
    terms = set(re.findall(r"[A-Z][A-Z0-9]*", line.split("=", 1)[1]))
    assert terms - {"PSCE"} == set(PSCE_RESIDUAL_LINES)
    # Five of them are also terms of the procurement residual (l.377), which
    # absorbs a shock to them before the subsidy residual sees it.
    (line,) = [ln for ln in listing.splitlines() if re.match(r"CGP\s+=", ln)]
    terms = set(re.findall(r"[A-Z][A-Z0-9]*", line.split("=", 1)[1]))
    assert terms - {"CGGPSPSF"} == set(PROCUREMENT_RESIDUAL_LINES)
    assert PROCUREMENT_RESIDUAL_LINES < PSCE_RESIDUAL_LINES
    # A procurement line needs the consumption total moved as well as PSCE.
    assert PROCUREMENT_RESIDUAL_LINES & set(NOMINAL_SPENDING_LEGS) == {"LAPR"}
    assert NOMINAL_SPENDING_LEGS["LAPR"] == ("CGGPSPSF", "PSCE")
    # Every instrument with a leg is one of: CGG, whose nominal counterpart
    # reaches l.504 through procurement (CGP); a term of l.504; an instrument
    # that sets a term of l.504 through a live equation; or a public
    # investment line, whose imposed total is PSNI.
    from obr_macro.reform_analysis import PSCE_LINE_SET_BY, PSNI_LEG_LINES

    for var, legs in NOMINAL_SPENDING_LEGS.items():
        if var in PSNI_LEG_LINES:
            assert legs == ("PSNI",)
            continue
        assert "PSCE" in legs
        assert var == "CGG" or var in PSCE_RESIDUAL_LINES or var in PSCE_LINE_SET_BY
        if var != "CGG" and var not in PROCUREMENT_RESIDUAL_LINES:
            assert legs == ("PSCE",)
    # TROD sets CGNCGA through l.403, and is a transfer debit in l.485.
    for src, line_var in PSCE_LINE_SET_BY.items():
        assert line_var in PSCE_RESIDUAL_LINES
        assert re.search(rf"^{line_var}\s+=\s+{src}\s*$", listing, re.M)
    (line,) = [ln for ln in listing.splitlines() if re.match(r"TRAND\s+=", ln)]
    assert "TROD" in re.findall(r"[A-Z][A-Z0-9]*", line.split("=", 1)[1])


def test_public_investment_legs_follow_the_listing():
    """CGIPS and LAIPS get a PSNI leg because the listing imposes public
    sector net investment: its identity (l.520) is commented out, the residual
    it leaves is central government inventories DINVCG (l.33), and public
    sector net borrowing reads PSNI directly (l.536). If the OBR changes any
    of that, the leg must be looked at again (#88)."""
    import re
    from importlib import resources

    from obr_macro.full_solver import KNOWN_NONFINITE_EQUATIONS
    from obr_macro.reform_analysis import NOMINAL_SPENDING_LEGS, PSNI_LEG_LINES

    listing = (
        resources.files("obr_macro")
        .joinpath("_data/obr_model_code_october_2025.txt")
        .read_text()
    )
    lines = listing.splitlines()

    def rhs_terms(lhs):
        (line,) = [ln for ln in lines if re.match(rf"{lhs}\s+=", ln)]
        return set(re.findall(r"[A-Z][A-Z0-9]*", line.split("=", 1)[1]))

    assert not [ln for ln in lines if re.match(r"PSNI\s+=", ln)]
    assert [ln for ln in lines if re.match(r"'PSNI\s+=\s+PSGI", ln)]
    assert PSNI_LEG_LINES <= rhs_terms("PSGI")
    assert {"PSNI", *PSNI_LEG_LINES} <= rhs_terms("DINVCG")
    assert "PSNI" in rhs_terms("PSNBNSA") and "PSNI" in rhs_terms("TME")
    assert "CGIPS" in rhs_terms("CGNB") and "LAIPS" in rhs_terms("LANB")
    # The residual that would absorb the shock is dropped for missing data,
    # which is why CGNB moves at all. If it ever goes live, CGNB stops moving
    # and this leg is no longer enough.
    assert "DINVCG" in KNOWN_NONFINITE_EQUATIONS
    for var in PSNI_LEG_LINES:
        assert NOMINAL_SPENDING_LEGS[var] == ("PSNI",)


def test_new_cash_lines_move_their_imposed_totals_by_the_shock():
    """Local authority lines and grants abroad move PSCE, local authority
    procurement moves CGGPSPSF and PSCE, public investment moves PSNI: each
    by the shock itself, and nothing else (#88)."""
    from obr_macro.reform_analysis import NOMINAL_SPENDING_LEGS, apply_spending_shock

    totals = {"CGGPS": None, "CGGPSPSF": 120.0, "PSCE": 300.0, "PSNI": 40.0}
    for var in (
        "LASBHH",
        "LAOTRHH",
        "LANCGA",
        "DILAPR",
        "LAPR",
        "CGNCGA",
        "TROD",
        "CGIPS",
        "LAIPS",
    ):
        s = _spending_solver()
        s.data["PSNI"] = 40.0
        s.data[var] = 70.0
        legs = apply_spending_shock(s, var, [10.0, -20.0, 5.0], "2025Q2")
        assert legs == list(NOMINAL_SPENDING_LEGS[var])
        assert list(s.data[var][:5]) == [70.0, 80.0, 50.0, 75.0, 70.0]
        for total, level in totals.items():
            if total in legs:
                assert list(s.data[total][:5]) == pytest.approx(
                    [level, level + 10, level - 20, level + 5, level]
                ), (var, total)
            elif level is not None:
                assert list(s.data[total]) == [level] * 8, (var, total)
        assert list(s.data["CGGPS"]) == [110.0, 112.0, 114.0, 116.0] * 2
        assert list(s.data["CGG"]) == [100.0] * 8

        missing = _spending_solver()
        missing.data[var] = 70.0  # no PSNI column; PSCE dropped below
        missing.data = missing.data.drop(columns=["PSCE"])
        with pytest.raises(KeyError, match=NOMINAL_SPENDING_LEGS[var][-1]):
            apply_spending_shock(missing, var, 10.0, "2025Q1", periods=4)


def test_la_borrowing_identity_is_the_listing_line_less_one_term():
    """LANB_EQ is l.526 with only the unpublished KGLAPC removed (#88)."""
    import re
    from importlib import resources

    from obr_macro.full_solver import KNOWN_NONFINITE_EQUATIONS
    from obr_macro.reform_analysis import LANB_EQ, LANB_TERMS

    listing = (
        resources.files("obr_macro")
        .joinpath("_data/obr_model_code_october_2025.txt")
        .read_text()
    )
    (line,) = [ln for ln in listing.splitlines() if re.match(r"LANB\s+=", ln)]
    terms = set(re.findall(r"[A-Z][A-Z0-9]*", line.split("=", 1)[1]))
    assert set(LANB_TERMS) == terms - {"KGLAPC"}
    assert "KGLAPC" in terms and "KGLAPC" not in LANB_EQ.python_expr
    assert LANB_EQ.lhs.strip() == "LANB"
    # Same signs as the listing: evaluate both with every term at a distinct
    # value and KGLAPC at zero.
    values = {name: float(i + 1) for i, name in enumerate(sorted(terms))}
    values["KGLAPC"] = 0.0
    expected = eval(
        re.sub(r"[A-Z][A-Z0-9]*", lambda m: repr(values[m[0]]), line.split("=", 1)[1])
    )
    assert eval(LANB_EQ.python_expr, {"v": values}) == pytest.approx(expected)
    # The listing's own line is still dropped by a plain solve.
    assert "LANB" in KNOWN_NONFINITE_EQUATIONS


def test_la_borrowing_identity_is_restored_only_on_complete_data():
    from obr_macro.reform_analysis import (
        LANB_EQ,
        LANB_TERMS,
        _restore_la_borrowing_identity,
    )

    def solver():
        s = _bare_solver()
        for col in ("LANB", *LANB_TERMS):
            s.data[col] = 5.0
        return s

    s = solver()
    assert _restore_la_borrowing_identity(s, "2025Q1", "2026Q4") is True
    assert s.eq_for_var["LANB"] is LANB_EQ
    # A clone and a later make_exogenous keep or drop it as for any equation.
    s.make_exogenous("LANB")
    assert "LANB" not in s.eq_for_var

    gap = solver()
    gap.data.loc[gap.data.index[2], "LAPR"] = float("nan")
    assert _restore_la_borrowing_identity(gap, "2025Q1", "2026Q4") is False
    assert "LANB" not in gap.eq_for_var
    # ... but a window that avoids the gap is fine.
    assert _restore_la_borrowing_identity(gap, "2026Q1", "2026Q4") is True

    absent = solver()
    absent.data = absent.data.drop(columns=["CIL"])
    assert _restore_la_borrowing_identity(absent, "2025Q1", "2026Q4") is False


def test_procurement_offset_is_noted_only_when_procurement_moved():
    """An employer NICs rise lifts government pay, and with the consumption
    total held the procurement residual falls by the sum (l.377). run_reform
    records it; the central/local split of borrowing is what it distorts."""
    import pandas as pd

    from obr_macro.reform_analysis import _label_procurement_offset

    base = pd.DataFrame({"CGP": [500.0] * 4, "CGWS": [300.0] * 4, "LAWS": [200.0] * 4})
    shocked = base + pd.DataFrame(
        {
            "CGP": [-250.0, -251.0, -252.0, -233.0],
            "CGWS": [179.0] * 4,
            "LAWS": [71.0] * 4,
        }
    )
    out = pd.DataFrame({"x": [0] * 4})
    _label_procurement_offset(out, "EMPNIC", base, shocked, 0, 3)
    note = out.attrs["procurement_offset_note"]
    assert "-250 / -233" in note and "+179 / +179" in note and "+71 / +71" in note
    assert "l.377" in note and "#88" in note
    assert out.attrs["procurement_offset_m"]["LAWS"] == [71.0] * 4

    for var, frame in (
        ("EMPNIC", base),  # nothing moved
        ("LAPR", shocked),  # labelled as a procurement line instead
        ("CGG", shocked),
        ("CGP", shocked),
    ):
        out = pd.DataFrame({"x": [0] * 4})
        _label_procurement_offset(out, var, base, frame, 0, 3)
        assert "procurement_offset_note" not in out.attrs, var
    out = pd.DataFrame({"x": [0] * 4})
    _label_procurement_offset(out, "EMPNIC", base.drop(columns=["CGP"]), shocked, 0, 3)
    assert not out.attrs


def test_run_reform_labels_a_spending_line_the_subsidy_residual_absorbs(monkeypatch):
    """A shock to a PSCE line with PSCE held is offset by subsidies, so its
    borrowing and profits figures are not the effect of the spending change.
    run_reform says so in attrs and with a warning; with the PSCE leg (the
    default for CGSB and CGOTR under the nominal-GDP pin) it does not."""
    from obr_macro import reform_analysis

    template = _FakeTemplate()
    for col in (
        "CGSB",
        "LASBHH",
        "DICGOP",
        "LAPR",
        "LAWS",
        "TROD",
        "CGIPS",
        "PSCE",
        "CGGPSPSF",
        "PSNI",
    ):
        template._proto.data[col] = 500.0
    monkeypatch.setattr(
        reform_analysis, "_build_reform_template", lambda *a, **k: template
    )
    kwargs = dict(start="2025Q1", end="2025Q4", periods=4)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        df = reform_analysis.run_reform("welfare", "CGSB", 100.0, **kwargs)
    assert df.attrs["nominal_consistent"] is True
    assert df.attrs["nominal_consistent_legs"] == ["PSCE"]
    assert "CGSB" in df.attrs["nominal_consistent_note"]
    assert "CGGPS" not in df.attrs["nominal_consistent_note"]
    assert "subsidy_residual_warning" not in df.attrs
    assert "welfare multiplier is 0.6" in df.attrs["transmission_note"]
    assert not [w for w in caught if "CGSUBP" in str(w.message)]

    off = {"nominal_consistent": False}
    for var, extra in (("CGSB", off), ("LASBHH", off), ("DICGOP", {}), ("TROD", off)):
        with pytest.warns(UserWarning, match="CGSUBP"):
            df = reform_analysis.run_reform("held", var, 100.0, **kwargs, **extra)
        assert df.attrs["nominal_consistent"] is False
        assert "nominal_consistent_legs" not in df.attrs
        assert var in df.attrs["subsidy_residual_warning"]
        assert "#88" in df.attrs["subsidy_residual_warning"]
        assert "procurement_residual_warning" not in df.attrs
        if var == "TROD":
            assert "which sets CGNCGA" in df.attrs["subsidy_residual_warning"]

    # Pay and procurement lines are absorbed by procurement (l.377), not by
    # subsidies, and the label says which.
    for var, extra in (("LAWS", {}), ("LAPR", off)):
        with pytest.warns(UserWarning, match="CGP"):
            df = reform_analysis.run_reform("la", var, 100.0, **kwargs, **extra)
        assert var in df.attrs["procurement_residual_warning"]
        assert "l.377" in df.attrs["procurement_residual_warning"]
        assert "subsidy_residual_warning" not in df.attrs
    # The lines given legs on 26 Nov 2026 carry them by default and say which.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        # CGIPS also warns that it has no route to GDP; that is a different label.
        warnings.filterwarnings("ignore", message=".*NO transmission path.*")
        for var, legs, phrase in (
            ("LASBHH", ["PSCE"], "public sector current expenditure PSCE"),
            ("TROD", ["PSCE"], "public sector current expenditure PSCE"),
            ("LAPR", ["CGGPSPSF", "PSCE"], "GDP does not respond"),
            ("CGIPS", ["PSNI"], "PSNI is still imposed"),
        ):
            df = reform_analysis.run_reform("paid", var, 100.0, **kwargs)
            assert df.attrs["nominal_consistent_legs"] == legs, var
            assert var in df.attrs["nominal_consistent_note"]
            assert phrase in df.attrs["nominal_consistent_note"], var
            for label in (
                "subsidy_residual_warning",
                "procurement_residual_warning",
                "investment_total_warning",
            ):
                assert label not in df.attrs, (var, label)

    # The double has no local authority identity, and the result says so.
    assert df.attrs["la_borrowing_identity"] is False
    assert "held on its data path" in df.attrs["la_borrowing_note"]

    # Public investment with PSNI held: CGNB moves, PSNBNSA and TME do not.
    with pytest.warns(UserWarning, match="PSNI"):
        df = reform_analysis.run_reform("inv", "CGIPS", 100.0, **kwargs, **off)
    assert "l.520" in df.attrs["investment_total_warning"]
    assert "nominal_consistent=True" in df.attrs["investment_total_warning"]

    # A line without a leg: asking for one is refused.
    with pytest.raises(ValueError, match="nominal_consistent applies only"):
        reform_analysis.run_reform(
            "la", "DICGOP", 100.0, nominal_consistent=True, **kwargs
        )


def test_nominal_consistent_default_follows_the_closure():
    from obr_macro.reform_analysis import resolve_nominal_consistent

    # Default: on for CGG under the nominal-GDP pin only.
    assert resolve_nominal_consistent(None, "CGG", True) is True
    assert resolve_nominal_consistent(None, "CGG", False) is False
    assert resolve_nominal_consistent(None, "TYEM", True) is False
    # Explicit choices are honoured for CGG; True elsewhere raises.
    assert resolve_nominal_consistent(False, "CGG", True) is False
    assert resolve_nominal_consistent(True, "CGG", False) is True
    assert resolve_nominal_consistent(False, "R", True) is False
    with pytest.raises(ValueError, match="nominal_consistent applies only"):
        resolve_nominal_consistent(True, "TYEM", True)
