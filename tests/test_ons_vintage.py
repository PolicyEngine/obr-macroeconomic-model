"""ONS vintage recorded per series (#49). Hermetic: no ONS request is made."""

import json

import pandas as pd

from obr_macro import ons_fetch, ons_pull


def _resp(release, n_quarters):
    return {
        "description": {"releaseDate": release, "datasetId": f"D{n_quarters}"},
        "quarters": [{}] * n_quarters,
    }


def test_latest_release_beats_longer_history():
    old_long = _resp("2024-03-28T00:00:00.000Z", 300)
    new_short = _resp("2026-09-30T00:00:00.000Z", 120)
    assert ons_fetch.pick_dataset([old_long, new_short]) is new_short


def test_same_release_falls_back_to_most_observations():
    a = _resp("2026-09-30T00:00:00.000Z", 100)
    b = _resp("2026-09-30T00:00:00.000Z", 200)
    assert ons_fetch.pick_dataset([a, b]) is b


def test_missing_release_date_loses_to_a_dated_one():
    undated = {"description": {}, "quarters": [{}] * 500}
    dated = _resp("2025-01-01T00:00:00.000Z", 10)
    assert ons_fetch.pick_dataset([undated, dated]) is dated
    assert ons_fetch.release_date(undated) == ""


def test_pick_dataset_empty():
    assert ons_fetch.pick_dataset([]) is None


def test_fresh_fetch_records_fetch_date(tmp_path, monkeypatch):
    monkeypatch.setattr(ons_pull, "CACHE", tmp_path)
    s = pd.Series([1.0, 2.0], index=pd.period_range("2025Q1", periods=2, freq="Q"))
    meta = {"cdid": "ABCD", "release_date": "2026-09-30"}
    monkeypatch.setattr(ons_pull, "fetch_series", lambda cdid: (s, dict(meta)))
    monkeypatch.setattr(ons_pull.time, "sleep", lambda _: None)
    _, got = ons_pull.fetch_cached("ABCD")
    today = pd.Timestamp.now().strftime("%Y-%m-%d")
    assert got["fetched"] == today
    on_disk = json.loads((tmp_path / "ABCD.meta.json").read_text())
    assert on_disk["fetched"] == today and on_disk["release_date"] == "2026-09-30"
    # A cache hit returns the stored dates, not today's.
    (tmp_path / "ABCD.meta.json").write_text(
        json.dumps({**on_disk, "fetched": "2026-01-02"})
    )
    _, hit = ons_pull.fetch_cached("ABCD")
    assert hit["fetched"] == "2026-01-02"


def test_pulled_is_the_oldest_fetch_not_the_write_date():
    manifest = {
        "A": {"cdid": "X", "fetched": "2026-07-11"},
        "B": {"cdid": "Y", "fetched": "2026-09-22"},
        "C": {
            "formula": "X+Y",
            "components": [{"cdid": "X", "fetched": "2026-05-01"}, {"cdid": "Y"}],
        },
    }
    dates = ons_pull.snapshot_dates(manifest, "2026-11-24")
    assert dates == {
        "pulled": "2026-05-01",
        "written": "2026-11-24",
        "fetched_unknown": 1,
    }


def test_all_unknown_gives_no_pulled_date():
    dates = ons_pull.snapshot_dates({"A": {"cdid": "X"}}, "2026-11-24")
    assert dates["pulled"] is None and dates["fetched_unknown"] == 1


def test_vintage_fields():
    assert ons_pull.vintage({"release_date": "2026-09-30", "fetched": ""}) == {
        "release_date": "2026-09-30",
        "fetched": None,
    }
    assert ons_pull.vintage(None) == {"release_date": None, "fetched": None}
