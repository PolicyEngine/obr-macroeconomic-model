"""The OBR's published fiscal-multiplier conventions, encoded as data.

WHAT THIS MODULE IS. The OBR does not derive its fiscal multipliers from the
macro model's equations: it imposes them as judgement, then applies them as
adjustments on top of the model. This module encodes that published judgement —
the impact multiplier per instrument class and the taper-to-zero assumption —
so that ``run_reform(..., published_conventions=True)`` can impose the same
convention on the two levers whose model channel cannot produce a multiplier
at all (government consumption: identity passthrough; government investment:
dead channel).

WHAT IT IS NOT. Nothing here is a model result, an estimate, or evidence.
A GDP path built from this table proves only that the arithmetic
``multiplier x shock`` was carried out; every run that uses it is labelled
"the OBR's published multiplier convention, not model dynamics" in
``df.attrs``.

Sources. The impact multipliers are the ones the OBR has used since the June
2010 Budget, restated in the Economic and fiscal outlook, July 2015, Box 3.2
"Fiscal multipliers" (obr.uk/box/fiscal-multipliers). The taper is from the
same box ("the multiplier was assumed to diminish or taper over five years, as
the initial effect was offset by changes in monetary policy, the exchange rate
and real wage adjustments") and is restated in the OBR's "Dynamic scoring of
policy measures in OBR forecasts" (articles.obr.uk): "All of these multipliers
are assumed to taper to zero over five years". The OBR publishes the impact
value and the zero endpoint; the quarterly path between them is NOT published
as a formula, so the linear shape below is this repo's choice (see
``multiplier_profile``).
"""

from collections.abc import Iterable
from dataclasses import dataclass


# The OBR's taper horizon: multipliers reach zero five years after the shock
# starts. Both cited OBR sources say five years ("taper to zero over five
# years"); the effect is already small after about three, which is why the
# assumption is often paraphrased as fading over roughly three years, but the
# published endpoint is zero at five. Since November 2015 the OBR tapers from
# the point of ANNOUNCEMENT rather than implementation; this repo has no
# announcement date, so the taper runs from the shock start — i.e. announcement
# and implementation are treated as coincident. That simplification is ours.
TAPER_QUARTERS = 20

_SOURCE = (
    "OBR, Economic and fiscal outlook, July 2015, Box 3.2 'Fiscal "
    "multipliers' (obr.uk/box/fiscal-multipliers); taper restated in OBR, "
    "'Dynamic scoring of policy measures in OBR forecasts' (articles.obr.uk)"
)


@dataclass(frozen=True)
class PublishedMultiplier:
    """One row of the OBR's published multiplier table.

    ``impact`` is the OBR's published first-year multiplier for the instrument
    class — a number the OBR imposes as judgement, not one that comes out of
    its model equations (or this emulator's). ``source`` names the OBR
    publication it is taken from.
    """

    label: str  # the OBR's name for the instrument class
    impact: float  # published impact (year-one) multiplier
    source: str  # OBR publication the number comes from


# The published table, verbatim. Every value is the OBR's, none is estimated
# here. Keys are this repo's identifiers; ``label`` is the OBR's wording.
PUBLISHED_MULTIPLIERS = {
    # EFO July 2015 Box 3.2: implied Resource DEL / "day-to-day spending on
    # public services" multiplier of 0.6.
    "current_spending": PublishedMultiplier(
        label="current (day-to-day) departmental spending",
        impact=0.6,
        source=_SOURCE,
    ),
    # EFO July 2015 Box 3.2: capital expenditure / "investment" multiplier of
    # 1.0 — the OBR's largest.
    "capital_spending": PublishedMultiplier(
        label="capital (investment) spending",
        impact=1.0,
        source=_SOURCE,
    ),
    # EFO July 2015 Box 3.2: welfare measures at 0.6, same as current spending.
    "welfare": PublishedMultiplier(
        label="welfare spending",
        impact=0.6,
        source=_SOURCE,
    ),
    # EFO July 2015 Box 3.2: VAT changes at 0.35.
    "vat": PublishedMultiplier(
        label="VAT",
        impact=0.35,
        source=_SOURCE,
    ),
    # EFO July 2015 Box 3.2: income tax and NICs changes at 0.3.
    "income_tax_and_nics": PublishedMultiplier(
        label="income tax and NICs",
        impact=0.3,
        source=_SOURCE,
    ),
}


@dataclass(frozen=True)
class InstrumentConvention:
    """How a model instrument maps onto the published table.

    ``deflator``: the OBR multipliers map REAL spending to REAL GDP, but some
    model instruments are nominal (£m current prices). For those, the shock is
    converted to real terms with the named baseline deflator (index, 100 =
    base year) before the multiplier is applied; ``None`` means the instrument
    is already real.
    """

    channel: str  # key into PUBLISHED_MULTIPLIERS
    deflator: "str | None"


# Instruments the conventions mode may override. ONLY levers whose model
# channel is an accounting identity or dead belong here — imposing a published
# number on top of a channel with live behaviour would mix imposed and modelled
# dynamics in one figure, which is exactly what the labelling exists to
# prevent. That is why HHDI_ADDFACTOR (household tax, live dlog(CONS) channel)
# and TCPRO (investment closure, live cost-of-capital channel) are absent.
INSTRUMENT_CONVENTIONS = {
    # Government consumption enters the GDP identity directly: the model's
    # "multiplier" is 1.0 flat by construction (accounting, not behaviour).
    "CGG": InstrumentConvention(channel="current_spending", deflator=None),
    # The government-investment levers are DEAD in the model (IF has no live
    # equation, so CGIPS -> GGIPS -> GGI -> IF never reaches GDP). They are
    # nominal £m; GGIDEF is the general-government investment deflator.
    "CGIPS": InstrumentConvention(channel="capital_spending", deflator="GGIDEF"),
    "LAIPS": InstrumentConvention(channel="capital_spending", deflator="GGIDEF"),
    "GGIPS": InstrumentConvention(channel="capital_spending", deflator="GGIDEF"),
}


def multiplier_at(channel: str, quarters_since_start: int) -> float:
    """The convention's multiplier ``q`` quarters after the shock starts.

    Linear fade from the published impact value to exactly zero at
    ``TAPER_QUARTERS``. The SHAPE is this repo's choice, not the OBR's: the
    OBR publishes the impact multiplier and the zero-at-five-years endpoint,
    not a quarterly path. Linear is the minimal-assumption path through both
    published points — it needs no free parameter beyond the horizon and
    actually reaches zero (a geometric fade never does, so it would require a
    second invented constant to truncate it). The OBR's illustrative
    year-by-year paths in its dynamic-scoring article are close to, though
    slightly more front-loaded than, this straight line.
    """
    m = PUBLISHED_MULTIPLIERS[channel]
    return m.impact * max(0.0, 1.0 - quarters_since_start / TAPER_QUARTERS)


def multiplier_profile(channel: str, quarters: int) -> "list[float]":
    """Per-quarter multiplier path ``[m(0), ..., m(quarters-1)]``."""
    return [multiplier_at(channel, q) for q in range(quarters)]


def target_gdp_delta(channel: str, real_shock_path: "Iterable[float]") -> "list[float]":
    """The GDP delta path (£m real, per quarter) the convention implies.

    Follows the OBR's application rule: the multiplier in force ``q`` periods
    after the shock starts is applied to the fiscal impulse IN PLACE in that
    period, so ``delta_GDP(q) = m(q) * shock(q)``. A truncated shock therefore
    drops out of GDP when it ends, and a sustained one fades with the taper.
    ``real_shock_path`` must already be in real £m per quarter (deflate nominal
    instruments first — see ``InstrumentConvention.deflator``).
    """
    return [multiplier_at(channel, q) * float(s) for q, s in enumerate(real_shock_path)]
