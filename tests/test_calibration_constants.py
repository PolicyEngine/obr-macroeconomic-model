"""Pin the model's calibration constants against the published OBR source.

Two separate honesty gates, both fast (they parse the model file; no solve):

1. Constants the OBR PUBLISHES must be seeded at the published value. A seed
   only applies where the databank is NaN, so an invented seed silently
   suppresses the published equation for every period that is initialised but
   never solved — including the whole residual window.

2. Constants this repo SUPPLIES must stay pinned to their stated basis. Each
   of DB/DP/DV/COCU has a published OBR equation, but its inputs are absent
   from every published artefact, so the equation always evaluates to NaN and
   solve_period silently drops it. The seeds are therefore the operative
   values for the entire run, and they set the magnitude of the corporation
   tax -> investment response. DB/DP/DV are estimated from statute and the
   OBR's published gilt assumption (obr_macro/cost_of_capital.py) and must
   equal that derivation; COCU is a declared seed whose level provably
   cancels in the corporation-tax deviation. Nothing else in the suite says
   so out loud; this does.
"""

import re

import pytest

from obr_macro.data import ensure_model_code
from obr_macro.full_solver import (
    PUBLISHED_MODEL_CONSTANTS,
    UNPUBLISHED_COST_OF_CAPITAL_SEEDS,
)
from obr_macro.transpiler import IDENT, RESERVED_WORDS, parse_model_file


@pytest.fixture(scope="module")
def published():
    """{LHS: ParsedEquation} for the published October-2025 model file."""
    return {eq.lhs.strip(): eq for eq in parse_model_file(str(ensure_model_code()))}


def test_published_constants_match_the_model_file(published):
    """WB/WP/WV/RDELTA are published as bare numeric level equations. The seed
    must equal the published number, not a guess. (Before this test the seeds
    were WB=0.6, WP=0.2, WV=0.2, RDELTA=0.025 against a published
    0.31/0.54/0.14/0.022 — none of which appear anywhere in the OBR source.)"""
    for name, seeded in PUBLISHED_MODEL_CONSTANTS.items():
        eq = published.get(name)
        assert eq is not None, f"{name} is no longer a published level equation"
        assert float(eq.rhs.strip()) == pytest.approx(seeded), (
            f"{name}: seed {seeded} disagrees with the published value {eq.rhs!r}"
        )


def test_capital_type_weights_sum_to_about_one():
    """TAF = WB*TAFB + WP*TAFP + WV*TAFV is a weighted average of capital
    types, so the weights should sum to 1.

    They sum to 0.99: the OBR publishes them rounded to two decimal places
    (0.31/0.54/0.14). That 1% shortfall scales the TAF LEVEL and is absorbed by
    the investment closure's add-factor anchor, so it does not distort the
    corporation-tax RESPONSE — but it is the OBR's rounding to live with, not
    ours to renormalise. The old seeds (0.6/0.2/0.2) summed to exactly 1, which
    is presumably why they were chosen; matching the published numbers is worth
    more than a tidy sum. Bounded here so a real mis-transcription still fails.
    """
    w = sum(PUBLISHED_MODEL_CONSTANTS[k] for k in ("WB", "WP", "WV"))
    assert 0.98 <= w <= 1.02, f"capital-type weights sum to {w}, not ~1"


def test_invented_seeds_have_no_computable_published_equation(published):
    """The honest claim about DB/DP/DV/COCU: each HAS a published equation, and
    that equation can never fire here because its inputs are neither computed
    by any other published equation nor supplied by any published data source.

    If this test ever fails because an input became computable, the seed stops
    being a fiction and should be deleted in favour of the real equation — so
    the failure is the signal to remove the invention, not to widen the test.
    """
    all_lhs = set(published)
    # "Orphan" = referenced on the RHS but computed by no equation in the file.
    # The companion fact — that no orphan is in the databank either — is what
    # test_invented_cost_of_capital_seeds_survive_a_solve checks empirically,
    # by observing that the solved values are still the seeds.
    for name in UNPUBLISHED_COST_OF_CAPITAL_SEEDS:
        eq = published.get(name)
        assert eq is not None, f"{name} lost its published equation"
        inputs = set(re.findall(rf"(?<![@\w])({IDENT})\b", eq.rhs)) - RESERVED_WORDS
        orphans = sorted(i for i in inputs if i not in all_lhs)
        assert orphans, (
            f"{name}'s published equation now has every input computed "
            f"({sorted(inputs)}) — delete the invented seed and use it"
        )


def test_invented_seeds_are_plausible_but_declared():
    """Bounds so a typo (0.9515 -> 9.515) is caught, and an explicit record of
    the operative values. DB is legitimately 0.0: the OBR's own equation
    zeroes buildings allowances after 2011Q2 (Industrial Buildings Allowance
    abolished), so the lower bound is inclusive."""
    for name, v in UNPUBLISHED_COST_OF_CAPITAL_SEEDS.items():
        assert 0.0 <= v < 1.0, f"{name}={v} is outside any sane range"
    # These four numbers appear in no OBR publication. Changing one changes
    # every corporation-tax costing the model produces, so a change must be a
    # deliberate edit here and not a silent drift elsewhere. (Deliberately
    # changed 2026-08: DB/DP/DV moved from the invented 0.18/0.06/0.25 —
    # statutory writing-down RATES mislabeled and pasted in as present
    # VALUES — to the estimates derived in obr_macro/cost_of_capital.py;
    # the next test pins them to that derivation.)
    assert UNPUBLISHED_COST_OF_CAPITAL_SEEDS == {
        "DB": 0.0,
        "DP": 0.9515,
        "DV": 0.7793,
        "COCU": 0.12,
    }


def test_estimated_allowance_pvs_match_their_committed_derivation():
    """DB/DP/DV must equal obr_macro.cost_of_capital's derivation (statutory
    allowance rates + the OBR's published long-gilt assumption, evaluated
    through the OBR's own published formulas) to within the declared 4-decimal
    rounding. If this fails, either the seeds were edited without re-running
    the derivation, or the committed EFO workbook changed under them — both
    must be a visible, deliberate change here."""
    from obr_macro.cost_of_capital import derive_allowance_pvs

    derived = derive_allowance_pvs()
    for name in ("DB", "DP", "DV"):
        assert UNPUBLISHED_COST_OF_CAPITAL_SEEDS[name] == pytest.approx(
            derived[name], abs=5e-5
        ), (
            f"{name}: seed {UNPUBLISHED_COST_OF_CAPITAL_SEEDS[name]} no longer "
            f"matches its derivation {derived[name]:.6f} "
            "(python -m obr_macro.cost_of_capital)"
        )
    # COCU is deliberately NOT derived: its level cancels in the deviation
    # (dlog COC = dlog TAF) and its published equation needs a 1970Q1 rebasing
    # anchor that predates every committed series. The seed stays declared.
    assert "COCU" not in derived


@pytest.mark.slow
def test_invented_seeds_survive_a_solve_while_published_ones_are_overwritten():
    """The empirical half of the claim, on a real solved model.

    - DB/DP/DV/COCU come out of a full solve at EXACTLY their seeded values:
      the published equations raised (NaN inputs) and solve_period dropped
      them, so nothing ever overwrote the seed. That is what "the seed is the
      operative value" means, and it is why the corporation-tax response size
      is this repo's number and not the OBR's.
    - WB/WP/WV/RDELTA come out at their published values, proving the seed is
      genuinely only a seed for them. Before the fix the seeds disagreed with
      the published equations (0.6/0.2/0.2, 0.025), so any period initialised
      but not solved carried a number found in no OBR document.
    """
    import warnings

    import numpy as np

    from obr_macro import reform_analysis as ra
    from obr_macro.full_solver import FullOBRSolver

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s = FullOBRSolver(verbose=False)
        s.swap_closure("DINV", ra.GDPM_EQ)
        s._shock_active = True
        s.solve("2025Q1", "2026Q4")
    t = s.period_idx("2026Q4")

    for name, seed in UNPUBLISHED_COST_OF_CAPITAL_SEEDS.items():
        got = float(s.data.iloc[t][name])
        assert got == pytest.approx(seed), (
            f"{name} solved to {got} rather than its seed {seed} — its "
            "published equation is now live, so delete the seed and let the "
            "OBR's equation set the corporation-tax response"
        )

    for name, published_value in PUBLISHED_MODEL_CONSTANTS.items():
        got = float(s.data.iloc[t][name])
        assert np.isfinite(got) and got == pytest.approx(published_value), (
            f"{name} solved to {got}, not the published {published_value}"
        )
