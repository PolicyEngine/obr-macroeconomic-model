"""run_reform's labels must describe the instrument that was shocked.

The "mechanical passthrough, multiplier 1.0" warning used to be attached to
every demand-closure run, so an income-tax, VAT or Bank Rate result told the
reader its GDP delta was an accounting identity. It is true only for a term of
the expenditure identity (GDPM_EQ).
"""

import re

import pytest

from obr_macro.reform_analysis import (
    EXPENDITURE_IDENTITY_TERMS,
    GDPM_EQ,
    TRANSMISSION_NOTES,
)


def test_identity_terms_are_exactly_the_exogenous_gdp_identity_terms():
    rhs = set(re.findall(r"[A-Z]+", GDPM_EQ.rhs))
    # Every term, CONS and IF included: apply_shock makes the shocked
    # variable exogenous, so each enters GDP as passthrough.
    assert EXPENDITURE_IDENTITY_TERMS == rhs


def test_tax_and_rate_instruments_are_not_labelled_passthrough():
    for var in ("TYEM", "EENIC", "HHDI_ADDFACTOR", "VREC", "TXFUEL", "NNSCTP", "R"):
        assert var not in EXPENDITURE_IDENTITY_TERMS, var
        assert var in TRANSMISSION_NOTES, var
    assert "#60" in TRANSMISSION_NOTES["VREC"]
    assert "TCPRO" in TRANSMISSION_NOTES["NNSCTP"]


@pytest.mark.slow
def test_income_tax_run_carries_its_own_note_not_the_passthrough_warning():
    from obr_macro import run_reform

    df = run_reform("income tax", "TYEM", 1725.0, periods=4, end="2025Q4")
    assert df.attrs["mechanical_passthrough"] is False
    assert "multiplier_warning" not in df.attrs
    assert "consumption equation" in df.attrs["transmission_note"]
