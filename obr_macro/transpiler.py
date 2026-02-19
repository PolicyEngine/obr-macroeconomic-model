"""EViews-to-Python transpiler for OBR model equations."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedEquation:
    """A parsed model equation."""
    lhs: str
    rhs: str
    original: str
    equation_type: str  # "identity", "ecm", "growth_rate", "simultaneous"
    python_expr: str


class EViewsTranspiler:
    """Convert EViews model syntax to Python expressions."""

    def __init__(self, base_period_values: dict[str, float] = None):
        """
        Args:
            base_period_values: Dict of @elem lookups like {"PGDP_1970Q1": 100.0}
        """
        self.base_values = base_period_values or {}

    def transpile(self, eviews_expr: str) -> str:
        """Convert EViews expression to Python."""
        s = eviews_expr.strip()

        # Step 1: Handle @elem(VAR, "PERIOD") - base period lookups
        s = self._convert_elem(s)

        # Step 2: Handle @recode for date conditionals
        s = self._convert_recode(s)

        # Step 3: Handle @TREND
        s = self._convert_trend(s)

        # Step 4: Handle dlog(X) - log differences
        s = self._convert_dlog(s)

        # Step 5: Handle d(X) - first differences
        s = self._convert_d(s)

        # Step 6: Handle lags X(-n)
        s = self._convert_lags(s)

        # Step 7: Handle log/exp
        s = self._convert_functions(s)

        # Step 8: Handle power operator
        s = s.replace("^", "**")

        return s

    def _convert_elem(self, s: str) -> str:
        """Convert @elem(VAR, "PERIOD") to constant lookup."""
        pattern = r'@elem\(\s*([A-Z][A-Z0-9_]*)\s*,\s*"(\d{4})[Q:](\d)"\s*\)'

        def replace(m):
            var = m.group(1)
            year = m.group(2)
            q = m.group(3)
            key = f"{var}_{year}Q{q}"
            if key in self.base_values:
                return str(self.base_values[key])
            return f"_elem('{var}', '{year}Q{q}')"

        return re.sub(pattern, replace, s, flags=re.IGNORECASE)

    def _convert_recode(self, s: str) -> str:
        """Convert @recode date conditionals to boolean masks."""
        # Pattern: @recode(@date = @dateval("YYYY:QQ"), 1, 0)
        pattern = r'@recode\(\s*@date\s*([<>=]+)\s*@dateval\(\s*"(\d{4}):(\d{2})"\s*\)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)'

        def replace(m):
            op = m.group(1)
            year = m.group(2)
            quarter = int(m.group(3))
            # Convert quarter: 01->1, 02->2, 03->3, 04->4
            if quarter > 4:
                quarter = (quarter - 1) % 4 + 1
            true_val = m.group(4)
            false_val = m.group(5)
            period = f"{year}Q{quarter}"
            return f"_recode(t, '{period}', '{op}', {true_val}, {false_val})"

        return re.sub(pattern, replace, s, flags=re.IGNORECASE)

    def _convert_trend(self, s: str) -> str:
        """Convert @TREND(base) to trend variable."""
        pattern = r'@TREND\(\s*(\d{4})([Q:])(\d)\s*\)'

        def replace(m):
            year = m.group(1)
            q = m.group(3)
            return f"_trend(t, '{year}Q{q}')"

        return re.sub(pattern, replace, s, flags=re.IGNORECASE)

    def _convert_dlog(self, s: str) -> str:
        """Convert dlog(X) to log difference.

        Uses balanced parenthesis matching to handle arbitrary nesting.
        """
        result = []
        i = 0

        while i < len(s):
            # Look for 'dlog('
            if s[i:i+5].lower() == 'dlog(':
                # Extract the balanced content
                inner, end_pos = self._extract_balanced_parens(s, i + 4)

                # Convert any lags in the inner expression
                inner_current = self._convert_lags_simple(inner, lag=0)
                inner_lagged = self._convert_lags_simple(inner, lag=1)

                result.append(f"(np.log({inner_current}) - np.log({inner_lagged}))")
                i = end_pos
            else:
                result.append(s[i])
                i += 1

        return ''.join(result)

    def _convert_lags_simple(self, s: str, lag: int) -> str:
        """Convert lags in expression, adding default lag to bare variables."""
        # First convert explicit lags VAR(-n)
        pattern = r'([A-Z][A-Z0-9_]*)\((-?\d+)\)'

        def replace(m):
            var = m.group(1)
            explicit_lag = -int(m.group(2))  # VAR(-1) means lag 1
            total_lag = explicit_lag + lag
            if total_lag == 0:
                return f"v['{var}']"
            else:
                return f"_lag('{var}', {total_lag})"

        s = re.sub(pattern, replace, s)

        # Then convert bare variable names
        bare_pattern = r'\b([A-Z][A-Z0-9_]*)\b(?!\s*[\(\[]|\')'

        def replace_bare(m):
            var = m.group(1)
            if var in ('NP', 'Q'):
                return var
            if lag == 0:
                return f"v['{var}']"
            else:
                return f"_lag('{var}', {lag})"

        s = re.sub(bare_pattern, replace_bare, s)
        return s

    def _extract_balanced_parens(self, s: str, start: int) -> tuple[str, int]:
        """Extract content within balanced parentheses starting at position start.

        Args:
            s: The string to parse
            start: Position of the opening parenthesis

        Returns:
            Tuple of (content inside parens, position after closing paren)
        """
        if s[start] != '(':
            return '', start

        depth = 1
        i = start + 1
        while i < len(s) and depth > 0:
            if s[i] == '(':
                depth += 1
            elif s[i] == ')':
                depth -= 1
            i += 1

        # Return content between parens (excluding the parens themselves)
        return s[start + 1:i - 1], i

    def _convert_d(self, s: str) -> str:
        """Convert d(X) to first difference.

        Only matches standalone d() not preceded by underscore or letter.
        Uses balanced parenthesis matching to handle arbitrary nesting.
        """
        result = []
        i = 0

        while i < len(s):
            # Look for 'd(' not preceded by letter/underscore
            if s[i:i+2] == 'd(' and (i == 0 or not s[i-1].isalpha() and s[i-1] != '_'):
                # Extract the balanced content
                inner, end_pos = self._extract_balanced_parens(s, i + 1)

                # Convert the inner expression - wrap each in parens for correct subtraction
                inner_current = self._convert_lags_simple(inner, lag=0)
                inner_lagged = self._convert_lags_simple(inner, lag=1)

                result.append(f"(({inner_current}) - ({inner_lagged}))")
                i = end_pos
            else:
                result.append(s[i])
                i += 1

        return ''.join(result)

    def _convert_lags(self, s: str, default_lag: int = None) -> str:
        """Convert VAR(-n) to _lag('VAR', n) and bare VAR to v['VAR']."""
        # Pattern: VARNAME(-n) where n is a positive integer
        pattern = r'([A-Z][A-Z0-9_]*)\((-?\d+)\)'

        def replace(m):
            var = m.group(1)
            lag = int(m.group(2))
            if lag == 0:
                return f"v['{var}']"
            elif lag < 0:
                return f"_lag('{var}', {-lag})"
            else:
                # Future value (rare)
                return f"_lead('{var}', {lag})"

        s = re.sub(pattern, replace, s)

        # Always convert bare variable names (uppercase words not followed by parentheses)
        # Match bare variable names not already converted to v['...'] or _lag(...)
        bare_pattern = r'\b([A-Z][A-Z0-9_]*)\b(?!\s*[\(\[\'])'

        def replace_bare(m):
            var = m.group(1)
            # Skip numpy functions and special names
            if var in ('Q', 'NP', 'LOG', 'EXP'):
                return var
            if default_lag is not None and default_lag > 0:
                return f"_lag('{var}', {default_lag})"
            else:
                return f"v['{var}']"

        s = re.sub(bare_pattern, replace_bare, s)

        return s

    def _convert_functions(self, s: str) -> str:
        """Convert log/exp to numpy."""
        # Avoid double-converting np.log
        s = re.sub(r'(?<!np\.)\blog\(', 'np.log(', s)
        s = re.sub(r'(?<!np\.)\bexp\(', 'np.exp(', s)
        return s

    def parse_equation(self, line: str) -> Optional[ParsedEquation]:
        """Parse a single equation line."""
        line = line.strip()
        if not line or line.startswith("'"):
            return None

        # Remove inline comments
        if "'" in line:
            line = line.split("'")[0].strip()

        if not line or "=" not in line:
            return None

        # Skip @ADD directives
        if "@ADD" in line.upper():
            return None

        # Split on first =
        parts = line.split("=", 1)
        if len(parts) != 2:
            return None

        lhs = parts[0].strip()
        rhs = parts[1].strip()

        # Determine equation type
        if "/" in lhs:
            eq_type = "growth_rate"
        elif "dlog(" in line.lower() or "d(" in rhs.lower():
            eq_type = "ecm"
        else:
            eq_type = "identity"

        # Transpile RHS
        python_rhs = self.transpile(rhs)

        return ParsedEquation(
            lhs=lhs,
            rhs=rhs,
            original=line,
            equation_type=eq_type,
            python_expr=python_rhs,
        )


def parse_model_file(filepath: str, include_behavioral: bool = False) -> list[ParsedEquation]:
    """Parse entire model file.

    Args:
        filepath: Path to model file
        include_behavioral: If True, include commented behavioral equations (dlog, d)
    """
    transpiler = EViewsTranspiler()
    equations = []

    with open(filepath) as f:
        content = f.read()

    # Join continuation lines
    lines = []
    current = ""
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("'"):
            # Check if this is a behavioral equation we want to include
            if include_behavioral and (line.startswith("'dlog(") or line.startswith("'d(")):
                # Strip the leading comment character
                line = line[1:]
            else:
                continue
        current += " " + line
        # Check if line is complete (has balanced parens)
        if current.count("(") == current.count(")"):
            lines.append(current.strip())
            current = ""

    for line in lines:
        eq = transpiler.parse_equation(line)
        if eq:
            equations.append(eq)

    return equations
