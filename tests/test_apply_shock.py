"""Fast tests for FullOBRSolver.apply_shock (no model download or build).

Builds a bare solver instance via __new__ with a tiny synthetic frame, so the
scalar/path shock semantics are covered in milliseconds. The full-solve
equivalence check lives in tests/test_solver.py (slow).
"""

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
        for col in ("GDPM", "CONS", "IF"):
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
