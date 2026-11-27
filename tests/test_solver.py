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

    # The figures docs/limitations.md, docs/examples.md and docs/decisions.md
    # quote, at q1 / q4 / q12, to the £0.5m they are rounded to. No results
    # file holds this run, so this is where those numbers are pinned. If a
    # deliberate model change moves them, update the three pages with them.
    quoted = {
        ("paid", "GDPM"): (91.827, 191.206, 323.082),
        ("paid", "HHDI"): (1000.651, 1013.229, 1027.751),
        ("paid", "GDPMPS"): (97.612, 208.032, 368.451),
        ("held", "GDPM"): (79.616, 167.468, 285.783),
        ("held", "HHDI"): (867.478, 887.016, 913.823),
        ("held", "FYCPR"): (-916.583, -820.468, -678.414),
    }
    held_run = deltas(False)
    for (which, series), values in quoted.items():
        got = (paid if which == "paid" else held_run)[series][[0, 3, 11]]
        np.testing.assert_allclose(
            got, values, atol=0.5, rtol=0, err_msg=f"{which} {series}"
        )

    held = held_run
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


def _borrowing_deltas(var, nominal_consistent, size=1000.0):
    """Shocked minus baseline for the borrowing accounts, default closure."""
    import warnings

    from obr_macro.reform_analysis import (
        LANB_EQ,
        _build_reform_template,
        apply_spending_shock,
    )

    start, end = "2025Q1", "2027Q4"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        template = _build_reform_template(var, start, end, False, True)
        assert template.eq_for_var["LANB"] is LANB_EQ
        base = template.clone()
        base.solve(start, end)
        k = template.clone()
        apply_spending_shock(
            k, var, size, start, 12, nominal_consistent=nominal_consistent
        )
        k.solve(start, end)
    assert set(k.last_solve_report["exit_status"].values()) == {"tol"}
    assert "LANB" not in base.last_solve_report["dropped"]
    t0, t1 = base.period_idx(start), base.period_idx(end)
    # The restored identity re-levels onto the data path: no baseline change.
    assert (
        abs(
            base.data["LANB"].iloc[t0 : t1 + 1]
            - template.baseline["LANB"].iloc[t0 : t1 + 1]
        ).max()
        < 1e-6
    )
    series = (
        "GDPM CGNB LANB GGNB TDEF PSNBNSA TME PSCE PSNI CGSUBP CGP CGWS LAWS "
        "PSCR CB HHDI FYCPR"
    ).split()
    return {
        c: (k.data[c].iloc[t0 : t1 + 1] - base.data[c].iloc[t0 : t1 + 1]).to_numpy(
            dtype=float
        )
        for c in series
    }


def test_local_authority_lines_raise_local_and_general_government_borrowing():
    """Local authority benefits and procurement, +£1,000m a quarter (#88).

    Before 26 Nov 2026 the subsidy residual (l.504) or the procurement
    residual (l.377) absorbed the shock inside central government and the
    local authority identity (l.526) was dropped, so CGNB and GGNB fell by
    the shock: the wrong sign. With the legs (the default) and l.526 run
    without its unpublished term, the borrowing is local authority borrowing
    and every wider aggregate rises by the shock.
    """
    import numpy as np

    size = 1000.0
    for var, residual in (("LASBHH", "CGSUBP"), ("LAPR", "CGP")):
        paid = _borrowing_deltas(var, True)
        for series in ("LANB", "GGNB", "TDEF", "PSNBNSA", "TME", "PSCE"):
            np.testing.assert_allclose(paid[series], size, atol=1e-6, err_msg=series)
        for series in ("CGNB", "CGSUBP", "CGP", "PSCR", "PSNI"):
            np.testing.assert_allclose(paid[series], 0.0, atol=1e-6, err_msg=series)

        # With the totals held, the old wrong sign is still there for CGNB,
        # but the local authority account now carries its own line, so
        # general government borrowing nets to zero like the public sector.
        held = _borrowing_deltas(var, False)
        np.testing.assert_allclose(held[residual], -size, atol=1e-6)
        np.testing.assert_allclose(held["CGNB"], -size, atol=1e-6)
        np.testing.assert_allclose(held["LANB"], size, atol=1e-6)
        for series in ("GGNB", "PSNBNSA", "TME"):
            np.testing.assert_allclose(held[series], 0.0, atol=1e-6, err_msg=series)

    # Benefits reach households; cash procurement on its own reaches nothing.
    paid = _borrowing_deltas("LASBHH", True)
    assert ((0.98 * size < paid["HHDI"]) & (paid["HHDI"] < 1.06 * size)).all()
    assert (np.diff(paid["GDPM"]) > 0).all() and paid["GDPM"][0] > 0
    # Quoted in docs/limitations.md and docs/decisions.md, q1 / q4 / q12.
    np.testing.assert_allclose(
        paid["GDPM"][[0, 3, 11]], (92.9, 193.5, 327.0), atol=0.5, rtol=0
    )
    np.testing.assert_allclose(_borrowing_deltas("LAPR", True)["GDPM"], 0.0, atol=1e-3)


def test_public_investment_reaches_public_sector_net_borrowing():
    """Central government investment CGIPS +£1,000m a quarter (#88).

    PSNI is imposed (l.520 commented out) and PSNBNSA = -PSCB + PSNI (l.536),
    so with PSNI held the shock raised CGNB and left PSNBNSA and TME at zero.
    The default under the nominal-GDP pin now moves PSNI with the shock.
    """
    import numpy as np

    size = 1000.0
    paid = _borrowing_deltas("CGIPS", True)
    for series in ("CGNB", "GGNB", "PSNBNSA", "TME", "PSNI"):
        np.testing.assert_allclose(paid[series], size, atol=1e-6, err_msg=series)
    for series in ("LANB", "PSCE", "CGSUBP", "PSCR"):
        np.testing.assert_allclose(paid[series], 0.0, atol=1e-6, err_msg=series)

    held = _borrowing_deltas("CGIPS", False)
    np.testing.assert_allclose(held["CGNB"], size, atol=1e-6)
    for series in ("PSNBNSA", "TME", "PSNI"):
        np.testing.assert_allclose(held[series], 0.0, atol=1e-6, err_msg=series)
    # The leg is accounting: it changes nothing in the real economy.
    # (to the solver's tolerance: two solves of the same real economy).
    np.testing.assert_allclose(paid["GDPM"], held["GDPM"], atol=1e-3)

    local = _borrowing_deltas("LAIPS", True)
    for series in ("LANB", "GGNB", "PSNBNSA", "TME"):
        np.testing.assert_allclose(local[series], size, atol=1e-6, err_msg=series)
    np.testing.assert_allclose(local["CGNB"], 0.0, atol=1e-6)


def test_investment_closure_keeps_psni_held_unless_asked():
    """CGIPS +£1,000m a quarter under the investment closure (#88).

    The PSNI leg is off by default there (the rule for every nominal leg),
    so public sector net borrowing does not move and the run says so. Asked
    for, it moves PSNBNSA by the shock and nothing in the real economy.
    """
    import warnings

    import numpy as np

    from obr_macro import run_reform

    size, runs = 1000.0, {}
    for label, extra in (("default", {}), ("asked", {"nominal_consistent": True})):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            runs[label] = run_reform(
                name=label,
                var="CGIPS",
                shock=size,
                periods=12,
                investment_closure=True,
                **extra,
            )
    default, asked = runs["default"], runs["asked"]
    assert default.attrs["nominal_consistent"] is False
    assert "PSNI" in default.attrs["investment_total_warning"]
    assert asked.attrs["nominal_consistent_legs"] == ["PSNI"]
    assert "investment_total_warning" not in asked.attrs
    np.testing.assert_allclose(
        asked["delta_gdp_m"], default["delta_gdp_m"], atol=1e-3, rtol=0
    )
    # Quoted in docs/limitations.md and docs/decisions.md, q1 / q4 / q12.
    np.testing.assert_allclose(
        default["delta_gdp_m"].to_numpy()[[0, 3, 11]],
        (1025.1, 966.9, 967.7),
        atol=0.5,
        rtol=0,
    )


def test_grants_abroad_move_borrowing_and_the_current_account():
    """Grants abroad, +£1,000m a quarter, through TROD (#88).

    CGNCGA = TROD (l.403) and TROD is a transfer debit (TRAND, l.485). A flat
    shock gives a flat response. The -1,926 / +125 / -146 subsidy path
    reported in #88 came from shocking CGNCGA on a template built for another
    instrument: the shocked run lost l.403 and the baseline kept it, so the
    difference was the shock plus the gap between the CGNCGA data and TROD.
    """
    import numpy as np

    size = 1000.0
    paid = _borrowing_deltas("TROD", True)
    for series in ("CGNB", "GGNB", "PSNBNSA", "TME", "PSCE"):
        np.testing.assert_allclose(paid[series], size, atol=1e-6, err_msg=series)
    np.testing.assert_allclose(paid["CGSUBP"], 0.0, atol=1e-6)
    assert (paid["CB"] <= -size + 1e-6).all() and (paid["CB"] > -1.1 * size).all()
    # Quoted in docs/limitations.md and docs/decisions.md, q1 / q4 / q12.
    np.testing.assert_allclose(
        paid["CB"][[0, 3, 11]], (-1000.0, -1015.0, -1056.4), atol=0.5, rtol=0
    )

    held = _borrowing_deltas("TROD", False)
    np.testing.assert_allclose(held["CGSUBP"], -size, atol=1e-6)
    np.testing.assert_allclose(held["PSNBNSA"], 0.0, atol=1e-6)

    # Shocked directly through run_reform, CGNCGA is flat too, but the
    # current account does not see it.
    direct = _borrowing_deltas("CGNCGA", False)
    np.testing.assert_allclose(direct["CGSUBP"], -size, atol=1e-6)
    np.testing.assert_allclose(direct["CB"], 0.0, atol=1.0)


def test_employer_nics_lower_general_government_borrowing_by_the_receipts():
    """Employer NICs +£1,000m a quarter (#88).

    Receipts and PSNBNSA move by the shock. Higher contributions lift
    government pay (l.369, l.371) and central government procurement, the
    residual of the imposed consumption total (l.377), falls by the sum, so
    CGNB falls by the receipts plus the local authority pay rise. With l.526
    live that pay rise is in LANB, and general government borrowing falls by
    exactly the receipts. The central/local split stays the listing's.
    """
    import warnings

    import numpy as np

    size = 1000.0
    d = _borrowing_deltas("EMPNIC", False)
    np.testing.assert_allclose(d["PSCR"], size, atol=1e-6)
    for series in ("GGNB", "TDEF", "PSNBNSA"):
        np.testing.assert_allclose(d[series], -size, atol=1e-6, err_msg=series)
    assert (d["LAWS"] > 50).all() and (d["CGWS"] > 100).all()
    np.testing.assert_allclose(d["CGP"], -(d["CGWS"] + d["LAWS"]), atol=1e-6)
    np.testing.assert_allclose(d["LANB"], d["LAWS"], atol=1e-6)
    np.testing.assert_allclose(d["CGNB"], -size - d["LAWS"], atol=1e-6)
    # Quoted in docs/limitations.md, q1 / q4 / q12.
    np.testing.assert_allclose(
        d["CGNB"][[0, 3, 11]], (-1070.9, -1073.0, -1068.4), atol=0.5, rtol=0
    )
    np.testing.assert_allclose(d["CGWS"][0], 178.6, atol=0.5, rtol=0)
    np.testing.assert_allclose(d["LAWS"][0], 70.9, atol=0.5, rtol=0)

    from obr_macro import run_reform

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = run_reform(name="Employer NICs", var="EMPNIC", shock=size, periods=12)
    assert "l.377" in df.attrs["procurement_offset_note"]
    assert df.attrs["la_borrowing_identity"] is True
    assert "KGLAPC" in df.attrs["la_borrowing_note"]
    np.testing.assert_allclose(
        df.attrs["procurement_offset_m"]["CGP"], d["CGP"], atol=1e-6
    )


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
