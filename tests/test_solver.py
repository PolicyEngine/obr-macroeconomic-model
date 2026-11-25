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


def test_welfare_shock_raises_borrowing_and_household_income_one_for_one():
    """Social benefits +£1,000m a quarter (issue #88).

    With the PSCE leg (the default under the nominal-GDP pin) borrowing and
    total managed expenditure rise by the shock, subsidies and taxes less
    subsidies on products do not move, and household income rises by about
    the shock. Measured 25 Nov 2026: HHDI +1,001 / +1,013 / +1,028 and GDP
    +92 / +191 / +323 at q1 / q4 / q12; current-price GDP per pound 0.098 /
    0.208 / 0.368, against the OBR's welfare multiplier of 0.6, fading.

    Without the leg the listing's subsidy residual (l.504) absorbs the
    shock: borrowing 0, subsidies -1,000, profits -917 / -820 / -678. That
    is pinned too, so a change to the listing's treatment shows up here.
    """
    import warnings

    import numpy as np

    from obr_macro.reform_analysis import _build_reform_template, apply_spending_shock

    start, end, size = "2025Q1", "2027Q4", 1000.0
    template = _build_reform_template("CGSB", start, end, False, True)
    base = template.clone()
    base.solve(start, end)
    t0, t1 = base.period_idx(start), base.period_idx(end)

    def deltas(nominal_consistent):
        k = template.clone()
        assert "CGSB" not in k.eq_for_var and "PSCE" not in k.eq_for_var
        apply_spending_shock(
            k, "CGSB", size, start, 12, nominal_consistent=nominal_consistent
        )
        k.solve(start, end)
        assert set(k.last_solve_report["exit_status"].values()) == {"tol"}
        return {
            c: (k.data[c].iloc[t0 : t1 + 1] - base.data[c].iloc[t0 : t1 + 1]).to_numpy(
                dtype=float
            )
            for c in (
                "GDPM",
                "GDPMPS",
                "CONS",
                "HHDI",
                "CGNB",
                "PSNBNSA",
                "TME",
                "CGSUBP",
                "BPAPS",
                "FYCPR",
                "PSCR",
            )
        }

    paid = deltas(True)
    for series in ("CGNB", "PSNBNSA", "TME"):
        np.testing.assert_allclose(paid[series], size, atol=1e-6, err_msg=series)
    for series in ("CGSUBP", "BPAPS", "PSCR"):
        np.testing.assert_allclose(paid[series], 0.0, atol=1e-6, err_msg=series)
    assert ((0.98 * size < paid["HHDI"]) & (paid["HHDI"] < 1.05 * size)).all()
    assert (np.diff(paid["GDPM"]) > 0).all() and paid["GDPM"][0] > 0
    np.testing.assert_allclose(paid["GDPM"], paid["CONS"], atol=1e-6)
    ratio = paid["GDPMPS"] / size
    assert 0.08 < ratio[0] < 0.12, ratio[0]
    assert 0.17 < ratio[3] < 0.25, ratio[3]
    assert 0.32 < ratio[11] < 0.43, ratio[11]

    held = deltas(False)
    for series in ("CGNB", "PSNBNSA", "TME"):
        np.testing.assert_allclose(held[series], 0.0, atol=1e-6, err_msg=series)
    np.testing.assert_allclose(held["CGSUBP"], -size, atol=1e-6)
    np.testing.assert_allclose(held["BPAPS"], size, atol=1e-6)
    assert (held["FYCPR"] < -0.6 * size).all()
    assert (held["HHDI"] < 0.93 * size).all()
    # Paying for the transfer raises the GDP effect by about 13% to 15%.
    assert (paid["GDPM"] > 1.1 * held["GDPM"]).all()

    # run_reform takes the paid-for route by default and says so.
    from obr_macro import run_reform

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = run_reform(name="Welfare", var="CGSB", shock=size, periods=12)
    assert df.attrs["nominal_consistent_legs"] == ["PSCE"]
    assert "subsidy_residual_warning" not in df.attrs
    np.testing.assert_allclose(df["delta_gdp_m"], paid["GDPM"], atol=1e-6)


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
