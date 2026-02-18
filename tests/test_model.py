import pytest
from obr_macro.variables import Variables
from obr_macro.equations import EQUATION_GROUPS


def test_imports():
    assert len(EQUATION_GROUPS) == 16


def test_variables_basic():
    v = Variables("2020Q1", "2022Q4")
    v["GDP"][:] = 500_000.0
    assert v["GDP"][0] == pytest.approx(500_000.0)
    assert v.elem("GDP", "2020Q1") == pytest.approx(500_000.0)


def test_date_helpers():
    v = Variables("2009Q1", "2010Q4")
    t = v.period_to_idx("2009Q3")
    assert v.date_equals(t, "2009Q3") == 1.0
    assert v.date_equals(t, "2009Q4") == 0.0
    assert v.date_gte(t, "2009Q1") == 1.0
    assert v.date_gte(t, "2010Q1") == 0.0


def test_model_class():
    from obr_macro.model import OBRMacroModel
    m = OBRMacroModel("2020Q1", "2025Q4")
    m.set("GDPM", 500_000.0)
    assert m.get("GDPM")[0] == pytest.approx(500_000.0)
