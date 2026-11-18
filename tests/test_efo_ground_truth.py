"""Ground-truth validation of the OBR EFO ingestion pipeline.

Every calibration and anchoring gate in this suite scores the model against
``load_obr_data()``. If that loader ever reads the wrong column, drops a unit
conversion, or silently mis-parses a re-laid-out workbook, the "ground truth"
the model is validated against stops being the OBR's published numbers — and
every downstream MAPE gate becomes meaningless while still passing.

These tests validate the loaded data against the publication itself, using
only numbers that ship in the repo's official OBR workbooks (obr_macro/_data):

1. The OBR's own published accounting identities must hold on the loaded
   series (GDP expenditure identity, growth-vs-index consistency,
   unemployment rate vs counts). These are properties of the official
   publication, so any violation is an ingestion bug, not a model error.
2. Pinned spot values transcribed from the October-2026 EFO economy workbook
   (Table 1.1), guarding the £bn→£m unit conversions.
3. Cross-vintage coherence: the November-2025 EFO workbook (also shipped in
   _data, previously read by nothing) must parse under the same layout
   assertions, and its overlap with the October-2026 vintage must agree to
   within normal forecast-revision size.

All tests here are fast and hermetic (no solver, no network): they run in the
PR-gating fast suite.
"""

import numpy as np
import openpyxl
import pandas as pd
import pytest

from obr_macro.data import (
    DATA_DIR,
    _assert_headers,
    _read_quarterly_table,
    load_obr_data,
)

SCORED_START = pd.Period("2025Q1", freq="Q")
SCORED_END = pd.Period("2027Q4", freq="Q")


@pytest.fixture(scope="module")
def efo():
    """The October-2026 EFO as the model consumes it (no ONS snapshot merge,
    so every value scored here traces to the OBR workbooks alone)."""
    return load_obr_data(merge_snapshot=False)


@pytest.fixture(scope="module")
def horizon(efo):
    return efo.loc[SCORED_START:SCORED_END]


# --- 0. Coverage -------------------------------------------------------------


def test_scored_horizon_is_fully_covered(horizon):
    """The calibration scorecard and anchoring gates score 2025Q1-2027Q4.
    Every quarter must be present with finite headline values — a silently
    truncated load would shrink the scoring sample instead of failing."""
    assert len(horizon) == 12, f"expected 12 quarters, got {len(horizon)}"
    for code in ("GDPM", "GDPMPS", "CONS", "CGG", "IF", "X", "M", "LFSUR", "CPI"):
        vals = horizon[code].to_numpy(dtype=float)
        assert np.isfinite(vals).all(), f"{code} not finite on the scored horizon"


# --- 1. Published accounting identities on the loaded data -------------------


def test_published_real_gdp_identity_holds_on_loaded_data(horizon):
    """CONS+CGG+IF+DINV+VAL+X-M+SDE must equal GDPM on the *published* series
    as loaded. In the workbook this holds to rounding; a column shift or a
    missed unit conversion breaks it by orders of magnitude. Observed max
    relative residual on the October-2026 vintage: ~5e-12."""
    rhs = (
        horizon["CONS"]
        + horizon["CGG"]
        + horizon["IF"]
        + horizon["DINV"]
        + horizon["VAL"]
        + horizon["X"]
        - horizon["M"]
        + horizon["SDE"]
    )
    resid = (rhs - horizon["GDPM"]).abs() / horizon["GDPM"].abs()
    assert resid.max() < 1e-6, (
        f"published real GDP identity broken in loaded data: max rel resid "
        f"{resid.max():.2e} — ingestion is reading the wrong columns or units"
    )


def test_published_nominal_gdp_identity_holds_on_loaded_data(horizon):
    """Nominal counterpart from Table 1.2 (no nominal SDE column is read, so
    the tolerance covers the published discrepancy: observed max ~3.2e-4)."""
    rhs = (
        horizon["CONSPS"]
        + horizon["CGGPS"]
        + horizon["IFPS"]
        + horizon["DINVPS"]
        + horizon["VALPS"]
        + horizon["XPS"]
        - horizon["MPS"]
    )
    resid = (rhs - horizon["GDPMPS"]).abs() / horizon["GDPMPS"].abs()
    assert resid.max() < 2e-3, (
        f"published nominal GDP identity broken: max rel resid {resid.max():.2e}"
    )


def test_cpi_growth_column_matches_cpi_index_column(efo):
    """Table 1.7 publishes both the CPI index and its year-on-year growth.
    The loaded pair must be mutually consistent: 100*(CPI/CPI[-4]-1) == CPIGR
    wherever both exist (observed max abs gap 0.0). A mismatch means one of
    the two price columns is being read from the wrong position."""
    implied = 100 * (efo["CPI"] / efo["CPI"].shift(4) - 1)
    both = pd.concat([implied, efo["CPIGR"]], axis=1).dropna()
    assert len(both) > 20, "too few overlapping CPI observations to validate"
    gap = (both.iloc[:, 0] - both.iloc[:, 1]).abs().max()
    assert gap < 0.05, f"CPI growth vs index inconsistent: max gap {gap:.3f}pp"


def test_unemployment_rate_matches_published_counts(efo):
    """LFSUR must equal 100*ULFSU/(ULFSU+ETLFS) on the loaded series
    (observed max abs gap ~1.5e-8pp). Guards the millions→thousands
    conversions on the labour-market counts and the rate column position."""
    implied = 100 * efo["ULFSU"] / (efo["ULFSU"] + efo["ETLFS"])
    both = pd.concat([implied, efo["LFSUR"]], axis=1).dropna()
    assert len(both) > 20, "too few overlapping labour-market observations"
    gap = (both.iloc[:, 0] - both.iloc[:, 1]).abs().max()
    assert gap < 0.01, f"LFSUR inconsistent with counts: max gap {gap:.4f}pp"


@pytest.fixture(scope="module")
def databank():
    """The EFO tables with the ONS snapshot merged: what the solver loads."""
    from obr_macro.data import load_obr_data

    return load_obr_data()


def test_efo_implied_population_matches_the_ons_series_over_history(databank):
    """The 16+ population implied by the EFO labour-market table,
    100*(ULFSU + ETLFS)/PART16 (l.175 rearranged), must equal the ONS series
    MGSL wherever MGSL is observed. Measured 18 Nov 2026 on 2019Q1 to the
    snapshot edge (2026Q1): the two agree to the nearest thousand people
    (max relative gap about 1e-5). That agreement is what licenses using
    the implied path beyond the edge; if it breaks, the EFO's participation
    rate is no longer on the MGSL basis and the forecast population must not
    be derived this way."""
    from obr_macro.data import efo_implied_pop16, ons_snapshot_edge

    edge = ons_snapshot_edge("POP16")
    assert edge is not None, "POP16 is missing from the ONS snapshot"
    implied = efo_implied_pop16(databank).loc["2019Q1":edge]
    observed = databank["POP16"].loc["2019Q1":edge]
    assert len(observed) >= 20, "too few observed population quarters"
    gap = (implied / observed - 1).abs().max()
    assert gap < 5e-5, f"EFO-implied POP16 off the ONS series by {gap:.2e}"


def test_forecast_population_follows_the_efo_and_closes_the_labour_identity(databank):
    """Beyond the last ONS observation POP16 is the EFO-implied path, not the
    trailing-mean hold every other snapshot series gets, so the labour-force
    identity ULFS = POP16*PART16/100 - ETLFS (l.163) returns the EFO's own
    unemployment. Held flat, the population sat at 56.4m (below its last
    observation, 56.6m) while employment rose, and the identity drained
    unemployment to 1.05% by 2031Q1 against the EFO's 4.17%."""
    from obr_macro.data import efo_implied_pop16, ons_snapshot_edge

    edge = ons_snapshot_edge("POP16")
    tail = databank.loc[edge + 1 : "2031Q1"]
    assert len(tail) >= 16, "the forecast horizon is shorter than expected"
    pd.testing.assert_series_equal(
        tail["POP16"], efo_implied_pop16(databank).loc[tail.index], check_names=False
    )
    # It grows: about 70-80 thousand a quarter, never flat, never falling.
    step = tail["POP16"].diff().dropna()
    assert (step > 20).all() and (step < 200).all(), step.describe()
    # No jump at the splice from observations to the implied path.
    splice = databank.loc[edge + 1, "POP16"] - databank.loc[edge, "POP16"]
    assert 20 < splice < 200, f"POP16 jumps {splice:.0f} thousand at the splice"
    # The identity closes on the EFO unemployment rate.
    ulfs = tail["POP16"] * tail["PART16"] / 100 - tail["ETLFS"]
    rate = 100 * ulfs / (tail["ETLFS"] + ulfs)
    gap = (rate - tail["LFSUR"]).abs().max()
    assert gap < 0.01, f"labour identity misses EFO unemployment by {gap:.4f}pp"


# --- 2. Pinned published spot values (unit-conversion guard) -----------------

# Transcribed from obr_macro/_data/obr_efo_october_2026_economy.xlsx,
# Table 1.1 (real GDP expenditure, £bn, row 2025Q1), converted to the model's
# £m units exactly as load_obr_data does. These are OBR-published numbers,
# not model outputs: if a future loader change scales or shifts a column,
# these fail with the exact variable named.
OCTOBER_2026_EFO_TABLE_1_1_2025Q1_M = {
    "GDPM": 703_178.0,  # real GDP, £m
    "CONS": 429_957.0,  # private consumption, £m
}


def test_pinned_published_2025q1_levels(efo):
    row = efo.loc[pd.Period("2025Q1", freq="Q")]
    for code, published in OCTOBER_2026_EFO_TABLE_1_1_2025Q1_M.items():
        assert row[code] == pytest.approx(published, rel=1e-9), (
            f"{code} 2025Q1 loaded as {row[code]:,.0f} but the October-2026 EFO "
            f"Table 1.1 publishes {published:,.0f} (£m) — ingestion drifted "
            "from the official workbook"
        )


# --- 3. Cross-vintage coherence (November-2025 EFO) --------------------------


@pytest.fixture(scope="module")
def november_gdp():
    """Real GDP and consumption from the November-2025 EFO economy workbook,
    read through the same layout-guarded path as the October vintage."""
    wb = openpyxl.load_workbook(
        str(DATA_DIR / "obr_efo_november_2025_economy.xlsx"), data_only=True
    )
    _assert_headers(
        wb,
        "1.1",
        {(2, 2): "1.1 GDP expend", (3, 3): "Private consum", (3, 4): "Government con"},
    )
    data = _read_quarterly_table(
        wb, "1.1", period_col=2, data_cols={"GDPM": 18, "CONS": 3}
    )
    return {k: v * 1000 for k, v in data.items()}  # £bn → £m


def test_november_2025_vintage_parses_under_same_layout(november_gdp):
    """The shipped November-2025 workbook must satisfy the same header
    assertions and yield a usable quarterly GDP series. This proves the
    absolute-column mapping is a property of the EFO format, not a
    coincidence of one file."""
    gdp = november_gdp["GDPM"]
    assert len(gdp) > 40, f"only {len(gdp)} GDPM quarters parsed from Nov-2025"
    assert gdp.index.min() <= pd.Period("2015Q1", freq="Q")
    assert gdp.index.max() >= pd.Period("2030Q1", freq="Q")


@pytest.mark.parametrize("code", ["GDPM", "CONS"])
def test_october_vs_november_vintages_agree_to_revision_size(efo, november_gdp, code):
    """On overlapping quarters the two official vintages must agree to within
    normal forecast-revision size (observed max relative gap, October 2026 vs
    November 2025: GDPM 0.95%, CONS 1.01%, both at 2027Q3). A gap of percent-scale or more means one vintage is being
    mis-read — the strongest available check that BOTH loads are faithful,
    since two independent workbooks would not mis-parse into agreement."""
    both = pd.concat([november_gdp[code], efo[code]], axis=1, keys=["nov", "oct"])
    both = both.dropna()
    assert len(both) > 40, f"too little vintage overlap for {code}"
    rev = (both["oct"] / both["nov"] - 1).abs()
    assert rev.max() < 0.02, (
        f"{code}: October-2026 vs November-2025 vintages diverge by "
        f"{100 * rev.max():.2f}% at {rev.idxmax()} — far beyond forecast "
        "revision size; one vintage is mis-read"
    )
