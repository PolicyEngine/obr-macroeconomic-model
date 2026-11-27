"""docs/forecasting_framework.md against the output of ``python -m obr_macro.forecast``.

The headline table on that page was typed by hand from the CLI's output. The
CLI reproduced it on 26 Nov 2026, but nothing checked that, so a change to the
model, the data vintage or the scoring could leave the page quoting a fit the
model no longer produces.

These tests run the CLI's ``main`` under both closures, parse what it prints
and compare it with the table, the "N of 16 computed" sentence and the figures
repeated in the page's prose. A failure means the page and the model disagree:
rerun ``uv run python -m obr_macro.forecast`` (and ``--published-closure``)
and update the page, or find out why the model moved.

Slow: two held-add-factor forecasts, about one minute together.
"""

import contextlib
import io
import re
from pathlib import Path

import pytest

from obr_macro import forecast

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "forecasting_framework.md"

# One printed line per panel variable, for example
#    [OK] Real GDP                  0.63%   computed
#    [OK] Current account         0.33%GDP   computed
LINE = re.compile(
    r"^\s*\[(?P<mark>..)\]\s+(?P<label>.+?)\s+(?P<err>\d+\.\d\d)(?P<unit>%GDP|pp|%)"
    r"\s+(?P<status>computed|passthrough \((?:exogenous|dead)\))\s*$"
)
SUMMARY = re.compile(r"computed (\d+)/(\d+) \| within band: (\d+)/(\d+) computed")
DOC_UNIT = {"%": "%", "pp": "pp", "%GDP": "% of GDP"}
NUMBER_WORDS = {6: "six", 7: "seven", 8: "eight"}


def _run_cli(argv):
    """Run the CLI's ``main`` and parse what it prints."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        forecast.main(argv)
    out = buf.getvalue()
    rows = {}
    for line in out.splitlines():
        m = LINE.match(line)
        if m:
            rows[m["label"]] = {
                "mark": m["mark"].strip(),
                "err": float(m["err"]),
                "cell": m["err"] + DOC_UNIT[m["unit"]],
                "computed": m["status"] == "computed",
            }
    summary = SUMMARY.search(out)
    assert summary, f"no summary line in the CLI output:\n{out}"
    assert len(rows) == len(forecast.PANEL), (
        f"parsed {len(rows)} of {len(forecast.PANEL)} panel lines:\n{out}"
    )
    return rows, tuple(int(g) for g in summary.groups())


@pytest.fixture(scope="module")
def cli():
    """Both closures, each run once."""
    return {"pin": _run_cli([]), "published": _run_cli(["--published-closure"])}


def _doc_table():
    """The headline table: {label: (default cell, band cell, published cell)}."""
    text = DOC.read_text()
    start = text.index("| Variable | Error (held-AF forecast) | band |")
    table = {}
    for line in text[start:].splitlines()[2:]:
        if not line.startswith("|"):
            break
        label, default, band_cell, published = (
            c.strip() for c in line.strip().strip("|").split("|")
        )
        table[label] = (default, band_cell, published)
    return table


def _within(mark):
    return mark in ("OK", "~")


def test_headline_table_matches_the_cli(cli):
    pin, _ = cli["pin"]
    published, _ = cli["published"]
    table = _doc_table()
    assert len(table) == 10, f"expected 10 table rows, found {sorted(table)}"
    for label, (default, band_cell, pub) in table.items():
        assert label in pin, f"the table has '{label}', the CLI does not print it"
        for closure, cell, row in (
            ("default closure", default, pin[label]),
            ("published closure", pub, published[label]),
        ):
            if not row["computed"]:
                assert cell == "—", (
                    f"{label} ({closure}): the CLI no longer computes it but "
                    f"the page quotes {cell!r}"
                )
                continue
            assert cell.split(" (")[0] == row["cell"], (
                f"{label} ({closure}): the page says {cell!r}, "
                f"`python -m obr_macro.forecast` prints {row['cell']!r}"
            )
            said = re.search(r"\((within|over)\)", cell)
            if said:
                assert (said[1] == "within") == _within(row["mark"]), (
                    f"{label} ({closure}): the page says {said[1]}, the CLI "
                    f"marks it [{row['mark']}]"
                )
        if pin[label]["computed"] and band_cell in ("within", "**over**"):
            assert (band_cell == "within") == _within(pin[label]["mark"]), (
                f"{label}: band column says {band_cell}, the CLI marks it "
                f"[{pin[label]['mark']}]"
            )


def test_every_computed_variable_is_in_the_table(cli):
    """A variable the CLI starts computing must not go unreported."""
    table = _doc_table()
    for closure in ("pin", "published"):
        rows, _ = cli[closure]
        missing = [k for k, r in rows.items() if r["computed"] and k not in table]
        assert not missing, (
            f"computed by the CLI ({closure}), absent from the page: {missing}"
        )


def test_computed_and_within_band_counts_match_the_cli(cli):
    text = DOC.read_text()
    m = re.search(
        r"\*\*(\d+) of (\d+) headline variables computed; (\d+) of those within "
        r"band under both\s+closures",
        text,
    )
    assert m, "the '8 of 16 headline variables computed' sentence has changed"
    doc_computed, doc_panel, doc_within = (int(g) for g in m.groups())
    for closure in ("pin", "published"):
        _, (computed, panel, within, of) = cli[closure]
        assert (computed, panel, within) == (doc_computed, doc_panel, doc_within), (
            f"{closure}: CLI says computed {computed}/{panel}, within band "
            f"{within}/{of}; the page says {doc_computed} of {doc_panel}, "
            f"{doc_within} within"
        )
        assert of == computed
    word = NUMBER_WORDS[doc_within]
    assert f"Two of the {word} are identities" in text


def test_prose_repeats_of_the_headline_figures_match_the_cli(cli):
    """The page repeats four table figures in its prose."""
    pin, _ = cli["pin"]
    text = " ".join(DOC.read_text().split())
    quoted = {
        "caveat 4": f'"Real GDP forecasts to {pin["Real GDP"]["cell"]}"',
        "over band": f"company profits ({pin['Company profits']['err']:.1f}%)",
        "business investment": (
            f"Business investment ({pin['Business investment']['err']:.1f}%)"
        ),
        "current account": f"current account ({pin['Current account']['cell']})",
        "unemployment": f"scores {pin['Unemployment rate']['cell']} because",
    }
    for where, phrase in quoted.items():
        assert phrase in text, f"{where}: expected the page to say {phrase!r}"


def test_chat_agent_overview_matches_the_cli(cli):
    """chat/agent.py's model_overview repeats the counts in plain text. Read
    as text: importing the module needs the optional ``chat`` dependencies."""
    rows, (computed, panel, within, _) = cli["pin"]
    source = (ROOT / "chat" / "agent.py").read_text()
    # Join the adjacent string literals the sentences are split across.
    text = " ".join(re.sub(r'"\s*\n\s*"', "", source).split())
    assert f"{computed} of the {panel} headline variables are computed" in text
    assert f"{within} of those {computed} stay within the scoring band" in text
    over = [
        k for k, r in rows.items() if r["computed"] and r["mark"] not in ("OK", "~")
    ]
    assert over == ["Company profits"], over
    assert "company profits do not" in text
