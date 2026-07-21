"""Contract tests for the machine-readable calibration evidence."""

from types import SimpleNamespace

import numpy as np
import pandas as pd

from obr_macro import calibration_score


def test_scorecard_excludes_passthroughs_from_accuracy_denominator(monkeypatch):
    periods = pd.period_range("2024Q4", "2027Q4", freq="Q")
    columns = sorted({entry[0] for rows in calibration_score.PANEL.values() for entry in rows})
    columns.append("RPIGR")
    raw = pd.DataFrame(100.0, index=periods, columns=columns)
    efo = raw.copy()
    solver = SimpleNamespace(data=raw)

    monkeypatch.setattr(calibration_score, "load_obr_data", lambda: efo)
    monkeypatch.setattr(
        calibration_score,
        "raw_solve",
        lambda: (solver, {"GDPM", "CONS"}, {"CONS"}, 1, len(periods) - 1),
    )

    report = calibration_score.build_scorecard()

    assert report["summary"]["computed_variables"] == 1
    assert report["summary"]["passthrough_variables"] == 20
    assert report["summary"]["within_band"] == 1
    rows = [row for block in report["blocks"] for row in block["rows"]]
    assert next(row for row in rows if row["variable"] == "CONS")["band"] is None
    assert next(row for row in rows if row["variable"] == "CONS")["status"].startswith("passthrough")


def test_scorecard_states_what_it_does_not_validate(monkeypatch):
    periods = pd.period_range("2024Q4", "2027Q4", freq="Q")
    columns = sorted({entry[0] for rows in calibration_score.PANEL.values() for entry in rows})
    columns.append("RPIGR")
    data = pd.DataFrame(np.ones((len(periods), len(columns))), index=periods, columns=columns)
    monkeypatch.setattr(calibration_score, "load_obr_data", lambda: data)
    monkeypatch.setattr(
        calibration_score,
        "raw_solve",
        lambda: (SimpleNamespace(data=data), set(columns), set(), 1, len(periods) - 1),
    )

    report = calibration_score.build_scorecard()
    assert any("not a historical-vintage" in item for item in report["limitations"])
    assert "anchored" in " ".join(report["limitations"]).lower()
