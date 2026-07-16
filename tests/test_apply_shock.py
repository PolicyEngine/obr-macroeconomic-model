"""Fast tests for FullOBRSolver.apply_shock (no model download or build).

Builds a bare solver instance via __new__ with a tiny synthetic frame, so the
scalar/path shock semantics are covered in milliseconds. The full-solve
equivalence check lives in tests/test_scoring.py (slow).
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
