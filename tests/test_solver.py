"""Tests for the OBR model solver."""

import pytest
import numpy as np


def test_data_loads():
    """Test that OBR data loads correctly."""
    from obr_macro import load_obr_data

    data = load_obr_data()
    assert len(data) > 0
    assert "GDPM" in data.columns
    assert "CGG" in data.columns
    assert "CONS" in data.columns


def test_transpiler_parses_equations():
    """Test that the transpiler parses OBR equations."""
    from obr_macro import parse_model_file, DATA_DIR

    equations = parse_model_file(str(DATA_DIR / "obr_model_code_march_2025.txt"))
    assert len(equations) > 300  # OBR has ~372 equations


def test_solver_initializes():
    """Test that the solver initializes without error."""
    from obr_macro import FullOBRSolver

    solver = FullOBRSolver(verbose=False)
    assert solver.data is not None
    assert len(solver.equations) > 0


def test_solver_solves_period():
    """Test that solver can solve a single period."""
    from obr_macro import FullOBRSolver

    solver = FullOBRSolver(verbose=False)
    t = solver.period_idx("2025Q1")
    iters = solver.solve_period(t)
    assert iters > 0


def test_fiscal_shock():
    """Test that a fiscal shock produces GDP changes."""
    from obr_macro import run_reform

    results = run_reform(
        name="Test Fiscal Shock",
        var="CGG",
        shock=1000,  # £1bn
        start="2025Q1",
        end="2025Q4",
        periods=4
    )

    # Should have 4 quarters of results
    assert len(results) == 4

    # GDP should change (multiplier effect)
    final_gdp_change = results.iloc[-1]["delta_gdp_m"]
    assert abs(final_gdp_change) > 0


def test_corp_tax_shock():
    """Test that a corporation tax shock affects investment."""
    from obr_macro import run_reform

    results = run_reform(
        name="Test Corp Tax",
        var="TCPRO",
        shock=0.01,  # +1pp
        start="2025Q1",
        end="2026Q4",
        periods=8,
        investment_closure=True
    )

    # Investment should decrease with higher corp tax
    final_if_change = results.iloc[-1]["delta_if_m"]
    assert final_if_change < 0
