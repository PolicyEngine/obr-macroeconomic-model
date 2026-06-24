"""Full OBR model solver that initializes missing variables.

This solver:
1. Loads the OBR equations exactly as published
2. Initializes any missing variables to 0 (or computes from equations)
3. Solves the complete system using Gauss-Seidel iteration
4. Allows closure swaps for policy simulation
"""

import numpy as np
import pandas as pd
from pathlib import Path

from obr_macro.data import load_obr_data, DATA_DIR, ensure_model_code
from obr_macro.transpiler import parse_model_file, ParsedEquation


class FullOBRSolver:
    """Solve the complete OBR model as published."""

    def __init__(self, verbose: bool = True, include_behavioral: bool = False,
                 hist_floor: str = "2016Q1"):
        self.verbose = verbose
        self._code_cache = {}          # python_expr -> compiled code object
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
            str(ensure_model_code()),
            include_behavioral=include_behavioral
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
        import re

        # Find all variables referenced in equations
        all_vars = set()
        for eq in self.equations:
            vars_in_eq = re.findall(r'\b([A-Z][A-Z0-9_]*)\b', eq.original)
            all_vars.update(vars_in_eq)

        # Add missing variables with NaN (will be computed)
        # Use concat for efficiency instead of adding columns one by one
        missing = all_vars - set(self.data.columns)
        if missing:
            missing_df = pd.DataFrame(
                np.nan,
                index=self.data.index,
                columns=list(missing)
            )
            self.data = pd.concat([self.data, missing_df], axis=1)

        if self.verbose:
            print(f"Initialized {len(missing)} missing variables")

        # Add proxy variables
        if 'GPW' not in self.data.columns or self.data['GPW'].isna().all():
            if 'HHPHYSA' in self.data.columns:
                self.data['GPW'] = self.data['HHPHYSA'] / 1000

        if 'NFWPE' not in self.data.columns or self.data['NFWPE'].isna().all():
            if 'HHFINA' in self.data.columns:
                self.data['NFWPE'] = self.data['HHFINA']

    def _build_equation_index(self):
        """Build index of which variable each equation computes."""
        self.eq_for_var = {}  # var -> equation
        self.var_for_eq = {}  # equation index -> var

        for i, eq in enumerate(self.equations):
            var = self._extract_lhs_var(eq.lhs)
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
                return float(fin.iloc[-min(len(fin), 4):].mean())  # recent rebase
            return default

        def ratio_base(num, den, default):
            """Base value for a ratio normaliser (e.g. OILBASE = PBRENT/RXD),
            evaluated at the most recent period where both inputs exist."""
            if num not in self.data.columns or den not in self.data.columns:
                return default
            both = self.data[[num, den]].dropna()
            if not len(both):
                return default
            r = (both[num] / both[den]).iloc[-min(len(both), 4):]
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
            if col.endswith("BASE") and not np.isfinite(self.data[col].to_numpy(dtype=float)).any():
                if col in explicit_base:
                    fill(col, explicit_base[col])
                else:
                    fill(col, base_year_value(col[:-4], 100.0))

        # starting levels for price-index deflators with no history
        for col in ("PMNOG", "PMS", "ULCMS"):
            if col in self.data.columns and not np.isfinite(self.data[col].to_numpy(dtype=float)).any():
                fill(col, 100.0)

        # WPG (world prices) is an OBR external assumption absent from the data; it
        # blocks the export/import deflator equations (dlog(PXNOG)/dlog(PMNOG)),
        # freezing nominal trade and the trade balance. Proxy it with producer
        # prices (PPIY) so the deflators compute and can be add-factored.
        if "WPG" in self.data.columns and not np.isfinite(self.data["WPG"].to_numpy(dtype=float)).any():
            if "PPIY" in self.data.columns and self.data["PPIY"].notna().any():
                self.data["WPG"] = self.data["PPIY"].to_numpy()
            else:
                fill("WPG", 100.0)

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
        except Exception:
            pass

        if self.verbose:
            print(f"Initializing from period {self.index[start_t]}")

        # Initialize key variables that require starting values
        # BPA (Basic Price Adjustment) is typically ~15% of GDP
        # GGVA (Government GVA) is typically ~20% of GDP
        col_idx = {col: self.data.columns.get_loc(col) for col in self.data.columns}

        for t in range(start_t, len(self.data)):
            gdpm = self._get('GDPM', t)
            etlfs = self._get('ETLFS', t)

            if np.isfinite(gdpm):
                # BPA ≈ 15% of GDP (taxes on products - subsidies)
                if np.isnan(self._get('BPA', t)):
                    self.data.iloc[t, col_idx['BPA']] = gdpm * 0.15

                # GGVA ≈ 20% of GDP (government value added)
                if np.isnan(self._get('GGVA', t)):
                    self.data.iloc[t, col_idx['GGVA']] = gdpm * 0.20

            if np.isfinite(etlfs):
                # EMS (market sector employment) ≈ 80% of total employment
                if np.isnan(self._get('EMS', t)):
                    self.data.iloc[t, col_idx['EMS']] = etlfs * 0.80 * 1000  # ETLFS in thousands

                # ET (total employment) from ETLFS
                if np.isnan(self._get('ET', t)):
                    self.data.iloc[t, col_idx['ET']] = etlfs * 1000

            # Initialize corporation tax parameters
            # TCPRO = corporation tax rate (25% from April 2023)
            if 'TCPRO' in col_idx and np.isnan(self._get('TCPRO', t)):
                self.data.iloc[t, col_idx['TCPRO']] = 0.25

            # DB, DP, DV = capital allowance rates (depreciation deductions)
            # Typical values: DB=0.18 (plant), DP=0.06 (buildings), DV=0.25 (vehicles)
            if 'DB' in col_idx and np.isnan(self._get('DB', t)):
                self.data.iloc[t, col_idx['DB']] = 0.18
            if 'DP' in col_idx and np.isnan(self._get('DP', t)):
                self.data.iloc[t, col_idx['DP']] = 0.06
            if 'DV' in col_idx and np.isnan(self._get('DV', t)):
                self.data.iloc[t, col_idx['DV']] = 0.25

            # WB, WP, WV = weights for capital types (sum to 1)
            if 'WB' in col_idx and np.isnan(self._get('WB', t)):
                self.data.iloc[t, col_idx['WB']] = 0.6
            if 'WP' in col_idx and np.isnan(self._get('WP', t)):
                self.data.iloc[t, col_idx['WP']] = 0.2
            if 'WV' in col_idx and np.isnan(self._get('WV', t)):
                self.data.iloc[t, col_idx['WV']] = 0.2

            # COCU = user cost of capital (pre-tax), typically ~0.1-0.15
            if 'COCU' in col_idx and np.isnan(self._get('COCU', t)):
                self.data.iloc[t, col_idx['COCU']] = 0.12

            # CBIUD = CBI uncertainty index (exogenous, normalize to 0)
            if 'CBIUD' in col_idx and np.isnan(self._get('CBIUD', t)):
                self.data.iloc[t, col_idx['CBIUD']] = 0

            # Initialize missing investment components
            # PCLEB = private capital leasing to business (small component)
            if 'PCLEB' in col_idx and np.isnan(self._get('PCLEB', t)):
                self.data.iloc[t, col_idx['PCLEB']] = 0

            # IPRL = private landlord investment (included in housing investment)
            if 'IPRL' in col_idx and np.isnan(self._get('IPRL', t)):
                self.data.iloc[t, col_idx['IPRL']] = 0

            # RDELTA = depreciation rate, typically ~0.025 (10% annual)
            if 'RDELTA' in col_idx and np.isnan(self._get('RDELTA', t)):
                self.data.iloc[t, col_idx['RDELTA']] = 0.025

            # Initialize business investment components if we have IF
            if_val = self._get('IF', t)
            if np.isfinite(if_val):
                # IBUS ≈ 50% of total investment (business investment)
                if 'IBUS' in col_idx and np.isnan(self._get('IBUS', t)):
                    self.data.iloc[t, col_idx['IBUS']] = if_val * 0.5

                # IBUSX = real business investment (similar scale to IBUS)
                if 'IBUSX' in col_idx and np.isnan(self._get('IBUSX', t)):
                    self.data.iloc[t, col_idx['IBUSX']] = if_val * 0.5

            # Initialize capital stock (KMSXH) from steady-state relationship
            # K = I / (g + delta) where g ≈ 0.005 (quarterly growth), delta ≈ 0.025
            if 'KMSXH' in col_idx and np.isnan(self._get('KMSXH', t)):
                ibusx = self._get('IBUSX', t)
                if np.isfinite(ibusx):
                    # KMSXH is in £bn, IBUSX in £m
                    self.data.iloc[t, col_idx['KMSXH']] = (ibusx / 1000) / 0.03

        # Solve identity equations only (no residuals yet)
        # Need multiple passes because equations may depend on each other
        identity_eqs = [eq for eq in self.equations
                       if not ("/" in eq.lhs or
                               eq.lhs.lower().startswith("dlog(") or
                               eq.lhs.lower().startswith("d("))]

        col_idx = {col: self.data.columns.get_loc(col) for col in self.data.columns}

        initialized = 0
        for t in range(start_t, len(self.data)):
            # Multiple passes to handle dependencies
            for _ in range(5):
                v = {col: self.data.iloc[t][col] for col in self.data.columns}
                ctx = {
                    "np": np,
                    "v": v,
                    "_lag": lambda var, lag, t=t: self._lag(var, lag, t),
                    "_recode": lambda t_arg, period, op, tv, fv, t=t: self._recode(t, period, op, tv, fv),
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
                        except:
                            pass

                # Stop if no new values computed this pass
                if pass_initialized == 0:
                    break

        if self.verbose:
            print(f"Initialized {initialized} values from identities")

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
        except:
            start_t = len(self.data) - 20  # Last 20 periods

        # Pre-filter behavioral equations
        behavioral_eqs = [
            eq for eq in self.equations
            if ("/" in eq.lhs or
                eq.lhs.lower().startswith("dlog(") or
                eq.lhs.lower().startswith("d("))
        ]

        for t in range(max(1, start_t), len(self.data)):
            # Build context once per period
            v = {col: self.data.iloc[t][col] for col in self.data.columns}
            ctx = {
                "np": np,
                "v": v,
                "_lag": lambda var, lag, t=t: self._lag(var, lag, t),
                # Residuals/add-factors are intentionally not computed for the
                # @recode/@TREND-driven equations: held add-factors overshoot on
                # them, so they project structurally (forecasts notably better —
                # e.g. trade balance 11% vs 29% with held add-factors).
                "_recode": lambda period, op, tv, fv, t=t: self._recode(t, period, op, tv, fv),
                "_trend": lambda base, t=t: self._trend(t, base),
                "_elem": self._elem,
                "t": t,
            }

            for eq in behavioral_eqs:
                var = self._extract_lhs_var(eq.lhs)
                try:
                    rhs_val = eval(eq.python_expr, ctx)
                    actual_val = self._get(var, t)

                    if "/" in eq.lhs:
                        lag_val = self._lag(var, 1, t)
                        predicted = lag_val * rhs_val if np.isfinite(lag_val) else np.nan
                    elif eq.lhs.lower().startswith("dlog("):
                        lag_val = self._lag(var, 1, t)
                        predicted = lag_val * np.exp(rhs_val) if np.isfinite(lag_val) else np.nan
                    elif eq.lhs.lower().startswith("d("):
                        lag_val = self._lag(var, 1, t)
                        predicted = lag_val + rhs_val if np.isfinite(lag_val) else np.nan
                    else:
                        predicted = rhs_val

                    if np.isfinite(actual_val) and np.isfinite(predicted):
                        self.residuals[(var, t)] = actual_val - predicted
                except:
                    pass

        if self.verbose:
            print(f"Computed {len(self.residuals)} residuals")

    def _extract_lhs_var(self, lhs: str) -> str:
        """Extract variable name from LHS."""
        lhs = lhs.strip()
        if "/" in lhs:
            return lhs.split("/")[0].strip()
        if lhs.lower().startswith("dlog("):
            return lhs[5:-1].strip()
        if lhs.lower().startswith("d("):
            return lhs[2:-1].strip()
        if lhs.startswith("@IDENTITY"):
            return lhs.replace("@IDENTITY", "").strip()
        return lhs

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

    def _recode(self, t: int, period: str, op: str, true_val: float, false_val: float) -> float:
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
        except:
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
            "v": v,
            "_lag": lambda var, lag: self._lag(var, lag, t),
            "_recode": lambda t_arg, period, op, tv, fv: self._recode(t, period, op, tv, fv),
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
        new._code_cache = self._code_cache          # compiled code objects (immutable)
        new._hist_floor = self._hist_floor
        new.index = self.index
        new.base_values = self.base_values
        new.residuals = self.residuals
        new.equations = list(self.equations)        # own list; shared eq objects
        new.data = self.data.copy()                 # own data
        new.baseline = self.baseline
        new._shock_active = getattr(self, "_shock_active", False)
        new._build_equation_index()
        return new

    def swap_closure(self, remove_var: str, add_eq: ParsedEquation):
        """Swap model closure by removing one equation and adding another.

        For fiscal shock: remove DINV equation, add GDPM equation.
        """
        # Remove equation for remove_var
        self.equations = [eq for eq in self.equations
                         if self._extract_lhs_var(eq.lhs) != remove_var]

        # Add new equation
        self.equations.append(add_eq)

        # Rebuild index
        self._build_equation_index()

        if self.verbose:
            print(f"Swapped closure: removed {remove_var}, added {add_eq.lhs}")

    def make_exogenous(self, var: str):
        """Make a variable exogenous by removing its equation."""
        self.equations = [eq for eq in self.equations
                         if self._extract_lhs_var(eq.lhs) != var]
        self._build_equation_index()

        if self.verbose:
            print(f"Made {var} exogenous (removed equation)")

    def apply_shock(self, var: str, shock: float, start: str, periods: int = 4):
        """Apply shock to a variable."""
        self.make_exogenous(var)

        # Mark that we're in shock mode (disable residuals)
        self._shock_active = True

        start_t = self.period_idx(start)
        for p in range(periods):
            t = start_t + p
            if t < len(self.data):
                old_val = self._get(var, t)
                self._set(var, t, old_val + shock)

        if self.verbose:
            print(f"Applied shock: {var} += {shock:+,.0f} for {periods} periods from {start}")

    def period_idx(self, period: str) -> int:
        return self.index.get_loc(pd.Period(period, freq="Q"))

    def solve_period(self, t: int, max_iter: int = 60, tol: float = 1e-6,
                     stall_patience: int = 8) -> int:
        """Solve all equations for period t using Gauss-Seidel."""
        # Pre-compute column indices for faster access
        col_idx = {col: self.data.columns.get_loc(col) for col in self.data.columns}

        best_change = float("inf")
        stall = 0
        for iteration in range(max_iter):
            max_change = 0.0

            # Build context once per iteration, use mutable v dict
            row = self.data.iloc[t]
            v = {col: row[col] for col in self.data.columns}

            ctx = {
                "np": np,
                "v": v,
                "_lag": lambda var, lag: self._lag(var, lag, t),
                "_recode": lambda t_arg, period, op, tv, fv: self._recode(t, period, op, tv, fv),
                "_trend": lambda t_arg, base: self._trend(t, base),
                "_elem": self._elem,
                "t": t,
            }

            for eq in self.equations:
                try:
                    var = self._extract_lhs_var(eq.lhs)
                    old_val = v.get(var, np.nan)

                    rhs_val = eval(self._compiled(eq.python_expr), ctx)

                    # Compute new value based on equation form
                    if "/" in eq.lhs:
                        lag_val = self._lag(var, 1, t)
                        new_val = lag_val * rhs_val if np.isfinite(lag_val) else np.nan
                    elif eq.lhs.lower().startswith("dlog("):
                        lag_val = self._lag(var, 1, t)
                        new_val = lag_val * np.exp(rhs_val) if np.isfinite(lag_val) else np.nan
                    elif eq.lhs.lower().startswith("d("):
                        lag_val = self._lag(var, 1, t)
                        new_val = lag_val + rhs_val if np.isfinite(lag_val) else np.nan
                    else:
                        new_val = rhs_val

                    if np.isfinite(new_val):
                        # Add residual adjustment for behavioral equations
                        # But only if we're not in shock mode (baseline preserved)
                        if not hasattr(self, '_shock_active') or not self._shock_active:
                            residual = self.residuals.get((var, t), 0)
                            new_val += residual

                        # Update both the DataFrame and the context dict
                        if var in col_idx:
                            self.data.iloc[t, col_idx[var]] = new_val
                        v[var] = new_val

                        if np.isfinite(old_val) and abs(old_val) > 1e-10:
                            change = abs(new_val - old_val) / abs(old_val)
                            max_change = max(max_change, change)
                except Exception as e:
                    pass  # Skip equations that can't be evaluated

            if max_change < tol:
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
        import re

        row = self.data.iloc[t]
        v = {col: row[col] for col in self.data.columns}
        ctx = {
            "np": np,
            "v": v,
            "_lag": lambda var, lag: self._lag(var, lag, t),
            "_recode": lambda t_arg, period, op, tv, fv: self._recode(t, period, op, tv, fv),
            "_trend": lambda t_arg, base: self._trend(t, base),
            "_elem": self._elem,
            "t": t,
        }

        def nan_inputs(expr):
            bad = []
            for m in re.finditer(r"v\['([A-Z0-9_]+)'\]", expr):
                name = m.group(1)
                if name in v and not np.isfinite(v.get(name, np.nan)):
                    bad.append(name)
            for m in re.finditer(r"_lag\('([A-Z0-9_]+)',\s*(\d+)\)", expr):
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
                    out.append({"var": var, "lhs": eq.lhs, "status": "nonfinite",
                                "reason": ("NaN inputs: " + ", ".join(inputs)) if inputs
                                else "evaluates to NaN/inf"})
            except Exception as e:
                out.append({"var": var, "lhs": eq.lhs, "status": "error",
                            "reason": f"{type(e).__name__}: {e}"})
        return out

    def solve(self, start: str, end: str) -> dict:
        """Solve model from start to end period."""
        t_start = self.period_idx(start)
        t_end = self.period_idx(end)

        results = {}
        for t in range(t_start, t_end + 1):
            iters = self.solve_period(t)
            period = str(self.index[t])
            results[period] = iters
            if self.verbose:
                print(f"  {period}: {iters} iterations")

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
        python_expr="v['CGG'] + v['CONS'] + v['IF'] + v['DINV'] + v['VAL'] + v['X'] - v['M'] + v['SDE']"
    )
    solver.swap_closure("DINV", gdpm_eq)

    # Apply shock
    shock_m = shock_bn * 1000
    solver.apply_shock("CGG", shock_m, "2025Q1", periods=4)

    print()
    print("Solving model...")
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

        cgg_base = solver.baseline.iloc[t]['CGG']
        cgg_curr = solver._get('CGG', t)
        delta_cgg = cgg_curr - cgg_base

        cons_base = solver.baseline.iloc[t]['CONS']
        cons_curr = solver._get('CONS', t)
        delta_cons = cons_curr - cons_base

        gdpm_base = solver.baseline.iloc[t]['GDPM']
        gdpm_curr = solver._get('GDPM', t)
        delta_gdpm = gdpm_curr - gdpm_base

        mult = delta_gdpm / delta_cgg if delta_cgg > 0 else np.nan
        mult_str = f"{mult:.2f}" if np.isfinite(mult) else "N/A"

        print(f"{period:<10} {delta_cgg:>+12,.0f} {delta_cons:>+12,.0f} {delta_gdpm:>+12,.0f} {mult_str:>12}")

    return solver


if __name__ == "__main__":
    run_fiscal_shock(1.0)
