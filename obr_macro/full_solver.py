"""Full OBR model solver that initializes missing variables.

This solver:
1. Loads the OBR equations exactly as published
2. Initializes any missing variables to 0 (or computes from equations)
3. Solves the complete system using Gauss-Seidel iteration
4. Allows closure swaps for policy simulation
"""

import numbers
import re
import warnings
from collections import Counter
from decimal import Decimal
from collections.abc import Iterable

import numpy as np
import pandas as pd

from obr_macro.data import load_obr_data, ensure_model_code
from obr_macro.transpiler import parse_model_file, ParsedEquation, IDENT, RESERVED_WORDS

# Cache of parsed LHS forms, keyed by the raw LHS string (parsing is
# deterministic, so the cache can be shared across solver instances/clones).
_LHS_CACHE: dict = {}

# Warn-once registries for model-file defects. The equation index is rebuilt on
# every clone()/make_exogenous()/swap_closure(), and the defects are properties
# of the parsed model file rather than of any one solver, so warning per rebuild
# emits the same message dozens of times in a single run. Keyed by LHS var.
_WARNED_UNPARSED_LHS: set = set()
_WARNED_DUPLICATE_LHS: set = set()


def reset_model_warnings() -> None:
    """Clear the warn-once registries so the model-file warnings are emitted
    again. Intended for tests and for callers that deliberately re-parse a
    different model file in the same process."""
    _WARNED_UNPARSED_LHS.clear()
    _WARNED_DUPLICATE_LHS.clear()


def _is_numeric(value) -> bool:
    """Real number of any stdlib/NumPy flavour (int, float, np.integer,
    np.floating, Fraction, Decimal); booleans (including np.bool_) are not.
    Decimal registers only as numbers.Number, hence the explicit union."""
    if isinstance(value, (bool, np.bool_)):
        return False
    return isinstance(value, (numbers.Real, Decimal))


def is_scalar_shock(shock) -> bool:
    """True for numeric scalars (Python or NumPy, including numeric 0-d
    arrays). Booleans are NOT scalars here — True/False as a shock is a
    caller bug and both helpers reject it explicitly; likewise a 0-d array
    of bool or string dtype is not a scalar shock.
    """
    if _is_numeric(shock):
        return True
    return (
        isinstance(shock, np.ndarray)
        and shock.ndim == 0
        and np.issubdtype(shock.dtype, np.number)
        and not np.issubdtype(shock.dtype, np.bool_)
    )


def shock_path(shock, periods: int) -> "list[float]":
    """Normalize a shock spec to a per-quarter list of floats.

    A numeric scalar repeats for ``periods`` quarters; an iterable of numbers
    (list/tuple, ndarray, Series) is a per-quarter path whose length overrides
    ``periods``. Booleans, strings, bytes, and mappings — as the spec or as
    path elements — are rejected with TypeError; an empty path raises
    ValueError.
    """
    from collections.abc import Mapping

    if isinstance(shock, (bool, np.bool_, str, bytes)) or isinstance(shock, Mapping):
        raise TypeError(
            "shock must be a number or a sequence of numbers, got "
            f"{type(shock).__name__}"
        )
    if is_scalar_shock(shock):
        return [float(shock)] * periods
    values = []
    for s in shock:
        if not _is_numeric(s):
            raise TypeError(
                f"shock path elements must be numbers, got {type(s).__name__}"
            )
        values.append(float(s))
    if not values:
        raise ValueError("shock sequence must be non-empty")
    return values


class FullOBRSolver:
    """Solve the complete OBR model as published."""

    def __init__(
        self,
        verbose: bool = True,
        include_behavioral: bool = False,
        hist_floor: str = "2016Q1",
    ):
        self.verbose = verbose
        self._code_cache = {}  # python_expr -> compiled code object
        self._hist_floor = hist_floor  # earliest period to initialise/solve over

        # Load data and equations.
        # In the October 2025 model code the behavioural equations (dlog, d) are
        # published uncommented, so they are parsed as part of the full 372-equation
        # model with include_behavioral=False. (The include_behavioral=True path
        # un-comments lines beginning with 'dlog/'d, which is only correct for older
        # model files where those equations were commented out, and on the current
        # file it would resurrect a commented, paren-unbalanced draft line.)
        self.data = load_obr_data()
        self.index = self.data.index
        self.equations = parse_model_file(
            str(ensure_model_code()), include_behavioral=include_behavioral
        )

        # Guard against the include_behavioral=True trap on current model files:
        # the October 2025 file publishes the behavioural equations uncommented,
        # and the un-commenting path resurrects a paren-unbalanced draft line
        # that silently collapses the model from ~372 to ~36 equations.
        if include_behavioral and len(self.equations) < 100:
            raise ValueError(
                f"include_behavioral=True parsed only {len(self.equations)} equations. "
                "The October 2025 model file publishes behavioural equations "
                "uncommented, so include_behavioral=True (which un-comments "
                "'dlog/'d lines) is only correct for pre-2025 model files. "
                "Use include_behavioral=False for this file."
            )

        if self.verbose:
            print(f"Loaded {len(self.equations)} equations")
            print(f"Data has {len(self.data.columns)} variables")

        # Extract base values for @elem
        self.base_values = self._extract_base_values()

        # Initialize missing variables
        self._initialize_missing_variables()

        # Seed the calibration constants (adjustments, residuals, *BASE
        # normalisers, base deflator levels) the published data does not supply.
        self._seed_constants()

        # Build equation index
        self._build_equation_index()

        # Initialize model by solving historical periods
        self._initialize_historical()

        # Compute residuals for behavioral equations
        self._compute_residuals()

        # Structural add-factors {(var, t): value}, applied in every solve
        # regardless of shock mode (see solve_period). Empty by default; the
        # investment closure populates it to anchor the dlog(IBUSX) baseline.
        self.add_factors = {}

        # Gauss-Seidel iteration cap (see solve()). Overridden per-solver.
        self.max_iter = 60

        # Store baseline
        self.baseline = self.data.copy()

    def _extract_base_values(self) -> dict:
        """Extract base period values for @elem lookups."""
        values = {}
        for col in self.data.columns:
            for period in self.data.index:
                key = f"{col}_{period}"
                val = self.data.loc[period, col]
                if pd.notna(val):
                    values[key] = val
        return values

    def _initialize_missing_variables(self):
        """Initialize variables that are computed by equations but not in data."""
        # Find all variables referenced in equations. Identifiers are mixed
        # case (OAHHx, DIPHHmf, ...); exclude @functions (e.g. @TREND) via the
        # lookbehind and function names via RESERVED_WORDS.
        all_vars = set()
        for eq in self.equations:
            vars_in_eq = re.findall(rf"(?<![@\w])({IDENT})\b", eq.original)
            all_vars.update(v for v in vars_in_eq if v not in RESERVED_WORDS)

        # Add missing variables with NaN (will be computed)
        # Use concat for efficiency instead of adding columns one by one
        missing = all_vars - set(self.data.columns)
        if missing:
            missing_df = pd.DataFrame(
                np.nan, index=self.data.index, columns=list(missing)
            )
            self.data = pd.concat([self.data, missing_df], axis=1)

        if self.verbose:
            print(f"Initialized {len(missing)} missing variables")

        # Add proxy variables
        if "GPW" not in self.data.columns or self.data["GPW"].isna().all():
            if "HHPHYSA" in self.data.columns:
                self.data["GPW"] = self.data["HHPHYSA"] / 1000

        if "NFWPE" not in self.data.columns or self.data["NFWPE"].isna().all():
            if "HHFINA" in self.data.columns:
                self.data["NFWPE"] = self.data["HHFINA"]

    def _build_equation_index(self):
        """Build index of which variable each equation computes."""
        self.eq_for_var = {}  # var -> equation
        self.var_for_eq = {}  # equation index -> var
        self.unparsed_lhs = {}  # non-identifier LHS key -> raw LHS string

        for i, eq in enumerate(self.equations):
            var = self._extract_lhs_var(eq.lhs)
            if not re.fullmatch(IDENT, var):
                # The index is rebuilt on every clone()/make_exogenous()/
                # swap_closure(), so warning unconditionally floods stderr with
                # the same handful of messages during a normal shock run. The
                # condition is a property of the parsed model file, not of this
                # solver instance, so report each distinct LHS once per process
                # and record it on the instance for programmatic inspection.
                self.unparsed_lhs[var] = eq.lhs
                if var not in _WARNED_UNPARSED_LHS:
                    _WARNED_UNPARSED_LHS.add(var)
                    warnings.warn(
                        f"Equation LHS parsed to non-identifier {var!r} "
                        f"(from LHS {eq.lhs!r}) — possible corrupted/unsupported "
                        "LHS form. This equation never fires, so the variable it "
                        "should compute stays at its data/last-solved value. "
                        "Warned once per process; see solver.unparsed_lhs for "
                        "the full set.",
                        stacklevel=2,
                    )
            if var in self.eq_for_var:
                if var not in _WARNED_DUPLICATE_LHS:
                    _WARNED_DUPLICATE_LHS.add(var)
                    warnings.warn(
                        f"Duplicate equation for variable {var!r}; the later "
                        "equation overwrites the earlier in the index. "
                        "Warned once per process.",
                        stacklevel=2,
                    )
            self.eq_for_var[var] = eq
            self.var_for_eq[i] = var

        if self.verbose:
            print(f"Built equation index for {len(self.eq_for_var)} variables")

    def _seed_constants(self):
        """Set calibration constants the published data does not supply, so the
        cost-competitiveness and government-pay blocks (and everything downstream)
        stop evaluating to NaN. For transmission these need to be finite and
        constant; the exact base-year levels affect the level, not the shock
        response. The *BASE normalisers are otherwise 2009 averages that @elem
        cannot resolve here (no 2009 history for the base variables).
        """

        def fill(col, value):
            if col in self.data.columns and np.isfinite(value):
                mask = ~np.isfinite(self.data[col].to_numpy(dtype=float))
                if mask.any():
                    self.data.loc[mask, col] = value

        def base_year_value(var, default):
            if var not in self.data.columns:
                return default
            s = self.data[var]
            # prefer the model's 2009 base year; else rebase to the most recent
            # year of data so the cost-competitiveness ratios sit near 1.
            yr = s[[p.year == 2009 for p in self.index]]
            if yr.notna().any():
                return float(yr.mean())
            fin = s.dropna()
            if len(fin):
                return float(fin.iloc[-min(len(fin), 4) :].mean())  # recent rebase
            return default

        def ratio_base(num, den, default):
            """Base value for a ratio normaliser (e.g. OILBASE = PBRENT/RXD),
            evaluated at the most recent period where both inputs exist."""
            if num not in self.data.columns or den not in self.data.columns:
                return default
            both = self.data[[num, den]].dropna()
            if not len(both):
                return default
            r = (both[num] / both[den]).iloc[-min(len(both), 4) :]
            return float(r.mean()) if r.notna().any() else default

        # multiplicative adjustment factors -> 1, additive residuals -> 0
        for col in self.data.columns:
            if col.endswith("ADJ"):
                fill(col, 1.0)
            elif col.endswith("RES"):
                fill(col, 0.0)

        # base-year normalisers. OILBASE = (PBRENT/RXD), TXRATEBASE = (BPAPS/GVA)
        # are ratios, computed from data; the rest rebase from their base series.
        explicit_base = {
            "OILBASE": ratio_base("PBRENT", "RXD", 40.0),
            "TXRATEBASE": ratio_base("BPAPS", "GVAFC", 0.1),
        }
        for col in self.data.columns:
            if (
                col.endswith("BASE")
                and not np.isfinite(self.data[col].to_numpy(dtype=float)).any()
            ):
                if col in explicit_base:
                    fill(col, explicit_base[col])
                else:
                    fill(col, base_year_value(col[:-4], 100.0))

        # starting levels for price-index deflators with no history
        for col in ("PMNOG", "PMS", "ULCMS"):
            if (
                col in self.data.columns
                and not np.isfinite(self.data[col].to_numpy(dtype=float)).any()
            ):
                fill(col, 100.0)

        # WPG (world prices) is an OBR external assumption absent from the data; it
        # blocks the export/import deflator equations (dlog(PXNOG)/dlog(PMNOG)),
        # freezing nominal trade and the trade balance. Proxy it with producer
        # prices (PPIY) so the deflators compute and can be add-factored.
        # World equity prices (WEQPR) and the long / corporate-bond rates (ROLT,
        # ROCB) are OBR external assumptions absent from the data; they drive the
        # overseas rates of return (REXC/REXD) behind investment income and the
        # current account. Proxy world prices/equities with their UK analogues and
        # the rates with the gilt yield, so the block computes instead of freezing.
        def proxy(col, src, default):
            if (
                col in self.data.columns
                and not np.isfinite(self.data[col].to_numpy(dtype=float)).any()
            ):
                if src in self.data.columns and self.data[src].notna().any():
                    self.data[col] = self.data[src].to_numpy()
                else:
                    fill(col, default)

        proxy("WPG", "PPIY", 100.0)  # world prices ~ producer prices
        # NOTE: proxying WEQPR/ROLT/ROCB (the investment-income drivers) was tried
        # to improve the current account, but it destabilised business investment
        # through the dividend/profit feedback (IBUS 7% -> 19%) for only a marginal
        # CA gain. Left out — the current account stays the open channel.

        fill("TCPRO", 0.25)

        # NOTE: a blanket "seed every still-NaN variable so it computes" was tried
        # and reverted — the circular fiscal/financial sub-blocks (interest,
        # dividends, the financial account) are numerically unstable without their
        # real balancing data and diverge to ~1e140 when run raw. Leaving those
        # variables at passthrough is safer than live-and-exploding. Reviving them
        # needs the actual data, not a starting seed.

    def _initialize_historical(self):
        """Initialize missing variables by solving through historical periods.

        The OBR data has ~125 variables but the model needs ~640. We solve
        the identity equations through history to populate the missing
        intermediate variables.
        """
        # Find the first period with data
        start_t = 0
        for t in range(len(self.data)):
            if self.data.iloc[t].notna().sum() > 50:
                start_t = t
                break

        # Only initialise recent history. Earlier periods are not needed for the
        # lags/levels at any realistic forecast start, and solving 50+ years of
        # history dominated build time (the snapshot pushes data back to 1972).
        try:
            start_t = max(start_t, self.period_idx(self._hist_floor))
        except Exception as e:
            warnings.warn(
                f"hist_floor {self._hist_floor!r} not found in data index "
                f"({type(e).__name__}: {e}); initialising from "
                f"{self.index[start_t]} instead.",
                stacklevel=2,
            )

        if self.verbose:
            print(f"Initializing from period {self.index[start_t]}")

        # Initialize key variables that require starting values
        # BPA (Basic Price Adjustment) is typically ~15% of GDP
        # GGVA (Government GVA) is typically ~20% of GDP
        col_idx = {col: self.data.columns.get_loc(col) for col in self.data.columns}

        for t in range(start_t, len(self.data)):
            gdpm = self._get("GDPM", t)
            etlfs = self._get("ETLFS", t)

            if np.isfinite(gdpm):
                # BPA ≈ 15% of GDP (taxes on products - subsidies)
                if np.isnan(self._get("BPA", t)):
                    self.data.iloc[t, col_idx["BPA"]] = gdpm * 0.15

                # GGVA ≈ 20% of GDP (government value added)
                if np.isnan(self._get("GGVA", t)):
                    self.data.iloc[t, col_idx["GGVA"]] = gdpm * 0.20

            if np.isfinite(etlfs):
                # EMS (market sector employment) ≈ 80% of total employment
                if np.isnan(self._get("EMS", t)):
                    self.data.iloc[t, col_idx["EMS"]] = (
                        etlfs * 0.80 * 1000
                    )  # ETLFS in thousands

                # ET (total employment) from ETLFS
                if np.isnan(self._get("ET", t)):
                    self.data.iloc[t, col_idx["ET"]] = etlfs * 1000

            # Initialize corporation tax parameters
            # TCPRO = corporation tax rate (25% from April 2023)
            if "TCPRO" in col_idx and np.isnan(self._get("TCPRO", t)):
                self.data.iloc[t, col_idx["TCPRO"]] = 0.25

            # DB, DP, DV = capital allowance rates (depreciation deductions)
            # Typical values: DB=0.18 (plant), DP=0.06 (buildings), DV=0.25 (vehicles)
            if "DB" in col_idx and np.isnan(self._get("DB", t)):
                self.data.iloc[t, col_idx["DB"]] = 0.18
            if "DP" in col_idx and np.isnan(self._get("DP", t)):
                self.data.iloc[t, col_idx["DP"]] = 0.06
            if "DV" in col_idx and np.isnan(self._get("DV", t)):
                self.data.iloc[t, col_idx["DV"]] = 0.25

            # WB, WP, WV = weights for capital types (sum to 1)
            if "WB" in col_idx and np.isnan(self._get("WB", t)):
                self.data.iloc[t, col_idx["WB"]] = 0.6
            if "WP" in col_idx and np.isnan(self._get("WP", t)):
                self.data.iloc[t, col_idx["WP"]] = 0.2
            if "WV" in col_idx and np.isnan(self._get("WV", t)):
                self.data.iloc[t, col_idx["WV"]] = 0.2

            # COCU = user cost of capital (pre-tax), typically ~0.1-0.15
            if "COCU" in col_idx and np.isnan(self._get("COCU", t)):
                self.data.iloc[t, col_idx["COCU"]] = 0.12

            # CBIUD = CBI uncertainty index (exogenous, normalize to 0)
            if "CBIUD" in col_idx and np.isnan(self._get("CBIUD", t)):
                self.data.iloc[t, col_idx["CBIUD"]] = 0

            # Initialize missing investment components
            # PCLEB = private capital leasing to business (small component)
            if "PCLEB" in col_idx and np.isnan(self._get("PCLEB", t)):
                self.data.iloc[t, col_idx["PCLEB"]] = 0

            # IPRL = private landlord investment (included in housing investment)
            if "IPRL" in col_idx and np.isnan(self._get("IPRL", t)):
                self.data.iloc[t, col_idx["IPRL"]] = 0

            # RDELTA = depreciation rate, typically ~0.025 (10% annual)
            if "RDELTA" in col_idx and np.isnan(self._get("RDELTA", t)):
                self.data.iloc[t, col_idx["RDELTA"]] = 0.025

            # Initialize business investment components if we have IF
            if_val = self._get("IF", t)
            if np.isfinite(if_val):
                # IBUS ≈ 50% of total investment (business investment)
                if "IBUS" in col_idx and np.isnan(self._get("IBUS", t)):
                    self.data.iloc[t, col_idx["IBUS"]] = if_val * 0.5

                # IBUSX = real business investment (similar scale to IBUS)
                if "IBUSX" in col_idx and np.isnan(self._get("IBUSX", t)):
                    self.data.iloc[t, col_idx["IBUSX"]] = if_val * 0.5

            # Initialize capital stock (KMSXH) from steady-state relationship
            # K = I / (g + delta) where g ≈ 0.005 (quarterly growth), delta ≈ 0.025
            if "KMSXH" in col_idx and np.isnan(self._get("KMSXH", t)):
                ibusx = self._get("IBUSX", t)
                if np.isfinite(ibusx):
                    # KMSXH is in £bn, IBUSX in £m
                    self.data.iloc[t, col_idx["KMSXH"]] = (ibusx / 1000) / 0.03

        # Solve identity equations only (no residuals yet)
        # Need multiple passes because equations may depend on each other
        identity_eqs = [
            eq
            for eq in self.equations
            if not (
                "/" in eq.lhs
                or eq.lhs.lower().startswith("dlog(")
                or eq.lhs.lower().startswith("d(")
            )
        ]

        col_idx = {col: self.data.columns.get_loc(col) for col in self.data.columns}

        initialized = 0
        self.init_failures = Counter()  # LHS var -> failed evaluations
        for t in range(start_t, len(self.data)):
            # Multiple passes to handle dependencies
            for _ in range(5):
                v = {col: self.data.iloc[t][col] for col in self.data.columns}
                ctx = {
                    "np": np,
                    "__builtins__": {},
                    "v": v,
                    "_lag": lambda var, lag, t=t: self._lag(var, lag, t),
                    "_lead": lambda var, lead, t=t: self._lead(var, lead, t),
                    "_recode": lambda t_arg, period, op, tv, fv, t=t: self._recode(
                        t, period, op, tv, fv
                    ),
                    "_trend": lambda t_arg, base, t=t: self._trend(t, base),
                    "_elem": self._elem,
                    "t": t,
                }

                pass_initialized = 0
                for eq in identity_eqs:
                    var = self._extract_lhs_var(eq.lhs)
                    current_val = v.get(var, np.nan)

                    # Only initialize if currently NaN
                    if not np.isfinite(current_val):
                        try:
                            new_val = eval(self._compiled(eq.python_expr), ctx)
                            if np.isfinite(new_val):
                                if var in col_idx:
                                    self.data.iloc[t, col_idx[var]] = new_val
                                v[var] = new_val
                                initialized += 1
                                pass_initialized += 1
                        except Exception:
                            # Count (don't raise): many equations legitimately
                            # fail here until their inputs get initialized.
                            self.init_failures[var] += 1

                # Stop if no new values computed this pass
                if pass_initialized == 0:
                    break

        if self.verbose:
            print(f"Initialized {initialized} values from identities")
            if self.init_failures:
                top = self.init_failures.most_common(5)
                print(
                    f"  ({sum(self.init_failures.values())} failed identity "
                    f"evaluations across {len(self.init_failures)} equations; "
                    "top: " + ", ".join(f"{v}({n})" for v, n in top) + ")"
                )

    def _compute_residuals(self):
        """Compute residuals between OBR data and equation predictions.

        For each behavioral equation (dlog, d, ratio), we compute what the
        equation predicts and compare to the actual data. The residual is
        stored and added back during solve to ensure the model matches
        the OBR baseline exactly.

        Only computes for forecast period (2024Q1 onwards) for efficiency.
        """
        self.residuals = {}  # {(var, t): residual}

        # Only compute for forecast period
        try:
            start_t = self.period_idx("2024Q1")
        except Exception:
            start_t = len(self.data) - 20  # Last 20 periods

        # Pre-filter behavioral equations.
        # Residuals/add-factors are intentionally NOT computed for the
        # @recode/@TREND-driven equations: held add-factors overshoot on them,
        # so they project structurally (forecasts notably better — e.g. trade
        # balance 11% vs 29% with held add-factors). This exclusion is explicit
        # here (skip anything calling _recode/_trend) so the remaining context
        # lambdas can carry the correct signatures without silently changing
        # which equations get add-factored.
        behavioral_eqs = [
            eq
            for eq in self.equations
            if (
                "/" in eq.lhs
                or eq.lhs.lower().startswith("dlog(")
                or eq.lhs.lower().startswith("d(")
            )
            and "_recode(" not in eq.python_expr
            and "_trend(" not in eq.python_expr
        ]

        self.residual_failures = Counter()  # LHS var -> failed evaluations
        for t in range(max(1, start_t), len(self.data)):
            # Build context once per period. Transpiled call forms are
            # _recode(t, period, op, tv, fv) and _trend(t, base); the lambdas
            # must match that arity (t_arg is ignored, the closure's t is used).
            v = {col: self.data.iloc[t][col] for col in self.data.columns}
            ctx = {
                "np": np,
                "__builtins__": {},
                "v": v,
                "_lag": lambda var, lag, t=t: self._lag(var, lag, t),
                "_lead": lambda var, lead, t=t: self._lead(var, lead, t),
                "_recode": lambda t_arg, period, op, tv, fv, t=t: self._recode(
                    t, period, op, tv, fv
                ),
                "_trend": lambda t_arg, base, t=t: self._trend(t, base),
                "_elem": self._elem,
                "t": t,
            }

            for eq in behavioral_eqs:
                var, kind, lag_n = self._parse_lhs(eq.lhs)
                try:
                    rhs_val = eval(self._compiled(eq.python_expr), ctx)
                    actual_val = self._get(var, t)

                    predicted = self._lhs_new_value(var, kind, lag_n, rhs_val, t)

                    if np.isfinite(actual_val) and np.isfinite(predicted):
                        self.residuals[(var, t)] = actual_val - predicted
                except Exception:
                    # Count (don't raise): NaN-input equations are expected.
                    self.residual_failures[var] += 1

        if self.verbose:
            print(f"Computed {len(self.residuals)} residuals")
            if self.residual_failures:
                top = self.residual_failures.most_common(5)
                print(
                    f"  ({sum(self.residual_failures.values())} failed residual "
                    f"evaluations across {len(self.residual_failures)} equations; "
                    "top: " + ", ".join(f"{v}({n})" for v, n in top) + ")"
                )

    def _parse_lhs(self, lhs: str) -> tuple:
        """Parse an equation LHS into (var, kind, lag).

        Kinds:
          'ratio':  X / X(-n) = rhs      ->  X = X(-n) * rhs
          'growth': d(X) / X(-n) = rhs   ->  X = X(-1) + rhs * X(-n)
          'dlog':   dlog(X) = rhs        ->  X = X(-1) * exp(rhs)
          'd':      d(X) = rhs           ->  X = X(-1) + rhs
          'level':  X = rhs              ->  X = rhs
        """
        cached = _LHS_CACHE.get(lhs)
        if cached is not None:
            return cached

        # Collapse whitespace so forms like 'dlog (X)' / 'd (X) / X( - 4 )'
        # parse the same as their tight-spaced equivalents.
        s = re.sub(r"\s+", "", lhs)
        if "/" in s:
            num, den = s.split("/", 1)
            num, den = num.strip(), den.strip()
            # Parse the actual lag from the denominator, e.g. PCE(-4) -> 4
            m = re.match(rf"({IDENT})\(\s*-\s*(\d+)\s*\)$", den)
            lag = int(m.group(2)) if m else 1
            if num.lower().startswith("d(") and num.endswith(")"):
                # growth-rate LHS: d(X) / X(-n)
                parsed = (num[2:-1].strip(), "growth", lag)
            else:
                parsed = (num, "ratio", lag)
        elif s.lower().startswith("dlog("):
            parsed = (s[5:-1].strip(), "dlog", 1)
        elif s.lower().startswith("d("):
            parsed = (s[2:-1].strip(), "d", 1)
        elif s.startswith("@IDENTITY"):
            parsed = (s.replace("@IDENTITY", "").strip(), "level", 0)
        else:
            parsed = (s, "level", 0)

        _LHS_CACHE[lhs] = parsed
        return parsed

    def _extract_lhs_var(self, lhs: str) -> str:
        """Extract variable name from LHS."""
        return self._parse_lhs(lhs)[0]

    def _lhs_new_value(
        self, var: str, kind: str, lag: int, rhs_val: float, t: int
    ) -> float:
        """Compute the implied LHS-variable value from an evaluated RHS."""
        if kind == "ratio":
            lag_val = self._lag(var, lag, t)
            return lag_val * rhs_val if np.isfinite(lag_val) else np.nan
        if kind == "growth":
            # d(X)/X(-n) = rhs  <=>  (X - X(-1)) / X(-n) = rhs
            #                   =>   X = X(-1) + rhs * X(-n)
            # (For n=1 this reduces to X(-1) * (1 + rhs).)
            prev = self._lag(var, 1, t)
            lag_val = self._lag(var, lag, t)
            if np.isfinite(prev) and np.isfinite(lag_val):
                return prev + rhs_val * lag_val
            return np.nan
        if kind == "dlog":
            lag_val = self._lag(var, lag, t)
            return lag_val * np.exp(rhs_val) if np.isfinite(lag_val) else np.nan
        if kind == "d":
            lag_val = self._lag(var, lag, t)
            return lag_val + rhs_val if np.isfinite(lag_val) else np.nan
        return rhs_val

    def _get(self, var: str, t: int) -> float:
        if var not in self.data.columns or t < 0 or t >= len(self.data):
            return np.nan
        return self.data.iloc[t][var]

    def _set(self, var: str, t: int, val: float):
        if var not in self.data.columns:
            self.data[var] = np.nan
        self.data.iloc[t, self.data.columns.get_loc(var)] = val

    def _lag(self, var: str, lag: int, t: int) -> float:
        return self._get(var, t - lag)

    def _lead(self, var: str, lead: int, t: int) -> float:
        """Future-dated term VAR(+n): value at t + n."""
        return self._get(var, t + lead)

    def _recode(
        self, t: int, period: str, op: str, true_val: float, false_val: float
    ) -> float:
        target = pd.Period(period, freq="Q")
        current = self.index[t]
        if op == "=":
            return true_val if current == target else false_val
        elif op == ">=":
            return true_val if current >= target else false_val
        elif op == "<=":
            return true_val if current <= target else false_val
        elif op == ">":
            return true_val if current > target else false_val
        elif op == "<":
            return true_val if current < target else false_val
        return false_val

    def _trend(self, t: int, base: str) -> float:
        try:
            base_p = pd.Period(base, freq="Q")
            base_idx = self.index.get_loc(base_p)
            return float(t - base_idx)
        except Exception:
            return 0.0

    def _elem(self, var: str, period: str) -> float:
        key = f"{var}_{period}"
        return self.base_values.get(key, np.nan)

    def _compiled(self, expr: str):
        """Compile an equation RHS once and cache it; eval(code) is far faster
        than eval(string) in the inner Gauss-Seidel loop."""
        code = self._code_cache.get(expr)
        if code is None:
            code = compile(expr, "<eq>", "eval")
            self._code_cache[expr] = code
        return code

    def _build_context(self, t: int) -> dict:
        """Build evaluation context for time t."""
        v = {col: self.data.iloc[t][col] for col in self.data.columns}
        return {
            "np": np,
            "__builtins__": {},
            "v": v,
            "_lag": lambda var, lag: self._lag(var, lag, t),
            "_lead": lambda var, lead: self._lead(var, lead, t),
            "_recode": lambda t_arg, period, op, tv, fv: self._recode(
                t, period, op, tv, fv
            ),
            "_trend": lambda t_arg, base: self._trend(t, base),
            "_elem": self._elem,
            "t": t,
        }

    def clone(self) -> "FullOBRSolver":
        """Fast copy that shares the immutable, expensive-to-build state (parsed
        equations, compiled-code cache, base values, residuals, index) and copies
        only the mutable data frame. Lets callers build/solve a baseline once and
        branch many shocked scenarios off it without paying the build cost again.
        """
        new = FullOBRSolver.__new__(FullOBRSolver)
        new.verbose = self.verbose
        new._code_cache = self._code_cache  # compiled code objects (immutable)
        new._hist_floor = self._hist_floor
        new.index = self.index
        new.base_values = self.base_values
        new.residuals = self.residuals
        # Own copy of the structural add-factors: a shocked clone must carry the
        # same held add-factors as its baseline so they cancel in the delta.
        new.add_factors = dict(getattr(self, "add_factors", {}))
        new.max_iter = getattr(self, "max_iter", 60)
        new.equations = list(self.equations)  # own list; shared eq objects
        new.data = self.data.copy()  # own data
        new.baseline = self.baseline
        new._shock_active = getattr(self, "_shock_active", False)
        new._build_equation_index()
        return new

    def swap_closure(self, remove_var: str, add_eq: ParsedEquation):
        """Swap model closure by removing one equation and adding another.

        For fiscal shock: remove DINV equation, add GDPM equation.
        """
        # Remove equation for remove_var
        self.equations = [
            eq for eq in self.equations if self._extract_lhs_var(eq.lhs) != remove_var
        ]

        # Add new equation
        self.equations.append(add_eq)

        # Rebuild index
        self._build_equation_index()

        if self.verbose:
            print(f"Swapped closure: removed {remove_var}, added {add_eq.lhs}")

    def make_exogenous(self, var: str):
        """Make a variable exogenous by removing its equation."""
        self.equations = [
            eq for eq in self.equations if self._extract_lhs_var(eq.lhs) != var
        ]
        self._build_equation_index()

        if self.verbose:
            print(f"Made {var} exogenous (removed equation)")

    def apply_shock(
        self,
        var: str,
        shock: "float | Iterable[float]",
        start: str,
        periods: int = 4,
    ):
        """Apply an additive shock to a variable.

        A numeric scalar ``shock`` (Python or NumPy, including 0-d arrays) is
        applied for ``periods`` quarters from ``start``. A sequence of
        per-quarter values is applied from ``start`` and its length overrides
        ``periods`` (externally costed reforms — e.g. a microsimulation
        revenue path — arrive as one value per quarter). Booleans, strings,
        and mappings are rejected.
        """
        # Validate everything BEFORE mutating solver state (make_exogenous
        # removes the equation and _shock_active disables residuals — neither
        # should happen if the shock spec or start period is invalid).
        scalar = is_scalar_shock(shock)
        values = shock_path(shock, periods)
        start_t = self.period_idx(start)

        self.make_exogenous(var)

        # Mark that we're in shock mode (disable residuals)
        self._shock_active = True

        for p, s in enumerate(values):
            t = start_t + p
            if t < len(self.data):
                self._set(var, t, self._get(var, t) + s)

        if self.verbose:
            if scalar:
                print(
                    f"Applied shock: {var} += {float(shock):+,.0f} for {periods} periods from {start}"
                )
            else:
                print(
                    f"Applied shock path: {var} += [{values[0]:+,.0f} … "
                    f"{values[-1]:+,.0f}] over {len(values)} periods from {start}"
                )

    def period_idx(self, period: str) -> int:
        return self.index.get_loc(pd.Period(period, freq="Q"))

    def solve_period(
        self, t: int, max_iter: int = 60, tol: float = 1e-6, stall_patience: int = 8
    ) -> int:
        """Solve all equations for period t using Gauss-Seidel.

        Records failure visibility without changing solve semantics:
        - ``self.eq_failures`` (Counter) is incremented with the LHS var each
          time an equation raises during evaluation (known-dead equations are
          expected — they are counted, never raised).
        - ``self._last_period_exit`` records how the iteration ended:
          'tol' (converged), 'stall' (stall break), or 'max_iter'.
        """
        # Pre-compute column indices for faster access
        col_idx = {col: self.data.columns.get_loc(col) for col in self.data.columns}

        if not hasattr(self, "eq_failures"):
            self.eq_failures = Counter()

        best_change = float("inf")
        stall = 0
        self._last_period_exit = "max_iter"
        for iteration in range(max_iter):
            max_change = 0.0

            # Build context once per iteration, use mutable v dict
            row = self.data.iloc[t]
            v = {col: row[col] for col in self.data.columns}

            ctx = {
                "np": np,
                "__builtins__": {},
                "v": v,
                "_lag": lambda var, lag: self._lag(var, lag, t),
                "_lead": lambda var, lead: self._lead(var, lead, t),
                "_recode": lambda t_arg, period, op, tv, fv: self._recode(
                    t, period, op, tv, fv
                ),
                "_trend": lambda t_arg, base: self._trend(t, base),
                "_elem": self._elem,
                "t": t,
            }

            for eq in self.equations:
                var, kind, lag_n = self._parse_lhs(eq.lhs)
                try:
                    old_val = v.get(var, np.nan)

                    rhs_val = eval(self._compiled(eq.python_expr), ctx)

                    # Compute new value based on equation form
                    new_val = self._lhs_new_value(var, kind, lag_n, rhs_val, t)

                    if np.isfinite(new_val):
                        # Add residual adjustment for behavioral equations
                        # But only if we're not in shock mode (baseline preserved)
                        if not hasattr(self, "_shock_active") or not self._shock_active:
                            residual = self.residuals.get((var, t), 0)
                            new_val += residual

                        # Structural add-factors: unlike anchoring residuals
                        # (above, disabled in shock mode), these are applied
                        # ALWAYS — in the baseline and every shocked clone alike.
                        # They therefore cancel in a base-vs-shock delta and
                        # only re-centre the shared level. The investment closure
                        # uses this to hold the reconstructed dlog(IBUSX) baseline
                        # on the OBR published path (see reform_analysis) without
                        # contaminating the corporation-tax response.
                        af = getattr(self, "add_factors", None)
                        if af:
                            new_val += af.get((var, t), 0.0)

                        # Update both the DataFrame and the context dict
                        if var in col_idx:
                            self.data.iloc[t, col_idx[var]] = new_val
                        v[var] = new_val

                        if np.isfinite(old_val):
                            # Relative change scaled by the larger of the old
                            # and new magnitudes, with an absolute floor so
                            # near-zero variables still register movement.
                            # Using max(|old|, |new|) keeps the criterion
                            # symmetric and stops a near-zero *old* value from
                            # inflating the ratio of an already-tiny update
                            # (which forced periods to hit the stall break
                            # mid-oscillation and desynchronised base vs shock
                            # runs). The 1e-6 floor stays well below the
                            # model's smallest meaningful scales (rates ~0.1)
                            # so small-magnitude channels still propagate.
                            change = abs(new_val - old_val) / max(
                                abs(old_val), abs(new_val), 1e-6
                            )
                            max_change = max(max_change, change)
                        else:
                            # NaN -> finite transition is a change; the period
                            # must not report converged while values appear.
                            max_change = max(max_change, 1.0)
                except Exception:
                    # Skip equations that can't be evaluated, but count them
                    # so dead equations are visible in the solve report.
                    self.eq_failures[var] += 1

            if max_change < tol:
                self._last_period_exit = "tol"
                return iteration + 1

            # Stall break: many periods never converge (a few equations oscillate
            # or overflow from unit issues), so stop once max_change stops
            # improving instead of burning all max_iter on them.
            if max_change < best_change - 1e-9:
                best_change = max_change
                stall = 0
            else:
                stall += 1
                if stall >= stall_patience:
                    self._last_period_exit = "stall"
                    return iteration + 1

        return max_iter

    def diagnose_period(self, t: int) -> list:
        """Non-mutating diagnostic for the silent-skip problem.

        Evaluates every equation once at period ``t`` against the current
        (already-solved) values and reports the equations that ``solve_period``
        would have silently dropped: those that raise, and those whose RHS
        evaluates to a non-finite value. For the non-finite ones it names the
        NaN inputs, which is usually where a transmission chain breaks.

        Returns a list of dicts: {var, lhs, status, reason}.
        """
        row = self.data.iloc[t]
        v = {col: row[col] for col in self.data.columns}
        ctx = {
            "np": np,
            "__builtins__": {},
            "v": v,
            "_lag": lambda var, lag: self._lag(var, lag, t),
            "_lead": lambda var, lead: self._lead(var, lead, t),
            "_recode": lambda t_arg, period, op, tv, fv: self._recode(
                t, period, op, tv, fv
            ),
            "_trend": lambda t_arg, base: self._trend(t, base),
            "_elem": self._elem,
            "t": t,
        }

        def nan_inputs(expr):
            bad = []
            for m in re.finditer(r"v\['([A-Za-z0-9_]+)'\]", expr):
                name = m.group(1)
                if name in v and not np.isfinite(v.get(name, np.nan)):
                    bad.append(name)
            for m in re.finditer(r"_lag\('([A-Za-z0-9_]+)',\s*(\d+)\)", expr):
                name, lag = m.group(1), int(m.group(2))
                if not np.isfinite(self._lag(name, lag, t)):
                    bad.append(f"{name}(-{lag})")
            return sorted(set(bad))

        out = []
        for eq in self.equations:
            var = self._extract_lhs_var(eq.lhs)
            try:
                val = eval(self._compiled(eq.python_expr), ctx)
                if not np.isfinite(val):
                    inputs = nan_inputs(eq.python_expr)
                    out.append(
                        {
                            "var": var,
                            "lhs": eq.lhs,
                            "status": "nonfinite",
                            "reason": ("NaN inputs: " + ", ".join(inputs))
                            if inputs
                            else "evaluates to NaN/inf",
                        }
                    )
            except Exception as e:
                out.append(
                    {
                        "var": var,
                        "lhs": eq.lhs,
                        "status": "error",
                        "reason": f"{type(e).__name__}: {e}",
                    }
                )
        return out

    def solve(self, start: str, end: str) -> dict:
        """Solve model from start to end period.

        Populates ``self.last_solve_report`` with per-solve failure counters
        and per-period convergence status (nothing is raised — the model has
        known-dead equations, which are counted rather than fatal).
        """
        t_start = self.period_idx(start)
        t_end = self.period_idx(end)

        self.eq_failures = Counter()
        exit_status = {}
        nonconverged = []

        # Per-solver iteration cap. Default (60) is unchanged for the demand
        # closure and the anchored baseline (which stall out at ~8 iterations
        # anyway). The investment closure sets a lower cap: its slow-converging
        # tail is a single rest-of-world national-accounts variable (NAOTAROW)
        # that is off the corporation-tax -> investment chain, so grinding it to
        # tol wastes ~50 iterations/period without moving the investment
        # response (see reform_analysis._IC_MAX_ITER).
        max_iter = getattr(self, "max_iter", 60)

        results = {}
        for t in range(t_start, t_end + 1):
            iters = self.solve_period(t, max_iter=max_iter)
            period = str(self.index[t])
            results[period] = iters
            status = getattr(self, "_last_period_exit", "unknown")
            exit_status[period] = status
            if status != "tol":
                nonconverged.append(period)
            if self.verbose:
                print(f"  {period}: {iters} iterations ({status})")

        self.last_solve_report = {
            "periods": t_end - t_start + 1,
            "eq_failures": dict(self.eq_failures),
            "exit_status": exit_status,
            "nonconverged": nonconverged,
        }

        if self.verbose:
            total_failures = sum(self.eq_failures.values())
            if total_failures:
                top = self.eq_failures.most_common(10)
                print(
                    f"Equation failures: {total_failures} evaluations across "
                    f"{len(self.eq_failures)} equations. Top: "
                    + ", ".join(f"{v}({n})" for v, n in top)
                )
            if nonconverged:
                print(
                    f"Non-converged periods ({len(nonconverged)}): "
                    + ", ".join(nonconverged)
                )

        return results


def run_fiscal_shock(shock_bn: float = 1.0):
    """Run fiscal shock using full OBR model."""
    print("=" * 70)
    print(f"FISCAL SHOCK ANALYSIS: £{shock_bn}bn Government Spending Increase")
    print("Using full OBR model equations")
    print("=" * 70)
    print()

    solver = FullOBRSolver(verbose=True)

    # Swap closure: DINV -> GDPM
    gdpm_eq = ParsedEquation(
        lhs="GDPM",
        rhs="CGG + CONS + IF + DINV + VAL + X - M + SDE",
        original="GDPM = CGG + CONS + IF + DINV + VAL + X - M + SDE",
        equation_type="identity",
        python_expr="v['CGG'] + v['CONS'] + v['IF'] + v['DINV'] + v['VAL'] + v['X'] - v['M'] + v['SDE']",
    )
    solver.swap_closure("DINV", gdpm_eq)

    # The control run must share the shocked run's structure (CGG exogenous,
    # residuals off, same starting data): comparing against the raw-data
    # baseline instead would attribute the model's own tracking drift to the
    # shock.
    solver.make_exogenous("CGG")
    solver._shock_active = True
    control = solver.clone()

    # Apply shock
    shock_m = shock_bn * 1000
    solver.apply_shock("CGG", shock_m, "2025Q1", periods=4)

    print()
    print("Solving model...")
    control.solve("2025Q1", "2027Q4")
    solver.solve("2025Q1", "2027Q4")

    # Compare to baseline
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print()

    print(f"{'Period':<10} {'ΔCGG':>12} {'ΔCONS':>12} {'ΔGDPM':>12} {'Multiplier':>12}")
    print("-" * 58)

    for t in range(solver.period_idx("2025Q1"), solver.period_idx("2027Q4") + 1):
        period = str(solver.index[t])

        cgg_base = control.data.iloc[t]["CGG"]
        cgg_curr = solver._get("CGG", t)
        delta_cgg = cgg_curr - cgg_base

        cons_base = control.data.iloc[t]["CONS"]
        cons_curr = solver._get("CONS", t)
        delta_cons = cons_curr - cons_base

        gdpm_base = control.data.iloc[t]["GDPM"]
        gdpm_curr = solver._get("GDPM", t)
        delta_gdpm = gdpm_curr - gdpm_base

        mult = delta_gdpm / delta_cgg if delta_cgg > 0 else np.nan
        mult_str = f"{mult:.2f}" if np.isfinite(mult) else "N/A"

        print(
            f"{period:<10} {delta_cgg:>+12,.0f} {delta_cons:>+12,.0f} {delta_gdpm:>+12,.0f} {mult_str:>12}"
        )

    return solver


if __name__ == "__main__":
    run_fiscal_shock(1.0)
