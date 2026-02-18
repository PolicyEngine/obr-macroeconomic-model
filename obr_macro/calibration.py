"""Load OBR Economic and Fiscal Outlook data and calibrate model variables."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import openpyxl

from obr_macro.variables import Variables


def _read_table(
    wb: openpyxl.Workbook,
    sheet: str,
    period_col: int,
    data_cols: dict[str, int],
    min_row: int = 5,
    max_row: int = 400,
) -> dict[str, dict[str, float]]:
    """Read quarterly data from an OBR table sheet.

    Returns {variable_name: {period_label: value}} for quarterly periods only.
    """
    ws = wb[sheet]
    result = {name: {} for name in data_cols}
    for r in range(min_row, max_row + 1):
        period = ws.cell(r, period_col).value
        if period is None:
            continue
        period = str(period)
        # Only keep quarterly data (e.g. '2024Q3')
        if len(period) != 6 or "Q" not in period:
            continue
        for name, col in data_cols.items():
            val = ws.cell(r, col).value
            if isinstance(val, (int, float)) and np.isfinite(val):
                result[name][period] = float(val)
    return result


def load_obr_efo(filepath: str | Path) -> dict[str, dict[str, float]]:
    """Load the OBR EFO economy supplementary tables.

    Returns a flat dict: {model_variable_name: {period_label: value}}.
    """
    wb = openpyxl.load_workbook(str(filepath), data_only=True)
    data: dict[str, dict[str, float]] = {}

    def merge(d: dict[str, dict[str, float]]) -> None:
        for k, v in d.items():
            data[k] = v

    # Table 1.7: Inflation indices (period in col B=2)
    # Growth rates in cols 3-12, index levels in cols 13-22
    merge(
        _read_table(
            wb,
            "1.7",
            period_col=2,
            data_cols={
                "RPI_yoy": 3,       # RPI yoy growth (%)
                "CPI_yoy": 5,       # CPI yoy growth (%)
                "PR": 13,           # RPI index (Jan 1987=100)
                "CPI": 15,          # CPI (2015=100)
                "CPIH": 16,         # CPIH (2015=100)
                "OOH": 17,          # OOH (2015=100)
                "PRMIP_raw": 18,    # Mortgage interest payments (Jan 1987=100)
                "_RENTS": 19,       # Actual rents for housing (2015=100)
                "PRENT": 20,        # Private rentals (2016=100)
                "PCE_raw": 21,      # Consumer expenditure deflator (2023=100)
                "PGDP_raw": 22,     # GDP deflator (2023=100)
            },
        )
    )

    # Table 1.9: Market-derived assumptions (period in col B=2, data from row 4)
    merge(
        _read_table(
            wb,
            "1.9",
            period_col=2,
            data_cols={
                "R": 3,         # Bank Rate (%)
                "RL": 4,        # Long-term gilt yield (%)
                "RMORT": 5,     # Average mortgage rate (%)
                "RDEP": 6,      # Deposit rate (%)
                "RX": 7,        # Sterling EER
                "RXD_GBP": 8,   # US$/£ exchange rate
                "PBRENT": 10,   # Oil prices ($)
                "FTSE": 12,     # Equity prices (FTSE All-Share)
            },
            min_row=4,
        )
    )

    # Table 1.1: Real GDP expenditure (period in col B=2)
    merge(
        _read_table(
            wb,
            "1.1",
            period_col=2,
            data_cols={
                "CONS": 3,      # Private consumption (real, £bn)
                "CGG": 4,       # Government consumption (real, £bn)
                "IF_real": 5,   # Fixed investment (real, £bn)
                "IBUS": 6,      # Business investment (real, £bn)
                "IH_real": 7,   # Private dwellings (real, £bn)
                "GGI_real": 8,  # General government investment (real, £bn)
                "X_real": 14,   # Exports (real, £bn)
                "M_real": 16,   # Imports (real, £bn)
                "GDPM_real": 18,  # Real GDP (£bn)
                "NOILGVA_real": 19,  # Non-oil GVA (real, £bn)
            },
        )
    )

    # Table 1.2: Nominal GDP expenditure (period in col B=2)
    merge(
        _read_table(
            wb,
            "1.2",
            period_col=2,
            data_cols={
                "CONSPS": 3,        # Private consumption (nominal, £bn)
                "CGGPS_nom": 4,     # Government consumption (nominal, £bn)
                "IFPS_nom": 5,      # Fixed investment (nominal, £bn)
                "XPS_nom": 11,      # Exports (nominal, £bn)
                "MPS_nom": 13,      # Imports (nominal, £bn)
                "GDPMPS_nom": 15,   # GDP at market prices (nominal, £bn)
                "GNIPS_nom": 16,    # Gross national income (nominal, £bn)
            },
        )
    )

    # Table 1.3: GDP income components (period in col B=2, data from row 4)
    merge(
        _read_table(
            wb,
            "1.3",
            period_col=2,
            data_cols={
                "LABOUR_INC": 3,    # Labour income (£bn)
                "FYCPR_nom": 4,     # Non-oil PNFC profits (£bn)
                "OTHER_INC": 5,     # Other income (£bn)
                "GVA_FC": 6,        # GVA at factor cost (£bn)
                "BPAPS_nom": 7,     # Taxes on products less subsidies (£bn)
                "GDPMPS_inc": 9,    # GDP (income measure, £bn)
            },
            min_row=4,
        )
    )

    # Table 1.6: Labour market (period in col B=2, data from row 4)
    merge(
        _read_table(
            wb,
            "1.6",
            period_col=2,
            data_cols={
                "ETLFS_m": 3,       # Employment (millions)
                "ER_pct": 4,        # Employment rate (%)
                "EMPLOYEES_m": 5,   # Employees (millions)
                "UNEMP_m": 6,       # ILO unemployment (millions)
                "LFSUR": 7,         # Unemployment rate (%)
                "PART16": 8,        # Participation rate (%)
                "AVH_raw": 9,       # Average hours worked
                "HWA_raw": 10,      # Total hours worked (millions)
                "COMP_EMP": 13,     # Compensation of employees (£bn)
                "WAGES_SAL": 14,    # Wages and salaries (£bn)
                "EMP_SOC": 15,      # Employers social contributions (£bn)
                "MI_raw": 16,       # Mixed income (£bn)
                "AWE_IDX": 18,      # AWE index (2008Q1=100)
            },
            min_row=4,
        )
    )

    # Table 1.12: Household disposable income (period in col B=2, data from row 4)
    merge(
        _read_table(
            wb,
            "1.12",
            period_col=2,
            data_cols={
                "HHDI_nom": 9,  # Household disposable income (£bn)
            },
            min_row=4,
        )
    )

    # Table 1.16: Housing market (period in col B=2, data from row 4)
    merge(
        _read_table(
            wb,
            "1.16",
            period_col=2,
            data_cols={
                "HPI": 3,           # House price index (Jan 2023=100)
                "HPI_yoy": 4,       # House price YoY change (%)
                "TRANS": 5,         # Residential property transactions (000s)
            },
            min_row=4,
        )
    )

    return data


def _set_var(
    v: Variables,
    name: str,
    series: dict[str, float],
    scale: float = 1.0,
    backfill: bool = True,
) -> None:
    """Set a model variable from an OBR quarterly series.

    For periods before OBR data starts, backfills with the earliest value.
    For periods after OBR data ends, forward-fills with the latest value.
    """
    if not series:
        return
    sorted_periods = sorted(series.keys())
    arr = v[name]

    # Fill known periods
    for period, val in series.items():
        try:
            t = v.period_to_idx(period)
            arr[t] = val * scale
        except (KeyError, IndexError):
            continue

    if backfill:
        earliest_val = series[sorted_periods[0]] * scale
        latest_val = series[sorted_periods[-1]] * scale

        # Find the model indices for earliest/latest OBR data
        try:
            t_first = v.period_to_idx(sorted_periods[0])
        except (KeyError, IndexError):
            t_first = 0
        try:
            t_last = v.period_to_idx(sorted_periods[-1])
        except (KeyError, IndexError):
            t_last = len(arr) - 1

        # Backfill before data
        arr[:t_first] = earliest_val
        # Forward-fill after data
        if t_last < len(arr) - 1:
            arr[t_last + 1 :] = latest_val


def calibrate_prices(v: Variables, data: dict[str, dict[str, float]]) -> None:
    """Set all price, interest rate and exchange rate variables from OBR data."""

    # CPI (2015=100) — model uses same basis
    _set_var(v, "CPI", data.get("CPI", {}))

    # CPIH (2015=100)
    _set_var(v, "CPIH", data.get("CPIH", {}))

    # OOH (2015=100)
    _set_var(v, "OOH", data.get("OOH", {}))

    # RPI index level (Jan 1987=100) — model stores as PR
    _set_var(v, "PR", data.get("PR", {}))

    # RPI year-on-year growth (%)
    _set_var(v, "RPI", data.get("RPI_yoy", {}))

    # Private rental prices (2016=100) — used for PRENT and CPIRENT
    _set_var(v, "PRENT", data.get("PRENT", {}))
    _set_var(v, "CPIRENT", data.get("PRENT", {}))

    # Consumer expenditure deflator (2023=100 in OBR)
    # Model uses this as an index — set directly
    _set_var(v, "PCE", data.get("PCE_raw", {}))

    # GDP deflator — OBR provides this as an index
    _set_var(v, "PGDP", data.get("PGDP_raw", {}))

    # Mortgage interest payments index
    _set_var(v, "PRMIP", data.get("PRMIP_raw", {}))

    # Interest rates (%) — direct mapping
    _set_var(v, "R", data.get("R", {}))
    _set_var(v, "RL", data.get("RL", {}))
    _set_var(v, "RMORT", data.get("RMORT", {}))
    _set_var(v, "RDEP", data.get("RDEP", {}))
    # Corporate bond rate: approximate as gilt yield + 1pp spread
    if "RL" in data:
        rocb_series = {p: val + 1.0 for p, val in data["RL"].items()}
        _set_var(v, "ROCB", rocb_series)

    # Exchange rates
    _set_var(v, "RX", data.get("RX", {}))
    # RXD in model is USD/GBP (how many dollars per pound)
    _set_var(v, "RXD", data.get("RXD_GBP", {}))

    # Oil prices ($/barrel)
    _set_var(v, "PBRENT", data.get("PBRENT", {}))


def calibrate_national_accounts(
    v: Variables, data: dict[str, dict[str, float]]
) -> None:
    """Set national accounts variables from OBR data.

    OBR reports in £bn; model uses £m. Scale = 1000.
    """
    S = 1000  # £bn → £m

    # Real GDP and components (Table 1.1, £bn constant prices)
    _set_var(v, "CONS", data.get("CONS", {}), scale=S)
    _set_var(v, "CGG", data.get("CGG", {}), scale=S)
    _set_var(v, "IF", data.get("IF_real", {}), scale=S)
    _set_var(v, "IBUS", data.get("IBUS", {}), scale=S)
    _set_var(v, "IH", data.get("IH_real", {}), scale=S)
    _set_var(v, "GGI", data.get("GGI_real", {}), scale=S)
    _set_var(v, "GGIX", data.get("GGI_real", {}), scale=S)
    _set_var(v, "GDPM", data.get("GDPM_real", {}), scale=S)
    _set_var(v, "TRGDP", data.get("GDPM_real", {}), scale=S)  # Trend = actual for now
    _set_var(v, "X", data.get("X_real", {}), scale=S)
    _set_var(v, "M", data.get("M_real", {}), scale=S)

    # Nominal GDP and components (Table 1.2, £bn current prices)
    _set_var(v, "CONSPS", data.get("CONSPS", {}), scale=S)
    _set_var(v, "CGGPS", data.get("CGGPS_nom", {}), scale=S)
    _set_var(v, "CGGPSPSF", data.get("CGGPS_nom", {}), scale=S)
    _set_var(v, "IFPS", data.get("IFPS_nom", {}), scale=S)
    _set_var(v, "GDPMPS", data.get("GDPMPS_nom", {}), scale=S)
    _set_var(v, "GNIPS", data.get("GNIPS_nom", {}), scale=S)
    _set_var(v, "XPS", data.get("XPS_nom", {}), scale=S)
    _set_var(v, "MPS", data.get("MPS_nom", {}), scale=S)

    # GDP income components (Table 1.3, £bn)
    _set_var(v, "FYCPR", data.get("FYCPR_nom", {}), scale=S)
    _set_var(v, "BPAPS", data.get("BPAPS_nom", {}), scale=S)

    # Derive FYEMP from labour income + employer social contributions
    if "COMP_EMP" in data:
        _set_var(v, "FYEMP", data["COMP_EMP"], scale=S)

    # Household disposable income (Table 1.12, £bn)
    _set_var(v, "HHDI", data.get("HHDI_nom", {}), scale=S)


def calibrate_labour_market(
    v: Variables, data: dict[str, dict[str, float]]
) -> None:
    """Set labour market variables from OBR data."""

    # Employment (OBR gives millions, model uses thousands)
    if "ETLFS_m" in data:
        etlfs = {p: val * 1000 for p, val in data["ETLFS_m"].items()}
        _set_var(v, "ETLFS", etlfs)
        _set_var(v, "ET", etlfs)

    if "EMPLOYEES_m" in data:
        employees = {p: val * 1000 for p, val in data["EMPLOYEES_m"].items()}
        # EMS = market sector employment ≈ employees - public sector
        # For now, approximate as total employees
        _set_var(v, "EMS", employees)

    # Unemployment rate (%)
    _set_var(v, "LFSUR", data.get("LFSUR", {}))

    # Participation rate (%)
    _set_var(v, "PART16", data.get("PART16", {}))

    # Employment rate (%)
    _set_var(v, "ER", data.get("ER_pct", {}))

    # Average hours worked
    if "AVH_raw" in data:
        _set_var(v, "AVH", data["AVH_raw"])

    # Total hours worked (OBR gives millions per week)
    if "HWA_raw" in data:
        _set_var(v, "HWA", data["HWA_raw"])

    # Mixed income (£bn → £m)
    _set_var(v, "MI", data.get("MI_raw", {}), scale=1000)

    # Employer social contributions (£bn → £m)
    _set_var(v, "EMPSC", data.get("EMP_SOC", {}), scale=1000)

    # Wages and salaries (£bn → £m) — this is WFP
    _set_var(v, "WFP", data.get("WAGES_SAL", {}), scale=1000)


def calibrate_housing(v: Variables, data: dict[str, dict[str, float]]) -> None:
    """Set housing market variables from OBR data."""
    # House price index (Jan 2023=100)
    _set_var(v, "APH", data.get("HPI", {}))


def calibrate_all(v: Variables, data: dict[str, dict[str, float]]) -> None:
    """Apply all calibration functions."""
    calibrate_prices(v, data)
    calibrate_national_accounts(v, data)
    calibrate_labour_market(v, data)
    calibrate_housing(v, data)
