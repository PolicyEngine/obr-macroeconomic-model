"""Does the model get the DIRECTION right?

test_model_invariants.py pins structural properties; test_solver.py checks
things ran. Neither asks the first question an economist asks of a policy
model: when I push this lever, does the economy move the way theory says it
should? A model can solve cleanly, reproduce its baseline to 0.15%, and still
answer "a tax rise raises GDP".

These are quick directional experiments -- one shock, one prior, one sign.
The priors are ordinary demand-side macroeconomics for a short-run quarterly
model with no supply block:

  * more government spending      -> GDP up
  * a tax rise on households      -> disposable income down -> consumption
                                     down -> GDP down
  * a corporation tax rise        -> cost of capital up -> business
                                     investment down

Two rules keep this honest.

**A sign is only meaningful above a noise floor.** The response to a shock is
the difference of two Gauss-Seidel solves that both exit on the stall break
(see PolicyEngine/obr-macroeconomic-model#38 -- no period converges to tol),
so every series carries residue. Under a +1250 CGG shock consumption "falls"
by 0.0019% of the shock; that is not a wrong sign, it is zero with a rounding
error attached. Sign assertions here require the response to clear
NOISE_FLOOR_PCT of the shock, and anything below it is asserted to be
absent rather than read as a direction.

**Known-wrong directions are pinned, not skipped.** Several channels are dead,
inert, or unusable. Those get a test that asserts the defect, so the day
someone fixes it the test fails loudly and gets updated, rather than the
defect quietly surviving a refactor. Each is marked DEFECT in its docstring.
"""

import warnings

import pytest

pytestmark = pytest.mark.slow  # every test here runs two full solves

warnings.filterwarnings("ignore")

START, END = "2026Q1", "2027Q4"
QUARTERS = 8

# A response smaller than this share of the shock is solver residue, not a
# direction. Calibrated off the measured CGG case: government consumption
# moves GDP by 100% of the shock and consumption by 0.0019% of it.
NOISE_FLOOR_PCT = 1.0

# Levels the shocks are read against (2026Q1, March 2026 EFO baseline):
#   R     = 3.67   Bank Rate, percent          -> +1.0 is +100bp
#   RX    = 84.78  sterling ERI, index         -> +5.0 is a ~6% appreciation
#   TCPRO = 0.25   corporation tax main rate   -> +0.05 is +5pp
#   CGG   = 150720 real government consumption, GBP m/quarter
TAX_RISE_M = 1615.75  # 1p on the basic rate, GBP m/quarter (PE static costing)


# Sentinel: "the test did not name a nominal-GDP closure".
_CLOSURE_DEFAULT = object()


class _Response(dict):
    """Per-variable deltas, plus how the two solves behind them ended."""

    exit_status: "list[str]" = []


def _panel(solver, col):
    return solver.data.loc[START:END, col].astype(float)


@pytest.fixture(scope="module")
def respond():
    """Run a shock and return per-variable deltas. Cached: each call solves twice."""
    from obr_macro.reform_analysis import (
        HOUSEHOLD_COSTING_VAR,
        _apply_household_costing,
        _build_reform_template,
    )

    cache = {}

    def run(
        var,
        shock,
        periods=QUARTERS,
        investment_closure=None,
        nominal_gdp_pin=_CLOSURE_DEFAULT,
    ):
        key = (var, shock, periods, investment_closure, nominal_gdp_pin)
        if key in cache:
            return cache[key]
        ic = (var == "TCPRO") if investment_closure is None else investment_closure
        # Unless a test names a closure, take the library's default, whatever
        # it is (the published closure, or the nominal-GDP pin once #54 lands).
        closure = () if nominal_gdp_pin is _CLOSURE_DEFAULT else (nominal_gdp_pin,)
        template = _build_reform_template(var, START, END, ic, *closure)
        baseline, shocked = template.clone(), template.clone()
        if var == HOUSEHOLD_COSTING_VAR:
            _apply_household_costing(shocked, shock, START, periods)
        else:
            shocked.apply_shock(var, shock, START, periods=periods)
        baseline.solve(START, END)
        shocked.solve(START, END)
        out = _Response()
        for col in (
            "GDPM",
            "CONS",
            "IF",
            "IBUSX",
            "GGIDEF",
            "LFSUR",
            "ETLFS",
            "RPI",
            "X",
            "M",
        ):
            if col not in baseline.data.columns:
                continue
            delta = _panel(shocked, col) - _panel(baseline, col)
            out[col] = {
                "mean": float(delta.mean()),
                "path": [float(x) for x in delta],
                "base_mean": float(_panel(baseline, col).mean()),
            }
        # How each quarter's Gauss-Seidel iteration ended in the two solves
        # ('tol' = converged, 'stall' = stall break): a delta is only as good
        # as the two solves it is the difference of.
        out.exit_status = sorted(
            set(baseline.last_solve_report["exit_status"].values())
            | set(shocked.last_solve_report["exit_status"].values())
        )
        cache[key] = out
        return out

    return run


def share_of_shock(response, col, shock):
    """Response in column `col` as a percentage of the shock size."""
    return 100.0 * response[col]["mean"] / abs(shock)


def clears_noise(response, col, shock):
    return abs(share_of_shock(response, col, shock)) >= NOISE_FLOOR_PCT


# ---------------------------------------------------------------------------
# Baseline sanity
# ---------------------------------------------------------------------------


def test_zero_shock_produces_exactly_zero_response(respond):
    """No shock, no movement -- in every variable, to the last float.

    If this fails nothing else in the file means anything: it would mean the
    baseline and shocked clones differ before the shock is applied, so every
    "response" below would be measuring the difference between two solvers
    rather than the effect of a policy.
    """
    r = respond("CGG", 0.0)
    for col, series in r.items():
        assert series["mean"] == 0.0, f"{col} moved under a zero shock"
        assert all(x == 0.0 for x in series["path"]), f"{col} path moved"


# ---------------------------------------------------------------------------
# Government consumption: the sign is right, and nothing else moves
# ---------------------------------------------------------------------------


def test_government_consumption_raises_gdp(respond):
    """More government spending raises GDP. The most basic prior there is."""
    r = respond("CGG", 1250.0)
    assert r["GDPM"]["mean"] > 0, "a spending increase did not raise GDP"
    assert all(x > 0 for x in r["GDPM"]["path"]), (
        "GDP response is not positive throughout"
    )


def test_government_consumption_cut_lowers_gdp(respond):
    """And a spending cut lowers it."""
    r = respond("CGG", -1250.0)
    assert r["GDPM"]["mean"] < 0, "a spending cut did not lower GDP"
    assert all(x < 0 for x in r["GDPM"]["path"])


def test_government_consumption_is_antisymmetric(respond):
    """+X and -X give equal and opposite answers.

    A demand identity is linear, so this should hold to solver noise. Where it
    does not, the model is carrying state between the two runs.
    """
    up = respond("CGG", 1250.0)["GDPM"]["mean"]
    down = respond("CGG", -1250.0)["GDPM"]["mean"]
    assert up > 0 > down
    assert abs(up + down) / abs(up) < 0.01, f"not antisymmetric: {up} vs {down}"


def test_government_consumption_multiplier_is_exactly_one(respond):
    """DEFECT (pinned). The multiplier is 1.0000 because it is an identity.

    The shock lands in the GDPM expenditure identity and no behavioural
    equation responds, so GDP moves one-for-one with the shock and stays
    flat. The OBR's published impact multiplier for day-to-day spending and
    welfare is 0.6, tapering over five years (July 2015 EFO, Box 3.2).

    This is the largest published-vs-modelled gap of any lever in the model.
    It is pinned rather than skipped: if a real second round is ever wired up
    this test fails, which is the point.
    """
    r = respond("CGG", 1250.0)
    assert share_of_shock(r, "GDPM", 1250.0) == pytest.approx(100.0, abs=0.5)
    path = r["GDPM"]["path"]
    assert max(path) - min(path) < 0.01 * abs(path[0]), "identity response is not flat"


def test_government_consumption_response_scales_linearly(respond):
    """Double the shock, double the response -- an identity cannot do otherwise."""
    one = respond("CGG", 1250.0)["GDPM"]["mean"]
    two = respond("CGG", 2500.0)["GDPM"]["mean"]
    assert two / one == pytest.approx(2.0, rel=0.01)


def test_government_consumption_moves_nothing_but_gdp(respond):
    """DEFECT (pinned). The spending second round is empty.

    Consumption moves by 0.002% of the shock and business investment by 0.09%
    -- both far under the noise floor. A spending increase in this model does
    not raise household income, employment or prices; it raises the GDP
    identity and stops. This is what "multiplier ~1 by construction" means
    mechanically.
    """
    shock = 1250.0
    r = respond("CGG", shock)
    for col in ("CONS", "IBUSX"):
        assert not clears_noise(r, col, shock), (
            f"{col} now responds to spending at "
            f"{share_of_shock(r, col, shock):.3f}% of the shock -- the second "
            "round may have been wired up; update this test"
        )


# ---------------------------------------------------------------------------
# The household bridge: the flagship path, and the one that behaves
# ---------------------------------------------------------------------------


def test_tax_rise_lowers_gdp(respond):
    """A tax rise on households lowers GDP -- in every quarter, not on average.

    This used to assert only the mean, because the first-year path flipped
    sign under a flat shock (solve residue, see #38): the pinned defect
    test_flat_shock_still_flips_the_gdp_sign_in_the_first_year recorded it.
    Completing the ONS snapshot made the path monotone, so that pin is gone
    and the assertion is tightened here, as its docstring instructed.
    """
    r = respond("HHDI_ADDFACTOR", TAX_RISE_M)
    assert r["GDPM"]["mean"] < 0, "a tax rise did not lower GDP"
    assert all(x < 0 for x in r["GDPM"]["path"]), (
        f"a flat tax rise did not lower GDP in every quarter: {r['GDPM']['path']}"
    )
    assert clears_noise(r, "GDPM", TAX_RISE_M)


def test_tax_rise_lowers_consumption(respond):
    """And it does so through consumption -- the channel the bridge claims."""
    r = respond("HHDI_ADDFACTOR", TAX_RISE_M)
    assert r["CONS"]["mean"] < 0, "a tax rise did not lower consumption"
    assert clears_noise(r, "CONS", TAX_RISE_M)


def test_tax_cut_raises_gdp(respond):
    """The giveaway direction works too."""
    r = respond("HHDI_ADDFACTOR", -TAX_RISE_M)
    assert r["GDPM"]["mean"] > 0, "a tax cut did not raise GDP"
    assert clears_noise(r, "GDPM", TAX_RISE_M)


def test_household_second_round_is_consumption_and_nothing_else(respond):
    """The GDP delta IS the consumption delta, to the pound.

    Not an approximation: every other expenditure component is exogenous or
    pinned under the demand closure, so the second round has exactly one
    channel. Worth pinning because it is the honest reading of the bridge --
    "GDP feedback" here means "the consumption equation", nothing more.
    """
    r = respond("HHDI_ADDFACTOR", TAX_RISE_M)
    assert r["GDPM"]["mean"] == pytest.approx(r["CONS"]["mean"], rel=1e-6)


def test_household_multiplier_is_in_the_published_neighbourhood(respond):
    """The one lever whose magnitude is defensible.

    The OBR's published impact multiplier for income tax and NICs is 0.3
    (July 2015 EFO, Box 3.2). Measured here: ~0.20 as a mean over eight
    quarters, building towards ~0.35-0.39 over a five-year window as the
    consumption equation's lags feed through. The band is wide because the
    solver does not converge, but it excludes both zero (no channel) and 1.0
    (the CGG-style identity), which is what this is guarding.
    """
    r = respond("HHDI_ADDFACTOR", TAX_RISE_M)
    multiplier = abs(share_of_shock(r, "GDPM", TAX_RISE_M)) / 100.0
    assert 0.10 < multiplier < 0.60, f"implied multiplier {multiplier:.3f} out of band"


def test_household_shock_signs_are_opposite_in_the_two_directions(respond):
    """A rise and a cut must not both push GDP the same way."""
    up = respond("HHDI_ADDFACTOR", TAX_RISE_M)["GDPM"]["mean"]
    down = respond("HHDI_ADDFACTOR", -TAX_RISE_M)["GDPM"]["mean"]
    assert up < 0 < down, f"tax rise {up} and cut {down} do not have opposite signs"


def test_temporary_government_consumption_shock_ends_when_it_ends(respond):
    """A four-quarter CGG rise moves GDP one-for-one for four quarters, then stops.

    CGG passes straight through the expenditure identity, so nothing should
    linger once the shock ends. Measured on 6 Nov 2026 (2025Q1 start, 25
    quarters): +1000m for q0-q3 to within 0.3m, then at most 1.0m (0.1%) up to
    q24. The bounds are 0.5% of the shock in both phases.
    """
    shock = 1250.0
    path = respond("CGG", shock, periods=4)["GDPM"]["path"]
    for q, x in enumerate(path):
        target = shock if q < 4 else 0.0
        assert abs(x - target) <= 0.005 * shock, (
            f"q{q}: GDP delta {x:.2f}, expected {target:.0f} (path {path})"
        )


def _max_abs(xs):
    return max(abs(x) for x in xs)


def test_household_response_scales_linearly_with_shock_size(respond):
    """Four times the tax rise gives about four times the GDP response.

    dlog(CONS) is log-linear, so the response is not exactly linear, and every
    path carries stall residue (#38). Measured on 6 Nov 2026 (2025Q1 start,
    12 shocked quarters): the 4x path deviates from 4 times the 1x path by at
    most 10.3% of its peak. The bound is 15%. A break here means the household
    channel has picked up a threshold or a regime switch.
    """
    one = respond("HHDI_ADDFACTOR", TAX_RISE_M)["GDPM"]["path"]
    four = respond("HHDI_ADDFACTOR", 4 * TAX_RISE_M)["GDPM"]["path"]
    gap = _max_abs([f - 4 * o for f, o in zip(four, one)])
    assert gap <= 0.15 * _max_abs([4 * o for o in one]), (
        f"4x response is not ~4x the 1x response: {four} vs 4 x {one}"
    )


def test_household_response_is_antisymmetric_in_magnitude(respond):
    """A cut moves GDP by about as much as an equal rise, the other way.

    The sign test above checks the signs only. Here the cumulative effects
    must match in size. Measured on 6 Nov 2026 in this file's 8-quarter
    window: rise -2,458m, cut +2,287m, a gap of 7.0% of the rise. The bound is
    15%. Per quarter, stall residue (#38) is larger: one quarter of the rise
    path dips out of line (q6, -364m between -392m and -455m), so the
    quarter-by-quarter gap reaches 21% of the peak. That is why the test uses
    the sum and not the path. (Over a 12-quarter window from 2025Q1 the
    per-quarter gap was 10.5%.)
    """
    up = sum(respond("HHDI_ADDFACTOR", TAX_RISE_M)["GDPM"]["path"])
    down = sum(respond("HHDI_ADDFACTOR", -TAX_RISE_M)["GDPM"]["path"])
    assert abs(up + down) <= 0.15 * abs(up), (
        f"cumulative rise {up:.0f} and cut {down:.0f} are not mirror images"
    )


def test_one_quarter_household_shock_decays_without_changing_sign(respond):
    """A one-quarter tax rise: GDP dips on impact, then recovers slowly.

    The fall never turns into a boom, and it shrinks quarter on quarter. It
    does not return to zero within the window: lower income lowers household
    wealth, and the wealth term keeps consumption lower. Measured on 6 Nov 2026
    (2025Q1 start): -148m on impact, -50m by q3, -39m by q7 and -28m by q24, so
    the decay is real but very slow. The bounds are loose on purpose (below
    half of impact by q3, magnitude never rising by more than 5% of impact).
    """
    path = respond("HHDI_ADDFACTOR", TAX_RISE_M, periods=1)["GDPM"]["path"]
    impact = path[0]
    assert impact < 0, f"a one-quarter tax rise did not lower GDP on impact: {path}"
    assert all(x < 0 for x in path), f"the dip turned into a rise: {path}"
    assert abs(path[3]) < 0.5 * abs(impact), f"no decay by q3: {path}"
    for a, b in zip(path, path[1:]):
        assert abs(b) <= abs(a) + 0.05 * abs(impact), f"the response grew back: {path}"


# ---------------------------------------------------------------------------
# Corporation tax: signs right, through a real channel
# ---------------------------------------------------------------------------


def test_corporation_tax_rise_lowers_business_investment(respond):
    """Higher corporation tax raises the cost of capital, so investment falls.

    The only lever in the model with a live behavioural chain
    (TCPRO -> TAF -> COC -> KSTAR -> IBUSX), and it gets the sign right.
    """
    r = respond("TCPRO", 0.05)
    assert r["IBUSX"]["mean"] < 0, "a corporation tax rise did not lower investment"
    assert r["GDPM"]["mean"] < 0, "and it did not lower GDP"


def test_corporation_tax_cut_raises_business_investment(respond):
    """And a cut raises it."""
    r = respond("TCPRO", -0.05)
    assert r["IBUSX"]["mean"] > 0, "a corporation tax cut did not raise investment"
    assert r["GDPM"]["mean"] > 0


def test_corporation_tax_moves_investment_and_gdp_together(respond):
    """Under the investment closure, GDP moves because investment does.

    IF (total fixed investment) tracks IBUSX one-for-one, and the GDP delta
    is that investment delta -- the same single-channel structure as the
    household route, one component along.
    """
    r = respond("TCPRO", 0.05)
    assert r["IBUSX"]["mean"] == pytest.approx(r["IF"]["mean"], rel=1e-6)
    assert r["GDPM"]["mean"] == pytest.approx(r["IF"]["mean"], rel=0.02)


# ---------------------------------------------------------------------------
# Blocks that never respond to anything
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "col,block",
    [
        ("LFSUR", "unemployment rate"),
        ("ETLFS", "employment"),
        ("RPI", "retail prices"),
        ("X", "exports"),
        ("M", "imports"),
    ],
)
def test_block_is_inert_under_every_lever(respond, col, block):
    """DEFECT (pinned). Labour, prices and trade do not respond to policy.

    Measured across every lever in this file -- spending, household taxes,
    corporation tax, Bank Rate, the exchange rate -- these move by EXACTLY
    zero, not approximately zero. There is no Okun channel (a demand shock
    does not change unemployment), no Phillips channel (it does not change
    prices) and no trade channel (a 6% sterling appreciation does not change
    exports or imports).

    This is the boundary of what the model can answer, and it is much
    narrower than "a 372-equation macroeconometric model" suggests. Pinned
    per block so that wiring any one of them up fails exactly one test.
    """
    for var, shock in (
        ("CGG", 1250.0),
        ("HHDI_ADDFACTOR", TAX_RISE_M),
        ("TCPRO", 0.05),
        ("R", 1.0),
        ("RX", 5.0),
    ):
        r = respond(var, shock)
        if col not in r:
            pytest.skip(f"{col} not in the solved panel")
        assert r[col]["mean"] == 0.0, (
            f"{block} now responds to {var} -- the {block} block may be live; "
            "update this test"
        )


# ---------------------------------------------------------------------------
# Levers that are not usable
# ---------------------------------------------------------------------------


def test_public_investment_does_not_transmit(respond):
    """DEFECT (pinned). CGIPS produces an accounting mirror, not a public
    investment effect.

    A rise in government investment should raise total investment -- the OBR's
    published impact multiplier for public investment is 1.0, the highest of
    any instrument. This model cannot deliver that, in two separate ways.

    First, total fixed investment (IF) moves EXACTLY zero, because IF has no
    live equation in the published listing (both IF identities, l.86 and
    l.112, are commented out). The CGIPS chain never reaches the GDP identity
    at all.

    Second, business investment (IBUSX) does move, but not as a channel. With
    IF exogenous, IBUS is the OBR's residual identity (l.84)
    IBUS = IF - GGI - PCIH - PCLEB - IH - IPRL, so a rise in real government
    investment GGI = 100*GGIPS/GGIDEF (l.96) is booked one-for-one as a FALL
    in business investment: IBUSX/CGIPS = -100/GGIDEF.

    The mirror is measured under the nominal-GDP pin (the OBR's commented-out
    l.690), because that is the closure in which the solve converges. Means
    over eight quarters from 2026Q1, every quarter of both solves exiting on
    the tolerance, GGIDEF 108.2 (11 Nov 2026, the same on the commit before
    and after the receipts identities went live, #56):

        shock  +1500   ->  IBUSX  -1387  (-92.44% of shock)
        shock  +3000   ->  IBUSX  -2773  (-92.44% of shock)
        shock  +6000   ->  IBUSX  -5547  (-92.44% of shock)

    Why not the published closure (l.688), where this test used to be taken.
    There nominal GDP and PIF are one identity written twice (#42), no quarter
    converges (all exit on the stall break), and GGIDEF follows PIF (l.100).
    Most shock sizes give the mirror (-98%, GGIDEF about 101.5), but one size
    lands on a different stalled branch: nominal GDP jumps by about +5.2bn in
    the first quarter, GGIDEF rises by 3.6 to 8 index points and the "mirror"
    reads anything. WHICH size does so is not a property of the model. It
    moved when the receipts identities went live, although they change BPAPS
    by under 1m here:

        published closure      +1500    +3000    +6000
        before #56 (95e66f1)   -0.979   -0.278   -0.990
        after  #56 (5314229)   -0.978   -0.980   -0.640

    So a -0.64 at +6000 is solver residue of the undetermined pair, not a
    consequence of live receipts, and the bound below was not moved for it.
    (test_government_investment_channel_is_dead_and_says_so pins the residue
    that the default run_reform call returns.)

    Capital spending must not be scored on this model.
    """
    sizes = (1500.0, 3000.0, 6000.0)
    runs = {s: respond("CGIPS", s, nominal_gdp_pin=True) for s in sizes}

    # The measurement is only meaningful on converged solves.
    for shock, r in runs.items():
        assert r.exit_status == ["tol"], (
            f"CGIPS {shock:+.0f} under the pin did not converge in every "
            f"quarter: {r.exit_status}"
        )

    # The dead leg: total fixed investment never moves, at any shock size.
    assert all(r["IF"]["mean"] == 0.0 for r in runs.values()), (
        "IF now responds to CGIPS -- an IF equation may have been added"
    )

    # The mirror leg: business investment falls by ~the shock, i.e. it is the
    # residual identity absorbing real GGI, not an investment response.
    ratios = {s: r["IBUSX"]["mean"] / s for s, r in runs.items()}
    for shock, ratio in ratios.items():
        assert -1.1 < ratio < -0.85, (
            f"IBUSX/CGIPS = {ratio:.2f} at a {shock:+.0f} shock -- no longer "
            "the one-for-one residual-identity mirror; re-measure and update"
        )
    # An identity is proportional: the ratio must not depend on the size
    # (measured identical to four decimals). This is what the stalled
    # published-closure solve fails.
    assert max(ratios.values()) - min(ratios.values()) < 0.005, (
        f"IBUSX/CGIPS depends on the shock size: {ratios}"
    )
    # And it is the deflator arithmetic of l.96, -100/GGIDEF, with GGIDEF
    # itself unmoved by the shock.
    for shock, r in runs.items():
        ggidef = r["GGIDEF"]["base_mean"]
        assert ratios[shock] == pytest.approx(-100.0 / ggidef, abs=0.005)
        assert abs(r["GGIDEF"]["mean"]) < 1e-3, (
            f"GGIDEF moved by {r['GGIDEF']['mean']:.4f} under a CGIPS shock"
        )


def test_bank_rate_response_is_consumption_only(respond):
    """DEFECT (pinned, narrowed 2026-10). Bank Rate moves GDP the right way,
    but only through consumption.

    Until 2026-10 this test pinned "a rate RISE raises GDP" (+387m) and
    "business investment falls under BOTH directions". Both were artefacts of
    scoring around the free-running baseline. Around the anchored baseline,
    over eight quarters from 2026Q1:

        +100bp  ->  GDP  -358m,  IBUSX  -360m
        -100bp  ->  GDP  +222m,  IBUSX +1464m

    The GDP sign is now right in both directions, and all of it is
    consumption (the d(R) and real-rate terms in dlog(CONS)): IF has no
    equation, so GDP == CONS. The IBUSX numbers are not an investment
    channel: under the demand closure IBUS is the residual identity
    IBUS = IF - GGI - ..., moved by the government-investment deflator. So
    this is a consumption-only rate channel, asymmetric and with no
    investment or exchange-rate leg -- not a monetary-policy model.
    """
    up = respond("R", 1.0)
    down = respond("R", -1.0)
    assert up["GDPM"]["mean"] < 0 < down["GDPM"]["mean"], (
        "Bank Rate GDP response has the wrong sign again"
    )
    for r in (up, down):
        assert r["IF"]["mean"] == 0.0, "IF responds to Bank Rate -- re-derive"
        assert r["GDPM"]["mean"] == pytest.approx(r["CONS"]["mean"], abs=1e-6), (
            "GDP now moves through something other than consumption -- re-derive"
        )


def test_exchange_rate_has_no_trade_channel(respond):
    """DEFECT (pinned). A sterling appreciation does not move net trade.

    RX is the sterling effective exchange rate index (84.8 in 2026Q1), so
    +5 is a ~6% appreciation. That should cut exports and raise imports.
    Both move by exactly zero, so whatever GDP does under RX is not coming
    from trade.
    """
    r = respond("RX", 5.0)
    assert r["X"]["mean"] == 0.0 and r["M"]["mean"] == 0.0, (
        "the trade block responds to the exchange rate now; update this test"
    )
