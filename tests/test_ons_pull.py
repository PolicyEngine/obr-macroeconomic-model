"""eval_compound: glossary arithmetic over ONS CDIDs, including lags (#43).

Hermetic: fetch_cached is replaced with synthetic quarterly series, so no ONS
request is made.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from obr_macro import ons_pull

DEBTU_FORMULA = "(NFYS-NGAS-CT9E+CT9E(-1))/(NNPP(-1)-NNRP(-1)-CT9E(-1))"


def _q(start, values):
    idx = pd.period_range(start, periods=len(values), freq="Q")
    return pd.Series(values, index=idx, dtype=float, name="value")


@pytest.fixture
def fake_fetch(monkeypatch):
    series = {}

    def fetch(cdid):
        s = series.get(cdid)
        return (None, {}) if s is None else (s.copy(), {"cdid": cdid})

    monkeypatch.setattr(ons_pull, "fetch_cached", fetch)
    return series


def test_glossary_debtu_formula_is_the_one_tested():
    # Guards the fixture: if the glossary's DEBTU formula changes, so must this test.
    glossary = Path(ons_pull.__file__).parent / "seeds/model_glossary.json"
    items = {it["code"]: it for it in json.loads(glossary.read_text())["items"]}
    assert items["DEBTU"]["ons"].strip() == DEBTU_FORMULA


def test_debtu_lags_evaluate_by_hand(fake_fetch):
    fake_fetch.update(
        NFYS=_q("2020Q1", [10, 11, 12, 13]),
        NGAS=_q("2020Q1", [1, 1, 2, 2]),
        CT9E=_q("2020Q1", [3, 4, 5, 6]),
        NNPP=_q("2020Q1", [100, 110, 120, 130]),
        NNRP=_q("2020Q1", [20, 20, 30, 30]),
    )
    out, err, metas = ons_pull.eval_compound(DEBTU_FORMULA)
    assert err is None
    assert len(metas) == 5
    # The first quarter has no lag available and is dropped, not mis-filled.
    assert list(out.index.astype(str)) == ["2020Q2", "2020Q3", "2020Q4"]
    # 2020Q2: (11 - 1 - 4 + 3) / (100 - 20 - 3)
    assert out[pd.Period("2020Q2", "Q")] == pytest.approx(9 / 77)
    # 2020Q3: (12 - 2 - 5 + 4) / (110 - 20 - 4)
    assert out[pd.Period("2020Q3", "Q")] == pytest.approx(9 / 86)
    # 2020Q4: (13 - 2 - 6 + 5) / (120 - 30 - 5)
    assert out[pd.Period("2020Q4", "Q")] == pytest.approx(10 / 85)


def test_lag_follows_period_labels_not_positions(fake_fetch):
    # Cached series are stored with gaps dropped. A positional shift would pair
    # 2020Q4 with 2020Q2's value; the lag must leave 2020Q4 without a t-1 value.
    gapped = _q("2020Q1", [1, 2, 3, 4]).drop(pd.Period("2020Q3", "Q"))
    fake_fetch["ABCD"] = gapped
    out, err, _ = ons_pull.eval_compound("ABCD-ABCD(-1)")
    assert err is None
    assert out.to_dict() == {pd.Period("2020Q2", "Q"): 1.0}


def test_multi_quarter_lag(fake_fetch):
    fake_fetch["ABCD"] = _q("2020Q1", [1, 2, 4, 8, 16])
    out, err, _ = ons_pull.eval_compound("ABCD/ABCD(-4)")
    assert err is None
    assert out.to_dict() == {pd.Period("2021Q1", "Q"): 16.0}


def test_unlagged_formula_unchanged(fake_fetch):
    fake_fetch.update(AAAA=_q("2020Q1", [1, 2]), BBBB=_q("2020Q1", [3, 5]))
    out, err, _ = ons_pull.eval_compound("AAAA+BBBB")
    assert err is None
    assert out.tolist() == [4.0, 7.0]


@pytest.mark.parametrize("formula", ["ABCD(1)", "ABCD(+1)", "ABCD(ABCD)"])
def test_leads_and_calls_are_rejected_not_evaled(fake_fetch, formula):
    fake_fetch["ABCD"] = _q("2020Q1", [1, 2, 3])
    out, err, _ = ons_pull.eval_compound(formula)
    assert out is None
    assert "unsupported" in err


def test_missing_lagged_component_reported(fake_fetch):
    out, err, _ = ons_pull.eval_compound("ABCD-ABCD(-1)")
    assert out is None
    assert err == "missing component ABCD"
