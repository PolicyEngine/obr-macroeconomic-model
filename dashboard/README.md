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

The tabs read two JSON files from `public/data/`, regenerated from the repo root:

```bash
uv run python dashboard/gen_model_data.py      # -> public/data/model_data.json   (variables + equations)
uv run python dashboard/gen_explorer_data.py   # -> public/data/explorer_data.json (scenario solver output; slow)
```

`gen_model_data.py` parses `data/obr_model_variables_october_2025.xlsx` and transpiles
each equation. `gen_explorer_data.py` solves the five reform scenarios (baseline vs
shock) — it is slow (two full 12-quarter solves per scenario).

## Structure

- `app/page.jsx` — tab routing, data fetch, layout
- `app/globals.css` — PolicyEngine design tokens + component classes
- `src/components/*Tab.jsx` — one component per tab
- `src/lib/` — `formatters`, `colors`, `chartUtils` (shared with the PolicyEngine template)
