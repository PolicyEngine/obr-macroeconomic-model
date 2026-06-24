"use client";

import SectionHeading from "./SectionHeading";

const STEPS = [
  {
    title: "Transpile",
    body: (
      <>
        Every EViews line &mdash; <code>dlog()</code>, <code>@elem</code>, lags like{" "}
        <code>X(-1)</code>, error-correction terms &mdash; is rewritten into an
        equivalent Python expression.
      </>
    ),
  },
  {
    title: "Initialise",
    body: (
      <>
        History is loaded from the OBR&rsquo;s detailed forecast tables; any
        variable a published equation needs but the data doesn&rsquo;t supply is
        created and seeded.
      </>
    ),
  },
  {
    title: "Solve simultaneously",
    body: (
      <>
        The 372 equations depend on each other, so they&rsquo;re solved together
        with <strong>Gauss&ndash;Seidel iteration</strong>: cycle through the
        equations, update values, repeat until nothing moves.
      </>
    ),
  },
  {
    title: "Swap the closure",
    body: (
      <>
        For a given experiment some variables flip between <em>cause</em> and{" "}
        <em>effect</em>. A closure swap removes one equation and adds another so
        the right thing stays fixed.
      </>
    ),
  },
  {
    title: "Shock & compare",
    body: (
      <>
        An input is nudged (a tax rate, a spending line). The model re-solves,
        and the difference from the baseline solution <em>is</em> the estimated
        economic impact.
      </>
    ),
  },
];

const RESULTS = [
  { q: "2025 Q1", inv: "0.0", gdp: "0.0", neg: false },
  { q: "2025 Q2", inv: "0.0", gdp: "0.0", neg: false },
  { q: "2025 Q3", inv: "−26.5", gdp: "−26.5", neg: true },
  { q: "2025 Q4", inv: "−76.2", gdp: "−76.2", neg: true },
  { q: "2026 Q1", inv: "−162.5", gdp: "−162.5", neg: true },
  { q: "2026 Q2", inv: "−324.4", gdp: "−324.4", neg: true },
  { q: "2026 Q3", inv: "−625.2", gdp: "−625.2", neg: true },
  { q: "2026 Q4", inv: "−1,200.0", gdp: "−1,200.0", neg: true, hl: true },
];

export default function HowItWorksTab({ model, explorer }) {
  return (
    <div className="space-y-6">
      <p className="text-sm leading-6 text-slate-600">
        The emulator reads the OBR&rsquo;s published EViews code, rewrites every
        equation as Python, and solves the whole system simultaneously. You
        change the model by <em>shocking</em> an input and comparing the new
        solution against a baseline.
      </p>

      {/* ===== PIPELINE ===== */}
      <div className="section-card">
        <SectionHeading
          title="The pipeline"
          description="From the OBR's published EViews code to a solved forecast."
        />
        <svg
          viewBox="0 0 920 170"
          role="img"
          aria-label="Pipeline: EViews code to transpiler to 372 Python equations to Gauss-Seidel solver to forecast."
          className="w-full h-auto"
        >
          <style
            dangerouslySetInnerHTML={{
              __html: `
                .p{fill:#fff;stroke:#d7d2c6;stroke-width:1.5}
                .pt{font:600 13px ui-sans-serif,system-ui;fill:#0c2233}
                .ps{font:11px ui-sans-serif,system-ui;fill:#5d6b74}
                .pa{stroke:#0f9488;stroke-width:2.2;fill:none}
              `,
            }}
          />
          <defs>
            <marker id="pm" markerWidth="10" markerHeight="10" refX="7" refY="5" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="#0f9488" />
            </marker>
          </defs>

          <rect className="p" x="20" y="52" width="150" height="66" rx="11" />
          <text className="pt" x="95" y="80" textAnchor="middle">EViews .txt</text>
          <text className="ps" x="95" y="99" textAnchor="middle">published model code</text>

          <rect className="p" x="222" y="52" width="150" height="66" rx="11" />
          <text className="pt" x="297" y="80" textAnchor="middle">Transpiler</text>
          <text className="ps" x="297" y="99" textAnchor="middle">EViews &rarr; Python</text>

          <rect className="p" x="424" y="52" width="160" height="66" rx="11" />
          <text className="pt" x="504" y="80" textAnchor="middle">372 equations</text>
          <text className="ps" x="504" y="99" textAnchor="middle">parsed &amp; indexed</text>

          <rect x="636" y="44" width="170" height="82" rx="13" fill="#0c2233" />
          <text x="721" y="78" textAnchor="middle" style={{ font: "600 14px Georgia,serif", fill: "#fff" }}>
            Gauss&ndash;Seidel
          </text>
          <text x="721" y="98" textAnchor="middle" style={{ font: "11px ui-sans-serif", fill: "#9fd8d0" }}>
            iterate to convergence
          </text>

          <rect className="p" x="838" y="52" width="62" height="66" rx="11" />
          <text className="pt" x="869" y="80" textAnchor="middle">Fore-</text>
          <text className="pt" x="869" y="96" textAnchor="middle">cast</text>

          <path className="pa" d="M170,85 L218,85" markerEnd="url(#pm)" />
          <path className="pa" d="M372,85 L420,85" markerEnd="url(#pm)" />
          <path className="pa" d="M584,85 L632,85" markerEnd="url(#pm)" />
          <path className="pa" d="M806,85 L834,85" markerEnd="url(#pm)" />

          <text className="ps" x="721" y="150" textAnchor="middle" style={{ fill: "#c9871f" }}>
            &uarr; closures &amp; shocks injected here
          </text>
        </svg>

        {/* ===== 5 STEPS ===== */}
        <ol className="mt-6 space-y-4">
          {STEPS.map((step, i) => (
            <li key={step.title} className="flex gap-4">
              <span className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-primary-700 text-sm font-semibold text-white">
                {i + 1}
              </span>
              <div>
                <h3 className="text-base font-semibold text-slate-900">{step.title}</h3>
                <p className="mt-1 text-sm leading-6 text-slate-600">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>

      {/* ===== WORKED EXAMPLE ===== */}
      <div className="section-card">
        <SectionHeading
          title="Worked example — a corporation-tax rise"
          description="How a +1pp rate rise travels through the equations and what the emulator reports."
        />

        <div className="grid gap-4 md:grid-cols-2">
          {/* Transmission chain */}
          <div>
            <p className="text-sm leading-6 text-slate-600">
              Raising the corporation-tax rate makes capital more expensive, so
              firms want a smaller capital stock and cut investment. In the model
              that runs along a chain of equations:
            </p>
            <svg
              viewBox="0 0 430 360"
              role="img"
              aria-label="Transmission chain: corporation tax up, cost-of-capital factor up, cost of capital up, desired capital down, capital gap, business investment down, total investment down, GDP down."
              className="mt-3 w-full h-auto"
            >
              <style
                dangerouslySetInnerHTML={{
                  __html: `
                    .cp{rx:9;ry:9}
                    .ct{font:600 12.5px ui-sans-serif,system-ui;fill:#0c2233}
                    .cv{font:700 12px ui-mono,ui-monospace,monospace;fill:#0b6c63}
                    .cl{stroke:#c2543d;stroke-width:2;fill:none}
                  `,
                }}
              />
              <defs>
                <marker id="cm" markerWidth="9" markerHeight="9" refX="6" refY="4.5" orient="auto">
                  <path d="M0,0 L9,4.5 L0,9 z" fill="#c2543d" />
                </marker>
              </defs>
              <g>
                <rect x="60" y="14" width="310" height="36" className="cp" fill="#fbf1dd" stroke="#e6c98a" />
                <text className="ct" x="76" y="37">
                  Corporation-tax rate&nbsp; <tspan className="cv">TCPRO &uarr;</tspan>
                </text>
                <rect x="60" y="64" width="310" height="36" className="cp" fill="#fff" stroke="#d7d2c6" />
                <text className="ct" x="76" y="87">
                  Tax-adjusted cost factor&nbsp; <tspan className="cv">TAF &uarr;</tspan>
                </text>
                <rect x="60" y="114" width="310" height="36" className="cp" fill="#fff" stroke="#d7d2c6" />
                <text className="ct" x="76" y="137">
                  Cost of capital&nbsp; <tspan className="cv">COC &uarr;</tspan>
                </text>
                <rect x="60" y="164" width="310" height="36" className="cp" fill="#fff" stroke="#d7d2c6" />
                <text className="ct" x="76" y="187">
                  Desired capital stock&nbsp; <tspan className="cv">KSTAR &darr;</tspan>
                </text>
                <rect x="60" y="214" width="310" height="36" className="cp" fill="#fff" stroke="#d7d2c6" />
                <text className="ct" x="76" y="237">
                  Capital gap&nbsp; <tspan className="cv">KGAP</tspan>
                </text>
                <rect x="60" y="264" width="310" height="36" className="cp" fill="#fdeeea" stroke="#e0a596" />
                <text className="ct" x="76" y="287">
                  Business investment&nbsp;{" "}
                  <tspan style={{ fill: "#c2543d" }} className="cv">IBUSX &darr;</tspan>
                </text>
                <rect x="60" y="314" width="310" height="36" className="cp" fill="#0c2233" />
                <text x="76" y="337" style={{ font: "600 12.5px ui-sans-serif", fill: "#fff" }}>
                  Total investment &amp; GDP&nbsp;{" "}
                  <tspan style={{ fill: "#ff9d86" }} className="cv">&darr;</tspan>
                </text>
              </g>
              <path className="cl" d="M215,50 L215,62" markerEnd="url(#cm)" />
              <path className="cl" d="M215,100 L215,112" markerEnd="url(#cm)" />
              <path className="cl" d="M215,150 L215,162" markerEnd="url(#cm)" />
              <path className="cl" d="M215,200 L215,212" markerEnd="url(#cm)" />
              <path className="cl" d="M215,250 L215,262" markerEnd="url(#cm)" />
              <path className="cl" d="M215,300 L215,312" markerEnd="url(#cm)" />
            </svg>
          </div>

          {/* Result chart */}
          <div>
            <h3 className="text-base font-semibold text-slate-900">
              Modelled impact of a <span className="text-red-700">+1pp</span> rate rise
            </h3>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              Change in business investment vs. baseline, &pound;m per quarter.
              The effect builds with a lag because investment responds to the{" "}
              <em>past</em> capital gap.
            </p>
            <svg
              viewBox="0 0 640 240"
              role="img"
              aria-label="Line chart: change in business investment is zero for two quarters then falls to about minus 1200 million by 2026 Q4."
              className="mt-3 w-full h-auto"
            >
              <style
                dangerouslySetInnerHTML={{
                  __html: `
                    .ax{stroke:#dcd7cb;stroke-width:1}
                    .gl{stroke:#eee9dd;stroke-width:1}
                    .axl{font:11px ui-sans-serif,system-ui;fill:#5d6b74}
                  `,
                }}
              />
              <line className="ax" x1="60" y1="30" x2="60" y2="190" />
              <line className="ax" x1="60" y1="190" x2="610" y2="190" />
              <line className="gl" x1="60" y1="30" x2="610" y2="30" />
              <line className="gl" x1="60" y1="83" x2="610" y2="83" />
              <line className="gl" x1="60" y1="136" x2="610" y2="136" />
              <text className="axl" x="54" y="34" textAnchor="end">0</text>
              <text className="axl" x="54" y="87" textAnchor="end">&minus;400</text>
              <text className="axl" x="54" y="140" textAnchor="end">&minus;800</text>
              <text className="axl" x="54" y="193" textAnchor="end">&minus;1200</text>
              <path
                d="M60,30 137,30 214,34 291,40 369,52 446,73 523,113 600,190 600,190 60,190 z"
                fill="rgba(194,84,61,.10)"
              />
              <polyline
                points="60,30 137,30 214,34 291,40 369,52 446,73 523,113 600,190"
                fill="none"
                stroke="#c2543d"
                strokeWidth="2.5"
              />
              <g fill="#c2543d">
                <circle cx="60" cy="30" r="3" />
                <circle cx="137" cy="30" r="3" />
                <circle cx="214" cy="34" r="3" />
                <circle cx="291" cy="40" r="3" />
                <circle cx="369" cy="52" r="3" />
                <circle cx="446" cy="73" r="3" />
                <circle cx="523" cy="113" r="3" />
                <circle cx="600" cy="190" r="4" />
              </g>
              <g className="axl" textAnchor="middle">
                <text x="60" y="208">25Q1</text>
                <text x="137" y="208">Q2</text>
                <text x="214" y="208">Q3</text>
                <text x="291" y="208">Q4</text>
                <text x="369" y="208">26Q1</text>
                <text x="446" y="208">Q2</text>
                <text x="523" y="208">Q3</text>
                <text x="600" y="208">Q4</text>
              </g>
              <text x="600" y="178" textAnchor="end" style={{ font: "600 12px ui-sans-serif", fill: "#c2543d" }}>
                &minus;&pound;1.20bn
              </text>
            </svg>
            <p className="mt-1 text-xs leading-6 text-slate-500">
              Numbers are this emulator&rsquo;s output for illustration, not an OBR
              forecast. The two-quarter flat start reflects the model&rsquo;s{" "}
              <code>KGAP(-2)</code> lag.
            </p>
          </div>
        </div>

        {/* Results table */}
        <div className="mt-6 overflow-x-auto">
          <table className="data-table" aria-label="Corporation-tax results table">
            <thead>
              <tr>
                <th>Quarter</th>
                <th>&Delta; business investment (&pound;m)</th>
                <th>&Delta; GDP (&pound;m)</th>
              </tr>
            </thead>
            <tbody>
              {RESULTS.map((r) => (
                <tr key={r.q} className={r.hl ? "font-semibold" : undefined}>
                  <td>{r.q}</td>
                  <td className={r.neg ? "text-red-700" : undefined}>{r.inv}</td>
                  <td className={r.neg ? "text-red-700" : undefined}>{r.gdp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Illustrative emulator output for a +1pp corporation-tax rise under the
          investment closure.
        </p>
      </div>

      {/* ===== METHOD & LIMITATIONS ===== */}
      <SectionHeading
        size="lg"
        title="Method & limitations"
        description="What the numbers are built from, and what they are not."
      />
      <div className="grid md:grid-cols-2 gap-4">
        <div className="section-card">
          <h3 className="text-base font-semibold text-slate-900">
            How these numbers are produced
          </h3>
          <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-6 text-slate-600">
            <li>
              History is loaded from the OBR&rsquo;s <strong>November 2025</strong>{" "}
              detailed forecast tables.
            </li>
            <li>
              The <strong>372 equations</strong> come from the OBR&rsquo;s 15 October
              2025 published model code.
            </li>
            <li>
              Each scenario is solved <strong>twice</strong> &mdash; baseline and
              shocked &mdash; and the dashboard shows the difference.
            </li>
            <li>
              Figures in the <em>Explore</em> tab are real solver output, computed
              once and stored with the page.
            </li>
          </ul>
        </div>
        <div className="section-card">
          <h3 className="text-base font-semibold text-slate-900">
            What to keep in mind
          </h3>
          <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-6 text-slate-600">
            <li>
              Results depend entirely on the <strong>user&rsquo;s assumptions</strong>{" "}
              &mdash; they are not OBR forecasts.
            </li>
            <li>
              The official model runs in EViews; this is an independent Python
              re-implementation.
            </li>
            <li>
              The business-investment equation is <strong>reconstructed</strong>{" "}
              from the OBR&rsquo;s (commented, truncated) published line.
            </li>
            <li>
              Add-factors and judgement that the OBR applies on top of the model
              are <strong>not</strong> reproduced here.
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
