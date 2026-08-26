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

    def run(var, shock, periods=QUARTERS, investment_closure=None):
        key = (var, shock, periods, investment_closure)
        if key in cache:
            return cache[key]
        ic = (var == "TCPRO") if investment_closure is None else investment_closure
        template = _build_reform_template(var, START, END, ic)
        baseline, shocked = template.clone(), template.clone()
        if var == HOUSEHOLD_COSTING_VAR:
            _apply_household_costing(shocked, shock, START, periods)
        else:
            shocked.apply_shock(var, shock, START, periods=periods)
        baseline.solve(START, END)
        shocked.solve(START, END)
        out = {}
        for col in ("GDPM", "CONS", "IF", "IBUSX", "LFSUR", "ETLFS", "RPI", "X", "M"):
            if col not in baseline.data.columns:
                continue
            delta = _panel(shocked, col) - _panel(baseline, col)
            out[col] = {
                "mean": float(delta.mean()),
                "path": [float(x) for x in delta],
                "base_mean": float(_panel(baseline, col).mean()),
            }
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
    """A tax rise takes income out of households, so GDP falls."""
    r = respond("HHDI_ADDFACTOR", TAX_RISE_M)
    assert r["GDPM"]["mean"] < 0, "a tax rise did not lower GDP"
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


def test_flat_shock_still_flips_the_gdp_sign_in_the_first_year(respond):
    """DEFECT (pinned). A constant shock produces a non-constant-sign response.

    The shock is flat at TAX_RISE_M for all eight quarters, yet the GDP path
    reads roughly -0.13, -0.48, +0.21, -0.24 bn across the first four. A
    constant input cannot produce a sign flip in a solved model; this is
    residue from two non-converged solves failing to cancel
    (obr-macroeconomic-model#38).

    Pinned so nobody reads an early-quarter number as economics, and so that
    fixing convergence trips this test. If it fails, check whether the path
    is now monotone -- and if so, delete this test and tighten
    test_tax_rise_lowers_gdp to assert the whole path.
    """
    path = respond("HHDI_ADDFACTOR", TAX_RISE_M)["GDPM"]["path"]
    first_year = path[:4]
    assert min(first_year) < 0 < max(first_year), (
        "the first-year sign flip is gone -- convergence may be fixed; see docstring"
    )


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


def test_public_investment_is_dead_and_wrong_signed(respond):
    """DEFECT (pinned). CGIPS moves investment hard in the WRONG direction.

    A rise in government investment should raise total investment; the OBR's
    published impact multiplier for public investment is 1.0, the highest of
    any instrument. Measured here: business investment moves by -292% of the
    shock -- it falls by roughly three times the amount the government spends.

    Capital spending must not be scored on this model. Pinned so the defect
    cannot quietly change size.
    """
    shock = 3000.0
    r = respond("CGIPS", shock)
    assert r["IBUSX"]["mean"] < 0, "the wrong-signed investment residue is gone"
    assert share_of_shock(r, "IBUSX", shock) < -100.0, (
        "the CGIPS investment residue changed magnitude; re-measure and update"
    )


def test_bank_rate_response_is_too_asymmetric_to_use(respond):
    """DEFECT (pinned). A rate cut and a rate rise are not mirror images.

    +100bp moves GDP by about -26m; -100bp moves it by about +2393m. The cut
    is roughly ninety times the rise. A linear-in-the-small-neighbourhood
    monetary channel cannot behave like this, and business investment falls
    under BOTH directions, so the sign is not informative either.

    There is no monetary policy experiment this model can answer. Pinned to
    stop R being offered as a lever on the strength of its GDP sign alone.
    """
    up = respond("R", 1.0)
    down = respond("R", -1.0)
    ratio = abs(down["GDPM"]["mean"]) / max(abs(up["GDPM"]["mean"]), 1e-9)
    assert ratio > 10.0, f"Bank Rate is now roughly symmetric (ratio {ratio:.1f})"
    assert up["IBUSX"]["mean"] < 0 and down["IBUSX"]["mean"] < 0, (
        "business investment no longer falls under both rate directions"
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
