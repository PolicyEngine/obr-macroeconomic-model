"""Opt-in demand overlays: import leakage and an employment response.

Both are off by default and labelled as judgement overlays in ``df.attrs``.
They answer two points raised in review of the OBR's October 2025 listing:

* Imports. Total imports ``M`` have no equation, and non-oil goods imports
  are the residual ``MNOG = M - MS - MOIL`` (l.217). A demand expansion
  therefore leaves ``M`` unchanged, and any rise in services or oil imports
  lowers measured goods imports one for one.
* Employment. Total employment is ``ETLFS = 1000 * HWA / AVH`` (l.153) with
  hours ``HWA`` and average hours ``AVH`` both inputs, so it does not respond
  to output. The listing's estimated labour-demand equation is for market
  sector employment ``EMS`` (l.145), which no equation links to ``ETLFS``.

Each overlay is written in deviation form against the solved baseline and
applied to the shocked run only, so the baseline (and every result with the
flags off) is unchanged. Baseline paths enter as ``*_BASE`` columns added to
the shocked solver's data.
"""

from __future__ import annotations

import numpy as np

from obr_macro.transpiler import EViewsTranspiler

# --- Imports -----------------------------------------------------------------
# Goods. The listing has NO estimated goods-import equation (the l.215 comment
# "Changed to enable indirect T2 fix" marks where one was replaced by the
# residual). What it does publish is the goods import content of each demand
# component, MGTFE (l.211, "index of final demand weighted by import
# intensity (goods)" in the variable list). For the four domestic demand
# components its weights and the services weights MSTFE (l.219) sum to the
# total import-content weights of l.195-l.201 (0.176 + 0.081 = 0.257 for
# consumption, 0.064 + 0.030 = 0.094 for government consumption, likewise
# investment and stockbuilding; the goods-export weights do not sum this
# way). The total weights are scaled against ALL imports, oil included
# (MINTY, l.209), so the goods weights are read here as covering all goods,
# oil included: over 2025Q1-2027Q4 baseline goods imports with oil are 1.04
# to 1.06 times MGTFE, and 0.92 to 0.97 times without.
#
# The overlay therefore holds the intensity of ALL goods imports,
# (MNOG + MOIL) / MGTFE, at its baseline path (an elasticity of 1 with
# respect to import-weighted demand) and takes off the oil imports the
# listing already computes (l.353, l.358), so oil is counted once. Until
# 22 Nov 2026 the overlay scaled non-oil goods alone and added the oil
# response on top, which put total goods imports GBP 110m to 190m a quarter
# above the unit-elastic path for government consumption of 1% of GDP (oil
# demand has an elasticity of 1.9 to non-oil GVA in l.353). The weights are
# the OBR's; the unit elasticity is this repo's judgement (constant import
# content), not an estimate.
IMPORT_RESPONSE_GOODS_ELASTICITY = 1.0
_GOODS_SRC = (
    "MNOG = (MNOG_BASE + MOIL_BASE) * (MGTFE / MGTFE_BASE) ^ {elasticity} - MOIL"
)

# Services. The listing's own estimated equation, l.223, written as a
# deviation from the baseline. It is linear in logs, so the terms in the
# relative price PMSREL, the specialisation index SPECX, the dummies and the
# constant cancel when those are held at baseline, leaving the MSTFE and
# lagged-MS terms with the published coefficients (long-run elasticity
# 1.079017). In levels the equation is dropped in this replication because
# PMSREL and SPECX have no data; the deviation form needs neither.
SERVICES_IMPORT_COEFFICIENTS = {
    "dlog_mstfe": (0.819114, 0.389511, -0.525436, 0.288639),
    "dlog_ms_lag1": -0.271392,
    "error_correction": -0.171294,
    "long_run_mstfe": 1.079017,
}
_c = SERVICES_IMPORT_COEFFICIENTS
_SERVICES_SRC = (
    "MS = MS_BASE * exp(log(MS(-1) / MS_BASE(-1))"
    + "".join(
        f" + ({coef}) * (dlog(MSTFE{lag}) - dlog(MSTFE_BASE{lag}))"
        for coef, lag in zip(_c["dlog_mstfe"], ("", "(-1)", "(-2)", "(-3)"))
    )
    + f" + ({_c['dlog_ms_lag1']}) * (dlog(MS(-1)) - dlog(MS_BASE(-1)))"
    + f" + ({_c['error_correction']}) * (log(MS(-1) / MS_BASE(-1))"
    + f" - {_c['long_run_mstfe']} * log(MSTFE(-1) / MSTFE_BASE(-1))))"
)
# l.217 inverted: with goods and services imports determined, total imports
# are their sum plus oil imports (MOIL, l.358, already live).
_TOTAL_SRC = "M = MNOG + MS + MOIL"

IMPORT_RESPONSE_BASE_VARS = ("MNOG", "MOIL", "MGTFE", "MS", "MSTFE")
IMPORT_RESPONSE_REPORT_VARS = ("M", "MNOG", "MS", "MOIL")
# Shocking one of these directly would fight the overlay's own equations.
IMPORT_RESPONSE_EXCLUDED_VARS = frozenset({"M", "MNOG", "MS", "MOIL"})
IMPORT_RESPONSE_NOTE = (
    "Judgement overlay, not the shipped listing (which holds total imports M "
    "exogenous). Applied to the shocked run only, as deviations from the "
    "solved baseline. Services imports follow the listing's own estimated "
    "equation (l.223) with relative prices and the specialisation index held "
    "at baseline. Goods imports, oil included, move in proportion to "
    "import-weighted demand MGTFE (l.211): the weights are the OBR's, the "
    f"elasticity of {IMPORT_RESPONSE_GOODS_ELASTICITY:g} is this repo's "
    "assumption because the listing has no estimated goods-import equation. "
    "Non-oil goods imports are that total less the oil imports the listing "
    "already computes (l.353, l.358), so oil is counted once. Total imports "
    "become M = MNOG + MS + MOIL (l.217 inverted). Import "
    "prices and exports do not respond. Measured under the default "
    "nominal-GDP pin only."
)

# --- Employment --------------------------------------------------------------
# The listing's only estimated labour-demand equation is dlog(EMS), l.145:
# market sector employment on lagged market sector GVA (short-run 0.171, unit
# long-run elasticity through an error-correction term of 0.0062 a quarter)
# and the real product wage. It is live in this replication. The overlay adds
# the missing bridge to total employment: the baseline-to-shock change in EMS
# is passed one for one to ETLFS, by scaling hours worked HWA with average
# hours AVH held (so l.153 stays live and holds exactly). General government
# employment EGG has no equation and stays at baseline. The EMS equation is
# the OBR's; the one-for-one bridge is this repo's judgement.
_HOURS_SRC = "HWA = HWA_BASE * (1 + (EMS - EMS_BASE) / ETLFS_BASE)"

EMPLOYMENT_RESPONSE_BASE_VARS = ("HWA", "EMS", "ETLFS")
EMPLOYMENT_RESPONSE_REPORT_VARS = ("EMS", "ETLFS", "ULFS", "LFSUR")
EMPLOYMENT_RESPONSE_EXCLUDED_VARS = frozenset({"HWA", "AVH", "ETLFS", "EMS"})
EMPLOYMENT_RESPONSE_NOTE = (
    "Judgement overlay, not the shipped listing (which sets total employment "
    "from hours inputs, ETLFS = 1000*HWA/AVH, l.153). Applied to the shocked "
    "run only. Market sector employment EMS follows the listing's own "
    "estimated equation (l.145: lagged market sector GVA, short-run 0.171, "
    "unit long-run elasticity closing at 0.6% a quarter). The overlay passes "
    "the change in EMS one for one to total employment by scaling hours "
    "worked with average hours held; that bridge is this repo's assumption, "
    "since no published equation links EMS to ETLFS. Unemployment then moves "
    "through the labour-force identity (l.163) with participation and "
    "population held. It reaches consumption through the unemployment term "
    "of l.4 and earnings through l.232. It does not reach the wage bill or "
    "household income: WFP (l.589) is dropped in this replication for "
    "missing inputs. Government employment does not respond, and government "
    "consumption is mostly government GVA here, so a government-consumption "
    "shock moves market sector GVA, and so employment, very little."
)
# Measured 22 Nov 2026 (October 2026 EFO, +1% of GDP on CGG for 12 quarters,
# results/demand_overlays.json): government GVA takes 94% to 96% of the shock
# (GGVA/GGVA(-1) = CGG/CGG(-1), with the GGVA level seeded at 20% of GDP), so
# market sector GVA moves by -0.05% to +0.01%. Employment falls by 0.8 to 1.9
# thousand from quarter 2 to quarter 5, then rises to +7.0 thousand by
# quarter 12. The rise comes from the real-product-wage term of l.145, not
# from output: the market sector GVA deflator PMSGVA jumps by about 1.3%, so
# PSAVEI/PMSGVA falls by 0.95% on impact and 0.2% by quarter 12. With
# import_response also on, GDP rises by less than government GVA, market
# sector GVA falls and employment falls in every quarter from quarter 2, by
# up to 19.7 thousand.
EMPLOYMENT_RESPONSE_CGG_WARNING = (
    "Do not read this as the jobs effect of government spending; the sign "
    "can be wrong. In this run a rise in government consumption can LOWER "
    "employment: for +1% of GDP, by 0.8 to 1.9 thousand from quarter 2 to "
    "quarter 5 before a rise to +7.0 thousand by quarter 12, and by up to "
    "19.7 thousand in every quarter from quarter 2 when import_response is "
    "also on. That is an artefact, not a finding. The listing's labour "
    "demand is for the market sector only. Here government GVA rises almost "
    "one for one with government consumption (l.760 scales it with CGG, "
    "from a level this repo seeds at 20% of GDP) and government employment "
    "has no equation, so market sector GVA barely moves and can fall. What "
    "employment change there is comes mostly from the real-product-wage "
    "term of l.145, because the market sector GVA deflator jumps with the "
    "shock."
)


def _parse(src: str):
    return EViewsTranspiler().parse_equation(src)


def _add_baseline_columns(shocked, baseline_data, names) -> None:
    for name in names:
        values = baseline_data[name].astype(float).to_numpy()
        shocked.data[f"{name}_BASE"] = values


def _replace_equation(shocked, var: str, src: str) -> None:
    """Swap ``var``'s equation (if any) for ``src`` on this solver only.

    ``clone()`` gives each solver its own equation list, so the cached
    template and the baseline are untouched.
    """
    if any(key[0] == var for key in (getattr(shocked, "anchor_terms", None) or {})):
        raise RuntimeError(
            f"{var} carries an anchoring residual; the overlay equation would "
            "inherit it and no longer be a pure deviation from baseline."
        )
    shocked.swap_closure(var, _parse(src))


def _require_finite(baseline_data, names, t_start, t_end, overlay: str) -> None:
    window = baseline_data.iloc[t_start : t_end + 1]
    bad = [
        n
        for n in names
        if n not in window.columns
        or not np.all(np.isfinite(window[n].astype(float).to_numpy()))
        or np.any(window[n].astype(float).to_numpy() <= 0)
    ]
    if bad:
        raise RuntimeError(
            f"{overlay} needs a finite, positive baseline path for "
            f"{', '.join(bad)} over the solve window."
        )


def apply_import_response(shocked, baseline_data, t_start: int, t_end: int) -> None:
    """Make imports respond to demand on the shocked solver (see module doc)."""
    _require_finite(
        baseline_data, IMPORT_RESPONSE_BASE_VARS, t_start, t_end, "import_response"
    )
    _add_baseline_columns(shocked, baseline_data, IMPORT_RESPONSE_BASE_VARS)
    _replace_equation(
        shocked, "MNOG", _GOODS_SRC.format(elasticity=IMPORT_RESPONSE_GOODS_ELASTICITY)
    )
    _replace_equation(shocked, "MS", _SERVICES_SRC)
    _replace_equation(shocked, "M", _TOTAL_SRC)


def apply_employment_response(shocked, baseline_data, t_start: int, t_end: int) -> None:
    """Link total employment to market sector employment on the shocked solver."""
    _require_finite(
        baseline_data,
        EMPLOYMENT_RESPONSE_BASE_VARS,
        t_start,
        t_end,
        "employment_response",
    )
    if "EMS" not in shocked.eq_for_var:
        raise RuntimeError(
            "employment_response needs the listing's dlog(EMS) equation "
            "(l.145) to be live."
        )
    _add_baseline_columns(shocked, baseline_data, EMPLOYMENT_RESPONSE_BASE_VARS)
    _replace_equation(shocked, "HWA", _HOURS_SRC)


def require_overlay_equations_live(report, import_response, employment_response):
    """Raise if the shocked solve dropped an equation an overlay relies on.

    ``solve`` tolerates a non-finite MS or EMS (both are known to drop in some
    windows), which would turn an overlay into a silent zero response.
    """
    if report is None:
        return
    needed = set()
    if import_response:
        needed |= {"M", "MNOG", "MS", "MGTFE", "MSTFE"}
    if employment_response:
        needed |= {"HWA", "EMS", "ETLFS"}
    dropped = sorted(needed & set(report.get("dropped", ())))
    if dropped:
        raise RuntimeError(
            f"overlay equation(s) {', '.join(dropped)} evaluated non-finite and "
            "were dropped in the shocked solve; the overlay response would be "
            "silently incomplete."
        )


def overlay_deltas(baseline_data, shocked_data, names, t_start: int, t_end: int):
    """Per-quarter shocked-minus-baseline paths for ``names`` over the window."""
    window = slice(t_start, t_end + 1)
    return {
        name: (
            shocked_data.iloc[window][name].astype(float)
            - baseline_data.iloc[window][name].astype(float)
        ).tolist()
        for name in names
    }


def import_response_detail(baseline_data, shocked_data, t_start, t_end) -> dict:
    deltas = overlay_deltas(
        baseline_data, shocked_data, IMPORT_RESPONSE_REPORT_VARS, t_start, t_end
    )
    return {
        "goods_elasticity": IMPORT_RESPONSE_GOODS_ELASTICITY,
        "goods_source": "import-content weights MGTFE, OBR model code l.211; "
        "unit elasticity assumed for goods imports including oil; non-oil "
        "goods are that total less the listing's oil imports",
        "services_coefficients": dict(SERVICES_IMPORT_COEFFICIENTS),
        "services_source": "OBR model code l.223, deviation form",
        "delta_m": {name: deltas[name] for name in IMPORT_RESPONSE_REPORT_VARS},
    }


def employment_response_detail(baseline_data, shocked_data, t_start, t_end) -> dict:
    deltas = overlay_deltas(
        baseline_data, shocked_data, EMPLOYMENT_RESPONSE_REPORT_VARS, t_start, t_end
    )
    return {
        "source": "OBR model code l.145 (dlog(EMS)); one-for-one bridge to "
        "ETLFS assumed",
        "delta_ems_thousands": deltas["EMS"],
        "delta_etlfs_thousands": deltas["ETLFS"],
        "delta_ulfs_thousands": deltas["ULFS"],
        "delta_lfsur_pp": deltas["LFSUR"],
    }


def services_imports_partial_response(ms_base, mstfe_base, mstfe_shocked):
    """Services-import change l.223 implies for a given MSTFE path.

    A partial calculation with no feedback: it applies the deviation form of
    l.223 to baseline and shocked import-weighted demand over the window
    (deviations are zero before it). Used to say what the published model,
    where l.223 is live and total imports are fixed, would do to the goods
    residual under a run in which imports did not respond.
    """
    c = SERVICES_IMPORT_COEFFICIENTS
    m = np.log(np.asarray(mstfe_shocked, float) / np.asarray(mstfe_base, float))
    d = np.zeros(len(m))

    def at(path, i):
        return path[i] if i >= 0 else 0.0

    for t in range(len(m)):
        step = sum(
            coef * (at(m, t - k) - at(m, t - k - 1))
            for k, coef in enumerate(c["dlog_mstfe"])
        )
        step += c["dlog_ms_lag1"] * (at(d, t - 1) - at(d, t - 2))
        step += c["error_correction"] * (
            at(d, t - 1) - c["long_run_mstfe"] * at(m, t - 1)
        )
        d[t] = at(d, t - 1) + step
    return (np.asarray(ms_base, float) * (np.exp(d) - 1.0)).tolist()
