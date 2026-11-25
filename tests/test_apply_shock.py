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


def test_rate_instrument_cannot_leave_its_usable_domain_fast():
    """The corporation-tax domain guard on a synthetic frame, no model build.

    The slow test_corp_tax_rate_cannot_leave_its_usable_domain covers the same
    guard through run_reform; this one keeps the boundary arithmetic in the
    fast suite. The domain is [0, 1): a 0% rate is a policy, 100% is the pole
    of the cost-of-capital block.
    """
    from obr_macro.reform_analysis import _check_instrument_domain

    s = _bare_solver()
    s.data["TCPRO"] = 0.25
    _check_instrument_domain(s, "TCPRO", [-0.25] * 4, "2025Q1")  # -> 0.0
    _check_instrument_domain(s, "TCPRO", [0.74] * 4, "2025Q1")  # -> 0.99
    with pytest.raises(ValueError, match="usable domain"):
        _check_instrument_domain(s, "TCPRO", [0.75] * 4, "2025Q1")  # -> 1.0
    with pytest.raises(ValueError, match="usable domain"):
        _check_instrument_domain(s, "TCPRO", [-0.26], "2025Q1")  # -> -0.01
    # The quarter is named, and only the offending one trips the guard.
    with pytest.raises(ValueError, match="2025Q3"):
        _check_instrument_domain(s, "TCPRO", [0.0, 0.0, 0.9], "2025Q1")
    # A path running past the end of the data is checked only where data exist.
    _check_instrument_domain(s, "TCPRO", [0.1] * 20, "2026Q4")
    # Instruments without a declared domain are not checked.
    _check_instrument_domain(s, "CGG", [1e9], "2025Q1")


def test_result_quotes_the_published_multipliers_from_the_table(monkeypatch):
    """df.attrs["obr_published_impact_multiplier"] is read from the encoded
    OBR table, not typed in a second time, and has the VAT and welfare rows
    (a VAT result used to carry a comparison table with no VAT figure)."""
    from obr_macro import reform_analysis
    from obr_macro.published_conventions import PUBLISHED_MULTIPLIERS

    monkeypatch.setattr(
        reform_analysis, "_build_reform_template", lambda *a, **k: _FakeTemplate()
    )
    df = reform_analysis.run_reform(
        name="any", var="GDPM", shock=1.0, start="2025Q1", end="2025Q4", periods=4
    )
    quoted = df.attrs["obr_published_impact_multiplier"]
    assert quoted == {
        "current_spending": 0.6,
        "capital_spending": 1.0,
        "welfare": 0.6,
        "vat": 0.35,
        "personal_tax_and_nics": 0.3,
    }
    table = {key: row.impact for key, row in PUBLISHED_MULTIPLIERS.items()}
    table["personal_tax_and_nics"] = table.pop("income_tax_and_nics")
    assert quoted == table
    # No sourced corporation-tax multiplier exists, so none is quoted (#54).
    assert not any("corporation" in key for key in quoted)
    # A fresh dict per result: editing one result's attrs leaves the next alone.
    quoted["vat"] = 99.0
    assert reform_analysis.published_impact_multipliers()["vat"] == 0.35
