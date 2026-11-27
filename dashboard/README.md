# OBR Macroeconomic Model — dashboard

A Next.js 14 (App Router) + React + Tailwind dashboard for the OBR model emulator,
built on PolicyEngine's design system. Five tabs: **About**, **How it works**,
**Explore scenarios** (interactive recharts), **Variables** (searchable glossary),
**Equations** (published EViews + transpiled Python).

## Run locally

```bash
cd dashboard
npm install
npm run dev      # http://localhost:3000
```

`npm run build && npm run start` runs the production build. Deploys on Vercel
(`vercel.json`, framework `nextjs`).

## Data

The tabs read three JSON files from `public/data/`, regenerated from the repo root:

```bash
uv run python dashboard/gen_model_data.py      # -> public/data/model_data.json    (variables + equations; about a second)
uv run python dashboard/gen_explorer_data.py   # -> public/data/explorer_data.json (15 solves; about four minutes)
uv run python -m dashboard.gen_reform_grid     # -> public/data/reform_grid.json   (10 solves; about half a minute)
```

Timings are from a laptop on 26 Nov 2026. The `demo.yml` workflow's
`dashboard-data` job runs the same three commands on GitHub Actions and uploads
the files as an artefact.

`gen_model_data.py` parses the OBR variable list and transpiles each equation.
It also writes the identical packaged copy `obr_macro/seeds/model_glossary.json`.
`gen_explorer_data.py` solves the five reform scenarios (a control, the shock
and a mirror shock each). `gen_reform_grid.py` solves the two ends of each
slider against a held-add-factor baseline. The chat agent in `chat/` reads
`model_data.json` and `explorer_data.json`; it has no data of its own.

**Vintage.** All three files were regenerated on 26 Nov 2026 against the
October 2026 EFO. The explorer and the grid had last been generated on 6 Nov
2026 against the March 2026 EFO; the regeneration moved GDP by up to £2m in
the spending and export scenarios and by up to £22m in the Bank Rate scenario
(first quarter −£143m before, −£133m now).

The explorer and `results/demo_shocks.json` differ for a known reason.
`run_reform` scores a shock around the baseline anchored to the EFO
(`freeze_anchoring` and `_anchor_published_levels` in
`obr_macro/reform_analysis.py`); the explorer builds the model without those
two steps, so it scores the same shock around the free-running model. With
them added, the explorer reproduces `run_reform` exactly (run on 26 Nov 2026):

| Real GDP change, £m (q1 / q4) | Explorer as shipped | Explorer with the anchoring | `results/demo_shocks.json` |
|---|--:|--:|--:|
| `CGG` +1,250 a quarter, real only | +1,267.9 / +1,285.8 | +1,266.8 / +1,283.3 | +1,266.8 / +1,283.3 (`cgg_real_only`) |
| Bank Rate +1pp | −133.2 / −401.3 | −128.4 / −406.3 | −128.4 / −406.3 (`bank_rate`) |

Two further differences are by design: the explorer's spending shock carries
no nominal legs (the demo's default `cgg` row does), and it holds the Bank
Rate rise for 12 quarters where the demo holds it for 4. `results/` is the
source of record for figures quoted in the docs. Issue #92 tracks moving the
explorer onto the anchored baseline.

**Staleness checks** (`tests/test_dashboard_fresh.py`). On every test run:
`model_data.json` and its packaged copy are rebuilt and compared byte for
byte, and the explorer and the grid must record the fingerprint of the input
data now in `obr_macro/_data` and `obr_macro/seeds` (`meta.inputs_sha256`),
along with the generators' current scenario lists, labels and notes. Nightly
(`--runslow`): every scenario and the whole grid are solved again and compared
with the committed numbers. If a check fails, run the three commands above and
commit the result.

## Structure

- `app/page.jsx` — tab routing, data fetch, layout
- `app/globals.css` — PolicyEngine design tokens + component classes
- `src/components/*Tab.jsx` — one component per tab
- `src/lib/` — `formatters`, `colors`, `chartUtils` (shared with the PolicyEngine template)
