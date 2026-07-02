"use client";

import SectionHeading from "./SectionHeading";

const STATS = [
  { big: "1970", lab: "First built by HM Treasury; updated continuously since" },
  { big: "372", lab: "Behavioural equations & accounting identities" },
  { big: "17", lab: "Thematic groups, from consumption to public finances" },
  { big: "ESA10", lab: "Aligned to the European System of Accounts" },
];

const GROUPS = [
  { n: "1", t: "Consumption", d: "— household spending & saving" },
  { n: "2", t: "Inventories", d: "— stockbuilding" },
  { n: "3", t: "Investment", d: "— business, housing, government" },
  { n: "4", t: "Labour market", d: "— employment, hours, earnings" },
  { n: "5", t: "Exports of goods & services", d: "— sold abroad" },
  { n: "6", t: "Imports of goods & services", d: "— bought in" },
  { n: "7", t: "Prices and wages", d: "— CPI, deflators, settlements" },
  { n: "8", t: "North Sea oil", d: "— production & revenues" },
  { n: "9", t: "Public expenditure", d: "— departmental & welfare spend" },
  { n: "10", t: "Public sector receipts", d: "— tax revenues" },
  { n: "11", t: "Balance of Payments", d: "— current account" },
  { n: "12", t: "Public Sector totals", d: "— borrowing & debt" },
  { n: "13", t: "PSNCR, debt and funding", d: "— cash borrowing & debt financing" },
  { n: "14", t: "Domestic financial sector", d: "" },
  { n: "15", t: "Income Account", d: "— household & corporate income" },
  { n: "16", t: "Gross Domestic Product", d: "— the central identities" },
  { n: "17", t: "Financial Account and Financial Balance Sheet", d: "— sector balance sheets" },
];

const FAMILIES = [
  {
    t: "Structural macroeconometric",
    here: true,
    agents: "Aggregates (National Accounts)",
    basis: "Estimated equations + identities, closed by judgement",
    best: "Consistent forecasting & fiscal scoring",
  },
  {
    t: "DSGE",
    agents: "Representative optimising agent",
    basis: "Micro-founded, rational expectations",
    best: "Theory & shock propagation",
  },
  {
    t: "HANK",
    agents: "Many heterogeneous households",
    basis: "DSGE + uninsurable risk & borrowing limits",
    best: "Distributional effects of policy",
  },
  {
    t: "OLG",
    agents: "Age cohorts over a lifecycle",
    basis: "Lifecycle saving & demographics",
    best: "Long-run pensions & debt sustainability",
  },
];

const SCHEMATIC_CSS = `
  .obr-bx{fill:#fff;stroke:#d7d2c6;stroke-width:1.5}
  .obr-t{font:600 13px ui-sans-serif,system-ui;fill:#0c2233}
  .obr-s{font:11px ui-sans-serif,system-ui;fill:#5d6b74}
  .obr-hd{font:700 11px ui-sans-serif,system-ui;letter-spacing:.12em;fill:#0b6c63}
  .obr-lk{stroke:#9fb0bb;stroke-width:1.6;fill:none}
  .obr-lkt{stroke:#0f9488;stroke-width:2;fill:none}
`;

export default function AboutTab({ model, explorer }) {
  return (
    <div className="space-y-6">
      <p className="text-base leading-7 text-slate-700">
        The OBR macroeconomic model is a simplified, computational representation
        of the UK National Accounts &mdash; the same set of equations the Budget
        Responsibility Committee uses to build the UK economy forecast. First built
        by HM Treasury in 1970 and jointly maintained by the OBR and the Treasury
        since 2010, it turns a small set of expert <em>judgements</em> into a large,
        internally consistent forecast for hundreds of economic variables. This
        dashboard runs that model as an independent{" "}
        <strong>Python re-implementation</strong>.
      </p>

      <section className="section-card">
        <SectionHeading title="At a glance" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {STATS.map((stat) => (
            <div key={stat.big} className="metric-card">
              <div className="text-3xl font-semibold tracking-tight text-[color:var(--pe-color-primary-700)]">
                {stat.big}
              </div>
              <div className="mt-2 text-sm leading-5 text-slate-600">
                {stat.lab}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="section-card">
        <SectionHeading title="What it is — and what it isn&rsquo;t" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-[color:var(--pe-color-primary-700)]">
              It is
            </h3>
            <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700 list-disc pl-5">
              <li>
                A <strong>computational tool</strong> that enforces accounting
                consistency across the whole economy.
              </li>
              <li>
                A way to generate a full forecast from a{" "}
                <strong>handful of key judgements</strong>.
              </li>
              <li>
                A system of <strong>simultaneous equations</strong> solved together
                until they all balance.
              </li>
            </ul>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-red-700">
              It is not
            </h3>
            <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700 list-disc pl-5">
              <li>
                The <strong>source</strong> of the forecast &mdash; the
                forecaster&rsquo;s judgement is.
              </li>
              <li>
                An <strong>OBR forecast</strong>: results here use the user&rsquo;s
                own assumptions.
              </li>
              <li>A black box &mdash; every equation is published and readable.</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="section-card">
        <SectionHeading
          title="Where this sits among macro models"
          description="A large-scale structural macroeconometric model in the HM Treasury / Cowles-Commission tradition — a different lineage from the micro-founded DSGE family (HANK, OLG)."
        />
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2 pr-4 font-semibold">Family</th>
                <th className="py-2 pr-4 font-semibold">Agents</th>
                <th className="py-2 pr-4 font-semibold">Basis</th>
                <th className="py-2 font-semibold">Best for</th>
              </tr>
            </thead>
            <tbody>
              {FAMILIES.map((f) => (
                <tr
                  key={f.t}
                  className={`border-b border-slate-100 align-top ${
                    f.here
                      ? "bg-[color:var(--pe-color-primary-50,#eef6f5)]"
                      : ""
                  }`}
                >
                  <td className="py-2.5 pr-4 font-semibold text-slate-900">
                    {f.t}
                    {f.here ? (
                      <span className="ml-1 text-[color:var(--pe-color-primary-700)]">
                        &larr; this model
                      </span>
                    ) : null}
                  </td>
                  <td className="py-2.5 pr-4 text-slate-600">{f.agents}</td>
                  <td className="py-2.5 pr-4 text-slate-600">{f.basis}</td>
                  <td className="py-2.5 text-slate-600">{f.best}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section-card">
        <SectionHeading
          title="How the model is wired together"
          description="Judgements feed the behavioural demand blocks; their components resolve into GDP, which drives incomes, prices and the public finances — and those feed back into demand. The model iterates until every block is mutually consistent."
        />
        <svg
          viewBox="0 0 920 470"
          role="img"
          aria-label="Schematic of the OBR model: judgements feed behavioural blocks, which resolve into GDP, which drives incomes, prices and the public finances, looping back to demand."
          className="w-full h-auto"
        >
          <defs>
            <marker
              id="ar"
              markerWidth="9"
              markerHeight="9"
              refX="7"
              refY="4.5"
              orient="auto"
            >
              <path d="M0,0 L9,4.5 L0,9 z" fill="#9fb0bb" />
            </marker>
            <marker
              id="art"
              markerWidth="9"
              markerHeight="9"
              refX="7"
              refY="4.5"
              orient="auto"
            >
              <path d="M0,0 L9,4.5 L0,9 z" fill="#0f9488" />
            </marker>
          </defs>
          <style dangerouslySetInnerHTML={{ __html: SCHEMATIC_CSS }} />

          {/* inputs */}
          <text className="obr-hd" x="40" y="34">
            JUDGEMENTS &amp; ASSUMPTIONS
          </text>
          <rect className="obr-bx" x="40" y="46" width="190" height="86" rx="11" />
          <text className="obr-t" x="58" y="74">
            Exogenous inputs
          </text>
          <text className="obr-s" x="58" y="94">
            World demand &middot; oil &amp; gas
          </text>
          <text className="obr-s" x="58" y="110">
            Bank Rate &middot; gilt yields &middot; FX
          </text>
          <text className="obr-s" x="58" y="126">
            Tax rates &middot; spending plans
          </text>

          {/* demand block */}
          <text className="obr-hd" x="300" y="34">
            DEMAND (behavioural)
          </text>
          <rect className="obr-bx" x="300" y="46" width="300" height="40" rx="9" />
          <text className="obr-t" x="316" y="71">
            1 &middot; Consumption
          </text>
          <text className="obr-s" x="470" y="71">
            households
          </text>
          <rect className="obr-bx" x="300" y="92" width="300" height="40" rx="9" />
          <text className="obr-t" x="316" y="117">
            3 &middot; Investment
          </text>
          <text className="obr-s" x="470" y="117">
            business &amp; housing
          </text>
          <rect className="obr-bx" x="300" y="138" width="300" height="40" rx="9" />
          <text className="obr-t" x="316" y="163">
            5&middot;6 &middot; Trade
          </text>
          <text className="obr-s" x="470" y="163">
            exports &amp; imports
          </text>
          <rect className="obr-bx" x="300" y="184" width="300" height="40" rx="9" />
          <text className="obr-t" x="316" y="209">
            9 &middot; Public expenditure
          </text>

          {/* GDP core */}
          <rect x="664" y="86" width="216" height="96" rx="13" fill="#0c2233" />
          <text
            x="772"
            y="124"
            textAnchor="middle"
            style={{ font: "700 17px Georgia,serif", fill: "#fff" }}
          >
            GDP
          </text>
          <text
            x="772"
            y="148"
            textAnchor="middle"
            style={{ font: "11px ui-sans-serif", fill: "#9fd8d0" }}
          >
            Group 16 — expenditure
          </text>
          <text
            x="772"
            y="164"
            textAnchor="middle"
            style={{ font: "11px ui-sans-serif", fill: "#9fd8d0" }}
          >
            = income = output
          </text>

          {/* supply / prices */}
          <text className="obr-hd" x="300" y="266">
            SUPPLY, PRICES &amp; INCOMES
          </text>
          <rect className="obr-bx" x="300" y="278" width="300" height="40" rx="9" />
          <text className="obr-t" x="316" y="303">
            4 &middot; Labour market
          </text>
          <text className="obr-s" x="470" y="303">
            jobs &middot; wages &middot; hours
          </text>
          <rect className="obr-bx" x="300" y="324" width="300" height="40" rx="9" />
          <text className="obr-t" x="316" y="349">
            7 &middot; Prices &amp; wages
          </text>
          <text className="obr-s" x="470" y="349">
            CPI &middot; deflators
          </text>
          <rect className="obr-bx" x="300" y="370" width="300" height="40" rx="9" />
          <text className="obr-t" x="316" y="395">
            15 &middot; Income account
          </text>

          {/* public finances */}
          <text className="obr-hd" x="664" y="266">
            PUBLIC FINANCES &amp; EXTERNAL
          </text>
          <rect className="obr-bx" x="664" y="278" width="216" height="40" rx="9" />
          <text className="obr-t" x="680" y="303">
            10 &middot; Receipts
          </text>
          <rect className="obr-bx" x="664" y="324" width="216" height="40" rx="9" />
          <text className="obr-t" x="680" y="349">
            12 &middot; PS net borrowing
          </text>
          <rect className="obr-bx" x="664" y="370" width="216" height="40" rx="9" />
          <text className="obr-t" x="680" y="395">
            11&middot;17 &middot; BoP &amp; balance sheets
          </text>

          {/* links: inputs -> demand */}
          <path
            className="obr-lk"
            d="M230,89 C265,89 268,66 300,66"
            markerEnd="url(#ar)"
          />
          <path
            className="obr-lk"
            d="M230,100 C262,112 270,112 300,112"
            markerEnd="url(#ar)"
          />
          <path
            className="obr-lk"
            d="M230,112 C258,158 268,158 300,158"
            markerEnd="url(#ar)"
          />
          <path
            className="obr-lk"
            d="M230,124 C255,204 270,204 300,204"
            markerEnd="url(#ar)"
          />
          {/* demand -> GDP */}
          <path
            className="obr-lkt"
            d="M600,66 C636,66 636,120 664,120"
            markerEnd="url(#art)"
          />
          <path
            className="obr-lkt"
            d="M600,112 C634,112 640,126 664,128"
            markerEnd="url(#art)"
          />
          <path
            className="obr-lkt"
            d="M600,158 C634,158 642,140 664,138"
            markerEnd="url(#art)"
          />
          <path
            className="obr-lkt"
            d="M600,204 C636,204 640,152 664,150"
            markerEnd="url(#art)"
          />
          {/* GDP -> supply/incomes (curves down into the labour-market block) */}
          <path
            className="obr-lk"
            d="M700,182 C700,248 650,298 602,298"
            markerEnd="url(#ar)"
          />
          {/* GDP -> public finances (straight down into receipts) */}
          <path
            className="obr-lk"
            d="M772,182 L772,274"
            markerEnd="url(#ar)"
          />
          {/* incomes & prices feed back to demand (dashed loop up the left gutter) */}
          <path
            className="obr-lk"
            d="M300,290 C250,250 250,110 300,72"
            strokeDasharray="5 5"
            markerEnd="url(#ar)"
          />
          <text className="obr-s" x="104" y="206" style={{ fill: "#0b6c63" }}>
            incomes &amp;
          </text>
          <text className="obr-s" x="104" y="222" style={{ fill: "#0b6c63" }}>
            prices loop back
          </text>
        </svg>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          Judgements feed the behavioural <em>demand</em> blocks; their components
          resolve into <strong>GDP</strong>, which drives incomes, prices and the
          public finances &mdash; and those feed back into demand. The model
          iterates until every block is mutually consistent.
        </p>
      </section>

      <section className="section-card">
        <SectionHeading title="The 17 equation groups" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3">
          {GROUPS.map((g) => (
            <div key={g.n} className="flex items-start gap-3">
              <span className="flex-shrink-0 inline-flex h-6 w-6 items-center justify-center rounded-full bg-[color:var(--pe-color-primary-700)] text-xs font-semibold text-white">
                {g.n}
              </span>
              <span className="text-sm leading-6 text-slate-700">
                <span className="font-semibold text-slate-900">{g.t}</span>{" "}
                {g.d ? <span className="text-slate-500">{g.d}</span> : null}
              </span>
            </div>
          ))}
        </div>
      </section>

      <div className="note-card rounded-r-xl p-4 text-sm leading-6">
        <strong>Health warning.</strong> This is an independent emulator built from
        the OBR&rsquo;s published model code. Outputs depend entirely on the
        user&rsquo;s assumptions and are <em>not</em> OBR or Treasury forecasts. The
        official model is operated in EViews; this project runs the same equations
        in Python.
      </div>
    </div>
  );
}
