"""Generate the dashboard's variable/equation glossary JSON from the OBR
variables spreadsheet.

Reads data/obr_model_variables_october_2025.xlsx, transpiles each equation with
the project's EViews transpiler, and writes dashboard/public/data/model_data.json
(consumed by the Variables and Equations tabs).

Run from the repo root:
    uv run python dashboard/gen_model_data.py
"""
import json

import openpyxl

from obr_macro.transpiler import EViewsTranspiler

XLSX = "data/obr_model_variables_october_2025.xlsx"
OUT = "dashboard/public/data/model_data.json"


def main():
    wb = openpyxl.load_workbook(XLSX, data_only=True)
    ws = wb["Sheet1"]
    tr = EViewsTranspiler()

    rows = list(ws.iter_rows(values_only=True))
    hdr = next(i for i, r in enumerate(rows) if r and r[0] == "Number")

    group = None
    items = []
    n_eq = 0
    for r in rows[hdr + 1:]:
        if not r:
            continue
        c0, c1, c2, c3, c4, c5 = (list(r) + [None] * 6)[:6]
        if c0 and isinstance(c0, str) and c0.strip().lower().startswith("group") and not c2:
            group = c0.strip()
            continue
        if not c2:
            continue
        eq = str(c4).strip() if c4 else ""
        py = ""
        if eq and "=" in eq:
            try:
                pe = tr.parse_equation(eq)
                if pe:
                    py = pe.python_expr
                    n_eq += 1
            except Exception:
                py = ""
        items.append({
            "n": str(c0).strip() if c0 else "",
            "code": str(c2).strip(),
            "desc": str(c1).strip() if c1 else "",
            "ons": str(c3).strip() if c3 else "",
            "group": group or "",
            "eq": eq,
            "type": str(c5).strip() if c5 else "",
            "py": py,
        })

    groups = []
    for it in items:
        if it["group"] and it["group"] not in groups:
            groups.append(it["group"])

    with open(OUT, "w") as f:
        json.dump({"groups": groups, "items": items}, f, separators=(",", ":"))
    print(f"wrote {OUT}: {len(items)} variables, {n_eq} transpiled equations, {len(groups)} groups")


if __name__ == "__main__":
    main()
