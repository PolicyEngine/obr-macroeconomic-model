"""Inline the dashboard's JSON data into index.html.

The dashboard is opened as a local file (file://), where fetch() of sibling
JSON is blocked, so the data is embedded directly into the page. Re-runnable:
it replaces the contents of the two <script type="application/json"> blocks.

Run from the repo root after regenerating model_data.json / explorer_data.json:
    uv run python dashboard/inject_data.py
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
HTML = HERE / "index.html"


def load(name):
    p = HERE / name
    if not p.exists():
        return None
    return json.loads(p.read_text())


def payload(obj):
    # Compact, and escape '<' so the JSON can never terminate the <script>.
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c")


def replace_block(html, script_id, data_text):
    pat = re.compile(
        r'(<script type="application/json" id="' + re.escape(script_id) + r'">).*?(</script>)',
        re.DOTALL,
    )
    if not pat.search(html):
        raise SystemExit(f"could not find <script id={script_id!r}> block in index.html")
    return pat.sub(lambda m: m.group(1) + data_text + m.group(2), html)


def main():
    html = HTML.read_text()

    model = load("model_data.json")
    if model is None:
        raise SystemExit("model_data.json not found — generate it first")
    html = replace_block(html, "model-data", payload(model))
    n_model = len(model.get("items", []))

    explorer = load("explorer_data.json")
    html = replace_block(html, "explorer-data", payload(explorer) if explorer else "null")
    n_scen = len(explorer["scenarios"]) if explorer else 0

    HTML.write_text(html)
    print(f"injected: {n_model} variables, {n_scen} explorer scenarios "
          f"({'explorer ready' if explorer else 'explorer pending'})")


if __name__ == "__main__":
    main()
