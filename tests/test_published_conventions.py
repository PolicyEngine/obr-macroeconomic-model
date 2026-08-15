"""Tests for the OBR published-multiplier conventions mode.

Two layers, matching what each can prove:

- Fast tests pin the conventions TABLE and profile arithmetic against the
  OBR's published values (obr.uk/box/fiscal-multipliers). They prove the
  encoded judgement is the OBR's, and nothing about the model.
- Slow tests (--runslow) prove run_reform imposes exactly that judgement on
  the two channels that cannot produce it (CGG identity, CGIPS dead), leaves
  the live household channel alone, and labels everything. They prove the
  imposition machinery works — the resulting GDP paths are the OBR's
  convention re-applied, NOT evidence about model dynamics, and the labels
  assert as much.
"""

import inspect
import warnings

import numpy as np
import pytest

from obr_macro.published_conventions import (
    INSTRUMENT_CONVENTIONS,
    PUBLISHED_MULTIPLIERS,
    TAPER_QUARTERS,
    multiplier_at,
    multiplier_profile,
    target_gdp_delta,
)


# --- The table: the OBR's published values, verbatim ------------------------


def test_table_matches_obr_published_values():
    """The encoded impact multipliers must be the OBR's published ones —
    current spending 0.6, capital 1.0, income tax/NICs 0.3 (plus welfare 0.6
    and VAT 0.35 from the same box). Any drift here is a misquote of the OBR,
    not a modelling change."""
    assert PUBLISHED_MULTIPLIERS["current_spending"].impact == 0.6
    assert PUBLISHED_MULTIPLIERS["capital_spending"].impact == 1.0
    assert PUBLISHED_MULTIPLIERS["income_tax_and_nics"].impact == 0.3
    assert PUBLISHED_MULTIPLIERS["welfare"].impact == 0.6
    assert PUBLISHED_MULTIPLIERS["vat"].impact == 0.35


def test_every_table_entry_names_an_obr_source():
    """Imposed numbers must carry their provenance: every entry names the OBR
    publication it is taken from."""
    for key, entry in PUBLISHED_MULTIPLIERS.items():
        assert "OBR" in entry.source, f"{key} has no OBR source"
        assert "obr.uk" in entry.source, f"{key} does not cite the publication"


def test_taper_profile_hits_the_published_endpoints():
    """The OBR publishes the impact value and taper-to-zero-at-five-years
    endpoint; the profile must hit both exactly. The linear path between them
    is this repo's choice, so the shape itself is only pinned as monotone —
    asserting more would present our interpolation as the OBR's."""
    assert TAPER_QUARTERS == 20  # five years, per the cited OBR sources
    for channel, entry in PUBLISHED_MULTIPLIERS.items():
        prof = multiplier_profile(channel, TAPER_QUARTERS + 4)
        assert prof[0] == entry.impact  # published impact, undamped
        assert multiplier_at(channel, TAPER_QUARTERS) == 0.0  # published endpoint
        assert all(m == 0.0 for m in prof[TAPER_QUARTERS:])  # stays zero
        diffs = np.diff(prof[: TAPER_QUARTERS + 1])
        assert (diffs < 0).all(), f"{channel} profile is not strictly fading"


def test_target_path_applies_multiplier_to_in_place_impulse():
    """delta_GDP(q) = m(q) * shock(q): a truncated shock must drop out of the
    target when it ends, and a sustained one must fade with the taper."""
    target = target_gdp_delta("capital_spending", [1000.0, 1000.0, 0.0, 0.0])
    assert target[0] == 1000.0  # impact multiplier 1.0
    assert target[1] == 1000.0 * (1 - 1 / TAPER_QUARTERS)
    assert target[2] == target[3] == 0.0


def test_instrument_map_covers_only_identity_or_dead_channels():
    """Only the levers whose model channel is an identity or dead may be
    overridden. The household-tax instrument and the corporation-tax rate have
    live behaviour and must never appear here — imposing published numbers on
    live channels would mix judgement and model dynamics in one figure."""
    from obr_macro.reform_analysis import HOUSEHOLD_COSTING_VAR

    assert set(INSTRUMENT_CONVENTIONS) == {"CGG", "CGIPS", "LAIPS", "GGIPS"}
    assert HOUSEHOLD_COSTING_VAR not in INSTRUMENT_CONVENTIONS
    assert "TCPRO" not in INSTRUMENT_CONVENTIONS
    # CGG is real; the investment levers are nominal and must be deflated.
    assert INSTRUMENT_CONVENTIONS["CGG"].deflator is None
    for v in ("CGIPS", "LAIPS", "GGIPS"):
        assert INSTRUMENT_CONVENTIONS[v].deflator == "GGIDEF"
        assert INSTRUMENT_CONVENTIONS[v].channel == "capital_spending"
    assert INSTRUMENT_CONVENTIONS["CGG"].channel == "current_spending"


def test_flag_defaults_to_off():
    """The honest default is the raw model: published_conventions is opt-in."""
    from obr_macro.reform_analysis import run_reform

    param = inspect.signature(run_reform).parameters["published_conventions"]
    assert param.default is False


def test_conventions_refused_with_investment_closure():
    """The corporation-tax channel has live (if non-converging) behaviour;
    combining it with an imposed convention must be refused up front (fails in
    milliseconds, before any solver build)."""
    from obr_macro.reform_analysis import run_reform

    with pytest.raises(ValueError, match="published_conventions"):
        run_reform(
            "refused",
            "TCPRO",
            0.05,
            periods=12,
            investment_closure=True,
            published_conventions=True,
        )


# --- Imposition on the model (slow: needs OBR download + solver build) ------


@pytest.fixture(scope="module")
def cgg_conventions():
    from obr_macro.reform_analysis import run_reform

    return run_reform(
        "cgg conventions",
        "CGG",
        1250.0,  # £1.25bn/quarter, sustained for 12 quarters
        periods=12,
        published_conventions=True,
    )


@pytest.mark.slow
def test_cgg_conventions_follows_published_profile(cgg_conventions):
    """A CGG shock under conventions must yield the 0.6 impact multiplier
    FADING along the encoded profile — the whole path is asserted, not just
    the impact quarter, because a flat 0.6 would still be the identity
    mechanics in disguise. What this proves: the imposition lands the reported
    delta on multiplier x shock exactly. What it cannot prove: anything about
    the economy or the model — the profile is the OBR's judgement re-applied."""
    df = cgg_conventions
    shock = 1250.0
    target = [0.6 * (1 - q / TAPER_QUARTERS) * shock for q in range(len(df))]
    got = df["delta_gdp_m"].to_numpy(dtype=float)
    # 5 £m absolute tolerance: the GDPM add-factor has no live feedback path
    # under the demand closure, so the only slack is second-order solver noise
    # (measured well under 1 £m). The quarterly fade step is 37.5 £m, so the
    # profile is resolved far beyond the tolerance.
    for q, (g, t) in enumerate(zip(got, target)):
        assert abs(g - t) < 5.0, f"quarter {q}: delta {g:.1f} vs convention {t:.1f}"
    # Explicitly: impact 0.6 and strictly fading thereafter.
    assert got[0] / shock == pytest.approx(0.6, abs=0.005)
    assert (np.diff(got) < 0).all(), "conventions path must fade, not stay flat"
    # Components are NOT overridden: consumption stays inert exactly as in the
    # raw model, so nobody can read behaviour into the imposed number.
    assert df["delta_cons_m"].abs().max() < 0.001 * shock


@pytest.mark.slow
def test_cgg_conventions_is_labelled_as_convention_not_model(cgg_conventions):
    attrs = cgg_conventions.attrs
    assert attrs["published_conventions"] is True
    note = attrs["published_conventions_note"]
    assert "the OBR's published multiplier convention, not model dynamics" in note
    assert "0.6" in note and "linear" in note.lower()
    conv = attrs["convention"]
    assert conv["impact_multiplier"] == 0.6
    assert conv["channel"] == "current_spending"
    assert conv["taper_quarters"] == TAPER_QUARTERS
    assert "OBR" in conv["source"] and "obr.uk" in conv["source"]
    # The raw-mechanics labels describe a number this frame no longer
    # contains, so they must be absent rather than contradictory.
    assert "mechanical_passthrough" not in attrs
    assert "multiplier_warning" not in attrs


@pytest.mark.slow
def test_cgips_conventions_imposes_capital_multiplier_of_one():
    """CGIPS under conventions: impact multiplier 1.0 on the REAL shock (the
    nominal £3bn/qtr is deflated by baseline GGIDEF), fading thereafter; the
    dead-channel warning does not fire because the reported number now follows
    the convention — but delta_IF stays exactly zero, because only the GDP
    total is imposed and the underlying channel is still dead."""
    from obr_macro.reform_analysis import run_reform

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        df = run_reform(
            "cgips conventions",
            "CGIPS",
            3000.0,
            periods=12,
            published_conventions=True,
        )
    dead_warnings = [w for w in caught if "NO transmission path" in str(w.message)]
    assert not dead_warnings, (
        "dead-channel warning fired under conventions mode — the warning "
        "describes the raw result, which this run no longer reports"
    )
    conv = df.attrs["convention"]
    real_shock = conv["real_shock_m"]
    # Deflation sanity: GGIDEF ~ 119, so £3,000m nominal ~ £2,500m real.
    assert 2000.0 < real_shock[0] < 3000.0
    got = df["delta_gdp_m"].to_numpy(dtype=float)
    assert got[0] / real_shock[0] == pytest.approx(1.0, abs=0.01)
    for q in range(len(df)):
        target = 1.0 * (1 - q / TAPER_QUARTERS) * real_shock[q]
        assert abs(got[q] - target) < 5.0, f"quarter {q}: {got[q]:.1f} vs {target:.1f}"
    # The channel itself is still dead and recorded as such.
    assert df.attrs["dead_channel"] is True
    assert (df["delta_if_m"] == 0.0).all()
    assert conv["impact_multiplier"] == 1.0
    assert conv["deflator"] == "GGIDEF"


@pytest.mark.slow
def test_dead_channel_warning_still_fires_when_conventions_off():
    """The honest default must keep announcing the dead channel: turning the
    conventions machinery ON for some runs must not soften the raw runs."""
    from obr_macro.reform_analysis import run_reform

    with pytest.warns(UserWarning, match="NO transmission path"):
        df = run_reform("cgips raw", "CGIPS", 3000.0, periods=12)
    assert df.attrs["dead_channel"] is True
    assert df.attrs["published_conventions"] is False
    assert "convention" not in df.attrs


@pytest.mark.slow
def test_cgg_default_run_is_unchanged_raw_passthrough():
    """Default (conventions off) must still be the raw model with its raw
    labels: flat 1.0 passthrough, mechanical_passthrough True, and the
    multiplier warning naming the published 0.6 it fails to match."""
    from obr_macro.reform_analysis import run_reform

    df = run_reform("cgg raw", "CGG", 1250.0, periods=12)
    mult = df["delta_gdp_m"].to_numpy(dtype=float) / 1250.0
    assert abs(mult[0] - 1.0) < 1e-3
    assert abs(mult[-1] - mult[0]) < 0.01  # flat, no fade
    assert df.attrs["published_conventions"] is False
    assert df.attrs["mechanical_passthrough"] is True
    assert "0.6" in df.attrs["multiplier_warning"]


@pytest.mark.slow
def test_household_tax_is_untouched_by_the_flag():
    """The household channel has real behaviour, so conventions mode must
    leave it bit-for-bit alone and say so in attrs."""
    from obr_macro.reform_analysis import run_reform

    kwargs = dict(
        var="HHDI_ADDFACTOR",
        shock=[1615.0] * 4,  # ~£6.46bn/yr, the repo's worked costing
        start="2025Q1",
        end="2025Q4",
    )
    raw = run_reform("household raw", **kwargs)
    flagged = run_reform("household flagged", published_conventions=True, **kwargs)

    assert np.array_equal(
        raw["delta_gdp_m"].to_numpy(), flagged["delta_gdp_m"].to_numpy()
    )
    assert raw.attrs["delta_hhdi_m"] == flagged.attrs["delta_hhdi_m"]
    assert flagged.attrs["published_conventions"] is False
    note = flagged.attrs["published_conventions_note"]
    assert "NOT applied" in note
    assert "live model behaviour" in note
    # The raw run carries no conventions note at all — nothing was requested.
    assert "published_conventions_note" not in raw.attrs
