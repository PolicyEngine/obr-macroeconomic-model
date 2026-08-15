"""Analyse policy reforms using OBR model and generate visualisations."""

import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from collections.abc import Iterable
from pathlib import Path

from obr_macro.full_solver import FullOBRSolver, is_scalar_shock, shock_path
from obr_macro.published_conventions import (
    INSTRUMENT_CONVENTIONS,
    PUBLISHED_MULTIPLIERS,
    TAPER_QUARTERS,
    target_gdp_delta,
)
from obr_macro.transpiler import ParsedEquation, EViewsTranspiler


# Standard equations for closure swaps
GDPM_EQ = ParsedEquation(
    lhs="GDPM",
    rhs="CGG + CONS + IF + DINV + VAL + X - M + SDE",
    original="GDPM = CGG + CONS + IF + DINV + VAL + X - M + SDE",
    equation_type="identity",
    python_expr="v['CGG'] + v['CONS'] + v['IF'] + v['DINV'] + v['VAL'] + v['X'] - v['M'] + v['SDE']",
)

IBUS_EQ = ParsedEquation(
    lhs="IBUS",
    rhs="IBUSX + adjustment",
    original="IBUS = IBUSX + 17394 * @recode(...)",
    equation_type="identity",
    python_expr="v['IBUSX'] + 17394 * _recode(t, '2005Q2', '=', 1, 0)",
)

IF_EQ = ParsedEquation(
    lhs="IF",
    rhs="IBUS + GGI + PCIH + PCLEB + IH + IPRL",
    original="IF = IBUS + GGI + PCIH + PCLEB + IH + IPRL",
    equation_type="identity",
    python_expr="v['IBUS'] + v['GGI'] + v['PCIH'] + v['PCLEB'] + v['IH'] + v['IPRL']",
)

# Business-investment error-correction equation, dlog(IBUSX).
# The OBR publishes this equation commented out and missing its closing
# parenthesis (identical in the March and October 2025 model code). It is
# reconstructed here (the single missing ')' restored) and transpiled with the
# real transpiler so it stays consistent with the parser. Under the investment
# closure it replaces the IBUSX residual identity, activating the
# cost-of-capital channel TCPRO -> TAF -> COC -> KSTAR -> KGAP -> IBUSX; without
# it, business investment is a pure residual and corporation-tax shocks have no
# effect on investment.
_IBUSX_SRC = (
    "dlog(IBUSX) = 0.1992007 * dlog(IBUSX(-3)) + 1.00573 * dlog(MSGVA(-1)) "
    "- 0.0012369*CBIUD - 0.0418036*(log(IBUSX(-1)) - log(KMSXH(-2) * 1000) "
    '+ KGAP(-2) + 0.0544706 * @recode(@date = @dateval("1998:01") , 1 , 0) '
    '+ 0.0597525 * @recode(@date = @dateval("2005:02") , 1 , 0) - 0.0884031)'
)
IBUSX_EQ = EViewsTranspiler().parse_equation(_IBUSX_SRC)

# Virtual reform instrument used by microsimulation consumers. It is not an
# OBR databank variable: run_reform translates it into a held add-factor on the
# household disposable-income identity.
HOUSEHOLD_COSTING_VAR = "HHDI_ADDFACTOR"


# Instruments whose post-shock LEVEL must stay inside a domain for the
# equations that consume them to mean anything. Checked before any solve.
#
# TCPRO: the tax-adjustment factor is TAF = sum_i W_i * (1 - TCPRO*D_i) /
# (1 - TCPRO). At TCPRO = 1 it is a pole; above 1 the denominator turns
# negative, TAF and hence COC = TAF*COCU turn negative, and log(COC) in KSTAR
# is undefined — solve_period then silently drops the KSTAR equation and the
# run completes with a WRONG-SIGNED investment response. Measured: shocking
# TCPRO from 0.25 to 1.05 returned delta_IF = +GBP 3.2bn, i.e. "a 105%
# corporation tax raises business investment", finite and unflagged. Below 0
# there is no such arithmetic failure, but a negative corporation-tax rate is
# not a policy this model was estimated on. Both are refused.
_INSTRUMENT_DOMAINS = {
    "TCPRO": (0.0, 1.0, "corporation tax rate"),
}


def _check_instrument_domain(template, var, values, start: str) -> None:
    """Refuse a shock that drives a rate instrument outside its usable domain."""
    domain = _INSTRUMENT_DOMAINS.get(var)
    if domain is None:
        return
    lo, hi, label = domain
    start_t = template.period_idx(start)
    for offset, s in enumerate(values):
        t = start_t + offset
        if t >= len(template.data):
            break
        level = template._get(var, t) + s
        if not (lo <= level < hi):
            raise ValueError(
                f"{var} ({label}) would become {level:.4g} at "
                f"{template.index[t]}, outside its usable domain "
                f"[{lo}, {hi}). The cost-of-capital block has a pole at "
                f"{var}=1 and sign-flips beyond it, so the model would return "
                "a finite but wrong-signed result rather than fail."
            )


# Instruments with NO transmission path to GDP under the demand closure.
# `IF` has no live equation in the published model (both IF identities are
# commented out), so it stays at its EFO value and the government-investment
# chain CGIPS -> GGIPS -> GGI -> IF never reaches the GDP identity. Measured on
# a sustained +GBP 3bn/quarter CGIPS shock over 12 quarters: delta_IF is
# EXACTLY 0.0 in every quarter and delta_GDP is +GBP 0.03bn on impact then
# NEGATIVE (to -GBP 0.14bn) — i.e. a GBP 12bn/year public investment programme
# reads as a small GDP *contraction*. That residue is deflator noise, not a
# crowding-out result, and it is the wrong sign to report either way.
# tests/test_stress.py already excludes CGIPS from its instrument list for this
# reason; the warning makes the same fact visible to anyone calling
# run_reform directly (including run_five_reforms' "GBP 10bn Gov Investment").
_DEAD_UNDER_DEMAND_CLOSURE = {
    "CGIPS": "central government investment (nominal)",
    "LAIPS": "local authority investment (nominal)",
    "GGIPS": "general government investment (nominal)",
}


# THE INVESTMENT CLOSURE'S SHOCK DEVIATION NOW HAS A STEADY STATE.
#
# Until 2026-08 it did not: the deviation compounded at 1.21-1.27x per quarter
# for all 25 quarters measured (|delta_IF| for a sustained +5pp TCPRO rise:
# GBP 1.0bn at q8, 2.9bn at q12, 43.4bn at q25) and run_reform warned on every
# run. The cause was NOT the missing MSGVA feedback, as this file previously
# claimed: with MSGVA frozen, the published equation's own error-correction
# term -0.0418*(log(IBUSX(-1)) - log(KSTAR(-2))) (KMSXH cancels against KGAP)
# already gives the log-deviation a stable root converging to
# dlog(KSTAR) = -0.4*dlog(TAF). What destroyed it was the anchoring
# convention: LEVEL add-factors on a LOG-difference equation multiply the
# deviation by rho = 1 - af/level each quarter, and with the equation
# over-predicting by 20-27% a quarter (af/level in [-0.27, -0.18]), rho was
# 1.18-1.28 — the measured compounding, reproduced to two decimal places.
# Anchoring in log space (_stabilise_investment_closure) removed the
# amplification; nothing else changed.
#
# Measured after the fix (sustained +5pp TCPRO, 2025Q1 start, current
# DB/DP/DV estimates): |delta_IF| GBP 0.24bn at q8, 0.38bn at q12, 0.68bn at
# q25, converging monotonically from below towards the analytic plateau
# IBUSX*(1-exp(dlog KSTAR)) ~ GBP 0.95bn/q with quarter-on-quarter growth
# falling 1.90 -> 1.023 by q25 and never rising. The error-correction root is
# slow (~0.958/quarter, half-life ~17 quarters), so the 12-quarter figure
# every published result uses is a partial response — ~40% of the plateau —
# and the attrs below say so. That is a statement about horizon choice, not
# about stability, hence no warning for it; the divergence warning is kept
# and fires only if the deviation ever overshoots its own steady-state target
# while still growing (the pre-fix signature).
_INVESTMENT_CLOSURE_CREDIBLE_QUARTERS = 12
# Quarter-on-quarter growth of |delta_IF| above which the tail has not yet
# settled. A converging error-correction response approaches 1.0 from above;
# combined with target overshoot (which a stable path cannot produce under a
# sustained shock) growth above this threshold marks genuine divergence.
_INVESTMENT_CLOSURE_COMPOUNDING_QOQ = 1.05
# |dlog(IBUSX)| may exceed |dlog(KSTAR)| transiently after a shock is
# switched off (the target collapses to ~0 faster than the slow root decays),
# so overshoot alone is not divergence; overshoot by more than this factor
# WHILE the deviation is still compounding is.
_INVESTMENT_CLOSURE_OVERSHOOT_TOL = 1.10


def _apply_household_costing(solver, shock, start: str, periods: int) -> None:
    """Apply an externally costed household reform to disposable income.

    ``shock`` is the static budgetary impact in £m per quarter using the fiscal
    convention: positive means revenue raised. Revenue raised reduces household
    disposable income, hence the minus sign on the HHDI level add-factor.
    """
    values = shock_path(shock, periods)
    start_t = solver.period_idx(start)
    if "HHDI" not in solver.eq_for_var:
        raise RuntimeError(
            "HHDI_ADDFACTOR requires the endogenous HHDI identity, but HHDI "
            "has no live equation in this model closure"
        )
    for offset, costing in enumerate(values):
        t = start_t + offset
        if t < len(solver.data):
            key = ("HHDI", t)
            solver.add_factors[key] = solver.add_factors.get(key, 0.0) - costing
    solver._shock_active = True


def _ensure_ibusx_inputs(solver):
    """Ensure inputs to the reconstructed IBUSX equation exist on the solver.

    CBIUD (a business-investment uncertainty differential) is referenced only by
    the reconstructed dlog(IBUSX) equation, so it is never seen by the solver's
    missing-variable initialisation and is absent from the EFO data. Default it
    to zero: it is neutral and cancels between the baseline and shocked runs, so
    it does not distort the corporation-tax differential.
    """
    if "CBIUD" not in solver.data.columns:
        # (May emit a benign pandas fragmentation PerformanceWarning, as
        # elsewhere in the solver; harmless for a single added column.)
        solver.data["CBIUD"] = 0.0


# Gauss-Seidel iteration cap for investment-closure solves (see
# _stabilise_investment_closure). 25 fully settles the corporation-tax ->
# investment response while cutting the irrelevant slow-converging tail.
_IC_MAX_ITER = 25


def _stabilise_investment_closure(baseline, start: str, end: str):
    """Tame the investment-closure instability (Option 1 fix).

    The reconstructed dlog(IBUSX) equation is faithful to the OBR source, but as
    an active closure on this data-starved model it sits inside an explosive
    accelerator loop and diverges even with no shock:

        IBUSX -> IF -> GDPM -> MSGVA (= GDPM - BPA - GGVA) -> back into dlog(IBUSX)
        via both 1.00573*dlog(MSGVA(-1)) and the KSTAR target (KSTAR ~ MSGVA).

    Here the market-sector supply block that would discipline MSGVA is not
    populated (see docs/stage1c_data_scope.md), so MSGVA is a ~1:1 mirror of
    investment-driven demand and the closed loop's eigenvalue exceeds 1 (the raw
    baseline runs IBUSX ~94,000 -> ~7,000,000 over 12 quarters). Two coupled
    defects: (a) that spurious accelerator feedback, and (b) a mis-scaled KSTAR
    level (desired capital ~=GBP 12.5tn vs a capital stock ~=GBP 2.5tn, because
    MSGVA/COC/deflators are off the OBR's calibrated scale), which puts the
    error-correction target ~=GBP 13tn instead of the published ~GBP 77.5bn.

    Fix (confined to the investment closure):
      1. Break the accelerator by decoupling MSGVA from the IBUSX feedback: hold
         it at a reference path taken from a tracking solve in which IBUSX is
         pinned to its OBR published values (so demand, and hence MSGVA, is not
         driven by the diverging investment). With MSGVA frozen the equation is
         dynamically stable, and the corporation-tax channel survives intact
         because KSTAR still responds to COC (TCPRO -> TAF -> COC -> KSTAR).
      2. Re-centre the level by anchoring dlog(IBUSX) to the OBR published path
         with held add-factors in LOG space (the EViews convention for a
         log-difference equation — see the block below for why the level
         convention used before 2026-08 destroyed the deviation's steady
         state). Applied identically in the baseline and every shocked clone,
         they cancel in the delta and only fix the shared level.

    Mutates ``baseline`` in place (freezes MSGVA, PIF and PIRHH; sets
    ``log_add_factors``). The
    reference MSGVA and add-factors are held constant across the base/shock pair,
    so the reported delta isolates the cost-of-capital response. This is a
    stop-gap for the missing supply-side calibration, not a substitute for it:
    when the market-sector block is populated, the frozen reference should be
    replaced by the genuine endogenous MSGVA.
    """
    # Cap Gauss-Seidel iterations for every solve off this baseline (the
    # tracking pass and, via clone(), the baseline and shocked runs). With the
    # investment closure the only variable still moving after ~20 iterations is
    # NAOTAROW (rest-of-world national accounts): it converges slowly but is off
    # the corporation-tax -> investment chain, so grinding it to tol spends ~50
    # extra iterations/period without moving the investment response (which is
    # settled to within ~1% by iteration 25). This tail is the dominant cost of
    # the closure; capping it cuts each solve from ~6.5s to ~2.7s locally.
    baseline.max_iter = _IC_MAX_ITER

    t0, t1 = baseline.period_idx(start), baseline.period_idx(end)
    actual_ibusx = baseline.baseline["IBUSX"].copy()  # OBR published path

    # --- Tracking pass: pin IBUSX to the published path, solve the rest. ---
    trk = baseline.clone()
    trk.make_exogenous("IBUSX")
    for t in range(t0, t1 + 1):
        trk._set("IBUSX", t, actual_ibusx.iloc[t])
    trk._shock_active = True
    trk.solve(start, end)
    msgva_ref = trk.data["MSGVA"].copy()

    # Held add-factors, in LOG space: actual dlog minus predicted dlog, the
    # EViews convention for add-factoring a log-difference equation (applied
    # in solve_period as new_val * exp(af)). This choice, not a nicety, is
    # what gives the closure a steady state in deviation space. Until 2026-08
    # the anchor was a LEVEL add-factor (actual - predicted level); because
    # the reconstructed equation persistently over-predicts IBUSX by ~20-25%
    # a quarter on this data-starved model, those add-factors were ~ -0.2 to
    # -0.27 of the level, and a level add-factor af turns the base-vs-shock
    # deviation recursion into exp(x_t) = rho*exp(x_{t-1}+delta) + (1-rho)
    # with rho = 1 - af/level ~ 1.18-1.28 — measured deviation compounding of
    # 1.21-1.27x per quarter, which exactly matched the divergence this
    # closure used to warn about. In log space the recursion is
    # x_t = x_{t-1} + delta_t and the published equation's own -0.0418
    # error-correction term (log(IBUSX(-1)) - log(KSTAR(-2)), once KGAP's
    # KMSXH cancels) gives the deviation a stable root: x converges to
    # dlog(KSTAR) = -0.4*dlog(TAF), a genuine steady state.
    log_add_factors = {}
    for t in range(t0, t1 + 1):
        pred_dlog = eval(trk._compiled(IBUSX_EQ.python_expr), trk._build_context(t))
        prev = actual_ibusx.iloc[t - 1]
        actual = actual_ibusx.iloc[t]
        if np.isfinite(pred_dlog) and prev > 0 and actual > 0:
            log_add_factors[("IBUSX", t)] = np.log(actual) - np.log(prev) - pred_dlog

    # --- Apply to the baseline: freeze the leak paths, hold the IBUSX
    # add-factors. MSGVA breaks the spurious accelerator (above). PIF and
    # PIRHH close two demand-side leaks exposed by the March 2026 re-anchor
    # (invariant test_corp_tax_rise_lowers_investment caught them): PIF's
    # shock response compounds through GGIDEF/GGIDEF(-1) = PIF/PIF(-1), so a
    # sub-percent investment-deflator dip snowballs into a double-digit
    # GGIDEF collapse that inflates real GGI (= 100*GGIPS/GGIDEF, nominal
    # GGIPS exogenous) by ~GBP 3.5bn/q; and PIRHH (household property
    # income) carries an uncalibrated ~receipts-sized response straight
    # into HHDI -> CONS. Neither is part of the cost-of-capital channel
    # this closure exists to expose; both are held at the tracking-pass
    # reference, identically in baseline and shocked clones, so they cancel
    # in the delta. Same stop-gap status as the MSGVA freeze: replace when
    # the market-sector supply and price blocks are calibrated
    # (docs/stage1c_data_scope.md).
    freeze_refs = {
        "MSGVA": msgva_ref,
        "PIF": trk.data["PIF"].copy(),
        "PIRHH": trk.data["PIRHH"].copy(),
    }
    for var, ref in freeze_refs.items():
        window = ref.iloc[t0 : t1 + 1]
        if not np.isfinite(window).all():
            raise RuntimeError(
                f"tracking pass produced non-finite {var} over the solve "
                "window; refusing to freeze the closure to a broken "
                "reference (inspect the EFO ingestion)"
            )
        baseline.make_exogenous(var)
        for t in range(t0, t1 + 1):
            baseline._set(var, t, ref.iloc[t])
    # Merge rather than assign: FullOBRSolver's own structural anchors (the
    # OSHH level add-factor) live in the additive dict and must survive.
    baseline.log_add_factors.update(log_add_factors)


# Cache of stabilised, unsolved reform templates keyed by structure
# (var, start, end, investment_closure) — NOT the shock size. Building the
# solver (~15s) and, for the investment closure, running the tracking pass
# (~3s) depend only on that structure, so they are done once and every scenario
# clones the pristine template. The template is never solved or shocked in
# place, so clones stay deterministic and independent.
_REFORM_TEMPLATE_CACHE = {}


def _build_reform_template(var, start, end, investment_closure):
    """Build (and cache) the stabilised, unsolved baseline template.

    The baseline and shocked runs must be structurally identical (same closures,
    same exogenous instrument, same starting data, same stabilisation) so the
    delta isolates the shock — hence a single shared template that both clone.
    """
    key = (var, start, end, investment_closure)
    cached = _REFORM_TEMPLATE_CACHE.get(key)
    if cached is not None:
        return cached

    baseline = FullOBRSolver(verbose=False)
    baseline.swap_closure("DINV", GDPM_EQ)
    if investment_closure:
        _ensure_ibusx_inputs(baseline)
        baseline.swap_closure("IBUSX", IBUSX_EQ)
        baseline.swap_closure("IBUS", IBUS_EQ)
        # IF has no live equation in the published model (both IF identities
        # are commented out), so IF_EQ is a pure addition. Guard against a
        # second live IF equation ever coexisting: remove any existing one
        # before adding (swap on "IF" is a no-op removal when none exists).
        assert "IF" not in baseline.eq_for_var, (
            "Model already has a live IF equation; adding IF_EQ would create "
            "two competing IF equations."
        )
        baseline.swap_closure("IF", IF_EQ)
    if var != HOUSEHOLD_COSTING_VAR:
        baseline.make_exogenous(var)
    if investment_closure:
        # Stabilise the reconstructed dlog(IBUSX) closure (breaks the spurious
        # MSGVA accelerator and anchors the level to the OBR path) before the
        # baseline/shock split, so both runs share the identical stabilisation.
        _stabilise_investment_closure(baseline, start, end)
    baseline._shock_active = True

    _REFORM_TEMPLATE_CACHE[key] = baseline
    return baseline


def _label_investment_closure_divergence(
    out: pd.DataFrame, dlog_ibusx_end: float, dlog_kstar_end: float
) -> None:
    """Label an investment-closure result with its convergence diagnostics.

    Since the 2026-08 log-anchoring fix the deviation converges: under a
    sustained shock |dlog(IBUSX)| approaches its steady-state target
    |dlog(KSTAR)| from below with quarter-on-quarter growth falling towards
    1.0 (see the measured path at ``_INVESTMENT_CLOSURE_CREDIBLE_QUARTERS``).
    The attrs report where on that path the horizon-end figure sits, because
    the error-correction root is slow (~0.958/quarter): a 12-quarter figure is
    ~40% of the plateau, which a caller quoting it should know — that is
    horizon information, not an instability, so it is recorded without a
    warning.

    The divergence warning is retained as a tripwire and fires only on the
    pre-fix signature — the deviation OVERSHOOTING its own steady-state target
    while still compounding — which a stable error-correction path cannot
    produce under a sustained shock. If it fires again, the deviation dynamics
    have genuinely broken (e.g. the anchoring convention regressed); do not
    quote magnitudes from such a run.
    """
    d = out["delta_if_m"].abs().to_numpy(dtype=float)
    tail_growth = None
    if len(d) >= 2 and np.isfinite(d[-1]) and np.isfinite(d[-2]) and d[-2] > 1e-9:
        tail_growth = float(d[-1] / d[-2])
    out.attrs["investment_closure_quarters"] = len(out)
    out.attrs["investment_closure_reference_quarters"] = (
        _INVESTMENT_CLOSURE_CREDIBLE_QUARTERS
    )
    out.attrs["investment_closure_tail_qoq_growth"] = tail_growth
    # Steady-state target of the deviation (dlog KSTAR = -0.4*dlog TAF under a
    # sustained shock) and the fraction of it attained at the horizon end.
    out.attrs["investment_closure_deviation_dlog"] = dlog_ibusx_end
    out.attrs["investment_closure_deviation_target_dlog"] = dlog_kstar_end
    plateau_fraction = None
    if np.isfinite(dlog_ibusx_end) and abs(dlog_kstar_end) > 1e-12:
        plateau_fraction = float(dlog_ibusx_end / dlog_kstar_end)
    out.attrs["investment_closure_plateau_fraction"] = plateau_fraction

    overshoot = (
        plateau_fraction is not None
        and plateau_fraction > _INVESTMENT_CLOSURE_OVERSHOOT_TOL
    )
    compounding = (
        tail_growth is not None and tail_growth > _INVESTMENT_CLOSURE_COMPOUNDING_QOQ
    )
    diverging = overshoot and compounding
    out.attrs["investment_closure_diverging"] = diverging
    if diverging:
        msg = (
            "Investment-closure result does not converge: |dlog(IBUSX)| is "
            f"{plateau_fraction:.2f}x its steady-state target |dlog(KSTAR)| "
            f"and still growing {tail_growth:.2f}x per quarter at the horizon "
            "end. A stable error-correction deviation cannot overshoot its "
            "own target under a sustained shock, so the deviation dynamics "
            "are broken (this is the signature of the pre-2026-08 level "
            "add-factor amplification). Read the sign and the direction, not "
            "the magnitude, and do not extrapolate the path."
        )
        out.attrs["investment_closure_warning"] = msg
        warnings.warn(msg, stacklevel=3)


def _impose_published_convention(
    template,
    baseline_data,
    raw_shocked_data,
    convention,
    var,
    shock,
    start: str,
    end: str,
    periods: int,
    t_start: int,
    t_end: int,
):
    """Impose the OBR's published multiplier convention as a GDPM add-factor path.

    Returns ``(shocked_data, detail)`` where ``shocked_data`` is the solved
    data of a third run — the shock plus add-factors on the GDPM identity that
    move the reported GDP delta onto the convention's path — and ``detail`` is
    the metadata run_reform records in ``df.attrs``.

    WHAT THIS PROVES AND CANNOT PROVE. The resulting delta_gdp path proves
    only that ``published multiplier x shock`` was imposed successfully; it is
    the OBR's judgement re-applied, not a model response, and it carries no
    information about this model's dynamics (the raw solve already measured
    those: 1.0-flat identity passthrough for CGG, exactly zero for
    CGIPS/LAIPS/GGIPS).

    Mechanics, and why add-factors rather than post-hoc arithmetic: add-factors
    are the OBR's own device for imposing judgement on a model solve, and this
    repo already uses them (solver.add_factors). Everywhere else they are
    applied to the baseline AND every shocked clone alike so they cancel in the
    delta; here they are applied to the shocked run ONLY, deliberately, so they
    do NOT cancel — the non-cancelling difference IS the convention. The
    add-factor for each quarter is (convention target - measured raw delta), so
    the imposed run lands on the target exactly, including the removal of the
    raw run's deflator noise (the wrong-signed residue a dead CGIPS shock
    leaves in GDP is part of what is being overridden).

    Units: the OBR multipliers map real spending to real GDP. Nominal
    instruments (CGIPS/LAIPS/GGIPS, £m current prices) are converted to real
    £m with the baseline path of the deflator named in the convention entry
    before the multiplier is applied; CGG is already real.
    """
    values = shock_path(shock, periods)
    horizon = t_end - t_start + 1
    real_shock = []
    for q in range(horizon):
        s = values[q] if q < len(values) else 0.0
        if convention.deflator is not None and s != 0.0:
            defl = float(baseline_data.iloc[t_start + q][convention.deflator])
            if not np.isfinite(defl) or defl <= 0:
                raise RuntimeError(
                    f"baseline {convention.deflator} is {defl} at offset {q}; "
                    "cannot deflate the nominal shock to real terms, so the "
                    "published-convention path cannot be computed"
                )
            s = 100.0 * s / defl
        real_shock.append(float(s))
    target = target_gdp_delta(convention.channel, real_shock)

    conv = template.clone()
    conv.apply_shock(var, shock, start, periods=periods)
    for q in range(horizon):
        t = t_start + q
        raw_delta = float(
            raw_shocked_data.iloc[t]["GDPM"] - baseline_data.iloc[t]["GDPM"]
        )
        key = ("GDPM", t)
        # += so the structural add-factors already on the template (e.g. the
        # OSHH anchor) are preserved, not clobbered.
        conv.add_factors[key] = conv.add_factors.get(key, 0.0) + (target[q] - raw_delta)
    conv.solve(start, end)

    entry = PUBLISHED_MULTIPLIERS[convention.channel]
    detail = {
        "instrument": var,
        "channel": convention.channel,
        "channel_label": entry.label,
        "impact_multiplier": entry.impact,
        "taper_quarters": TAPER_QUARTERS,
        "taper_shape": (
            "linear fade to zero from the shock start (the SHAPE is this "
            "repo's choice — the OBR publishes the impact value and the "
            "zero-at-five-years endpoint, not a quarterly path)"
        ),
        "source": entry.source,
        "deflator": convention.deflator,
        "real_shock_m": real_shock,
        "target_delta_gdp_m": target,
    }
    return conv.data.copy(), detail


def run_reform(
    name: str,
    var: str,
    shock: "float | Iterable[float]",
    start: str = "2025Q1",
    end: str = "2027Q4",
    periods: int = 12,
    investment_closure: bool = False,
    published_conventions: bool = False,
):
    """Run a reform scenario and return results DataFrame.

    Args:
        name: Name of the reform for labeling
        var: Variable to shock (must be exogenous - no equation computes it),
            or ``"HHDI_ADDFACTOR"`` for an externally costed household reform.
        shock: Size of shock (units depend on variable). A scalar is applied
            for ``periods`` quarters; a sequence of per-quarter values is
            applied from ``start`` and its length overrides ``periods``
            (externally costed reforms — e.g. a microsimulation revenue
            path — arrive as one value per quarter). For
            ``HHDI_ADDFACTOR``, values are quarterly £m using the fiscal
            convention: positive = revenue raised = disposable income falls.
        start: Start quarter (e.g., "2025Q1")
        end: End quarter for simulation
        periods: Number of quarters to apply shock (ignored for a sequence)
        investment_closure: If True, use investment closure (for corp tax shocks)
        published_conventions: If True, and ``var`` is an instrument whose
            model channel is an accounting identity or dead (CGG,
            CGIPS/LAIPS/GGIPS), impose the OBR's PUBLISHED multiplier
            convention (obr_macro.published_conventions) as a GDPM add-factor
            path on the shocked run, so ``delta_gdp`` follows the convention
            instead of the raw mechanics. The result is labelled in
            ``df.attrs`` as the OBR's published multiplier convention, not
            model dynamics. Instruments with live behaviour (the household-tax
            channel; the investment closure) are NEVER overridden: the
            household channel is left alone with an attrs note, and combining
            the flag with ``investment_closure=True`` raises. Default False —
            the honest default is the raw model.
    """
    if published_conventions and investment_closure:
        raise ValueError(
            "published_conventions covers only instruments whose model channel "
            "is an accounting identity or dead (CGG, CGIPS/LAIPS/GGIPS). The "
            "investment closure has a live cost-of-capital channel; imposing "
            "the OBR's published corporation-tax convention on top of it would "
            "mix imposed and modelled dynamics in a single number. Run one or "
            "the other."
        )
    # Normalize/validate the shock spec BEFORE _build_reform_template: a bad
    # spec must fail in milliseconds, not after an expensive template solve.
    # (apply_shock re-normalizes; this early pass exists for fail-fast UX and
    # is pinned by test_run_reform_validates_before_template_build.)
    if not is_scalar_shock(shock):
        shock = shock_path(shock, periods)
        periods = len(shock)
    # Clone the shared (cached) template for both runs; the template is pristine
    # and unsolved, so the baseline and shocked clones are structurally
    # identical and the delta isolates the shock.
    template = _build_reform_template(var, start, end, investment_closure)
    if var != HOUSEHOLD_COSTING_VAR:
        _check_instrument_domain(template, var, shock_path(shock, periods), start)
    baseline = template.clone()
    shocked = template.clone()
    if var == HOUSEHOLD_COSTING_VAR:
        _apply_household_costing(shocked, shock, start, periods)
    else:
        shocked.apply_shock(var, shock, start, periods=periods)

    baseline.solve(start, end)
    baseline_data = baseline.data.copy()
    shocked.solve(start, end)
    shocked_data = shocked.data.copy()

    # Build results
    t_start = baseline.period_idx(start)
    t_end = baseline.period_idx(end)

    # Published-conventions override: only for instruments whose model channel
    # is an identity or dead. The raw solve above is kept as the measurement of
    # what the model does; a third solve imposes the convention on top of it.
    convention = INSTRUMENT_CONVENTIONS.get(var) if published_conventions else None
    convention_detail = None
    if convention is not None:
        shocked_data, convention_detail = _impose_published_convention(
            template,
            baseline_data,
            shocked_data,
            convention,
            var,
            shock,
            start,
            end,
            periods,
            t_start,
            t_end,
        )

    results = []
    for t in range(t_start, t_end + 1):
        period = str(baseline.index[t])
        gdp_base = baseline_data.iloc[t]["GDPM"]
        gdp_shock = shocked_data.iloc[t]["GDPM"]
        delta_gdp = gdp_shock - gdp_base
        pct_gdp = 100 * delta_gdp / gdp_base

        cons_base = baseline_data.iloc[t]["CONS"]
        cons_shock = shocked_data.iloc[t]["CONS"]
        delta_cons = cons_shock - cons_base

        if_base = baseline_data.iloc[t]["IF"]
        if_shock = shocked_data.iloc[t]["IF"]
        delta_if = if_shock - if_base
        results.append(
            {
                "period": period,
                "reform": name,
                "delta_gdp_m": delta_gdp,
                "delta_gdp_bn": delta_gdp / 1000,
                "pct_gdp": pct_gdp,
                "delta_cons_m": delta_cons,
                "delta_if_m": delta_if,
            }
        )

    out = pd.DataFrame(results)

    # Honest-labelling metadata (df.attrs travels with the frame). Under the
    # demand closure a spending shock's GDP response is MECHANICAL PASSTHROUGH:
    # the shock lands in the GDPM expenditure identity with a flat multiplier
    # of ~1.0 and no decay, because every second-round behavioural channel is
    # structurally absent from the published October-2025 model file as
    # parsed/populated here:
    #   - import leakage: M has NO behavioural equation in the published file
    #     (MNOG is computed residually as M - MS - MOIL, so M is exogenous);
    #     the live dlog(MS) equation is dead on this data (PMSREL/SPECX NaN);
    #   - consumption: the dlog(CONS) equation is live, but its income input
    #     RHHDI does not respond to demand because the labour-income chain
    #     (GDP -> employment -> wages -> HHDI) is unpopulated
    #     (docs/stage1c_data_scope.md);
    #   - crowding out/decay: no monetary rule (R is exogenous) and no output
    #     gap, so nothing closes the multiplier over the horizon.
    # Activating any of these would mean inventing equations or data the OBR
    # did not publish, so the passthrough is kept and labelled instead of
    # being dressed up as a validated multiplier profile.
    #
    # AGAINST THE PUBLISHED RANGE. The OBR's own impact multipliers are 1.0 for
    # CAPITAL spending, 0.6 for CURRENT spending, 0.6 for welfare, 0.3 for
    # personal tax and NICs and 0.2 for corporation tax, and all of them decay
    # to zero as the output gap closes. This model returns 1.00 flat for a
    # government-CONSUMPTION shock — measured impact 1.0000, quarter 12 0.9995,
    # linear in shock size from GBP 0.1bn to GBP 10bn. So it overstates the
    # OBR's current-spending multiplier by ~67% on impact and by more at every
    # subsequent quarter, because nothing here decays. An earlier version of
    # this comment claimed the impact quarter "matches the OBR's ~1.0
    # multiplier for government consumption": 1.0 is the OBR's CAPITAL
    # multiplier, not its current-spending one, and the claim was wrong.
    if convention_detail is not None:
        # The reported delta_gdp is IMPOSED, so the raw-mechanics labels
        # (mechanical_passthrough / multiplier_warning / dead-channel warning)
        # would describe a number this frame no longer contains. They are
        # replaced by the convention labels; the dead-channel FACT is still
        # recorded because the underlying channel is still dead — only the
        # reported GDP total is overridden.
        entry = PUBLISHED_MULTIPLIERS[convention_detail["channel"]]
        out.attrs["published_conventions"] = True
        out.attrs["convention"] = convention_detail
        out.attrs["dead_channel"] = var in _DEAD_UNDER_DEMAND_CLOSURE
        out.attrs["published_conventions_note"] = (
            "delta_gdp follows the OBR's published multiplier convention, not "
            f"model dynamics: impact multiplier {entry.impact} for "
            f"{entry.label} ({entry.source}), fading linearly to zero over "
            f"{TAPER_QUARTERS} quarters from the shock start. The linear path "
            "shape is this repo's choice — the OBR publishes the impact value "
            "and the zero endpoint, not the path. Imposed as a GDPM add-factor "
            "on the shocked run only; the model's own channel for this "
            "instrument is "
            + (
                "dead (no transmission path to GDP)"
                if var in _DEAD_UNDER_DEMAND_CLOSURE
                else "an accounting identity (1.0-flat passthrough)"
            )
            + " and cannot produce this profile. Component deltas "
            "(delta_cons_m, delta_if_m) are NOT overridden — they remain the "
            "raw model's values, so e.g. delta_if_m stays exactly zero for a "
            "capital-spending shock even though delta_gdp follows the "
            "convention."
        )
    elif not investment_closure:
        out.attrs["published_conventions"] = False
        out.attrs["mechanical_passthrough"] = True
        out.attrs["obr_published_impact_multiplier"] = {
            "current_spending": 0.6,
            "capital_spending": 1.0,
            "personal_tax_and_nics": 0.3,
            "corporation_tax": 0.2,
        }
        out.attrs["multiplier_warning"] = (
            "Demand-closure shock: GDP delta is mechanical passthrough via the "
            "expenditure identity (flat multiplier 1.0, no behavioural "
            "second-round effects and no decay). Import leakage, income-driven "
            "consumption and crowding-out channels are structurally inert in "
            "the published model file/data. This does NOT match the OBR's "
            "published impact multiplier for current spending (0.6, decaying "
            "to zero as the output gap closes) — it is ~67% too large on "
            "impact and stays flat where the OBR's decays. Do not read the "
            "path as a multiplier profile."
        )
        if var in _DEAD_UNDER_DEMAND_CLOSURE:
            msg = (
                f"{var} ({_DEAD_UNDER_DEMAND_CLOSURE[var]}) has NO transmission "
                "path to GDP under the demand closure: IF has no live equation "
                "in the published model, so the CGIPS -> GGIPS -> GGI -> IF "
                "chain never reaches the GDP identity. delta_IF is exactly "
                "zero and the small GDP residue is deflator noise of "
                "indeterminate sign. This result is not a public-investment "
                "multiplier and must not be reported as one."
            )
            out.attrs["dead_channel"] = True
            out.attrs["dead_channel_warning"] = msg
            warnings.warn(msg, stacklevel=2)
        else:
            out.attrs["dead_channel"] = False
        if published_conventions:
            # The flag was requested but no convention is wired for this
            # instrument. Deliberate for the household channel: it has live
            # behaviour, and imposing a published number on top of behaviour
            # would mix judgement and model dynamics in one figure.
            if var == HOUSEHOLD_COSTING_VAR:
                out.attrs["published_conventions_note"] = (
                    "published_conventions requested but NOT applied: the "
                    "household-tax channel has live model behaviour "
                    "(dlog(CONS) responds to real income), so the model's own "
                    "response is reported unchanged. The OBR's published "
                    "income tax/NICs multiplier (0.3, fading) is in "
                    "obr_macro.published_conventions for reference but is "
                    "never imposed on a live channel."
                )
            else:
                out.attrs["published_conventions_note"] = (
                    f"published_conventions requested but NOT applied: no "
                    f"published convention is wired for instrument {var!r} "
                    "(only identity/dead channels — CGG, CGIPS/LAIPS/GGIPS — "
                    "are overridden). The raw model result is reported."
                )
    else:
        out.attrs["published_conventions"] = False
        out.attrs["mechanical_passthrough"] = False
        # End-of-horizon log deviations of investment and its steady-state
        # target, for the convergence diagnostics (guarded: a broken run can
        # leave non-positive levels, which must label as NaN, not raise).
        with np.errstate(invalid="ignore", divide="ignore"):
            dlog_ibusx_end = float(
                np.log(shocked_data.iloc[t_end]["IBUSX"])
                - np.log(baseline_data.iloc[t_end]["IBUSX"])
            )
            dlog_kstar_end = float(
                np.log(shocked_data.iloc[t_end]["KSTAR"])
                - np.log(baseline_data.iloc[t_end]["KSTAR"])
            )
        _label_investment_closure_divergence(out, dlog_ibusx_end, dlog_kstar_end)
    if var == HOUSEHOLD_COSTING_VAR:
        out.attrs["costing_sign_convention"] = (
            "Quarterly £m; positive = revenue raised = household disposable "
            "income falls."
        )
        window = slice(t_start, t_end + 1)
        out.attrs["delta_hhdi_m"] = (
            shocked_data.iloc[window]["HHDI"] - baseline_data.iloc[window]["HHDI"]
        ).tolist()
        out.attrs["delta_rhhdi_m"] = (
            shocked_data.iloc[window]["RHHDI"] - baseline_data.iloc[window]["RHHDI"]
        ).tolist()
    return out


def run_five_reforms():
    """Run five interesting policy reforms."""

    reforms = []

    # 1. Government spending increase: £5bn/year (£1.25bn/quarter)
    print("Running Reform 1: £5bn government spending increase...")
    df = run_reform(
        name="£5bn Gov Spending",
        var="CGG",
        shock=1250,  # £1.25bn per quarter = £5bn/year
        periods=12,
        investment_closure=False,
    )
    reforms.append(df)

    # 2. Corporation tax cut: -5pp (from 25% to 20%)
    print("Running Reform 2: 5pp corporation tax cut...")
    df = run_reform(
        name="5pp Corp Tax Cut",
        var="TCPRO",
        shock=-0.05,  # -5pp
        periods=12,
        investment_closure=True,
    )
    reforms.append(df)

    # 3. Corporation tax rise: +5pp (from 25% to 30%)
    print("Running Reform 3: 5pp corporation tax rise...")
    df = run_reform(
        name="5pp Corp Tax Rise",
        var="TCPRO",
        shock=0.05,  # +5pp
        periods=12,
        investment_closure=True,
    )
    reforms.append(df)

    # 4. Government investment boost: £10bn/year
    # Chain: CGIPS (exog) → GGIPS = CGIPS + LAIPS → GGI = 100 * GGIPS / GGIDEF
    # GGIDEF ≈ 119, so to get £2.5bn real GGI, need ~£3bn nominal CGIPS
    #
    # KNOWN DEAD: the chain stops at GGI. IF has no live equation under the
    # demand closure, so GGI never reaches the GDP identity — delta_IF is
    # exactly zero and delta_GDP is +£0.03bn on impact then negative to
    # -£0.14bn. run_reform emits a dead_channel warning for it. Kept in the
    # demo so the defect is visible rather than quietly dropped; do not quote
    # this row as a public-investment multiplier.
    print("Running Reform 4: £10bn government investment (DEAD CHANNEL — see note)...")
    df = run_reform(
        name="£10bn Gov Investment (dead channel)",
        var="CGIPS",
        shock=3000,  # £3bn nominal per quarter ≈ £2.5bn real
        periods=12,
        investment_closure=False,
    )
    reforms.append(df)

    # 5. Austerity scenario: -£10bn government spending
    print("Running Reform 5: £10bn spending cut...")
    df = run_reform(
        name="£10bn Spending Cut",
        var="CGG",
        shock=-2500,  # -£2.5bn per quarter
        periods=12,
        investment_closure=False,
    )
    reforms.append(df)

    return pd.concat(reforms, ignore_index=True)


def create_visualisations(results: pd.DataFrame, output_dir: str = None):
    """Create reform impact visualisations."""

    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "outputs"
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    # Set style
    plt.style.use("seaborn-v0_8-whitegrid")

    reforms = results["reform"].unique()
    colors = plt.cm.tab10(np.linspace(0, 1, len(reforms)))
    color_map = dict(zip(reforms, colors))

    # Figure 1: GDP impact over time (£bn)
    fig, ax = plt.subplots(figsize=(12, 6))
    for reform in reforms:
        df = results[results["reform"] == reform]
        ax.plot(
            df["period"],
            df["delta_gdp_bn"],
            label=reform,
            color=color_map[reform],
            linewidth=2,
        )
    ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax.set_xlabel("Quarter", fontsize=12)
    ax.set_ylabel("Change in GDP (£bn)", fontsize=12)
    ax.set_title("GDP Impact of Policy Reforms\n(OBR Model)", fontsize=14)
    ax.legend(loc="best", fontsize=10)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_dir / "reform_gdp_impact.png", dpi=150)
    plt.close()
    print(f"Saved: {output_dir / 'reform_gdp_impact.png'}")

    # Figure 2: GDP impact (% change)
    fig, ax = plt.subplots(figsize=(12, 6))
    for reform in reforms:
        df = results[results["reform"] == reform]
        ax.plot(
            df["period"],
            df["pct_gdp"],
            label=reform,
            color=color_map[reform],
            linewidth=2,
        )
    ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax.set_xlabel("Quarter", fontsize=12)
    ax.set_ylabel("Change in GDP (%)", fontsize=12)
    ax.set_title("GDP Impact of Policy Reforms (% Change)\n(OBR Model)", fontsize=14)
    ax.legend(loc="best", fontsize=10)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_dir / "reform_gdp_pct.png", dpi=150)
    plt.close()
    print(f"Saved: {output_dir / 'reform_gdp_pct.png'}")

    # Figure 3: Final period comparison (bar chart)
    final_period = results["period"].iloc[-1]
    final_results = results[results["period"] == final_period].copy()

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(final_results))
    bars = ax.bar(
        x,
        final_results["delta_gdp_bn"],
        color=[color_map[r] for r in final_results["reform"]],
    )
    ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(final_results["reform"], rotation=30, ha="right")
    ax.set_ylabel("Change in GDP (£bn)", fontsize=12)
    ax.set_title(f"Cumulative GDP Impact by {final_period}\n(OBR Model)", fontsize=14)

    # Add value labels
    for bar, val in zip(bars, final_results["delta_gdp_bn"]):
        height = bar.get_height()
        ax.annotate(
            f"{val:+.1f}",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 3 if height >= 0 else -12),
            textcoords="offset points",
            ha="center",
            va="bottom" if height >= 0 else "top",
            fontsize=10,
        )

    plt.tight_layout()
    plt.savefig(output_dir / "reform_comparison.png", dpi=150)
    plt.close()
    print(f"Saved: {output_dir / 'reform_comparison.png'}")

    # Figure 4: Spending vs Tax reforms
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Spending reforms
    spending_reforms = [
        "£5bn Gov Spending",
        "£10bn Gov Investment",
        "£10bn Spending Cut",
    ]
    for reform in spending_reforms:
        if reform in reforms:
            df = results[results["reform"] == reform]
            ax1.plot(df["period"], df["delta_gdp_bn"], label=reform, linewidth=2)
    ax1.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax1.set_xlabel("Quarter")
    ax1.set_ylabel("Change in GDP (£bn)")
    ax1.set_title("Spending Policy Reforms")
    ax1.legend()
    ax1.tick_params(axis="x", rotation=45)

    # Tax reforms
    tax_reforms = ["5pp Corp Tax Cut", "5pp Corp Tax Rise"]
    for reform in tax_reforms:
        if reform in reforms:
            df = results[results["reform"] == reform]
            ax2.plot(df["period"], df["delta_gdp_bn"], label=reform, linewidth=2)
    ax2.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax2.set_xlabel("Quarter")
    ax2.set_ylabel("Change in GDP (£bn)")
    ax2.set_title("Corporation Tax Reforms")
    ax2.legend()
    ax2.tick_params(axis="x", rotation=45)

    plt.tight_layout()
    plt.savefig(output_dir / "reform_spending_vs_tax.png", dpi=150)
    plt.close()
    print(f"Saved: {output_dir / 'reform_spending_vs_tax.png'}")

    return output_dir


def main():
    """Run all reforms and create visualisations."""
    print("=" * 70)
    print("OBR MODEL: POLICY REFORM ANALYSIS")
    print("=" * 70)
    print()

    # Run reforms
    results = run_five_reforms()

    # Save results
    output_dir = Path(__file__).parent.parent / "outputs"
    output_dir.mkdir(exist_ok=True)
    results.to_csv(output_dir / "reform_results.csv", index=False)
    print(f"\nSaved results: {output_dir / 'reform_results.csv'}")

    # Create visualisations
    print("\nCreating visualisations...")
    create_visualisations(results, output_dir)

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY: Final Period GDP Impacts")
    print("=" * 70)
    final = results[results["period"] == results["period"].iloc[-1]]
    for _, row in final.iterrows():
        print(
            f"{row['reform']:<25} {row['delta_gdp_bn']:>+8.1f} £bn ({row['pct_gdp']:>+6.2f}%)"
        )

    return results


if __name__ == "__main__":
    main()
