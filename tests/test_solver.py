"""Tests for the OBR model solver."""

import pytest

pytestmark = pytest.mark.slow  # needs OBR download + full solver build


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

    equations = parse_model_file(str(DATA_DIR / "obr_model_code_october_2025.txt"))
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
        periods=4,
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
        investment_closure=True,
    )

    # Investment should decrease with higher corp tax
    final_if_change = results.iloc[-1]["delta_if_m"]
    assert final_if_change < 0


def test_path_shock_matches_constant_scalar():
    """A constant per-quarter path reproduces the scalar shock exactly."""
    from obr_macro import run_reform

    kwargs = dict(var="CGG", start="2025Q1", end="2025Q4")
    scalar = run_reform(name="scalar", shock=1000, periods=4, **kwargs)
    path = run_reform(name="path", shock=[1000.0] * 4, **kwargs)
    assert len(path) == len(scalar)
    for col in ("delta_gdp_m", "delta_gdp_bn", "pct_gdp", "delta_cons_m", "delta_if_m"):
        assert list(scalar[col]) == list(path[col])


def test_household_costing_addfactor_solves_with_documented_sign():
    """A positive static costing lowers HHDI and returns the standard frame."""
    from obr_macro import run_reform

    results = run_reform(
        name="Household tax rise",
        var="HHDI_ADDFACTOR",
        shock=[250.0, 500.0, 750.0, 1000.0],
        start="2025Q1",
        end="2025Q4",
    )

    assert len(results) == 4
    assert {
        "delta_gdp_m",
        "delta_cons_m",
        "delta_if_m",
    } <= set(results)
    assert all(delta < 0 for delta in results.attrs["delta_hhdi_m"])
    assert results.attrs["costing_sign_convention"].startswith("Quarterly £m")


def test_household_costing_path_is_linear_superposition():
    """A path is near the sum of isolated impulses in the small-shock region.

    Exact equality is not expected: the OBR consumption equation uses log
    differences and an error-correction term, so HHDI shocks propagate
    nonlinearly through consumption and GDP. The tolerance bounds that
    nonlinearity to 0.05% for these £100m--£400m quarterly costings.
    """
    import numpy as np

    from obr_macro import run_reform

    path = [100.0, 200.0, 300.0, 400.0]
    kwargs = dict(var="HHDI_ADDFACTOR", start="2025Q1", end="2025Q4")
    combined = run_reform(name="combined", shock=path, **kwargs)
    impulses = []
    for quarter, value in enumerate(path):
        impulse = [0.0] * len(path)
        impulse[quarter] = value
        impulses.append(run_reform(name=f"q{quarter + 1}", shock=impulse, **kwargs))

    for col in ("delta_gdp_m", "delta_cons_m"):
        summed = np.sum([result[col].to_numpy() for result in impulses], axis=0)
        assert np.allclose(combined[col], summed, rtol=5e-4, atol=0.05)
    for attr in ("delta_hhdi_m", "delta_rhhdi_m"):
        summed = np.sum([result.attrs[attr] for result in impulses], axis=0)
        assert np.allclose(combined.attrs[attr], summed, rtol=5e-4, atol=0.05)
